import argparse
from firearm_values import estimate_value
import random

# Sample firearm database for testing
SAMPLE_FIREARMS = [
    {"manufacturer": "GLOCK", "model": "19", "caliber": "9MM"},
    {"manufacturer": "SMITH & WESSON", "model": "M&P Shield", "caliber": "9MM"},
    {"manufacturer": "RUGER", "model": "10/22", "caliber": "22 LR"},
    {"manufacturer": "SIG SAUER", "model": "P365", "caliber": "9MM"},
    {"manufacturer": "COLT", "model": "Python", "caliber": "357 MAG"},
    {"manufacturer": "REMINGTON", "model": "700", "caliber": "308 WIN"},
    {"manufacturer": "WINCHESTER", "model": "SXP", "caliber": "12 GAUGE"},
    {"manufacturer": "MOSSBERG", "model": "500", "caliber": "12 GAUGE"},
    {"manufacturer": "BERETTA", "model": "92FS", "caliber": "9MM"},
    {"manufacturer": "SAVAGE", "model": "Axis", "caliber": "30-06"},
    {"manufacturer": "SPRINGFIELD", "model": "1911", "caliber": "45 ACP"},
    {"manufacturer": "TAURUS", "model": "G3C", "caliber": "9MM"},
    {"manufacturer": "HENRY", "model": "Big Boy", "caliber": "45-70 GOVT"},
    {"manufacturer": "BROWNING", "model": "BPS", "caliber": "12 GAUGE"},
    {"manufacturer": "CZ", "model": "75", "caliber": "9MM"},
    {"manufacturer": "KIMBER", "model": "Micro 9", "caliber": "9MM"},
    {"manufacturer": "HK", "model": "VP9", "caliber": "9MM"},
    {"manufacturer": "TIKKA", "model": "T3X", "caliber": "6.5 CREEDMOOR"},
    {"manufacturer": "MARLIN", "model": "336", "caliber": "30-30 WIN"},
    {"manufacturer": "STOEGER", "model": "M3000", "caliber": "12 GAUGE"}
]

def main():
    parser = argparse.ArgumentParser(description="Test the firearm value estimation module")
    parser.add_argument("--manufacturer", type=str, help="Specific manufacturer to test")
    parser.add_argument("--model", type=str, help="Specific model to test")
    parser.add_argument("--caliber", type=str, help="Specific caliber to test")
    parser.add_argument("--limit", type=int, default=5, help="Number of firearms to test (default: 5)")
    args = parser.parse_args()
    
    # If specific firearm details provided, test just that one
    if args.manufacturer and args.model and args.caliber:
        print(f"\nTesting value estimation for: {args.manufacturer} {args.model} {args.caliber}")
        print("-" * 60)
        test_specific_firearm(args.manufacturer, args.model, args.caliber)
        return
    
    # Otherwise test a sample of firearms
    print(f"\nTesting firearm value estimation with {args.limit} sample firearms")
    print("-" * 60)
    
    # Get a random sample of firearms to test
    sample_size = min(args.limit, len(SAMPLE_FIREARMS))
    test_sample = random.sample(SAMPLE_FIREARMS, sample_size)
    
    for i, firearm in enumerate(test_sample, 1):
        print(f"\n{i}. Testing: {firearm['manufacturer']} {firearm['model']} {firearm['caliber']}")
        print("-" * 40)
        test_specific_firearm(
            firearm['manufacturer'], 
            firearm['model'], 
            firearm['caliber']
        )

def test_specific_firearm(manufacturer, model, caliber):
    """Test the value estimation for a specific firearm"""
    value_info = estimate_value(manufacturer, model, caliber)
    
    print(f"Manufacturer: {manufacturer}")
    print(f"Model: {model}")
    print(f"Caliber: {caliber}")
    print(f"Estimated Value: ${value_info['estimated_value']:.2f}" if value_info['estimated_value'] else "No estimate available")
    
    if value_info['value_range']:
        print(f"Value Range: ${value_info['value_range'][0]:.2f} - ${value_info['value_range'][1]:.2f}")
    
    print(f"Source: {value_info['source']}")
    print(f"Confidence: {value_info['confidence']}")
    
    return value_info

if __name__ == "__main__":
    main() 