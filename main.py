from dataclasses import dataclass
import time

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from validation import InputValidator, validate_scraping_url


@dataclass
class FirearmListing:
    section: str
    manufacturer: str
    model: str
    caliber: str
    price: float
    description: str
    condition: str  # "new" or "used"


def parse_table(table, section, condition="used"):
    listings = []
    rows = table.find_all("tr")[1:]  # skip header
    for row in rows:
        cols = [td.get_text(strip=True) for td in row.find_all("td")]

        # Handle different table formats
        if len(cols) == 6:
            # Used guns format: [_, manufacturer, model, caliber, price, description]
            _, manufacturer, model, caliber, price, description = cols
        elif len(cols) == 7:
            # New guns format: [item_number, type, manufacturer, model, caliber, price, description]
            _, _, manufacturer, model, caliber, price, description = cols
        else:
            continue  # skip incomplete rows

        try:
            price_val = float(price.replace("$", "").replace(",", ""))
        except ValueError:
            price_val = 0.0
        listings.append(
            FirearmListing(
                section=section,
                manufacturer=manufacturer,
                model=model,
                caliber=caliber,
                price=price_val,
                description=description,
                condition=condition,
            )
        )
    return listings


def scrape_guns_from_url(url, condition="used", progress_base=0, progress_range=50, timeout=30, max_retries=3):
    """
    Scrape firearms listings from a specific Elk River Guns URL

    Args:
        url: The URL to scrape
        condition: "new" or "used"
        progress_base: Base progress percentage for this URL
        progress_range: Range of progress for this URL
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts

    Returns:
        List of FirearmListing objects
        
    Raises:
        requests.RequestException: If network request fails after retries
        ValueError: If URL is invalid
    """
    if not url or not url.startswith(('http://', 'https://')):
        raise ValueError(f"Invalid URL: {url}")
    
    # Configure session with retry strategy
    session = requests.Session()
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set headers to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        resp = session.get(url, timeout=timeout, headers=headers)
        resp.raise_for_status()  # Raises HTTPError for bad responses
        
        if not resp.text.strip():
            raise ValueError(f"Empty response from {url}")
            
        soup = BeautifulSoup(resp.text, "html.parser")
        
    except requests.exceptions.Timeout:
        raise requests.RequestException(f"Request timeout after {timeout} seconds for {url}")
    except requests.exceptions.ConnectionError:
        raise requests.RequestException(f"Connection error when accessing {url}")
    except requests.exceptions.HTTPError as e:
        raise requests.RequestException(f"HTTP error {e.response.status_code} for {url}: {e}")
    except requests.exceptions.RequestException as e:
        raise requests.RequestException(f"Request failed for {url}: {e}")
    except Exception as e:
        raise requests.RequestException(f"Unexpected error scraping {url}: {e}")
    finally:
        session.close()
    all_listings = []

    # Find section headers for tables
    sections = {"Pistols": None, "Rifles": None, "Revolvers": None, "Shotguns": None}

    # Locate section headers (h2 elements with specific text)
    for header in soup.find_all("h2"):
        header_text = header.get_text(strip=True)
        if "Pistols" in header_text:
            sections["Pistols"] = header
        elif "Rifles" in header_text:
            sections["Rifles"] = header
        elif "Revolvers" in header_text:
            sections["Revolvers"] = header
        elif "Shotguns" in header_text:
            sections["Shotguns"] = header

    # Track progress through section parsing
    total_sections = len([s for s in sections.values() if s is not None])
    current_section = 0

    # Match tables to section headers
    for section_name, section_header in sections.items():
        if section_header:
            current_section += 1
            # Find the table that follows this header
            table = section_header.find_next("table")
            if table:
                # Add condition prefix to section name for clarity
                full_section_name = f"{condition.title()} {section_name}"
                listings = parse_table(table, full_section_name, condition)
                all_listings.extend(listings)

    return all_listings


