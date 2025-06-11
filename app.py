import hashlib
import json
import time
import urllib.parse
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st
from supabase import create_client

import price_analysis
from firearm_values import estimate_value
from main import scrape_all_guns
from concurrent_estimator import ConcurrentValueEstimator, create_estimation_tasks
from cache_manager import get_market_cache
from validation import InputValidator


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
    result = supabase.table("firearm_listings").select("*").eq("is_latest", True).execute()

    # Convert to a list of dictionaries for easier manipulation
    return result.data


def get_last_scrape_time():
    """Get the timestamp of the most recent scrape"""
    supabase = get_connection()
    result = (
        supabase.table("firearm_listings")
        .select("date_scraped")
        .order("date_scraped", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        # Return the timestamp of the most recent record
        return result.data[0]["date_scraped"]
    return None


def mark_listings_as_not_latest():
    """Mark all existing listings as not latest"""
    supabase = get_connection()
    # Update all records to set is_latest to False
    # We need to include a filter to satisfy PostgreSQL's requirement for a WHERE clause
    supabase.table("firearm_listings").update({"is_latest": False}).neq("id", 0).execute()


def generate_listing_hash(listing):
    """Generate a unique hash for a listing to identify duplicates"""
    # Create a string that uniquely identifies this firearm
    # Include condition to differentiate between new and used guns with same specs
    unique_str = f"{listing.manufacturer}|{listing.model}|{listing.caliber}|{listing.price}|{listing.description}|{listing.condition}"
    # Generate a hash
    return hashlib.md5(unique_str.encode()).hexdigest()


def store_listings(listings, max_workers=4, enable_caching=True):
    """Store listings in the database with value estimates, preventing duplicates"""
    supabase = get_connection()

    # First, mark all existing listings as not latest
    mark_listings_as_not_latest()

    # Prepare data for database insertion
    db_records = []
    current_time = datetime.now().isoformat()

    # Define max length for varchar fields to prevent DB errors
    VARCHAR_LIMITS = {
        "section": 30,
        "manufacturer": 30,
        "model": 30,
        "caliber": 30,
        "value_source": 30,
    }

    use_online = st.session_state.get("use_online_sources", False)

    # Show cache statistics
    if enable_caching:
        cache = get_market_cache()
        cache_stats = cache.get_cache_stats()
        st.info(
            f"Cache: {cache_stats['memory_entries']} in memory, {cache_stats['file_entries']} on disk"
        )

    if use_online and len(listings) > 10:
        # Use concurrent processing for larger datasets
        st.info(
            f"🚀 Using concurrent processing with {max_workers} workers for faster value estimation..."
        )

        # Create progress bars
        overall_progress = st.progress(0)
        detail_progress = st.empty()

        # Create estimation tasks
        tasks = create_estimation_tasks(listings, use_online_sources=use_online)

        # Configure concurrent estimator
        estimator = ConcurrentValueEstimator(
            max_workers=max_workers,
            rate_limit_delay=0.3,  # Reduced delay for better performance
        )

        # Override caching if disabled
        if not enable_caching:
            estimator.cache = None

        # Progress callback
        def progress_callback(completed: int, total: int, status: str):
            progress_percent = int(100 * completed / total)
            overall_progress.progress(
                progress_percent, text=f"Processing {completed}/{total} firearms"
            )
            detail_progress.text(status)

        # Process all estimates concurrently
        start_time = time.time()
        results = estimator.estimate_values_batch(tasks, progress_callback)
        processing_time = time.time() - start_time

        # Show performance stats
        successful_results = [r for r in results if r.success]
        avg_time = (
            sum(r.processing_time for r in successful_results) / len(successful_results)
            if successful_results
            else 0
        )

        st.success(
            f"✅ Completed in {processing_time:.1f}s (avg {avg_time:.1f}s per firearm, {len(successful_results)}/{len(results)} successful)"
        )

        # Process results into database records
        for i, listing in enumerate(listings):
            result = results[i]

            # Generate a unique hash for this listing
            listing_hash = generate_listing_hash(listing)

            if result.success and result.value_info:
                value_info = result.value_info

                # Calculate price difference if we have an estimated value
                price_difference = None
                price_difference_percent = None

                if value_info["estimated_value"]:
                    price_difference = listing.price - value_info["estimated_value"]
                    price_difference_percent = (
                        price_difference / value_info["estimated_value"]
                    ) * 100

                # Create record for database
                record = {
                    "section": listing.section[: VARCHAR_LIMITS["section"]]
                    if listing.section
                    else None,
                    "manufacturer": listing.manufacturer[: VARCHAR_LIMITS["manufacturer"]]
                    if listing.manufacturer
                    else None,
                    "model": listing.model[: VARCHAR_LIMITS["model"]] if listing.model else None,
                    "caliber": listing.caliber[: VARCHAR_LIMITS["caliber"]]
                    if listing.caliber
                    else None,
                    "list_price": listing.price,
                    "description": listing.description,
                    "condition": listing.condition,
                    "estimated_value": value_info["estimated_value"],
                    "value_source": value_info["source"][: VARCHAR_LIMITS["value_source"]]
                    if value_info["source"]
                    else None,
                    "value_confidence": value_info["confidence"],
                    "price_difference": price_difference,
                    "price_difference_percent": price_difference_percent,
                    "listing_hash": listing_hash,
                    "is_latest": True,
                    "date_scraped": current_time,
                }

                # Add value range if available
                if value_info["value_range"]:
                    record["value_range_low"] = value_info["value_range"][0]
                    record["value_range_high"] = value_info["value_range"][1]

                # Add market listings data if available (as JSON)
                if value_info.get("market_listings"):
                    record["market_listings_json"] = json.dumps(value_info["market_listings"])
                    record["market_listings_count"] = len(value_info["market_listings"])

                db_records.append(record)
            else:
                # Fallback for failed estimates
                record = {
                    "section": listing.section[: VARCHAR_LIMITS["section"]]
                    if listing.section
                    else None,
                    "manufacturer": listing.manufacturer[: VARCHAR_LIMITS["manufacturer"]]
                    if listing.manufacturer
                    else None,
                    "model": listing.model[: VARCHAR_LIMITS["model"]] if listing.model else None,
                    "caliber": listing.caliber[: VARCHAR_LIMITS["caliber"]]
                    if listing.caliber
                    else None,
                    "list_price": listing.price,
                    "description": listing.description,
                    "condition": listing.condition,
                    "estimated_value": None,
                    "value_source": "Estimation failed",
                    "value_confidence": "none",
                    "price_difference": None,
                    "price_difference_percent": None,
                    "listing_hash": listing_hash,
                    "is_latest": True,
                    "date_scraped": current_time,
                }
                db_records.append(record)

        # Clear progress indicators
        overall_progress.empty()
        detail_progress.empty()

    else:
        # Use sequential processing for smaller datasets or when online sources disabled
        progress_bar = st.progress(0)
        total_listings = len(listings)

        # Process each listing with a progress indicator
        for i, l in enumerate(listings):
            # Update progress bar
            progress_percent = int(100 * (i / total_listings))
            progress_bar.progress(
                progress_percent,
                text=f"Processing {i + 1}/{total_listings}: {l.manufacturer} {l.model}",
            )

            # Generate a unique hash for this listing
            listing_hash = generate_listing_hash(l)

            # Get value estimate
            value_info = estimate_value(
                l.manufacturer, l.model, l.caliber, use_online_sources=use_online
            )

            # Calculate price difference if we have an estimated value
            price_difference = None
            price_difference_percent = None

            if value_info["estimated_value"]:
                price_difference = l.price - value_info["estimated_value"]
                price_difference_percent = (price_difference / value_info["estimated_value"]) * 100

            # Create record for database - truncate fields to prevent varchar limit errors
            record = {
                "section": l.section[: VARCHAR_LIMITS["section"]] if l.section else None,
                "manufacturer": l.manufacturer[: VARCHAR_LIMITS["manufacturer"]]
                if l.manufacturer
                else None,
                "model": l.model[: VARCHAR_LIMITS["model"]] if l.model else None,
                "caliber": l.caliber[: VARCHAR_LIMITS["caliber"]] if l.caliber else None,
                "list_price": l.price,
                "description": l.description,
                "condition": l.condition,
                "estimated_value": value_info["estimated_value"],
                "value_source": value_info["source"][: VARCHAR_LIMITS["value_source"]]
                if value_info["source"]
                else None,
                "value_confidence": value_info["confidence"],
                "price_difference": price_difference,
                "price_difference_percent": price_difference_percent,
                "listing_hash": listing_hash,
                "is_latest": True,
                "date_scraped": current_time,
            }

            # Add value range if available
            if value_info["value_range"]:
                record["value_range_low"] = value_info["value_range"][0]
                record["value_range_high"] = value_info["value_range"][1]

            # Add market listings data if available (as JSON)
            if value_info.get("market_listings"):
                record["market_listings_json"] = json.dumps(value_info["market_listings"])
                record["market_listings_count"] = len(value_info["market_listings"])

            db_records.append(record)

        # Clear progress bar
        progress_bar.empty()

    # Insert records in batches of 50 to avoid potential size limits
    batch_size = 50
    for i in range(0, len(db_records), batch_size):
        batch = db_records[i : i + batch_size]
        supabase.table("firearm_listings").insert(batch).execute()

    return len(db_records)


def format_price_comparison(value, percent):
    """Format the price difference nicely for display"""
    if value is None or percent is None:
        return "N/A"

    if value > 0:
        return f"+${value:.2f} ({percent:.1f}% premium)"
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

    # Check if the required columns exist
    has_market_listings = (
        "market_listings_count" in df.columns and "market_listings_json" in df.columns
    )

    # Extract section types for filtering
    df["section_type"] = df["section"].apply(lambda x: x.split()[0] if " " in x else x)

    # Get unique section types for the dropdown
    section_types = sorted(df["section_type"].unique())

    # Add "All" option
    options = ["All"] + section_types

    # Create sidebar for filters
    st.sidebar.header("Filters")

    # Add condition filter (new/used)
    condition_filter = st.sidebar.radio("Condition:", ["All", "New Only", "Used Only"])

    # Create a dropdown for filtering
    selected_section = st.sidebar.selectbox("Select Firearm Type:", options)

    # Add option to show good deals
    deal_filter = st.sidebar.radio(
        "Price Filter:", ["All Listings", "Good Deals (Below Market Value)", "Premium Priced"]
    )

    # Filter by condition
    if "condition" in df.columns:
        if condition_filter == "New Only":
            df = df[df["condition"] == "new"]
        elif condition_filter == "Used Only":
            df = df[df["condition"] == "used"]

    # Filter by section
    if selected_section != "All":
        df = df[df["section_type"] == selected_section]

    # Filter by deals
    if deal_filter == "Good Deals (Below Market Value)":
        df = df[df["price_difference"] < 0]
    elif deal_filter == "Premium Priced":
        df = df[df["price_difference"] > 0]

    # Show count of results
    st.write(
        f"Showing {len(df)} listings"
        + (f" for {selected_section}" if selected_section != "All" else "")
        + (f" ({deal_filter})" if deal_filter != "All Listings" else "")
    )

    if not df.empty:
        # Create a display-ready DataFrame with sanitized data
        display_df = pd.DataFrame(
            {
                "Condition": df["condition"].apply(lambda x: InputValidator.sanitize_for_display(x.title()) if x else "Unknown")
                if "condition" in df.columns
                else "Unknown",
                "Type": df["section_type"].apply(lambda x: InputValidator.sanitize_for_display(str(x))),
                "Manufacturer": df["manufacturer"].apply(lambda x: InputValidator.sanitize_for_display(str(x))),
                "Model": df["model"].apply(lambda x: InputValidator.sanitize_for_display(str(x))),
                "Caliber/Gauge": df["caliber"].apply(lambda x: InputValidator.sanitize_for_display(str(x))),
                "List Price": df["list_price"].apply(lambda x: f"${x:,.2f}" if x else "N/A"),
                "Est. Market Value": df["estimated_value"].apply(
                    lambda x: f"${x:,.2f}" if x else "No data"
                ),
                "Value Range": df.apply(
                    lambda row: f"${row['value_range_low']:,.2f} - ${row['value_range_high']:,.2f}"
                    if pd.notna(row["value_range_low"]) and pd.notna(row["value_range_high"])
                    else "N/A",
                    axis=1,
                ),
                "Value Source": df["value_source"].fillna("N/A").apply(lambda x: InputValidator.sanitize_for_display(str(x))),
                "Description": df["description"].apply(lambda x: InputValidator.sanitize_for_display(str(x)) if x else ""),
            }
        )

        # Add the sortable price comparison column
        display_df["Price Difference"] = df["price_difference"]  # Hidden column for sorting
        display_df["Price Difference %"] = df[
            "price_difference_percent"
        ]  # Hidden column for sorting
        display_df["Price vs Market"] = df.apply(
            lambda row: format_price_comparison(
                row["price_difference"], row["price_difference_percent"]
            ),
            axis=1,
        )

        # Add online listings indicator only if the columns exist
        if has_market_listings:
            has_listings = df.apply(
                lambda row: "✓"
                if pd.notna(row.get("market_listings_count")) and row["market_listings_count"] > 0
                else "",
                axis=1,
            )
            if df["market_listings_count"].sum() > 0:
                display_df["Online Listings"] = has_listings

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
            "List Price": st.column_config.TextColumn(
                "List Price", help="Listing price at Elk River Guns"
            ),
            "Est. Market Value": st.column_config.TextColumn(
                "Est. Market Value", help="Estimated market value"
            ),
            "Value Range": st.column_config.TextColumn(
                "Value Range", help="Typical price range for this firearm"
            ),
            "Value Source": st.column_config.TextColumn(
                "Value Source", help="Source of the value estimate"
            ),
            "Price Difference": st.column_config.NumberColumn(
                "Price Difference",
                help="Difference between list price and market value",
                format="$%.2f",
                disabled=True,  # Hide this column, just use for sorting
            ),
            "Price Difference %": st.column_config.NumberColumn(
                "Price Difference %",
                help="Percentage difference from market value",
                format="%.1f%%",
                disabled=True,  # Hide this column, just use for sorting
            ),
            "Price vs Market": st.column_config.TextColumn(
                "Price vs Market", help="Price comparison to market value"
            ),
            "Description": st.column_config.TextColumn("Description", help="Listing description"),
        }

        # Add online listings column config if applicable
        if "Online Listings" in display_df.columns:
            column_config["Online Listings"] = st.column_config.TextColumn(
                "Online Listings",
                help="Click to view current online marketplace listings for this firearm",
            )

        # Display the dataframe with the column configuration
        st.dataframe(
            display_df, use_container_width=True, hide_index=True, column_config=column_config
        )

        # Note: In Streamlit 1.20.0+, getting selected rows requires a different approach
        # For now, let's comment out the selection functionality since it's causing an error

        # Display a message about the market listings if they exist
        if has_market_listings:
            st.info(
                "To view online marketplace listings for a specific firearm, search for the manufacturer and model in the search box above."
            )

            # Optional: Add a selector to let users pick a firearm to view listings for
            if len(df) > 0:
                firearm_options = [
                    f"{row['manufacturer']} {row['model']} {row['caliber']}"
                    for _, row in df.iterrows()
                    if pd.notna(row.get("market_listings_json"))
                ]

                if firearm_options:
                    st.subheader("Online Marketplace Listings")
                    selected_firearm = st.selectbox(
                        "Select a firearm to view online listings:", ["Select..."] + firearm_options
                    )

                    if selected_firearm != "Select...":
                        # Find the matching row
                        for idx, row in df.iterrows():
                            firearm = f"{row['manufacturer']} {row['model']} {row['caliber']}"
                            if firearm == selected_firearm and pd.notna(
                                row.get("market_listings_json")
                            ):
                                try:
                                    # Parse the JSON string to get the listings
                                    market_listings = json.loads(row["market_listings_json"])

                                    if market_listings:
                                        st.markdown(f"### Current listings for {firearm}")

                                        # Create a DataFrame to display the listings
                                        listings_df = pd.DataFrame(
                                            [
                                                {
                                                    "Title": l.get("title", "No Title"),
                                                    "Price": l.get(
                                                        "price_text", "Price not listed"
                                                    ),
                                                    "Location": l.get("location", "Not specified"),
                                                    "Ships": "Yes"
                                                    if l.get("ships", False)
                                                    else "No",
                                                    "Source": l.get("source", "Unknown"),
                                                }
                                                for l in market_listings
                                            ]
                                        )

                                        # Display the listings
                                        st.dataframe(
                                            listings_df, use_container_width=True, hide_index=True
                                        )

                                        # Add a link to the original search
                                        search_query = f"{row['manufacturer']} {row['model']} {row['caliber']}".strip()
                                        encoded_query = urllib.parse.quote(search_query)
                                        armslist_url = f"https://www.armslist.com/classifieds/search?search={encoded_query}&location=usa&category=all&posttype=7&ships=&ispowersearch=1&hs=1"

                                        st.markdown(
                                            f"[View more listings on Armslist]({armslist_url})"
                                        )
                                except Exception as e:
                                    st.error(f"Error displaying online listings: {e}")

        # If market listing columns don't exist, show a message
        if not has_market_listings and st.session_state.get("use_online_sources", False):
            st.warning("""
            **Database Update Required**: To use online marketplace data, you need to update your database schema.
            
            Run the migration script to add the required columns:
            ```
            python db_migration.py --add-market-columns
            ```
            
            Or add the columns manually through the Supabase console:
            - market_listings_json (JSONB)
            - market_listings_count (INTEGER)
            """)
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
        avg_list = report["general_stats"]["avg_list_price"]
        st.metric("Average List Price", f"${avg_list:.2f}")

    with col3:
        if "avg_price_difference_percent" in report["general_stats"]:
            avg_diff_pct = report["general_stats"]["avg_price_difference_percent"]
            st.metric("Avg. Price Difference", f"{avg_diff_pct:.1f}%")

    # Price distribution visualization
    st.subheader("Price Distribution")

    # Create a histogram of prices
    if not df.empty and "list_price" in df.columns:
        price_chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                alt.X("list_price:Q", bin=alt.Bin(maxbins=20), title="Price ($)"),
                alt.Y("count()", title="Number of Listings"),
            )
            .properties(height=300)
        )

        st.altair_chart(price_chart, use_container_width=True)

    # Firearm type distribution
    st.subheader("Inventory Composition")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Firearm Types**")
        if report["type_distribution"] and report["type_distribution"]["counts"]:
            # Extract data for the chart
            type_data = pd.DataFrame(
                {
                    "Type": report["type_distribution"]["counts"].keys(),
                    "Count": report["type_distribution"]["counts"].values(),
                }
            )

            # Create the pie chart
            type_chart = (
                alt.Chart(type_data)
                .mark_arc()
                .encode(theta="Count:Q", color="Type:N", tooltip=["Type:N", "Count:Q"])
                .properties(height=300)
            )

            st.altair_chart(type_chart, use_container_width=True)

    with col2:
        st.markdown("**Caliber Distribution**")
        if report["caliber_distribution"] and report["caliber_distribution"]["counts"]:
            # Extract data for the chart (top 5 calibers)
            caliber_data = pd.DataFrame(
                {
                    "Caliber": list(report["caliber_distribution"]["counts"].keys())[:5],
                    "Count": list(report["caliber_distribution"]["counts"].values())[:5],
                }
            )

            # Create the bar chart
            caliber_chart = (
                alt.Chart(caliber_data)
                .mark_bar()
                .encode(
                    x="Count:Q", y=alt.Y("Caliber:N", sort="-x"), tooltip=["Caliber:N", "Count:Q"]
                )
                .properties(height=300)
            )

            st.altair_chart(caliber_chart, use_container_width=True)

    # Top deals section
    st.subheader("Top Deals")
    if not report["top_deals"].empty:
        # Create a display-ready version
        deals_df = report["top_deals"].copy()

        # Format the display columns
        display_deals = pd.DataFrame(
            {
                "Type": deals_df["section_type"]
                if "section_type" in deals_df.columns
                else deals_df["section"],
                "Manufacturer": deals_df["manufacturer"],
                "Model": deals_df["model"],
                "Caliber": deals_df["caliber"],
                "List Price": deals_df["list_price"].apply(lambda x: f"${x:,.2f}"),
                "Market Value": deals_df["estimated_value"].apply(
                    lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"
                ),
                "Savings": deals_df.apply(
                    lambda row: f"${abs(row['price_difference']):,.2f} ({abs(row['price_difference_percent']):.1f}%)",
                    axis=1,
                ),
            }
        )

        # Display the top deals
        st.dataframe(display_deals, use_container_width=True, hide_index=True)
    else:
        st.info("No deals currently found in the inventory.")

    # Market pricing analysis
    st.subheader("Market Value Analysis")

    col1, col2, col3 = st.columns(3)

    with col1:
        below_market_pct = report["general_stats"].get("percent_below_market", 0)
        st.metric("Below Market Value", f"{below_market_pct:.1f}%")

    with col2:
        at_market_pct = report["general_stats"].get("percent_at_market", 0)
        st.metric("At Market Value", f"{at_market_pct:.1f}%")

    with col3:
        above_market_pct = report["general_stats"].get("percent_above_market", 0)
        st.metric("Above Market Value", f"{above_market_pct:.1f}%")

    # Create chart showing the pricing distribution
    if "price_difference_percent" in df.columns:
        # Create a histogram of price difference percentages
        diff_chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                alt.X(
                    "price_difference_percent:Q",
                    bin=alt.Bin(maxbins=15),
                    title="Price Difference (%)",
                ),
                alt.Y("count()", title="Number of Listings"),
                alt.Color(
                    "price_difference_percent:Q",
                    scale=alt.Scale(scheme="blueorange", domain=[-30, 30]),
                    legend=None,
                ),
            )
            .properties(height=300)
        )

        st.altair_chart(diff_chart, use_container_width=True)

        # Add explanation
        st.caption(
            "Distribution of listings by price difference percentage. Negative values (blue) represent listings below market value, positive values (orange) are above market value."
        )

    # Add after the existing price diff_chart code
    # Historical price trends (if data is available)
    st.subheader("Historical Price Trends")

    # Get manufacturers for the dropdown
    manufacturers = sorted(df["manufacturer"].unique())
    selected_manufacturer = st.selectbox("Select Manufacturer", ["All"] + list(manufacturers))

    # If a manufacturer is selected, get models for that manufacturer
    if selected_manufacturer != "All":
        models = sorted(df[df["manufacturer"] == selected_manufacturer]["model"].unique())
        selected_model = st.selectbox("Select Model", ["All"] + list(models))
    else:
        selected_model = "All"

    # Get period for historical data
    period = st.slider("Time Period (days)", min_value=7, max_value=180, value=30, step=7)

    # Get historical price trends
    supabase = get_connection()

    if selected_manufacturer != "All" and selected_model != "All":
        trends = price_analysis.get_historical_price_trends(
            supabase, manufacturer=selected_manufacturer, model=selected_model, days=period
        )
        trend_title = f"{selected_manufacturer} {selected_model}"
    elif selected_manufacturer != "All":
        trends = price_analysis.get_historical_price_trends(
            supabase, manufacturer=selected_manufacturer, days=period
        )
        trend_title = f"{selected_manufacturer} (All Models)"
    else:
        trends = price_analysis.get_historical_price_trends(supabase, days=period)
        trend_title = "All Firearms"

    if trends and len(trends["dates"]) > 1:
        # Create data for the line chart
        trend_data = pd.DataFrame(
            {
                "Date": trends["dates"],
                "List Price": trends["list_prices"],
                "Market Value": trends["est_values"],
            }
        )

        # Create a line chart
        trend_chart = (
            alt.Chart(trend_data)
            .transform_fold(["List Price", "Market Value"], as_=["Price Type", "Price"])
            .mark_line()
            .encode(
                x="Date:T",
                y=alt.Y("Price:Q", title="Price ($)"),
                color="Price Type:N",
                tooltip=["Date:T", "Price Type:N", "Price:Q"],
            )
            .properties(title=f"Price Trends for {trend_title}", height=300)
        )

        st.altair_chart(trend_chart, use_container_width=True)
    else:
        st.info("Not enough historical data available for the selected criteria.")


