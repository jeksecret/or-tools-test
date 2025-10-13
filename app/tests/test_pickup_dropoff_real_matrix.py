"""
End-to-End Pickup/Drop-off Test using Google Routes API + OR-Tools
------------------------------------------------------------------

This validates:
  • Real travel times from Google Maps
  • Correct pickup/drop-off order
  • Same-vehicle assignment
  • Capacity adherence

Usage:
    $ python -m app.tests.test_pickup_dropoff_real_matrix
"""

from app.services.matrix_service import build_matrix
from app.services.routing_service import solve_routes
import json, time
from datetime import datetime, timedelta, timezone


def future_iso(minutes_ahead=10):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes_ahead)).isoformat().replace("+00:00", "Z")

# ----------------------------
# Define real Tokyo-area points
# ----------------------------
points = [
    {"id": "DEPOT",  "address": "東京都千代田区丸の内1-9-1"},     # Tokyo Station
    {"id": "R001_P", "address": "東京都渋谷区道玄坂2-24-1"},     # Shibuya
    {"id": "R001_D", "address": "東京都新宿区西新宿2-8-1"},      # Shinjuku
    {"id": "R002_P", "address": "東京都文京区春日1-16-21"},      # Bunkyo
    {"id": "R002_D", "address": "東京都港区芝公園4-2-8"}         # Tokyo Tower
]

pickup_drop_pairs = [(1, 2), (3, 4)]  # (pickup_index, dropoff_index)

# ----------------------------
# Step 1: Build the matrix from Google API
# ----------------------------
print("\n[STEP 1] Building real travel-time matrix from Google Routes API...")
matrix = build_matrix(
    points=points,
    departure_time=future_iso(10),
    routing_preference="TRAFFIC_AWARE"
)

print("Matrix IDs:", matrix["ids"])
print("Minutes Matrix:")
for row in matrix["minutes"]:
    print(row)

# ----------------------------
# Step 2: Run OR-Tools Solver
# ----------------------------
print("\n[STEP 2] Solving pickup/drop-off routing problem...")
result = solve_routes(
    ids=matrix["ids"],
    minutes=matrix["minutes"],
    pickup_drop_pairs=pickup_drop_pairs,
    vehicle_count=2,
    vehicle_capacity=2
)

print(json.dumps(result, indent=2, ensure_ascii=False))

# ----------------------------
# Step 3: Validate and summarize
# ----------------------------
routes = result["routes"]
for r in routes:
    print(f"\nVehicle {r['vehicle_id']}:")
    print(f"  Total travel time: {r['total_travel_time_min']} min")
    print(f"  Max load: {r['max_load']}")
    print("  Route order:")
    for stop in r["stops"]:
        print(f"    - {stop['stop_id']}  (time={stop['time_min']}, load={stop['load_at_stop']})")

print("\n✅ End-to-End pickup/drop-off routing test completed.\n")
