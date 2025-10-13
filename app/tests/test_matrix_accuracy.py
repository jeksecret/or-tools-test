"""
Matrix Accuracy & Behavior Tests for Google Routes API
------------------------------------------------------

This script tests:
1. TRAFFIC_AWARE vs TRAFFIC_UNAWARE
2. Departure time sensitivity
3. No-route edge cases
4. Precision stability
5. Large matrix handling
6. Error & caching behavior

Usage:
    $ python -m app.tests.test_matrix_accuracy
"""

import json, time
from datetime import datetime, timedelta, timezone
from app.services.matrix_service import build_matrix

def future_iso(minutes_ahead=10):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes_ahead)).isoformat().replace("+00:00", "Z")


# ----------------------------
# Define sample points
# ----------------------------
TOKYO_TEST_POINTS = [
    {"id": "DEPOT", "address": "東京都千代田区丸の内1-9-1"},     # Tokyo Station
    {"id": "R001_P", "address": "東京都渋谷区道玄坂2-24-1"},     # Shibuya
    {"id": "R001_D", "address": "東京都新宿区西新宿2-8-1"},      # Shinjuku
]

REMOTE_TEST_POINTS = [
    {"id": "DEPOT", "address": "東京都港区芝公園4-2-8"},          # Tokyo Tower
    {"id": "REMOTE", "address": "北海道札幌市中央区北3条西4丁目"}  # Sapporo (should be unreachable)
]

# ----------------------------
# 🧪 Helper for pretty printing
# ----------------------------
def print_matrix(title, matrix):
    print(f"\n--- {title} ---")
    print("IDs:", matrix["ids"])
    for row in matrix["minutes"]:
        print(row)

# ----------------------------
# TEST 1: TRAFFIC_AWARE vs TRAFFIC_UNAWARE
# ----------------------------
def test_traffic_modes():
    print("\n[TEST 1] TRAFFIC_AWARE vs TRAFFIC_UNAWARE")
    matrix_aware = build_matrix(
        TOKYO_TEST_POINTS,
        departure_time=future_iso(10),
        routing_preference="TRAFFIC_AWARE"
    )
    matrix_unaware = build_matrix(
        TOKYO_TEST_POINTS,
        departure_time=None,
        routing_preference="TRAFFIC_UNAWARE"
    )
    print_matrix("TRAFFIC_AWARE (08:00)", matrix_aware)
    print_matrix("TRAFFIC_UNAWARE (08:00)", matrix_unaware)

# ----------------------------
# TEST 2: Departure time sensitivity
# ----------------------------
def test_departure_time():
    print("\n[TEST 2] Departure Time Sensitivity")
    matrix_morning = build_matrix(
        TOKYO_TEST_POINTS,
        departure_time=future_iso(10),
        routing_preference="TRAFFIC_AWARE"
    )
    matrix_night = build_matrix(
        TOKYO_TEST_POINTS,
        departure_time=future_iso(600),
        routing_preference="TRAFFIC_AWARE"
    )
    print_matrix("Morning (08:00)", matrix_morning)
    print_matrix("Night (23:00)", matrix_night)

# ----------------------------
# TEST 3: No-route edge case
# ----------------------------
def test_no_route_case():
    print("\n[TEST 3] No-Route Edge Case (Tokyo → Sapporo)")
    matrix_remote = build_matrix(
        REMOTE_TEST_POINTS,
        departure_time=None,
        routing_preference="TRAFFIC_UNAWARE"
    )
    print_matrix("No-route test", matrix_remote)

# ----------------------------
# TEST 4: Precision Stability
# ----------------------------
def test_precision_stability():
    print("\n[TEST 4] Precision Stability")
    start = time.perf_counter()
    m1 = build_matrix(TOKYO_TEST_POINTS, future_iso(10), "TRAFFIC_AWARE")
    m2 = build_matrix(TOKYO_TEST_POINTS, future_iso(10), "TRAFFIC_AWARE")
    elapsed = time.perf_counter() - start
    print(f"Runtime (should be fast on 2nd call due to cache): {elapsed:.2f}s")
    print("Matrix 1 == Matrix 2?", m1["minutes"] == m2["minutes"])

# ----------------------------
# TEST 5: Large Matrix Handling
# ----------------------------
def test_large_matrix():
    print("\n[TEST 5] Large Matrix Handling (Performance Stress Test)")
    points = []
    base_lat, base_lng = 35.68, 139.76
    for i in range(15):  # 15 points (small but can scale to 100+)
        points.append({"id": f"P{i}", "lat": base_lat + i*0.01, "lng": base_lng + i*0.01})
    start = time.perf_counter()
    m = build_matrix(points, None, "TRAFFIC_UNAWARE")
    elapsed = time.perf_counter() - start
    print(f"Matrix {len(points)}x{len(points)} built in {elapsed:.1f}s")

# ----------------------------
# TEST 6: Error & Cache Behavior
# ----------------------------
def test_error_and_cache():
    print("\n[TEST 6] Error & Cache Behavior")
    try:
        build_matrix([], future_iso(10))
    except Exception as e:
        print("Empty list test:", str(e)[:100])
    print("Reusing same key (cache hit):")
    m = build_matrix(TOKYO_TEST_POINTS, future_iso(10))
    m2 = build_matrix(TOKYO_TEST_POINTS, future_iso(10))
    print("Cache reused?", id(m) == id(m2))

# ----------------------------
# Run All Tests
# ----------------------------
if __name__ == "__main__":
    print("=== Google Routes API Matrix Accuracy Tests ===")
    test_traffic_modes()
    test_departure_time()
    test_no_route_case()
    test_precision_stability()
    test_large_matrix()
    test_error_and_cache()
    print("\n✅ All matrix accuracy tests completed.\n")
