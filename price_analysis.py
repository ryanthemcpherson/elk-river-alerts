import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client

def get_connection(url, key):
    """Create a Supabase client connection"""
    return create_client(url, key)

def get_historical_data(supabase, days=30):
    """
    Get historical firearm listings from the past X days
    Returns a pandas DataFrame with the data
    """
    # Calculate the date X days ago
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Query the database for listings after the cutoff date
    # Include both current and historical listings
    result = supabase.table('firearm_listings').select('*').gte('date_scraped', cutoff_date).execute()
    
    # Convert to DataFrame
    if result.data:
        return pd.DataFrame(result.data)
    return pd.DataFrame()

def get_historical_price_trends(supabase, manufacturer=None, model=None, days=90):
    """
    Get price trends for a specific firearm over time
    Returns a dictionary with trend data
    """
    # Calculate the date X days ago
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Build the query
    query = supabase.table('firearm_listings').select('*').gte('date_scraped', cutoff_date)
    
    # Add filters if specified
    if manufacturer:
        query = query.eq('manufacturer', manufacturer)
    if model:
        query = query.eq('model', model)
    
    # Execute the query
    result = query.execute()
    
    if not result.data:
        return None
    
    # Convert to DataFrame and sort by date
    df = pd.DataFrame(result.data)
    df['date_scraped'] = pd.to_datetime(df['date_scraped'])
    df = df.sort_values('date_scraped')
    
    # Group by date and calculate average prices
    df['date'] = df['date_scraped'].dt.date
    price_trends = df.groupby('date').agg({
        'list_price': 'mean',
        'estimated_value': 'mean',
        'price_difference_percent': 'mean'
    }).reset_index()
    
    return {
        'dates': price_trends['date'].tolist(),
        'list_prices': price_trends['list_price'].tolist(),
        'est_values': price_trends['estimated_value'].tolist(),
        'price_diff_pct': price_trends['price_difference_percent'].tolist()
    }

def analyze_price_trends(df):
    """
    Analyze price trends in the data
    Returns a dictionary of trend analysis results
    """
    if df.empty:
        return None
    
    # Calculate basic statistics
    results = {
        "total_listings": len(df),
        "avg_list_price": df['list_price'].mean(),
        "median_list_price": df['list_price'].median(),
        "min_price": df['list_price'].min(),
        "max_price": df['list_price'].max()
    }
    
    # Calculate value statistics if we have estimates
    if 'estimated_value' in df.columns and not df['estimated_value'].isna().all():
        results.update({
            "avg_estimated_value": df['estimated_value'].mean(),
            "median_estimated_value": df['estimated_value'].median(),
            "avg_price_difference": df['price_difference'].mean(),
            "median_price_difference": df['price_difference'].median(),
            "avg_price_difference_percent": df['price_difference_percent'].mean()
        })
    
    # Percentage of listings above/below market value
    if 'price_difference' in df.columns:
        below_market = df[df['price_difference'] < 0]
        above_market = df[df['price_difference'] > 0]
        at_market = df[df['price_difference'] == 0]
        
        results.update({
            "percent_below_market": len(below_market) / len(df) * 100 if len(df) > 0 else 0,
            "percent_above_market": len(above_market) / len(df) * 100 if len(df) > 0 else 0,
            "percent_at_market": len(at_market) / len(df) * 100 if len(df) > 0 else 0,
            "avg_savings_pct": below_market['price_difference_percent'].mean() * -1 if len(below_market) > 0 else 0,
            "avg_premium_pct": above_market['price_difference_percent'].mean() if len(above_market) > 0 else 0
        })
    
    return results

def get_top_deals(df, limit=5):
    """
    Get the top deals (firearms with biggest price difference below market value)
    Returns a DataFrame sorted by best deals first
    """
    if df.empty or 'price_difference_percent' not in df.columns:
        return pd.DataFrame()
    
    # Filter to only get deals (negative price difference = below market)
    deals = df[df['price_difference'] < 0].copy()
    
    if deals.empty:
        return pd.DataFrame()
    
    # Sort by price difference percentage (ascending = better deals first)
    deals = deals.sort_values('price_difference_percent', ascending=True)
    
    # Take top N deals
    return deals.head(limit)

def get_type_distribution(df):
    """
    Get distribution of firearms by type
    Returns a dictionary with counts by type
    """
    if df.empty or 'section' not in df.columns:
        return {}
    
    # Extract section types
    if 'section_type' not in df.columns:
        df['section_type'] = df['section'].apply(lambda x: x.split()[0] if ' ' in x else x)
    
    # Get counts by type
    type_counts = df['section_type'].value_counts().to_dict()
    
    # Calculate percentages
    total = sum(type_counts.values())
    type_percentages = {k: (v / total * 100) for k, v in type_counts.items()}
    
    return {
        "counts": type_counts,
        "percentages": type_percentages
    }

def get_caliber_distribution(df):
    """
    Get distribution of firearms by caliber
    Returns a dictionary with the most common calibers
    """
    if df.empty or 'caliber' not in df.columns:
        return {}
    
    # Get counts by caliber
    caliber_counts = df['caliber'].value_counts().to_dict()
    
    # Calculate percentages
    total = sum(caliber_counts.values())
    caliber_percentages = {k: (v / total * 100) for k, v in caliber_counts.items()}
    
    return {
        "counts": caliber_counts,
        "percentages": caliber_percentages
    }

def generate_price_report(df):
    """
    Generate a comprehensive price analysis report
    Returns a dictionary with all analysis results
    """
    if df.empty:
        return {"error": "No data available for analysis"}
    
    report = {
        "general_stats": analyze_price_trends(df),
        "top_deals": get_top_deals(df, limit=5),
        "type_distribution": get_type_distribution(df),
        "caliber_distribution": get_caliber_distribution(df)
    }
    
    return report 