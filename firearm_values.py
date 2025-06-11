import random
import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from validation import validate_search_params


def search_armslist(manufacturer, model, caliber, location="usa", category="all", timeout=15, max_retries=2):
    """
    Search Armslist for current listings matching the firearm details
    
    Args:
        manufacturer: Firearm manufacturer
        model: Firearm model
        caliber: Firearm caliber
        location: Search location (default: "usa")
        category: Search category (default: "all")
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        
    Returns:
        List of dictionaries with listing information
        
    Raises:
        requests.RequestException: If network request fails after retries
        ValueError: If search parameters are invalid
    """
    # Validate and clean input parameters
    validation_result = validate_search_params(manufacturer, model, caliber)
    if not validation_result.is_valid:
        raise ValueError(f"Invalid search parameters: {validation_result.error_message}")
    
    # Use cleaned parameters
    cleaned_params = validation_result.cleaned_value
    manufacturer = cleaned_params['manufacturer']
    model = cleaned_params['model']
    caliber = cleaned_params['caliber']
    
    try:
        # Build the search query
        search_query = f"{manufacturer} {model} {caliber}".strip()

        # URL encode the search query
        encoded_query = urllib.parse.quote(search_query)

        # Construct the Armslist search URL
        url = f"https://www.armslist.com/classifieds/search?search={encoded_query}&location={location}&category={category}&posttype=7&ships=&ispowersearch=1&hs=1"

        print(f"Searching Armslist for: {search_query}")
        print(f"URL: {url}")
        
        # Configure session with retry strategy
        session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set headers to mimic a browser request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        try:
            # Send the request to Armslist
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()  # Raises HTTPError for bad responses
            
            if not response.text.strip():
                print(f"Warning: Empty response from Armslist for {search_query}")
                return []
                
        except requests.exceptions.Timeout:
            raise requests.RequestException(f"Armslist request timeout after {timeout} seconds")
        except requests.exceptions.ConnectionError:
            raise requests.RequestException(f"Connection error when accessing Armslist")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise requests.RequestException(f"Rate limited by Armslist (HTTP 429)")
            elif e.response.status_code in [500, 502, 503, 504]:
                raise requests.RequestException(f"Armslist server error (HTTP {e.response.status_code})")
            else:
                raise requests.RequestException(f"HTTP error {e.response.status_code} from Armslist")
        except requests.exceptions.RequestException as e:
            raise requests.RequestException(f"Request failed for Armslist: {e}")
        finally:
            session.close()

        try:
            # Parse the HTML content
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            raise ValueError(f"Failed to parse HTML response from Armslist: {e}")

        # Find all listing items
        listings = []

        try:
            # The search results appear to be in sections for "Near Match Records" and "Related Match Records"
            # Look for listing elements that have class attributes consistent with listings
            listing_elements = soup.find_all("div", class_=lambda c: c and "listing" in c.lower())

            if not listing_elements:
                # Fall back to a more generic approach if class-based search fails
                listing_elements = soup.find_all(
                    "div", class_=lambda c: c and ("item" in c.lower() or "product" in c.lower())
                )

            for item in listing_elements:
                try:
                    # Extract listing data with error handling for each field
                    title_element = item.find("h3") or item.find("h2")
                    title = title_element.text.strip() if title_element else "No Title"

                    # Try to find the price
                    price_element = item.find(
                        "span", class_=lambda c: c and "price" in c.lower()
                    ) or item.find("div", class_=lambda c: c and "price" in c.lower())
                    price_text = price_element.text.strip() if price_element else "Price not listed"

                    # Clean up the price text and convert to float if possible
                    price = None
                    if price_text and "$" in price_text:
                        price_str = re.sub(r"[^\d.]", "", price_text)
                        try:
                            price = float(price_str)
                            # Validate price is reasonable (between $10 and $50,000)
                            if price < 10 or price > 50000:
                                price = None
                        except (ValueError, TypeError):
                            price = None

                    # Try to find the link
                    link_element = item.find("a", href=True)
                    link = (
                        "https://www.armslist.com" + link_element["href"]
                        if link_element and link_element.get("href", "").startswith("/")
                        else link_element.get("href", "#")
                        if link_element
                        else "#"
                    )

                    # Try to find the location
                    location_element = item.find("div", class_=lambda c: c and "location" in c.lower())
                    location = (
                        location_element.text.strip() if location_element else "Location not specified"
                    )

                    # Try to find if it will ship
                    ships_element = item.find("span", class_=lambda c: c and "ship" in c.lower())
                    ships = (
                        True
                        if ships_element and ships_element.text.strip().lower() == "will ship"
                        else False
                    )

                    # Compile the listing data
                    listing = {
                        "title": title,
                        "price": price,
                        "price_text": price_text,
                        "link": link,
                        "location": location,
                        "ships": ships,
                        "source": "Armslist",
                    }

                    listings.append(listing)
                except Exception as e:
                    # Log parsing error but continue with other listings
                    print(f"Warning: Error parsing individual listing: {e}")
                    continue

            print(f"Found {len(listings)} listings on Armslist")
            return listings
            
        except Exception as e:
            # If parsing completely fails, log and return empty list
            print(f"Warning: Failed to parse Armslist response: {e}")
            return []

    except requests.RequestException:
        # Re-raise network-related exceptions
        raise
    except ValueError:
        # Re-raise validation exceptions
        raise
    except Exception as e:
        # Catch any other unexpected errors
        raise requests.RequestException(f"Unexpected error searching Armslist: {e}")


