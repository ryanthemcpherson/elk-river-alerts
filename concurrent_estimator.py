"""
Concurrent value estimation system for processing multiple firearms in parallel
"""

import concurrent.futures
import time
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass
import threading

import requests

from cache_manager import get_market_cache
from firearm_values import estimate_market_value, search_armslist


@dataclass
class EstimationTask:
    """Task for value estimation"""

    index: int
    manufacturer: str
    model: str
    caliber: str
    use_online_sources: bool = False


@dataclass
class EstimationResult:
    """Result of value estimation"""

    index: int
    manufacturer: str
    model: str
    caliber: str
    success: bool
    value_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: float = 0.0


class ConcurrentValueEstimator:
    """Concurrent value estimator with caching and rate limiting"""

    def __init__(self, max_workers: int = 4, rate_limit_delay: float = 0.5):
        self.max_workers = max_workers
        self.rate_limit_delay = rate_limit_delay
        self.cache = get_market_cache()
        self.rate_limiter = threading.Semaphore(max_workers)
        self.last_request_time = 0
        self.request_lock = threading.Lock()

    def _rate_limited_request(self, func, *args, **kwargs):
        """Execute a function with rate limiting"""
        with self.request_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - time_since_last)
            self.last_request_time = time.time()

        return func(*args, **kwargs)

    def _get_cached_or_fetch_listings(
        self, manufacturer: str, model: str, caliber: str
    ) -> List[Dict[str, Any]]:
        """Get market listings from cache or fetch them"""
        # Check cache first
        cached_listings = self.cache.get(manufacturer, model, caliber)
        if cached_listings is not None:
            return cached_listings

        # Fetch from online source with rate limiting
        try:
            listings = self._rate_limited_request(search_armslist, manufacturer, model, caliber, timeout=15, max_retries=2)
            # Cache the results
            self.cache.set(manufacturer, model, caliber, listings)
            return listings
        except requests.RequestException as e:
            print(f"Network error fetching listings for {manufacturer} {model}: {e}")
            return []
        except ValueError as e:
            print(f"Validation error fetching listings for {manufacturer} {model}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error fetching listings for {manufacturer} {model}: {e}")
            return []

    def _estimate_single_value(self, task: EstimationTask) -> EstimationResult:
        """Estimate value for a single firearm"""
        start_time = time.time()

        try:
            # Get algorithmic estimate (this is fast)
            algo_result = estimate_market_value(task.manufacturer, task.model, task.caliber)

            # Minimum acceptable value
            MIN_VALUE = 50.0

            # Initialize result with algorithmic estimate
            if algo_result:
                avg_price, price_range, _ = algo_result
                avg_price = max(avg_price, MIN_VALUE)

                market_listings = []
                if task.use_online_sources:
                    # Get market listings (cached or fetched)
                    market_listings = self._get_cached_or_fetch_listings(
                        task.manufacturer, task.model, task.caliber
                    )

                    # Filter out suspicious prices
                    if market_listings:
                        market_listings = [
                            listing
                            for listing in market_listings
                            if listing.get("price") is None or listing.get("price") >= MIN_VALUE
                        ]

                # Blend with online data if available
                if market_listings and any(l.get("price") for l in market_listings):
                    valid_prices = [
                        l.get("price") for l in market_listings if l.get("price") is not None
                    ]
                    if valid_prices:
                        online_avg = sum(valid_prices) / len(valid_prices)
                        online_avg = max(online_avg, MIN_VALUE)

                        # Blend algorithmic estimate with online prices (70% online, 30% algorithm)
                        if online_avg > 0:
                            blended_price = (online_avg * 0.7) + (avg_price * 0.3)
                            blended_price = max(blended_price, MIN_VALUE)

                            # Adjust the range
                            range_adjustment = min(abs(blended_price - avg_price) / avg_price, 0.3)
                            new_range_low = max(
                                blended_price * (0.85 - range_adjustment / 2), MIN_VALUE
                            )
                            new_range_high = max(
                                blended_price * (1.15 + range_adjustment / 2), new_range_low * 1.1
                            )

                            avg_price = blended_price
                            price_range = (new_range_low, new_range_high)

                # Ensure price range is valid
                range_low, range_high = price_range
                range_low = max(range_low, MIN_VALUE)
                range_high = max(range_high, range_low * 1.1)
                price_range = (range_low, range_high)

                value_info = {
                    "estimated_value": avg_price,
                    "value_range": price_range,
                    "sample_size": len(market_listings) if market_listings else "N/A",
                    "source": "Market Estimator"
                    if not market_listings
                    else f"Market Estimator + {len(market_listings)} Online Listings",
                    "confidence": "medium" if not market_listings else "high",
                    "market_listings": market_listings if market_listings else [],
                }

                processing_time = time.time() - start_time
                return EstimationResult(
                    index=task.index,
                    manufacturer=task.manufacturer,
                    model=task.model,
                    caliber=task.caliber,
                    success=True,
                    value_info=value_info,
                    processing_time=processing_time,
                )

            # Fallback to online-only if algorithm failed
            elif task.use_online_sources:
                market_listings = self._get_cached_or_fetch_listings(
                    task.manufacturer, task.model, task.caliber
                )

                if market_listings and any(l.get("price") for l in market_listings):
                    valid_prices = [
                        l.get("price") for l in market_listings if l.get("price") is not None
                    ]
                    if valid_prices:
                        online_avg = sum(valid_prices) / len(valid_prices)
                        range_low = min(valid_prices)
                        range_high = max(valid_prices)

                        # Apply minimum value safeguards
                        online_avg = max(online_avg, MIN_VALUE)
                        range_low = max(range_low, MIN_VALUE)
                        range_high = max(range_high, range_low * 1.1)

                        value_info = {
                            "estimated_value": online_avg,
                            "value_range": (range_low, range_high),
                            "sample_size": len(valid_prices),
                            "source": f"Online Listings ({len(valid_prices)} samples)",
                            "confidence": "medium",
                            "market_listings": market_listings,
                        }

                        processing_time = time.time() - start_time
                        return EstimationResult(
                            index=task.index,
                            manufacturer=task.manufacturer,
                            model=task.model,
                            caliber=task.caliber,
                            success=True,
                            value_info=value_info,
                            processing_time=processing_time,
                        )

            # No data available
            value_info = {
                "estimated_value": None,
                "value_range": None,
                "sample_size": 0,
                "source": "No data available",
                "confidence": "none",
                "market_listings": [],
            }

            processing_time = time.time() - start_time
            return EstimationResult(
                index=task.index,
                manufacturer=task.manufacturer,
                model=task.model,
                caliber=task.caliber,
                success=True,
                value_info=value_info,
                processing_time=processing_time,
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return EstimationResult(
                index=task.index,
                manufacturer=task.manufacturer,
                model=task.model,
                caliber=task.caliber,
                success=False,
                error=str(e),
                processing_time=processing_time,
            )

    def estimate_values_batch(
        self,
        tasks: List[EstimationTask],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[EstimationResult]:
        """Estimate values for multiple firearms concurrently"""

        results = [None] * len(tasks)
        completed_count = 0

        def update_progress(result: EstimationResult):
            nonlocal completed_count
            completed_count += 1
            results[result.index] = result

            if progress_callback:
                status = f"Completed {result.manufacturer} {result.model} ({result.processing_time:.1f}s)"
                progress_callback(completed_count, len(tasks), status)

        # Submit all tasks to thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self._estimate_single_value, task): task for task in tasks
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_task):
                result = future.result()
                update_progress(result)

        return results


def create_estimation_tasks(listings, use_online_sources: bool = False) -> List[EstimationTask]:
    """Create estimation tasks from firearm listings"""
    tasks = []
    for i, listing in enumerate(listings):
        task = EstimationTask(
            index=i,
            manufacturer=listing.manufacturer,
            model=listing.model,
            caliber=listing.caliber,
            use_online_sources=use_online_sources,
        )
        tasks.append(task)
    return tasks