def scrape_all_guns(progress_callback=None, include_new=True, include_used=True):
    """
    Scrape all firearms listings from Elk River Guns website (both new and used)

    Args:
        progress_callback: Optional callback function to report progress
                          Function should accept (stage, message, percent) parameters
        include_new: Whether to include new guns
        include_used: Whether to include used guns

    Returns:
        List of FirearmListing objects
    """
    all_listings = []

    # Report progress if a callback is provided
    if progress_callback:
        progress_callback("scraping", "Connecting to Elk River Guns website...", 0)

    urls_to_scrape = []
    if include_used:
        urls_to_scrape.append(("https://elkriverguns.com/used-guns/", "used"))
    if include_new:
        urls_to_scrape.append(("https://elkriverguns.com/new-guns/", "new"))

    if not urls_to_scrape:
        return []

    # Calculate progress ranges for each URL
    progress_per_url = 90 // len(urls_to_scrape)

    for idx, (url, condition) in enumerate(urls_to_scrape):
        if progress_callback:
            progress_base = 5 + (idx * progress_per_url)
            progress_callback("scraping", f"Fetching {condition} guns inventory...", progress_base)

        try:
            # Additional validation for condition parameter
            condition_validation = InputValidator.validate_condition(condition)
            if not condition_validation.is_valid:
                raise ValueError(f"Invalid condition '{condition}': {condition_validation.error_message}")
            
            listings = scrape_guns_from_url(url, condition_validation.cleaned_value, timeout=30, max_retries=3)
            all_listings.extend(listings)

            if progress_callback:
                progress_callback(
                    "scraping",
                    f"Found {len(listings)} {condition} firearms",
                    progress_base + progress_per_url,
                )
        except requests.RequestException as e:
            error_msg = f"Network error scraping {condition} guns: {e}"
            print(error_msg)
            if progress_callback:
                progress_callback(
                    "scraping",
                    f"Network error for {condition} guns - continuing...",
                    progress_base + progress_per_url,
                )
        except ValueError as e:
            error_msg = f"Data error scraping {condition} guns: {e}"
            print(error_msg)
            if progress_callback:
                progress_callback(
                    "scraping",
                    f"Data error for {condition} guns - continuing...",
                    progress_base + progress_per_url,
                )
        except Exception as e:
            error_msg = f"Unexpected error scraping {condition} guns: {e}"
            print(error_msg)
            if progress_callback:
                progress_callback(
                    "scraping",
                    f"Unexpected error for {condition} guns - continuing...",
                    progress_base + progress_per_url,
                )

    # Final progress update
    if progress_callback:
        progress_callback("scraping", f"Found {len(all_listings)} total firearms", 100)

    return all_listings


# Keep the old function for backward compatibility but have it use the new one
def scrape_used_guns(progress_callback=None):
    """
    Scrape used firearms listings from Elk River Guns website

    Args:
        progress_callback: Optional callback function to report progress
                          Function should accept (stage, message, percent) parameters

    Returns:
        List of FirearmListing objects
    """
    return scrape_all_guns(progress_callback, include_new=False, include_used=True)


if __name__ == "__main__":
    # Test scraping all guns (both new and used)
    listings = scrape_all_guns()

    # Separate by condition for display
    new_guns = [l for l in listings if l.condition == "new"]
    used_guns = [l for l in listings if l.condition == "used"]

    print(f"\nFound {len(new_guns)} new guns and {len(used_guns)} used guns")
    print(f"Total: {len(listings)} firearms\n")

    # Show a few examples
    if new_guns:
        print("Sample NEW guns:")
        for l in new_guns[:3]:
            print(f"  {l.manufacturer} {l.model} - ${l.price} ({l.section})")

    if used_guns:
        print("\nSample USED guns:")
        for l in used_guns[:3]:
            print(f"  {l.manufacturer} {l.model} - ${l.price} ({l.section})")