def get_market_listings(manufacturer, model, caliber, use_cache=True, timeout=15, max_retries=2):
    """
    Get current market listings from various sources
    
    Args:
        manufacturer: Firearm manufacturer
        model: Firearm model
        caliber: Firearm caliber
        use_cache: Whether to use caching
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        
    Returns:
        List of dictionaries with listing information
        
    Raises:
        ValueError: If input parameters are invalid
        requests.RequestException: If network requests fail
    """
    # Validate and clean input parameters
    validation_result = validate_search_params(manufacturer, model, caliber)
    if not validation_result.is_valid:
        raise ValueError(f"Invalid search parameters: {validation_result.error_message}")
    
    # Use cleaned parameters
    cleaned_params = validation_result.cleaned_value
    manufacturer = cleaned_params['manufacturer']
    model = cleaned_params['model']
    caliber = cleaned_params['caliber']
    
    # Try cache first if enabled
    if use_cache:
        try:
            from cache_manager import get_market_cache

            cache = get_market_cache()
            cached_listings = cache.get(manufacturer, model, caliber)
            if cached_listings is not None:
                print(f"Using cached listings for {manufacturer} {model} {caliber}")
                return cached_listings
        except ImportError:
            print("Warning: Cache not available, continuing without cache")
        except Exception as e:
            print(f"Warning: Cache error: {e}, continuing without cache")

    # Add a small delay to prevent aggressive scraping (reduced from 0.5-1.5s)
    time.sleep(random.uniform(0.2, 0.8))

    try:
        # Search Armslist with error handling
        armslist_results = search_armslist(manufacturer, model, caliber, timeout=timeout, max_retries=max_retries)
    except requests.RequestException as e:
        print(f"Network error searching Armslist: {e}")
        armslist_results = []
    except ValueError as e:
        print(f"Validation error searching Armslist: {e}")
        armslist_results = []
    except Exception as e:
        print(f"Unexpected error searching Armslist: {e}")
        armslist_results = []

    # Combine results from different sources (currently just Armslist)
    all_listings = armslist_results

    # Sort listings by price (lowest first) with error handling
    if all_listings:
        try:
            # Filter out listings with invalid prices
            valid_listings = []
            for listing in all_listings:
                price = listing.get("price")
                if price is not None and isinstance(price, (int, float)) and price > 0:
                    valid_listings.append(listing)
            
            all_listings = sorted(valid_listings, key=lambda x: x["price"])

            # Calculate average price if we have enough data
            if len(all_listings) >= 3:
                prices = [l.get("price") for l in all_listings if l.get("price") is not None]
                if prices:
                    avg_price = sum(prices) / len(prices)
                    # Add average price to the results
                    for listing in all_listings:
                        listing["avg_price"] = avg_price
        except Exception as e:
            print(f"Warning: Error processing listings: {e}")
            # Continue with unsorted listings

    # Cache the results if caching is enabled
    if use_cache and all_listings:
        try:
            from cache_manager import get_market_cache

            cache = get_market_cache()
            cache.set(manufacturer, model, caliber, all_listings)
            print(f"Cached {len(all_listings)} listings for {manufacturer} {model} {caliber}")
        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: Failed to cache results: {e}")

    return all_listings


