# Elk River Guns Inventory Tracker

A simple application that scrapes and displays the used gun inventory from Elk River Guns website, with market value estimation for each firearm.

## Features

- Scrapes real-time data from the Elk River Guns used guns page
- Displays inventory in a clean, filterable table
- Filter by firearm type (Pistols, Rifles, Revolvers, Shotguns)
- **Market Value Estimation**: Provides estimated market values for each firearm
- Compare listing prices to market values to identify potential deals
- See value ranges and sources for each estimate
- **Analytics Dashboard**: View price trends, inventory composition, and top deals
- Interactive charts and visualizations for market analysis
- Highlights best value firearms across different categories
- **Historical Price Tracking**: Tracks price changes over time 
- **Duplicate Prevention**: Smart detection and handling of duplicate listings

## Installation

1. Clone this repository
2. Create a virtual environment (recommended):
   ```
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   source .venv/bin/activate  # On macOS/Linux
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. (Optional) Install development dependencies for linting:
   ```
   pip install -r requirements-dev.txt
   pre-commit install  # Enables automatic linting before commits
   ```

## Usage

Run the Streamlit application:
```
streamlit run app.py
```

The application will open in your web browser automatically. If it doesn't, navigate to http://localhost:8501

### Value Estimation

The app uses an intelligent market value estimator to provide price guidance:

- **Market Estimator**: Analyzes manufacturer, model, and caliber to estimate value
- Incorporates knowledge of market trends and popular models
- Adjusts values based on firearm characteristics and current market conditions

Value estimates include:
- Estimated market value
- Typical price range
- Price comparison (premium or savings compared to market value)

### Market Analytics

The application includes a dedicated analytics page with:

- **Market Overview**: Key statistics about the current inventory
- **Price Distribution**: Histogram showing the distribution of firearm prices
- **Inventory Composition**: Visual breakdown of firearm types and calibers
- **Top Deals**: Quick view of the best-value firearms currently listed
- **Market Value Analysis**: Comparison of listing prices to estimated market values
- **Historical Price Trends**: Track price changes for specific firearms over time

### Historical Data Tracking

The application now tracks historical data over time:

- **Price Tracking**: See how prices for specific manufacturers and models change
- **Trend Analysis**: Visualize pricing trends with interactive charts
- **Comparison**: Compare listing prices to market values over time

### Testing Firearm Value Estimation

You can test the value estimation functionality separately using the included test script:

```
python test_firearm_values.py
```

This will run a series of tests on the market estimator with common firearms.

Additional options:
- `--limit N`: Set the number of test firearms (default: 5)
- Test a specific firearm:
  ```
  python test_firearm_values.py --manufacturer "GLOCK" --model "19" --caliber "9MM"
  ```

## Development

### Code Quality

This project uses `ruff` for linting and code formatting:

```bash
# Run linting checks
make lint

# Auto-fix issues and format code
make fix

# Run tests
make test
```

### GitHub Actions

The project includes GitHub Actions workflows for:
- **Automatic linting** on push and pull requests
- **Manual code formatting** via workflow dispatch

## Project Structure

- `main.py` - Web scraping functionality using BeautifulSoup
- `app.py` - Streamlit user interface with inventory and analytics pages
- `firearm_values.py` - Firearm market value estimation module
- `price_analysis.py` - Market analysis and price trend functionality
- `test_firearm_values.py` - Test script for the value estimation module
- `test_armslist_search.py` - Test script for Armslist integration
- `db_migration.py` - Database migration utilities
- `requirements.txt` - Project dependencies
- `requirements-dev.txt` - Development dependencies (linting, testing)
- `Makefile` - Common development commands
- `.github/workflows/` - CI/CD workflows

## Requirements

- Python 3.8+
- BeautifulSoup4
- Requests
- Streamlit
- Pandas
- Altair
- Supabase

## Disclaimer

Market value estimates are provided for informational purposes only and should not be considered financial advice. Actual firearm values can vary based on condition, modifications, local market factors, and other considerations. 