def main():
    st.set_page_config(page_title="Elk River Guns Inventory Tracker", layout="wide")

    # Add a title and description
    st.title("Elk River Guns Inventory Tracker")
    st.markdown(
        "This app tracks inventory and estimates market values for both new and used firearms at Elk River Guns."
    )
    st.markdown(
        "This app is not affiliated with Elk River Guns. It is a personal project to help track the market value of firearms."
    )
    col1, col2 = st.columns(2)
    with col1:
        st.link_button("Used Guns", "https://elkriverguns.com/used-guns")
    with col2:
        st.link_button("New Guns", "https://elkriverguns.com/new-guns")
    # Check when data was last scraped
    last_scrape_time = get_last_scrape_time()

    # If we have a timestamp, show when data was last updated
    if last_scrape_time:
        st.sidebar.info(f"Data last updated: {last_scrape_time}")

    # Add refresh button in sidebar
    with st.sidebar:
        refresh = st.button("Refresh Data")

        # Add a separator
        st.markdown("---")

        # Add option to enable online sources
        st.subheader("Market Data Settings")
        # Initialize the session state if not already done
        if "use_online_sources" not in st.session_state:
            st.session_state.use_online_sources = False

        use_online = st.checkbox(
            "Use online marketplace data",
            value=st.session_state.use_online_sources,
            help="When enabled, the app will search online marketplaces like Armslist for current listings. This may slow down data refresh.",
        )

        # Update session state if changed
        if use_online != st.session_state.use_online_sources:
            st.session_state.use_online_sources = use_online
            # If settings changed, suggest a refresh
            st.info(
                "Online market data settings changed. Please refresh the data to apply changes."
            )

    # Determine if we need to fetch new data
    needs_update = refresh or not last_scrape_time

    # Show performance settings BEFORE the data refresh process (outside any containers)
    if needs_update and st.session_state.get("use_online_sources", False):
        st.subheader("⚙️ Processing Configuration")
        with st.expander("🚀 Performance Settings", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                max_workers = st.number_input(
                    "Concurrent Workers",
                    min_value=1,
                    max_value=8,
                    value=4,
                    help="More workers = faster processing, but higher server load",
                )
            with col2:
                enable_caching = st.checkbox(
                    "Enable Caching", value=True, help="Cache online lookups to avoid repeated searches"
                )
            with col3:
                if st.button("Clear Cache"):
                    cache = get_market_cache()
                    cleared = cache.clear_expired()
                    st.success(f"Cleared {cleared} expired cache entries")
    else:
        # Default values when not showing UI
        max_workers = 4
        enable_caching = True

    # If data needs to be refreshed, scrape new data
    if needs_update:
        # Create a status container to show overall progress
        with st.status("Data Refresh Process", expanded=True) as status:
            status.update(
                label="Step 1/3: Fetching latest inventory from Elk River Guns...", state="running"
            )

            # Create a progress bar for the scraping process
            scrape_progress_bar = st.progress(0, text="Starting data collection...")

            # Define a callback function to update the progress bar during scraping
            def update_scrape_progress(stage, message, percent):
                scrape_progress_bar.progress(percent, text=message)
                if percent >= 100:
                    time.sleep(0.5)  # Give a moment to see 100%

            # Scrape new data with progress updates (both new and used guns)
            listings = scrape_all_guns(progress_callback=update_scrape_progress)

            if listings:
                # Update status for the next phase
                status.update(
                    label=f"Step 2/3: Processing {len(listings)} firearms and estimating market values...",
                    state="running",
                )

                # Remove the scraping progress bar and add a message about found firearms
                scrape_progress_bar.empty()
                st.success(f"Found {len(listings)} firearms at Elk River Guns")
                
                # Process data and store in database
                total_stored = store_listings(listings, max_workers, enable_caching)

                # Update status one more time
                status.update(label="Step 3/3: Finalizing database update...", state="running")

                # Refresh last scrape time
                last_scrape_time = get_last_scrape_time()

                # Complete the status
                status.update(
                    label=f"✅ Complete! Updated database with {total_stored} firearms.",
                    state="complete",
                )

                # Also show a success message in the sidebar
                st.sidebar.success(f"Data refreshed successfully! Added {total_stored} firearms.")
            else:
                status.update(
                    label="❌ Error: Could not retrieve inventory data from Elk River Guns.",
                    state="error",
                )
                st.error("Failed to fetch data from Elk River Guns. Please try again later.")

    # Create tabs for different pages
    tab1, tab2 = st.tabs(["Inventory", "Analytics"])

    with tab1:
        inventory_page()

    with tab2:
        analytics_page()


if __name__ == "__main__":
    main()
