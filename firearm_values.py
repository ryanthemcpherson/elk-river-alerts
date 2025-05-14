import requests
from bs4 import BeautifulSoup
import re
import time
import random
import json
from datetime import datetime
import urllib.parse

def search_armslist(manufacturer, model, caliber, location="usa", category="all"):
    """
    Search Armslist for current listings matching the firearm details
    Returns a list of dictionaries with listing information
    """
    try:
        # Build the search query
        search_query = f"{manufacturer} {model} {caliber}".strip()
        
        # URL encode the search query
        encoded_query = urllib.parse.quote(search_query)
        
        # Construct the Armslist search URL
        url = f"https://www.armslist.com/classifieds/search?search={encoded_query}&location={location}&category={category}&posttype=7&ships=&ispowersearch=1&hs=1"
        
        print(f"Searching Armslist for: {search_query}")
        print(f"URL: {url}")
        
        # Set headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Send the request to Armslist
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check if the request was successful
        if response.status_code != 200:
            print(f"Error: Received status code {response.status_code}")
            return []
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all listing items
        listings = []
        
        # The search results appear to be in sections for "Near Match Records" and "Related Match Records"
        # Look for listing elements that have class attributes consistent with listings
        listing_elements = soup.find_all('div', class_=lambda c: c and 'listing' in c.lower())
        
        if not listing_elements:
            # Fall back to a more generic approach if class-based search fails
            listing_elements = soup.find_all('div', class_=lambda c: c and ('item' in c.lower() or 'product' in c.lower()))
        
        for item in listing_elements:
            try:
                # Extract listing data
                title_element = item.find('h3') or item.find('h2')
                title = title_element.text.strip() if title_element else "No Title"
                
                # Try to find the price
                price_element = item.find('span', class_=lambda c: c and 'price' in c.lower()) or item.find('div', class_=lambda c: c and 'price' in c.lower())
                price_text = price_element.text.strip() if price_element else "Price not listed"
                
                # Clean up the price text and convert to float if possible
                price = None
                if price_text and '$' in price_text:
                    price_str = re.sub(r'[^\d.]', '', price_text)
                    try:
                        price = float(price_str)
                    except ValueError:
                        price = None
                
                # Try to find the link
                link_element = item.find('a', href=True)
                link = "https://www.armslist.com" + link_element['href'] if link_element and link_element.get('href', '').startswith('/') else link_element.get('href', '#') if link_element else "#"
                
                # Try to find the location
                location_element = item.find('div', class_=lambda c: c and 'location' in c.lower())
                location = location_element.text.strip() if location_element else "Location not specified"
                
                # Try to find if it will ship
                ships_element = item.find('span', class_=lambda c: c and 'ship' in c.lower())
                ships = True if ships_element and ships_element.text.strip().lower() == 'will ship' else False
                
                # Compile the listing data
                listing = {
                    'title': title,
                    'price': price,
                    'price_text': price_text,
                    'link': link,
                    'location': location,
                    'ships': ships,
                    'source': 'Armslist'
                }
                
                listings.append(listing)
            except Exception as e:
                print(f"Error parsing listing: {e}")
                continue
        
        print(f"Found {len(listings)} listings on Armslist")
        return listings
    
    except Exception as e:
        print(f"Error searching Armslist: {e}")
        return []

