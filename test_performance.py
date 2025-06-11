"""
Performance test script for value estimation optimization
"""

import time
from concurrent_estimator import ConcurrentValueEstimator, EstimationTask
from firearm_values import estimate_value
from cache_manager import get_market_cache


def test_sequential_vs_concurrent():
    """Test sequential vs concurrent processing performance"""

    # Sample firearms for testing
    test_firearms = [
        ("GLOCK", "19", "9MM"),
        ("SMITH & WESSON", "M&P Shield", "9MM"),
        ("RUGER", "10/22", "22 LR"),
        ("SIG SAUER", "P365", "9MM"),
        ("COLT", "Python", "357 MAG"),
        ("REMINGTON", "700", "308 WIN"),
        ("MOSSBERG", "500", "12 GAUGE"),
        ("SPRINGFIELD", "XD", "9MM"),
        ("BERETTA", "92FS", "9MM"),
        ("HK", "VP9", "9MM"),
    ]

    print("Performance Test: Sequential vs Concurrent Processing")
    print("=" * 60)

    # Test 1: Sequential processing without online sources
    print("\n1. Sequential processing (no online sources)")
    start_time = time.time()
    for manufacturer, model, caliber in test_firearms:
        result = estimate_value(manufacturer, model, caliber, use_online_sources=False)
    sequential_time_offline = time.time() - start_time
    print(f"   Time: {sequential_time_offline:.2f}s for {len(test_firearms)} firearms")
    print(f"   Avg: {sequential_time_offline / len(test_firearms):.2f}s per firearm")

    # Test 2: Sequential processing with online sources (limited to 3 items)
    print("\n2. Sequential processing (with online sources) - 3 items")
    limited_firearms = test_firearms[:3]
    start_time = time.time()
    for manufacturer, model, caliber in limited_firearms:
        result = estimate_value(manufacturer, model, caliber, use_online_sources=True)
    sequential_time_online = time.time() - start_time
    print(f"   Time: {sequential_time_online:.2f}s for {len(limited_firearms)} firearms")
    print(f"   Avg: {sequential_time_online / len(limited_firearms):.2f}s per firearm")

    # Test 3: Concurrent processing with online sources
    print("\n3. Concurrent processing (with online sources) - 3 items")
    tasks = [
        EstimationTask(i, manufacturer, model, caliber, use_online_sources=True)
        for i, (manufacturer, model, caliber) in enumerate(limited_firearms)
    ]

    estimator = ConcurrentValueEstimator(max_workers=2, rate_limit_delay=0.3)
    start_time = time.time()
    results = estimator.estimate_values_batch(tasks)
    concurrent_time_online = time.time() - start_time

    successful_results = [r for r in results if r.success]
    print(f"   Time: {concurrent_time_online:.2f}s for {len(limited_firearms)} firearms")
    print(f"   Avg: {concurrent_time_online / len(limited_firearms):.2f}s per firearm")
    print(f"   Success rate: {len(successful_results)}/{len(results)}")

    # Calculate speedup
    if sequential_time_online > 0:
        speedup = sequential_time_online / concurrent_time_online
        print(f"   Speedup: {speedup:.1f}x faster than sequential")

    # Test 4: Cache effectiveness test
    print("\n4. Cache effectiveness test")
    cache = get_market_cache()
    cache_stats_before = cache.get_cache_stats()

    # First run (should populate cache)
    start_time = time.time()
    for manufacturer, model, caliber in limited_firearms[:2]:
        result = estimate_value(manufacturer, model, caliber, use_online_sources=True)
    first_run_time = time.time() - start_time

    cache_stats_after_first = cache.get_cache_stats()

    # Second run (should use cache)
    start_time = time.time()
    for manufacturer, model, caliber in limited_firearms[:2]:
        result = estimate_value(manufacturer, model, caliber, use_online_sources=True)
    second_run_time = time.time() - start_time

    cache_stats_after_second = cache.get_cache_stats()

    print(f"   First run (populate cache): {first_run_time:.2f}s")
    print(f"   Second run (use cache): {second_run_time:.2f}s")
    if first_run_time > 0:
        cache_speedup = first_run_time / second_run_time if second_run_time > 0 else float("inf")
        print(f"   Cache speedup: {cache_speedup:.1f}x faster")

    print(
        f"   Cache entries: {cache_stats_after_second['memory_entries']} in memory, {cache_stats_after_second['file_entries']} on disk"
    )

    print("\n" + "=" * 60)
    print("Summary:")
    print(
        f"  • Sequential (offline): {sequential_time_offline / len(test_firearms):.2f}s per firearm"
    )
    print(
        f"  • Sequential (online):  {sequential_time_online / len(limited_firearms):.2f}s per firearm"
    )
    print(
        f"  • Concurrent (online):  {concurrent_time_online / len(limited_firearms):.2f}s per firearm"
    )
    if sequential_time_online > 0 and concurrent_time_online > 0:
        print(f"  • Concurrent speedup:   {sequential_time_online / concurrent_time_online:.1f}x")
    if first_run_time > 0 and second_run_time > 0:
        print(f"  • Cache speedup:        {first_run_time / second_run_time:.1f}x")


def test_cache_performance():
    """Test cache hit rates and performance"""
    print("\nCache Performance Test")
    print("=" * 30)

    cache = get_market_cache()

    # Clear cache for clean test
    cache.clear_expired()

    test_queries = [
        ("GLOCK", "19", "9MM"),
        ("GLOCK", "17", "9MM"),  # Similar to above, might benefit from cache
        ("GLOCK", "19", "9MM"),  # Exact repeat
    ]

    for i, (manufacturer, model, caliber) in enumerate(test_queries, 1):
        print(f"\nQuery {i}: {manufacturer} {model} {caliber}")

        # Check if in cache
        cached_result = cache.get(manufacturer, model, caliber)
        cache_hit = cached_result is not None
        print(f"  Cache hit: {'Yes' if cache_hit else 'No'}")

        # Time the estimation
        start_time = time.time()
        result = estimate_value(manufacturer, model, caliber, use_online_sources=True)
        processing_time = time.time() - start_time

        print(f"  Processing time: {processing_time:.2f}s")
        print(
            f"  Estimated value: ${result['estimated_value']:.2f}"
            if result["estimated_value"]
            else "No estimate"
        )

    # Show final cache stats
    final_stats = cache.get_cache_stats()
    print(f"\nFinal cache stats:")
    print(f"  Memory entries: {final_stats['memory_entries']}")
    print(f"  File entries: {final_stats['file_entries']}")


if __name__ == "__main__":
    try:
        test_sequential_vs_concurrent()
        test_cache_performance()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback

        traceback.print_exc()
