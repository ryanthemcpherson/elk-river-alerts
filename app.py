import streamlit as st
from main import scrape_used_guns

def main():
    st.set_page_config(page_title="Elk River Used Guns Inventory", layout="wide")
    
    # Add a title
    st.title("Elk River Used Guns Inventory")
    
    # Show loading message while fetching data
    with st.spinner("Fetching latest inventory..."):
        # Fetch data and normalize section types
        listings = scrape_used_guns()
        
    # Process listings to extract section types
    for l in listings:
        # First word of the section is typically the type
        if hasattr(l, 'section') and l.section:
            l.section_type = l.section.split()[0] if ' ' in l.section else l.section
        else:
            l.section_type = "Unknown"
    
    # Get unique section types for the dropdown
    section_types = sorted(set(l.section_type for l in listings))
    
    # Add "All" option
    options = ["All"] + section_types
    
    # Create a dropdown for filtering
    selected_section = st.selectbox("Select Firearm Type:", options)
    
    # Filter listings based on selected section
    if selected_section == "All":
        filtered_listings = listings
    else:
        filtered_listings = [l for l in listings if l.section_type == selected_section]
    
    # Show count of results
    st.write(f"Showing {len(filtered_listings)} listings" + 
             (f" for {selected_section}" if selected_section != "All" else ""))
    
    # Convert to a format suitable for DataFrame
    data = []
    for l in filtered_listings:
        data.append({
            "Type": l.section_type,
            "Manufacturer": l.manufacturer,
            "Model": l.model,
            "Caliber/Gauge": l.caliber,
            "Price": f"${l.price:,.2f}",
            "Description": l.description
        })
    
    # Display as a table
    if data:
        st.dataframe(data, use_container_width=True, hide_index=True)
    else:
        st.info("No listings found for the selected criteria.")

if __name__ == "__main__":
    main() 