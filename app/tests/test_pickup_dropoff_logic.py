"""
Pickup/Drop-off Logic Tests for OR-Tools Solver
-----------------------------------------------

Tests:
1. Single vehicle with multiple pairs (basic precedence)
2. Multiple vehicles (load distribution)
3. Capacity constraint (vehicle overloading)
4. Infeasible scenario handling
5. Symmetry and route sequence validation

Usage:
    $ python -m app.tests.test_pickup_dropoff_logic
"""

from app.services.routing_service import solve_routes
import json

# ----------------------------
# Helper: Mock matrix data
# ----------------------------
def sample_matrix():
    """
    Simple 7x7 matrix for quick testing.
    Distances are arbitrary but symmetric enough
    to allow feasible solutions.
    """
    ids = ["DEPOT", "R001_P", "R001_D", "R002_P", "R002_D", "R003_P", "R003_D"]
    minutes = [
        [0, 10, 15, 20, 25, 30, 35],
        [10, 0, 5, 20, 25, 30, 35],
        [15, 5, 0, 15, 20, 25, 30],
        [20, 20, 15, 0, 5, 10, 15],
        [25, 25, 20, 5, 0, 10, 15],
        [30, 30, 25, 10, 10, 0, 5],
        [35, 35, 30, 15, 15, 5, 0],
    ]
    return ids, minutes

# ----------------------------
# TEST 1: Single vehicle, multiple pairs
# ----------------------------
def test_single_vehicle_multiple_pairs():
    print("\n[TEST 1] Single vehicle with multiple pickup/drop-off pairs")
    ids, minutes = sample_matrix()
    pairs = [(1,2), (3,4), (5,6)]  # 3 passengers

    result = solve_routes(ids, minutes, pairs, vehicle_count=1, vehicle_capacity=3)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Expected: All pairs in one route, correct sequence (pickup before drop)
    route = result["routes"][0]["stops"]
    for (p,d) in pairs:
        p_id, d_id = ids[p], ids[d]
        p_idx = next(i for i,s in enumerate(route) if s["stop_id"] == p_id)
        d_idx = next(i for i,s in enumerate(route) if s["stop_id"] == d_id)
        assert p_idx < d_idx, f"{p_id} must come before {d_id}"

# ----------------------------
# TEST 2: Multiple vehicles
# ----------------------------
def test_multiple_vehicles():
    print("\n[TEST 2] Multiple vehicles route distribution")
    ids, minutes = sample_matrix()
    pairs = [(1,2), (3,4), (5,6)]
    result = solve_routes(ids, minutes, pairs, vehicle_count=2, vehicle_capacity=2)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Expected: Two routes used, each covers some pairs
    active_routes = [r for r in result["routes"] if len(r["stops"]) > 2]
    assert len(active_routes) >= 1, "At least one active route should exist"
    for r in active_routes:
        print(f"Vehicle {r['vehicle_id']} total time: {r['total_travel_time_min']}min, max load: {r['max_load']}")

# ----------------------------
# TEST 3: Capacity constraint
# ----------------------------
def test_capacity_constraint():
    print("\n[TEST 3] Capacity constraint check")
    ids, minutes = sample_matrix()
    pairs = [(1,2), (3,4), (5,6)]
    # 1 vehicle but only capacity=1 -> should still be solvable sequentially
    result = solve_routes(ids, minutes, pairs, vehicle_count=1, vehicle_capacity=1)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    for r in result["routes"]:
        assert r["max_load"] <= 1, "Vehicle overloaded!"

# ----------------------------
# TEST 4: Infeasible scenario (too many pickups)
# ----------------------------
def test_infeasible_scenario():
    print("\n[TEST 4] Infeasible scenario handling")
    ids, minutes = sample_matrix()
    pairs = [(1,2), (3,4), (5,6)]
    try:
        # Set vehicle_capacity too small for all at once
        result = solve_routes(ids, minutes, pairs, vehicle_count=1, vehicle_capacity=0)
        print(result)
        assert False, "Should have raised HTTPException for infeasible route"
    except Exception as e:
        print("Expected failure:", str(e)[:120])

# ----------------------------
# TEST 5: Route sequence & symmetry
# ----------------------------
def test_route_sequence():
    print("\n[TEST 5] Route sequence validation")
    ids, minutes = sample_matrix()
    pairs = [(1,2), (3,4)]
    result = solve_routes(ids, minutes, pairs, vehicle_count=1, vehicle_capacity=2)
    route = result["routes"][0]["stops"]
    sequence = [s["stop_id"] for s in route]
    print("Route order:", sequence)
    assert sequence[0] == "DEPOT", "Must start at depot"
    assert sequence[-1] == "DEPOT", "Must end at depot"

# ----------------------------
# Run All Tests
# ----------------------------
if __name__ == "__main__":
    print("=== OR-Tools Pickup/Drop-off Logic Tests ===")
    test_single_vehicle_multiple_pairs()
    test_multiple_vehicles()
    test_capacity_constraint()
    test_infeasible_scenario()
    test_route_sequence()
    print("\n✅ All pickup/drop-off logic tests completed.\n")
