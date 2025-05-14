import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from main import scrape_used_guns
from firearm_values import estimate_value
from supabase import create_client
import price_analysis
import altair as alt
import hashlib

# Cache the connection
@st.cache_resource
def get_connection():
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    return create_client(url, key)

def get_latest_listings():
    """Get the latest listings from the database"""
    supabase = get_connection()
    # Get only the most recent entries for each unique firearm by using the max date
    result = supabase.table('firearm_listings').select('*').eq('is_latest', True).execute()
    
    # Convert to a list of dictionaries for easier manipulation
    return result.data

def get_last_scrape_time():
    """Get the timestamp of the most recent scrape"""
    supabase = get_connection()
    result = supabase.table('firearm_listings').select('date_scraped').order('date_scraped', desc=True).limit(1).execute()
    
    if result.data:
        # Return the timestamp of the most recent record
        return result.data[0]['date_scraped']
    return None

def mark_listings_as_not_latest():
    """Mark all existing listings as not latest"""
    supabase = get_connection()
    # Update all records to set is_latest to False
    # We need to include a filter to satisfy PostgreSQL's requirement for a WHERE clause
    supabase.table('firearm_listings').update({"is_latest": False}).neq('id', 0).execute()

def generate_listing_hash(listing):
    """Generate a unique hash for a listing to identify duplicates"""
    # Create a string that uniquely identifies this firearm
    unique_str = f"{listing.manufacturer}|{listing.model}|{listing.caliber}|{listing.price}|{listing.description}"
    # Generate a hash
    return hashlib.md5(unique_str.encode()).hexdigest()

def store_listings(listings):
    """Store listings in the database with value estimates, preventing duplicates"""
    supabase = get_connection()
    
    # First, mark all existing listings as not latest
    mark_listings_as_not_latest()
    
    # Prepare data for database insertion
    db_records = []
    current_time = datetime.now().isoformat()
    
    for l in listings:
        # Generate a unique hash for this listing
        listing_hash = generate_listing_hash(l)
        
        # Get value estimate
        value_info = estimate_value(l.manufacturer, l.model, l.caliber)
        
        # Calculate price difference if we have an estimated value
        price_difference = None
        price_difference_percent = None
        
        if value_info["estimated_value"]:
            price_difference = l.price - value_info["estimated_value"]
            price_difference_percent = (price_difference / value_info["estimated_value"]) * 100
        
        # Create record for database
        record = {
            "section": l.section,
            "manufacturer": l.manufacturer,
            "model": l.model,
            "caliber": l.caliber,
            "list_price": l.price,
            "description": l.description,
            "estimated_value": value_info["estimated_value"],
            "value_source": value_info["source"],
            "value_confidence": value_info["confidence"],
            "price_difference": price_difference,
            "price_difference_percent": price_difference_percent,
            "listing_hash": listing_hash,
            "is_latest": True,
            "date_scraped": current_time
        }
        
        # Add value range if available
        if value_info["value_range"]:
            record["value_range_low"] = value_info["value_range"][0]
            record["value_range_high"] = value_info["value_range"][1]
        
        db_records.append(record)
    
    # Insert records in batches of 50 to avoid potential size limits
    batch_size = 50
    for i in range(0, len(db_records), batch_size):
        batch = db_records[i:i+batch_size]
        supabase.table('firearm_listings').insert(batch).execute()
    
    return len(db_records)

def format_price_comparison(value, percent):
    """Format the price difference nicely for display"""
    if value is None or percent is None:
        return "N/A"
    
    if value > 0:
        return f"+${value:.2f} ({percent:.1f}% premium)"
    else:
        return f"-${abs(value):.2f} ({abs(percent):.1f}% savings)"

