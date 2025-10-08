from typing import List, Dict, Tuple
from fastapi import HTTPException
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

def solve_routes(
    ids: List[str],
    minutes: List[List[int]],
    pickup_drop_pairs: List[Tuple[int, int]],
    vehicle_count: int = 2,
    vehicle_capacity: int = 2,
    depot_index: int = 0,
) -> Dict:
    """Solve pickup/drop-off VRP with capacity + time dimensions and return route summaries."""

    manager = pywrapcp.RoutingIndexManager(len(ids), vehicle_count, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    # --- Transit callback (time cost) ---
    def time_callback(from_index, to_index):
        return minutes[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit_cb_idx = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    # --- Time dimension ---
    routing.AddDimension(
        transit_cb_idx,
        30,       # slack (waiting)
        1440,     # max route horizon
        True,     # start cumul = 0
        "Time"
    )
    time_dim = routing.GetDimensionOrDie("Time")

    # --- Capacity dimension ---
    def demand_callback(from_index):
        node = manager.IndexToNode(from_index)
        for (p, d) in pickup_drop_pairs:
            if node == p:
                return 1
            if node == d:
                return -1
        return 0

    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb_idx,
        0,
        [vehicle_capacity] * vehicle_count,
        True,
        "Capacity"
    )
    cap_dim = routing.GetDimensionOrDie("Capacity")

    # --- Pickup & Delivery constraints ---
    for (p, d) in pickup_drop_pairs:
        p_i, d_i = manager.NodeToIndex(p), manager.NodeToIndex(d)
        routing.AddPickupAndDelivery(p_i, d_i)
        routing.solver().Add(routing.VehicleVar(p_i) == routing.VehicleVar(d_i))
        routing.solver().Add(time_dim.CumulVar(p_i) <= time_dim.CumulVar(d_i))

    # --- Search parameters ---
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = 10

    # --- Solve ---
    solution = routing.SolveWithParameters(search_params)
    if not solution:
        raise HTTPException(status_code=500, detail="No feasible route found")

    # --- Extract detailed routes ---
    routes = []
    for v in range(vehicle_count):
        index = routing.Start(v)
        vehicle_route = []
        max_load = 0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            stop_id = ids[node]
            load = solution.Value(cap_dim.CumulVar(index))
            max_load = max(max_load, load)
            vehicle_route.append({
                "stop_id": stop_id,
                "load_at_stop": load,
                "time_min": solution.Value(time_dim.CumulVar(index))
            })
            index = solution.Value(routing.NextVar(index))

        # end node (return to depot)
        end_node = manager.IndexToNode(index)
        vehicle_route.append({
            "stop_id": ids[end_node],
            "load_at_stop": solution.Value(cap_dim.CumulVar(index)),
            "time_min": solution.Value(time_dim.CumulVar(index))
        })

        total_time = vehicle_route[-1]["time_min"]  # final cumulative time
        routes.append({
            "vehicle_id": v,
            "stops": vehicle_route,
            "total_travel_time_min": total_time,
            "max_load": max_load
        })

    return {"routes": routes}
