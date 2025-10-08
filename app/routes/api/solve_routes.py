from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Tuple, Optional
from app.services.matrix_service import build_matrix
from app.services.routing_service import solve_routes

router = APIRouter()

# --- Request Schema ---
class Point(BaseModel):
    id: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = None

class SolveRoutesRequest(BaseModel):
    points: List[Point]
    pickup_drop_pairs: List[Tuple[int, int]]   # index pairs relative to `points`
    vehicle_count: Optional[int] = 2
    vehicle_capacity: Optional[int] = 2
    departure_time: Optional[str] = None
    routing_preference: Optional[str] = "TRAFFIC_AWARE"

# --- Route Definition ---
@router.post("/api/solve-routes")
def solve_routes_endpoint(req: SolveRoutesRequest):
    try:
        # Step 1. Build matrix via Google Routes API
        matrix = build_matrix(
            points=[p.model_dump() for p in req.points],
            departure_time=req.departure_time,
            routing_preference=req.routing_preference,
        )

        # Step 2. Solve using OR-Tools
        result = solve_routes(
            ids=matrix["ids"],
            minutes=matrix["minutes"],
            pickup_drop_pairs=req.pickup_drop_pairs,
            vehicle_count=req.vehicle_count,
            vehicle_capacity=req.vehicle_capacity,
        )
        return {"status": "ok", **result}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