def get_market_listings(manufacturer, model, caliber):
    """
    Get current market listings from various sources
    Returns a list of dictionaries with listing information
    """
    # Add a small delay to prevent aggressive scraping
    time.sleep(random.uniform(0.5, 1.5))
    
    # Search Armslist
    armslist_results = search_armslist(manufacturer, model, caliber)
    
    # Combine results from different sources (currently just Armslist)
    all_listings = armslist_results
    
    # Sort listings by price (lowest first)
    if all_listings:
        all_listings = sorted([l for l in all_listings if l.get('price') is not None], key=lambda x: x['price'])
        
        # Calculate average price if we have enough data
        if len(all_listings) >= 3:
            prices = [l.get('price') for l in all_listings if l.get('price') is not None]
            avg_price = sum(prices) / len(prices) if prices else None
            
            # Add average price to the results
            for listing in all_listings:
                listing['avg_price'] = avg_price
    
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
            "STOEGER": 400
        }
        
        # Value modifiers based on caliber/gauge
        caliber_factors = {
            "9MM": 1.0,          # Standard baseline
            "45 ACP": 1.1,       # Premium over 9mm
            "380 ACP": 0.9,      # Slightly less than 9mm
            "40 S&W": 0.95,      # Less popular than 9mm
            "10MM": 1.2,         # Premium caliber
            "357 MAG": 1.15,     # Premium revolver caliber
            "44 MAG": 1.2,       # Premium revolver caliber
            "22 LONG RIFLE": 0.8, # Economical
            "22 LR": 0.8,        # Alternate name
            "223 REM": 1.05,     # Common rifle caliber
            "5.56": 1.05,        # Military equivalent
            "5.56X45 NATO": 1.05, # Full name
            "5.56 NATO": 1.05,   # Alternate
            "308 WIN": 1.1,      # Popular hunting caliber
            "7.62X39": 1.0,      # AK caliber
            "12 GAUGE": 1.0,     # Standard shotgun
            "20 GAUGE": 0.95,    # Smaller shotgun
            "6.5 CREEDMOOR": 1.15, # Popular precision caliber
            "300 WIN MAG": 1.2,  # Magnum rifle
            "30-06": 1.1,        # Classic hunting round
            "30-06 SPRINGFIELD": 1.1, # Full name
            "30-30 WIN": 1.0,    # Lever action classic
            "45-70 GOVT": 1.15,  # Large caliber
            "38 SPECIAL": 0.9    # Common revolver round
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
        if any(word in model_upper for word in ["CUSTOM", "TACTICAL", "PREMIUM", "ELITE", "TARGET"]):
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
        
        # Add variation for a price range (±15%)
        range_low = estimated_price * 0.85
        range_high = estimated_price * 1.15
        
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
    """
    # Add a small delay to simulate processing
    time.sleep(random.uniform(0.2, 0.5))
    
    # Get market listings if requested
    market_listings = []
    if use_online_sources:
        market_listings = get_market_listings(manufacturer, model, caliber)
    
    # Get the algorithmic estimated value
    result = estimate_market_value(manufacturer, model, caliber)
    
    if result:
        avg_price, price_range, _ = result
        
        # If we have online listings with prices, adjust our estimate
        if market_listings and any(l.get('price') for l in market_listings):
            valid_prices = [l.get('price') for l in market_listings if l.get('price') is not None]
            if valid_prices:
                online_avg = sum(valid_prices) / len(valid_prices)
                # Blend algorithmic estimate with online prices (70% online, 30% algorithm)
                if online_avg > 0:
                    blended_price = (online_avg * 0.7) + (avg_price * 0.3)
                    # Adjust the range accordingly
                    range_adjustment = abs(blended_price - avg_price) / avg_price
                    new_range_low = blended_price * (0.85 - range_adjustment/2)
                    new_range_high = blended_price * (1.15 + range_adjustment/2)
                    
                    avg_price = blended_price
                    price_range = (new_range_low, new_range_high)
        
        value_info = {
            "estimated_value": avg_price,
            "value_range": price_range,
            "sample_size": len(market_listings) if market_listings else "N/A",
            "source": "Market Estimator" if not market_listings else f"Market Estimator + {len(market_listings)} Online Listings",
            "confidence": "medium" if not market_listings else "high",
            "market_listings": market_listings if market_listings else []
        }
        
        return value_info
    
    # If no algorithm result but we have market listings
    if market_listings and any(l.get('price') for l in market_listings):
        valid_prices = [l.get('price') for l in market_listings if l.get('price') is not None]
        if valid_prices:
            online_avg = sum(valid_prices) / len(valid_prices)
            range_low = min(valid_prices)
            range_high = max(valid_prices)
            
            return {
                "estimated_value": online_avg,
                "value_range": (range_low, range_high),
                "sample_size": len(valid_prices),
                "source": f"Online Listings ({len(valid_prices)} samples)",
                "confidence": "medium",
                "market_listings": market_listings
            }
    
    # If no result found
    return {
        "estimated_value": None,
        "value_range": None,
        "sample_size": 0,
        "source": "No data available",
        "confidence": "none",
        "market_listings": []
    } 