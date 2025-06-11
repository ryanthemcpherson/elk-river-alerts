from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


@dataclass
class FirearmListing:
    section: str
    manufacturer: str
    model: str
    caliber: str
    price: float
    description: str


def parse_table(table, section):
    listings = []
    rows = table.find_all("tr")[1:]  # skip header
    for row in rows:
        cols = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cols) < 6:
            continue  # skip incomplete rows
        _, manufacturer, model, caliber, price, description = cols
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
            )
        )
    return listings


def scrape_used_guns(progress_callback=None):
    """
    Scrape used firearms listings from Elk River Guns website

    Args:
        progress_callback: Optional callback function to report progress
                          Function should accept (stage, message, percent) parameters

    Returns:
        List of FirearmListing objects
    """
    # Report progress if a callback is provided
    if progress_callback:
        progress_callback("scraping", "Connecting to Elk River Guns website...", 0)

    url = "https://elkriverguns.com/used-guns/"
    resp = requests.get(url)

    if progress_callback:
        progress_callback("scraping", "Parsing webpage content...", 10)

    soup = BeautifulSoup(resp.text, "html.parser")
    all_listings = []

    # Find all tables on the page
    tables = soup.find_all("table")

    if progress_callback:
        progress_callback("scraping", "Finding firearm sections...", 20)

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
            # Report progress
            if progress_callback:
                current_section += 1
                progress_percent = 30 + (60 * current_section / total_sections)
                progress_callback(
                    "scraping", f"Parsing {section_name} listings...", int(progress_percent)
                )

            # Find the table that follows this header
            table = section_header.find_next("table")
            if table:
                listings = parse_table(table, section_name)
                all_listings.extend(listings)

    # Final progress update
    if progress_callback:
        progress_callback("scraping", f"Found {len(all_listings)} firearms", 100)

    return all_listings


if __name__ == "__main__":
    listings = scrape_used_guns()
    for l in listings:
        print(l)
