import argparse

from firearm_values import estimate_value, get_market_listings, search_armslist


def main():
    parser = argparse.ArgumentParser(description="Test the Armslist search functionality")
    parser.add_argument("--manufacturer", type=str, help="Firearm manufacturer", default="TAURUS")
    parser.add_argument("--model", type=str, help="Firearm model", default="PT22")
    parser.add_argument("--caliber", type=str, help="Firearm caliber", default="22 LR")
    parser.add_argument("--location", type=str, help="Search location", default="usa")
    parser.add_argument("--compare", action="store_true", help="Compare with algorithm estimate")
    args = parser.parse_args()

    print(f"\nSearching Armslist for: {args.manufacturer} {args.model} {args.caliber}")
    print("-" * 60)

    # Test the direct search function
    listings = search_armslist(args.manufacturer, args.model, args.caliber, args.location)

    if not listings:
        print("No listings found on Armslist.")
        return

    print(f"\nFound {len(listings)} listings:")
    print("-" * 60)

    # Display each listing
    for i, listing in enumerate(listings, 1):
        print(f"\n{i}. {listing.get('title', 'No Title')}")
        print(f"   Price: {listing.get('price_text', 'Price not listed')}")
        print(f"   Location: {listing.get('location', 'Location not specified')}")
        print(f"   Ships: {'Yes' if listing.get('ships', False) else 'No'}")
        print(f"   Link: {listing.get('link', '#')}")

    # Test the market listings function
    print("\n\nTesting market listings aggregation:")
    print("-" * 60)

    market_listings = get_market_listings(args.manufacturer, args.model, args.caliber)

    if market_listings:
        prices = [l.get("price") for l in market_listings if l.get("price") is not None]
        if prices:
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)

            print(f"Average Price: ${avg_price:.2f}")
            print(f"Price Range: ${min_price:.2f} - ${max_price:.2f}")
            print(f"Number of Listings with Prices: {len(prices)}")

    # Compare with algorithm estimate if requested
    if args.compare:
        print("\n\nComparing with algorithm estimate:")
        print("-" * 60)

        # Get estimate without online sources
        algo_estimate = estimate_value(
            args.manufacturer, args.model, args.caliber, use_online_sources=False
        )

        print(f"Algorithm Estimate: ${algo_estimate['estimated_value']:.2f}")
        if algo_estimate["value_range"]:
            print(
                f"Algorithm Range: ${algo_estimate['value_range'][0]:.2f} - ${algo_estimate['value_range'][1]:.2f}"
            )
        print(f"Source: {algo_estimate['source']}")
        print(f"Confidence: {algo_estimate['confidence']}")

        # Get blended estimate with online sources
        print("\nBlended estimate with online sources:")
        blended_estimate = estimate_value(
            args.manufacturer, args.model, args.caliber, use_online_sources=True
        )

        print(f"Blended Estimate: ${blended_estimate['estimated_value']:.2f}")
        if blended_estimate["value_range"]:
            print(
                f"Blended Range: ${blended_estimate['value_range'][0]:.2f} - ${blended_estimate['value_range'][1]:.2f}"
            )
        print(f"Source: {blended_estimate['source']}")
        print(f"Confidence: {blended_estimate['confidence']}")
        print(f"Sample Size: {blended_estimate['sample_size']}")


if __name__ == "__main__":
    main()
