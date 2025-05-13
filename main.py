import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass

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
    rows = table.find_all('tr')[1:]  # skip header
    for row in rows:
        cols = [td.get_text(strip=True) for td in row.find_all('td')]
        if len(cols) < 6:
            continue  # skip incomplete rows
        _, manufacturer, model, caliber, price, description = cols
        try:
            price_val = float(price.replace('$', '').replace(',', ''))
        except ValueError:
            price_val = 0.0
        listings.append(FirearmListing(
            section=section,
            manufacturer=manufacturer,
            model=model,
            caliber=caliber,
            price=price_val,
            description=description
        ))
    return listings

def scrape_used_guns():
    url = "https://elkriverguns.com/used-guns/"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    all_listings = []
    
    # Find all tables on the page
    tables = soup.find_all('table')
    
    # Find section headers for tables
    sections = {
        'Pistols': None,
        'Rifles': None,
        'Revolvers': None,
        'Shotguns': None
    }
    
    # Locate section headers (h2 elements with specific text)
    for header in soup.find_all('h2'):
        header_text = header.get_text(strip=True)
        if 'Pistols' in header_text:
            sections['Pistols'] = header
        elif 'Rifles' in header_text:
            sections['Rifles'] = header
        elif 'Revolvers' in header_text:
            sections['Revolvers'] = header
        elif 'Shotguns' in header_text:
            sections['Shotguns'] = header
    
    # Match tables to section headers
    for section_name, section_header in sections.items():
        if section_header:
            # Find the table that follows this header
            table = section_header.find_next('table')
            if table:
                listings = parse_table(table, section_name)
                all_listings.extend(listings)
    
    return all_listings

if __name__ == "__main__":
    listings = scrape_used_guns()
    for l in listings:
        print(l)