def estimate_market_value(manufacturer, model, caliber):
    """
    Estimate firearm value based on typical market prices
    Returns a tuple of (avg_price, price_range, sample_size)

    Uses a data-driven algorithm based on market knowledge and pricing patterns
    to estimate the value of firearms without external API calls.
    """
    try:
        # Use a market-based estimation algorithm based on manufacturer, model, and caliber

        print(f"Estimating value for: {manufacturer} {model} {caliber}")

        # Define base values for popular manufacturers (based on market research)
        manufacturer_values = {
            "GLOCK": 500,
            "SMITH & WESSON": 450,
            "S&W": 450,
            "RUGER": 400,
            "SIG SAUER": 600,
            "COLT": 800,
            "REMINGTON": 450,
            "WINCHESTER": 600,
            "MOSSBERG": 350,
            "BERETTA": 550,
            "SAVAGE": 400,
            "SPRINGFIELD": 550,
            "TAURUS": 300,
            "HENRY": 450,
            "BROWNING": 700,
            "FN": 750,
            "CZ": 600,
            "KIMBER": 850,
            "KEL-TEC": 300,
            "HK": 900,
            "TIKKA": 700,
            "MARLIN": 500,
            "STOEGER": 400,
        }

        # Value modifiers based on caliber/gauge
        caliber_factors = {
            "9MM": 1.0,  # Standard baseline
            "45 ACP": 1.1,  # Premium over 9mm
            "380 ACP": 0.9,  # Slightly less than 9mm
            "40 S&W": 0.95,  # Less popular than 9mm
            "10MM": 1.2,  # Premium caliber
            "357 MAG": 1.15,  # Premium revolver caliber
            "44 MAG": 1.2,  # Premium revolver caliber
            "22 LONG RIFLE": 0.8,  # Economical
            "22 LR": 0.8,  # Alternate name
            "223 REM": 1.05,  # Common rifle caliber
            "5.56": 1.05,  # Military equivalent
            "5.56X45 NATO": 1.05,  # Full name
            "5.56 NATO": 1.05,  # Alternate
            "308 WIN": 1.1,  # Popular hunting caliber
            "7.62X39": 1.0,  # AK caliber
            "12 GAUGE": 1.0,  # Standard shotgun
            "20 GAUGE": 0.95,  # Smaller shotgun
            "6.5 CREEDMOOR": 1.15,  # Popular precision caliber
            "300 WIN MAG": 1.2,  # Magnum rifle
            "30-06": 1.1,  # Classic hunting round
            "30-06 SPRINGFIELD": 1.1,  # Full name
            "30-30 WIN": 1.0,  # Lever action classic
            "45-70 GOVT": 1.15,  # Large caliber
            "38 SPECIAL": 0.9,  # Common revolver round
        }

        # Calculate base price from manufacturer (or use default)
        mfg_upper = manufacturer.upper()
        base_price = manufacturer_values.get(mfg_upper, 450)  # Default to 450 if not found

        # Apply caliber factor
        cal_upper = caliber.upper()
        caliber_factor = caliber_factors.get(cal_upper, 1.0)  # Default to 1.0 if not found

        # Model-specific adjustments
        model_factor = 1.0
        model_upper = model.upper()

        # Common model words that affect value
        if any(
            word in model_upper for word in ["CUSTOM", "TACTICAL", "PREMIUM", "ELITE", "TARGET"]
        ):
            model_factor *= 1.2
        if any(word in model_upper for word in ["COMPACT", "CARRY"]):
            model_factor *= 1.05
        if "COMPETITION" in model_upper:
            model_factor *= 1.25
        if "HUNTER" in model_upper:
            model_factor *= 1.1

        # Specific popular models (non-exhaustive)
        if mfg_upper == "GLOCK":
            if model_upper in ["17", "19", "43", "43X", "48"]:
                model_factor *= 1.1  # Popular models command premium
        elif mfg_upper in ["SMITH & WESSON", "S&W"]:
            if "SHIELD" in model_upper:
                model_factor *= 1.05
            elif "629" in model_upper or "686" in model_upper:
                model_factor *= 1.2  # Premium revolvers
        elif mfg_upper == "RUGER":
            if "10/22" in model_upper:
                model_factor *= 0.9  # Common, highly available
            elif "MINI-14" in model_upper:
                model_factor *= 1.15
            elif "GP100" in model_upper:
                model_factor *= 1.1
        elif mfg_upper == "COLT":
            if "PYTHON" in model_upper:
                model_factor *= 1.5  # Highly desirable
            elif "1911" in model_upper:
                model_factor *= 1.2
        elif mfg_upper == "TAURUS":
            if "PT22" in model_upper or "PT-22" in model_upper:
                model_factor *= 0.85  # Less popular pocket pistol

        # Calculate estimated price
        estimated_price = base_price * caliber_factor * model_factor

        # Ensure price is positive and reasonable
        MIN_VALUE = 50.0  # Minimum reasonable value for any firearm
        estimated_price = max(estimated_price, MIN_VALUE)

        # Add variation for a price range (±15%)
        range_low = max(estimated_price * 0.85, MIN_VALUE)
        range_high = max(estimated_price * 1.15, range_low * 1.1)

        print(f"Estimated value: ${estimated_price:.2f}")
        print(f"Range: ${range_low:.2f} - ${range_high:.2f}")

        # Return the tuple with the estimated values
        return (estimated_price, (range_low, range_high), 0)  # 0 indicates this is an estimate

    except Exception as e:
        print(f"Error estimating value: {e}")
        return None


