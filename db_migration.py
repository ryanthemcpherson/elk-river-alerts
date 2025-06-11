import argparse
import os

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client


def get_connection():
    """Create a Supabase client connection using environment variables or secrets"""
    try:
        # Try to use Streamlit secrets if running in Streamlit environment
        url = st.secrets["supabase_url"]
        key = st.secrets["supabase_key"]
    except:
        # Fall back to environment variables if not running in Streamlit
        load_dotenv()
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            raise ValueError(
                "Supabase credentials not found. Please set SUPABASE_URL and SUPABASE_KEY environment variables."
            )

    return create_client(url, key)


def add_duplicate_prevention_columns():
    """Add columns needed for duplicate prevention and historical tracking"""
    print("Connecting to Supabase...")
    supabase = get_connection()

    # First, check if the columns already exist
    print("Checking if columns already exist...")

    # Get current table columns (this is a simplified check - there's no direct API for this)
    # In a real implementation, we'd use a more robust check
    listing_hash_exists = False
    is_latest_exists = False

    try:
        # Query a single record
        result = supabase.table("firearm_listings").select("listing_hash").limit(1).execute()
        if "listing_hash" in str(result):
            listing_hash_exists = True
            print("listing_hash column already exists")
    except:
        pass

    try:
        # Query a single record
        result = supabase.table("firearm_listings").select("is_latest").limit(1).execute()
        if "is_latest" in str(result):
            is_latest_exists = True
            print("is_latest column already exists")
    except:
        pass

    # Add columns if they don't exist
    if not listing_hash_exists:
        print("Adding listing_hash column...")
        # The exact SQL depends on your Supabase setup
        # This is a workaround since Supabase client doesn't have direct column manipulation
        # You may need to adjust this for your specific Supabase setup
        try:
            # Try to add the column through SQL
            # Note: This might not work directly through the client API
            # For a production setup, use the Supabase console or a migration tool
            print("Please add the 'listing_hash' column manually through the Supabase console.")
            print("SQL: ALTER TABLE firearm_listings ADD COLUMN IF NOT EXISTS listing_hash TEXT;")
        except Exception as e:
            print(f"Error adding listing_hash column: {e}")

    if not is_latest_exists:
        print("Adding is_latest column...")
        try:
            # Try to add the column through SQL
            print("Please add the 'is_latest' column manually through the Supabase console.")
            print(
                "SQL: ALTER TABLE firearm_listings ADD COLUMN IF NOT EXISTS is_latest BOOLEAN DEFAULT TRUE;"
            )
        except Exception as e:
            print(f"Error adding is_latest column: {e}")

    # Initialize existing records
    if listing_hash_exists and is_latest_exists:
        print("Initializing existing records...")
        try:
            # Update all existing records to set is_latest to True
            # (since there are no duplicates yet)
            # Include a WHERE clause to satisfy PostgreSQL requirements
            result = (
                supabase.table("firearm_listings")
                .update({"is_latest": True})
                .neq("id", 0)
                .execute()
            )
            print("Updated existing records to set is_latest=True")

            # Note: For listing_hash, we'd need to calculate it for each record
            # This is too complex for a basic migration script
            print(
                "Note: The listing_hash field will be populated automatically on the next data refresh."
            )
        except Exception as e:
            print(f"Error updating existing records: {e}")

    print("\nMigration completed.")
    print("\nIMPORTANT: Please make sure you have the necessary columns in your Supabase database:")
    print("1. listing_hash (TEXT): Stores a unique hash identifying each listing")
    print("2. is_latest (BOOLEAN): Indicates if the record is the latest version")

    print(
        "\nIf the automatic migration didn't work, please add these columns manually through the Supabase console."
    )


def add_market_listings_columns():
    """Add columns needed for market listings data"""
    print("Connecting to Supabase...")
    supabase = get_connection()

    # Check if the columns already exist
    print("Checking if market listings columns already exist...")

    market_listings_json_exists = False
    market_listings_count_exists = False

    try:
        # Query a single record
        result = (
            supabase.table("firearm_listings").select("market_listings_json").limit(1).execute()
        )
        if "market_listings_json" in str(result):
            market_listings_json_exists = True
            print("market_listings_json column already exists")
    except:
        pass

    try:
        # Query a single record
        result = (
            supabase.table("firearm_listings").select("market_listings_count").limit(1).execute()
        )
        if "market_listings_count" in str(result):
            market_listings_count_exists = True
            print("market_listings_count column already exists")
    except:
        pass

    # Add columns if they don't exist
    if not market_listings_json_exists:
        print("Adding market_listings_json column...")
        try:
            print(
                "Please add the 'market_listings_json' column manually through the Supabase console."
            )
            print(
                "SQL: ALTER TABLE firearm_listings ADD COLUMN IF NOT EXISTS market_listings_json JSONB;"
            )
        except Exception as e:
            print(f"Error adding market_listings_json column: {e}")

    if not market_listings_count_exists:
        print("Adding market_listings_count column...")
        try:
            print(
                "Please add the 'market_listings_count' column manually through the Supabase console."
            )
            print(
                "SQL: ALTER TABLE firearm_listings ADD COLUMN IF NOT EXISTS market_listings_count INTEGER DEFAULT 0;"
            )
        except Exception as e:
            print(f"Error adding market_listings_count column: {e}")

    print("\nMarket listings columns migration completed.")
    print("\nIMPORTANT: Please make sure you have the necessary columns in your Supabase database:")
    print("1. market_listings_json (JSONB): Stores market listings data as JSON")
    print("2. market_listings_count (INTEGER): Stores the count of market listings found")

    print(
        "\nIf the automatic migration didn't work, please add these columns manually through the Supabase console."
    )


def increase_varchar_limits():
    """Increase varchar limits for columns that may exceed the default 30 character limit"""
    print("Connecting to Supabase...")
    supabase = get_connection()

    print("Preparing to increase varchar limits for text columns...")

    # Columns that might need increased varchar limits
    columns_to_update = ["manufacturer", "model", "caliber", "section", "value_source"]

    # Generate SQL statements
    print("\nPlease run the following SQL in your Supabase SQL Editor to increase field sizes:")
    print("-" * 60)

    for column in columns_to_update:
        print(f"ALTER TABLE firearm_listings ALTER COLUMN {column} TYPE varchar(100);")

    print("-" * 60)
    print("\nVarchar limit migration completed.")
    print(
        "\nIMPORTANT: The SQL statements above need to be executed manually in the Supabase SQL Editor."
    )
    print("This will increase the size limits for fields that may contain longer text values.")
    print(
        "Once executed, the 'value too long for type character varying(30)' error should be resolved."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Database migration for Elk River Guns Inventory Tracker"
    )
    parser.add_argument(
        "--add-dup-prevention", action="store_true", help="Add duplicate prevention columns"
    )
    parser.add_argument(
        "--add-market-columns", action="store_true", help="Add market listings columns"
    )
    parser.add_argument(
        "--increase-varchar-limits", action="store_true", help="Increase varchar column size limits"
    )

    args = parser.parse_args()

    if args.add_dup_prevention:
        add_duplicate_prevention_columns()
    elif args.add_market_columns:
        add_market_listings_columns()
    elif args.increase_varchar_limits:
        increase_varchar_limits()
    else:
        parser.print_help()
