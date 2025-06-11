"""
Cache manager for firearm market listings to avoid repeated API calls
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading


class MarketListingsCache:
    """Thread-safe cache for market listings data"""

    def __init__(self, cache_dir: str = ".cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_lock = threading.Lock()

    def _generate_cache_key(self, manufacturer: str, model: str, caliber: str) -> str:
        """Generate a consistent cache key for a firearm"""
        # Normalize the input to avoid cache misses due to case/spacing differences
        normalized = (
            f"{manufacturer.upper().strip()}|{model.upper().strip()}|{caliber.upper().strip()}"
        )
        return hashlib.md5(normalized.encode()).hexdigest()

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the file path for a cache entry"""
        return self.cache_dir / f"{cache_key}.json"

    def _is_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid based on TTL"""
        if "timestamp" not in cache_data:
            return False
        age_seconds = time.time() - cache_data["timestamp"]
        return age_seconds < self.ttl_seconds

    def get(self, manufacturer: str, model: str, caliber: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached market listings for a firearm"""
        cache_key = self._generate_cache_key(manufacturer, model, caliber)

        with self.cache_lock:
            # Check memory cache first
            if cache_key in self.memory_cache:
                cache_data = self.memory_cache[cache_key]
                if self._is_cache_valid(cache_data):
                    return cache_data.get("listings", [])
                else:
                    # Remove expired entry from memory cache
                    del self.memory_cache[cache_key]

            # Check file cache
            cache_file = self._get_cache_file_path(cache_key)
            if cache_file.exists():
                try:
                    with open(cache_file, "r") as f:
                        cache_data = json.load(f)

                    if self._is_cache_valid(cache_data):
                        # Load into memory cache
                        self.memory_cache[cache_key] = cache_data
                        return cache_data.get("listings", [])
                    else:
                        # Remove expired file
                        cache_file.unlink()
                except (json.JSONDecodeError, IOError):
                    # Corrupted cache file, remove it
                    if cache_file.exists():
                        cache_file.unlink()

        return None

    def set(
        self, manufacturer: str, model: str, caliber: str, listings: List[Dict[str, Any]]
    ) -> None:
        """Cache market listings for a firearm"""
        cache_key = self._generate_cache_key(manufacturer, model, caliber)
        cache_data = {
            "timestamp": time.time(),
            "listings": listings,
            "manufacturer": manufacturer,
            "model": model,
            "caliber": caliber,
        }

        with self.cache_lock:
            # Store in memory cache
            self.memory_cache[cache_key] = cache_data

            # Store in file cache
            cache_file = self._get_cache_file_path(cache_key)
            try:
                with open(cache_file, "w") as f:
                    json.dump(cache_data, f, indent=2)
            except IOError as e:
                print(f"Warning: Could not write cache file {cache_file}: {e}")

    def clear_expired(self) -> int:
        """Clear expired cache entries and return count of removed entries"""
        removed_count = 0

        with self.cache_lock:
            # Clear expired memory cache entries
            expired_keys = []
            for key, data in self.memory_cache.items():
                if not self._is_cache_valid(data):
                    expired_keys.append(key)

            for key in expired_keys:
                del self.memory_cache[key]
                removed_count += 1

            # Clear expired file cache entries
            if self.cache_dir.exists():
                for cache_file in self.cache_dir.glob("*.json"):
                    try:
                        with open(cache_file, "r") as f:
                            cache_data = json.load(f)

                        if not self._is_cache_valid(cache_data):
                            cache_file.unlink()
                            removed_count += 1
                    except (json.JSONDecodeError, IOError):
                        # Corrupted file, remove it
                        cache_file.unlink()
                        removed_count += 1

        return removed_count

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache"""
        with self.cache_lock:
            memory_entries = len(self.memory_cache)
            file_entries = (
                len(list(self.cache_dir.glob("*.json"))) if self.cache_dir.exists() else 0
            )

            # Calculate hit rate if we've been tracking it
            return {
                "memory_entries": memory_entries,
                "file_entries": file_entries,
                "cache_dir": str(self.cache_dir),
                "ttl_hours": self.ttl_seconds / 3600,
            }


# Global cache instance
_market_cache = None


def get_market_cache() -> MarketListingsCache:
    """Get the global market listings cache instance"""
    global _market_cache
    if _market_cache is None:
        _market_cache = MarketListingsCache()
    return _market_cache