def inventory_page():
    """Main inventory display page"""
    st.header("Inventory Listings")
    st.markdown("Current inventory from Elk River Guns with market value comparison.")
    
    # Get data from database
    db_listings = get_latest_listings()
    
    if not db_listings:
        st.warning("No data available. Please click 'Refresh Data' to fetch the latest inventory.")
        return
    
    # Convert database records to DataFrame for easier filtering
    df = pd.DataFrame(db_listings)
    
    # Extract section types for filtering
    df['section_type'] = df['section'].apply(lambda x: x.split()[0] if ' ' in x else x)
    
    # Get unique section types for the dropdown
    section_types = sorted(df['section_type'].unique())
    
    # Add "All" option
    options = ["All"] + section_types
    
    # Create sidebar for filters
    st.sidebar.header("Filters")
    
    # Create a dropdown for filtering
    selected_section = st.sidebar.selectbox("Select Firearm Type:", options)
    
    # Add option to show good deals
    deal_filter = st.sidebar.radio(
        "Price Filter:",
        ["All Listings", "Good Deals (Below Market Value)", "Premium Priced"]
    )
    
    # Filter by section
    if selected_section != "All":
        df = df[df['section_type'] == selected_section]
    
    # Filter by deals
    if deal_filter == "Good Deals (Below Market Value)":
        df = df[df['price_difference'] < 0]
    elif deal_filter == "Premium Priced":
        df = df[df['price_difference'] > 0]
    
    # Show count of results
    st.write(f"Showing {len(df)} listings" + 
             (f" for {selected_section}" if selected_section != "All" else "") +
             (f" ({deal_filter})" if deal_filter != "All Listings" else ""))
    
    if not df.empty:
        # Create a display-ready DataFrame
        display_df = pd.DataFrame({
            "Type": df['section_type'],
            "Manufacturer": df['manufacturer'],
            "Model": df['model'],
            "Caliber/Gauge": df['caliber'],
            "List Price": df['list_price'].apply(lambda x: f"${x:,.2f}" if x else "N/A"),
            "Est. Market Value": df['estimated_value'].apply(lambda x: f"${x:,.2f}" if x else "No data"),
            "Value Range": df.apply(lambda row: f"${row['value_range_low']:,.2f} - ${row['value_range_high']:,.2f}" 
                                  if pd.notna(row['value_range_low']) and pd.notna(row['value_range_high']) 
                                  else "N/A", axis=1),
            "Value Source": df['value_source'].fillna("N/A"),
            "Description": df['description']
        })
        
        # Add the sortable price comparison column
        display_df["Price Difference"] = df['price_difference']  # Hidden column for sorting
        display_df["Price Difference %"] = df['price_difference_percent']  # Hidden column for sorting
        display_df["Price vs Market"] = df.apply(
            lambda row: format_price_comparison(row['price_difference'], row['price_difference_percent']), axis=1
        )
        
        # Create expandable section for explanation
        with st.expander("About Value Estimates"):
            st.markdown("""
            **Market Value Estimates**: These values are estimated from market data and should be used as a rough guideline only.
            
            - **Market Estimator**: Values are estimated based on manufacturer, model, and caliber.
            - **Value Range**: The typical price range for this model in similar condition.
            - **Price vs Market**: Comparison between the listing price and estimated market value.
            
            *Note: These estimates do not account for specific condition, modifications, accessories, or other factors that may affect value.*
            """)
        
        # Configure the column display and sorting
        column_config = {
            "List Price": st.column_config.TextColumn("List Price", help="Listing price at Elk River Guns"),
            "Est. Market Value": st.column_config.TextColumn("Est. Market Value", help="Estimated market value"),
            "Value Range": st.column_config.TextColumn("Value Range", help="Typical price range for this firearm"),
            "Value Source": st.column_config.TextColumn("Value Source", help="Source of the value estimate"),
            "Price Difference": st.column_config.NumberColumn(
                "Price Difference", 
                help="Difference between list price and market value",
                format="$%.2f",
                disabled=True  # Hide this column, just use for sorting
            ),
            "Price Difference %": st.column_config.NumberColumn(
                "Price Difference %", 
                help="Percentage difference from market value",
                format="%.1f%%",
                disabled=True  # Hide this column, just use for sorting
            ),
            "Price vs Market": st.column_config.TextColumn(
                "Price vs Market", 
                help="Price comparison to market value"
            ),
            "Description": st.column_config.TextColumn("Description", help="Listing description")
        }
        
        # Display the dataframe with the column configuration
        st.dataframe(
            display_df, 
            use_container_width=True, 
            hide_index=True,
            column_config=column_config
        )
    else:
        st.info("No listings found for the selected criteria.")