def estimate_value(manufacturer, model, caliber, use_online_sources=False):
    """
    Main function to estimate the value of a firearm
    Returns a dictionary with value information

    Parameters:
    - manufacturer: The firearm manufacturer
    - model: The firearm model
    - caliber: The firearm caliber
    - use_online_sources: Whether to also search online marketplaces for current listings
    
    Raises:
        ValueError: If input parameters are invalid
    """
    # Validate input parameters
    validation_result = validate_search_params(manufacturer, model, caliber)
    if not validation_result.is_valid:
        raise ValueError(f"Invalid parameters for value estimation: {validation_result.error_message}")
    
    # Use cleaned parameters
    cleaned_params = validation_result.cleaned_value
    manufacturer = cleaned_params['manufacturer']
    model = cleaned_params['model']
    caliber = cleaned_params['caliber']
    # Minimal delay for rate limiting (reduced from 0.2-0.5s)
    time.sleep(random.uniform(0.05, 0.1))

    # Minimum acceptable value for any firearm to prevent negative prices
    MIN_VALUE = 50.0

    # Get market listings if requested
    market_listings = []
    if use_online_sources:
        market_listings = get_market_listings(manufacturer, model, caliber)

        # Filter out any suspiciously low-priced listings (likely data errors)
        if market_listings:
            market_listings = [
                listing
                for listing in market_listings
                if listing.get("price") is None or listing.get("price") >= MIN_VALUE
            ]

    # Get the algorithmic estimated value
    result = estimate_market_value(manufacturer, model, caliber)

    if result:
        avg_price, price_range, _ = result

        # Ensure base algorithm price is not too low
        avg_price = max(avg_price, MIN_VALUE)

        # If we have online listings with prices, adjust our estimate
        if market_listings and any(l.get("price") for l in market_listings):
            valid_prices = [l.get("price") for l in market_listings if l.get("price") is not None]
            if valid_prices:
                online_avg = sum(valid_prices) / len(valid_prices)

                # Ensure online average is reasonable
                online_avg = max(online_avg, MIN_VALUE)

                # Blend algorithmic estimate with online prices (70% online, 30% algorithm)
                if online_avg > 0:
                    blended_price = (online_avg * 0.7) + (avg_price * 0.3)

                    # Make sure blended price is at least the minimum value
                    blended_price = max(blended_price, MIN_VALUE)

                    # Adjust the range accordingly, but limit the adjustment
                    range_adjustment = min(
                        abs(blended_price - avg_price) / avg_price, 0.3
                    )  # Cap at 30%

                    # Calculate range with floors to prevent negative values
                    new_range_low = max(blended_price * (0.85 - range_adjustment / 2), MIN_VALUE)
                    new_range_high = max(
                        blended_price * (1.15 + range_adjustment / 2), new_range_low * 1.1
                    )

                    avg_price = blended_price
                    price_range = (new_range_low, new_range_high)

        # Final safety check - ensure price range values are positive
        range_low, range_high = price_range
        range_low = max(range_low, MIN_VALUE)
        range_high = max(range_high, range_low * 1.1)  # Ensure high > low by at least 10%
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

        return value_info

    # If no algorithm result but we have market listings
    if market_listings and any(l.get("price") for l in market_listings):
        valid_prices = [l.get("price") for l in market_listings if l.get("price") is not None]
        if valid_prices:
            online_avg = sum(valid_prices) / len(valid_prices)
            range_low = min(valid_prices)
            range_high = max(valid_prices)

            # Apply minimum value safeguards
            online_avg = max(online_avg, MIN_VALUE)
            range_low = max(range_low, MIN_VALUE)
            range_high = max(range_high, range_low * 1.1)  # Ensure high > low by at least 10%

            return {
                "estimated_value": online_avg,
                "value_range": (range_low, range_high),
                "sample_size": len(valid_prices),
                "source": f"Online Listings ({len(valid_prices)} samples)",
                "confidence": "medium",
                "market_listings": market_listings,
            }

    # If no result found
    return {
        "estimated_value": None,
        "value_range": None,
        "sample_size": 0,
        "source": "No data available",
        "confidence": "none",
        "market_listings": [],
    }