def analytics_page():
    """Analytics page with charts and statistics"""
    st.header("Market Analysis")
    st.markdown("Analysis of firearm pricing trends and inventory statistics.")
    
    # Get data from database
    db_listings = get_latest_listings()
    
    if not db_listings:
        st.warning("No data available. Please click 'Refresh Data' to fetch the latest inventory.")
        return
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(db_listings)
    
    # Generate the price analysis report
    report = price_analysis.generate_price_report(df)
    
    if "error" in report:
        st.error(report["error"])
        return
    
    # Display general statistics in metrics
    st.subheader("Market Overview")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Listings", f"{report['general_stats']['total_listings']}")
        
    with col2:
        avg_list = report['general_stats']['avg_list_price']
        st.metric("Average List Price", f"${avg_list:.2f}")
        
    with col3:
        if 'avg_price_difference_percent' in report['general_stats']:
            avg_diff_pct = report['general_stats']['avg_price_difference_percent']
            st.metric("Avg. Price Difference", f"{avg_diff_pct:.1f}%")
    
    # Price distribution visualization
    st.subheader("Price Distribution")
    
    # Create a histogram of prices
    if not df.empty and 'list_price' in df.columns:
        price_chart = alt.Chart(df).mark_bar().encode(
            alt.X('list_price:Q', bin=alt.Bin(maxbins=20), title='Price ($)'),
            alt.Y('count()', title='Number of Listings')
        ).properties(
            height=300
        )
        
        st.altair_chart(price_chart, use_container_width=True)
    
    # Firearm type distribution
    st.subheader("Inventory Composition")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Firearm Types**")
        if report['type_distribution'] and report['type_distribution']['counts']:
            # Extract data for the chart
            type_data = pd.DataFrame({
                'Type': report['type_distribution']['counts'].keys(),
                'Count': report['type_distribution']['counts'].values()
            })
            
            # Create the pie chart
            type_chart = alt.Chart(type_data).mark_arc().encode(
                theta='Count:Q',
                color='Type:N',
                tooltip=['Type:N', 'Count:Q']
            ).properties(
                height=300
            )
            
            st.altair_chart(type_chart, use_container_width=True)
    
    with col2:
        st.markdown("**Caliber Distribution**")
        if report['caliber_distribution'] and report['caliber_distribution']['counts']:
            # Extract data for the chart (top 5 calibers)
            caliber_data = pd.DataFrame({
                'Caliber': list(report['caliber_distribution']['counts'].keys())[:5],
                'Count': list(report['caliber_distribution']['counts'].values())[:5]
            })
            
            # Create the bar chart
            caliber_chart = alt.Chart(caliber_data).mark_bar().encode(
                x='Count:Q',
                y=alt.Y('Caliber:N', sort='-x'),
                tooltip=['Caliber:N', 'Count:Q']
            ).properties(
                height=300
            )
            
            st.altair_chart(caliber_chart, use_container_width=True)
    
    # Top deals section
    st.subheader("Top Deals")
    if not report['top_deals'].empty:
        # Create a display-ready version
        deals_df = report['top_deals'].copy()
        
        # Format the display columns
        display_deals = pd.DataFrame({
            "Type": deals_df['section_type'] if 'section_type' in deals_df.columns else deals_df['section'],
            "Manufacturer": deals_df['manufacturer'],
            "Model": deals_df['model'],
            "Caliber": deals_df['caliber'],
            "List Price": deals_df['list_price'].apply(lambda x: f"${x:,.2f}"),
            "Market Value": deals_df['estimated_value'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"),
            "Savings": deals_df.apply(
                lambda row: f"${abs(row['price_difference']):,.2f} ({abs(row['price_difference_percent']):.1f}%)",
                axis=1
            )
        })
        
        # Display the top deals
        st.dataframe(
            display_deals,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No deals currently found in the inventory.")
    
    # Market pricing analysis
    st.subheader("Market Value Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        below_market_pct = report['general_stats'].get('percent_below_market', 0)
        st.metric("Below Market Value", f"{below_market_pct:.1f}%")
        
    with col2:
        at_market_pct = report['general_stats'].get('percent_at_market', 0)
        st.metric("At Market Value", f"{at_market_pct:.1f}%")
        
    with col3:
        above_market_pct = report['general_stats'].get('percent_above_market', 0)
        st.metric("Above Market Value", f"{above_market_pct:.1f}%")
    
    # Create chart showing the pricing distribution
    if 'price_difference_percent' in df.columns:
        # Create a histogram of price difference percentages
        diff_chart = alt.Chart(df).mark_bar().encode(
            alt.X('price_difference_percent:Q', bin=alt.Bin(maxbins=15), title='Price Difference (%)'),
            alt.Y('count()', title='Number of Listings'),
            alt.Color(
                'price_difference_percent:Q',
                scale=alt.Scale(scheme='blueorange', domain=[-30, 30]),
                legend=None
            )
        ).properties(
            height=300
        )
        
        st.altair_chart(diff_chart, use_container_width=True)
        
        # Add explanation
        st.caption("Distribution of listings by price difference percentage. Negative values (blue) represent listings below market value, positive values (orange) are above market value.")

    # Add after the existing price diff_chart code
    # Historical price trends (if data is available)
    st.subheader("Historical Price Trends")
    
    # Get manufacturers for the dropdown
    manufacturers = sorted(df['manufacturer'].unique())
    selected_manufacturer = st.selectbox("Select Manufacturer", ["All"] + list(manufacturers))
    
    # If a manufacturer is selected, get models for that manufacturer
    if selected_manufacturer != "All":
        models = sorted(df[df['manufacturer'] == selected_manufacturer]['model'].unique())
        selected_model = st.selectbox("Select Model", ["All"] + list(models))
    else:
        selected_model = "All"
    
    # Get period for historical data
    period = st.slider("Time Period (days)", min_value=7, max_value=180, value=30, step=7)
    
    # Get historical price trends
    supabase = get_connection()
    
    if selected_manufacturer != "All" and selected_model != "All":
        trends = price_analysis.get_historical_price_trends(
            supabase, 
            manufacturer=selected_manufacturer, 
            model=selected_model, 
            days=period
        )
        trend_title = f"{selected_manufacturer} {selected_model}"
    elif selected_manufacturer != "All":
        trends = price_analysis.get_historical_price_trends(
            supabase, 
            manufacturer=selected_manufacturer, 
            days=period
        )
        trend_title = f"{selected_manufacturer} (All Models)"
    else:
        trends = price_analysis.get_historical_price_trends(
            supabase, 
            days=period
        )
        trend_title = "All Firearms"
    
    if trends and len(trends['dates']) > 1:
        # Create data for the line chart
        trend_data = pd.DataFrame({
            'Date': trends['dates'],
            'List Price': trends['list_prices'],
            'Market Value': trends['est_values']
        })
        
        # Create a line chart
        trend_chart = alt.Chart(trend_data).transform_fold(
            ['List Price', 'Market Value'],
            as_=['Price Type', 'Price']
        ).mark_line().encode(
            x='Date:T',
            y=alt.Y('Price:Q', title='Price ($)'),
            color='Price Type:N',
            tooltip=['Date:T', 'Price Type:N', 'Price:Q']
        ).properties(
            title=f"Price Trends for {trend_title}",
            height=300
        )
        
        st.altair_chart(trend_chart, use_container_width=True)
    else:
        st.info("Not enough historical data available for the selected criteria.")

def main():
    st.set_page_config(page_title="Elk River Used Guns Inventory", layout="wide")
    
    # Add a title and description
    st.title("Elk River Used Guns Inventory")
    st.markdown("This app tracks inventory and estimates market values for used firearms at Elk River Guns.")
    
    # Check when data was last scraped
    last_scrape_time = get_last_scrape_time()
    
    # If we have a timestamp, show when data was last updated
    if last_scrape_time:
        st.sidebar.info(f"Data last updated: {last_scrape_time}")
    
    # Add refresh button in sidebar
    with st.sidebar:
        refresh = st.button("Refresh Data")
    
    # Determine if we need to fetch new data
    needs_update = refresh or not last_scrape_time
    
    # If data needs to be refreshed, scrape new data
    if needs_update:
        with st.spinner("Fetching latest inventory from Elk River Guns..."):
            # Scrape new data
            listings = scrape_used_guns()
            
            if listings:
                # Show progress for value estimation
                progress_text = "Estimating market values for firearms..."
                with st.status(progress_text) as status:
                    total_stored = store_listings(listings)
                    status.update(label=f"Updated database with {total_stored} firearms", state="complete")
                
                # Refresh last scrape time
                last_scrape_time = get_last_scrape_time()
                st.sidebar.success(f"Data refreshed successfully!")
    
    # Create tabs for different pages
    tab1, tab2 = st.tabs(["Inventory", "Analytics"])
    
    with tab1:
        inventory_page()
        
    with tab2:
        analytics_page()

if __name__ == "__main__":
    main()