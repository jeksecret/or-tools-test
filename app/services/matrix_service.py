# Focused only on fetching distances/times
# using Google Maps Routes API.
import os, json, hashlib
from typing import List, Dict, Tuple, Optional, Iterable
import requests
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

MAX_BLOCK = 100
_cache: Dict[str, Dict] = {}

def _get_key() -> str:
    k = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not k:
        raise HTTPException(status_code=500, detail="GOOGLE_MAPS_API_KEY not set")
    return k

def _cache_key(coords: List[Tuple[float, float]],
               departure_time: Optional[str],
               routing_pref: str) -> str:
    sig = {"coords": [(round(a, 6), round(b, 6)) for a, b in coords],
           "dep": departure_time, "pref": routing_pref}
    return hashlib.sha256(json.dumps(sig, sort_keys=True).encode()).hexdigest()

def geocode(address: str) -> Tuple[float, float]:
    key = _get_key()
    r = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": address, "key": key, "language": "ja", "region": "JP"},
        timeout=20,
    )
    r.raise_for_status()
    j = r.json()
    if j.get("status") != "OK" or not j.get("results"):
        raise HTTPException(status_code=400, detail=f"Geocode failed: {address} → {j.get('status')}")
    loc = j["results"][0]["geometry"]["location"]
    return float(loc["lat"]), float(loc["lng"])

def _parse_route_matrix_text(txt: str) -> Iterable[dict]:
    """
    Accept both:
      1) Full JSON array:   [ {..}, {..} ]
      2) NDJSON stream:     {..}\n{..}\n
    Also tolerates bracket/commas on separate lines.
    """
    s = txt.strip()
    if not s:
        return []
    # Full JSON array
    if s.startswith('['):
        data = json.loads(s)
        # Some error payloads are arrays with one {error:...}
        if isinstance(data, list) and len(data) and isinstance(data[0], dict) and "error" in data[0]:
            raise HTTPException(status_code=502, detail=s[:400])
        return data
    # NDJSON fallback
    out = []
    for line in s.splitlines():
        t = line.strip()
        if not t or t in ('[', ']', ','):
            continue
        if t.startswith(")]}'"):
            continue  # XSSI guard
        if t.endswith(','):
            t = t[:-1]
        if t.startswith('{"error"'):
            raise HTTPException(status_code=502, detail=t[:400])
        try:
            out.append(json.loads(t))
        except json.JSONDecodeError:
            raise HTTPException(status_code=502, detail=f"Bad JSON line from Routes API: {t[:160]}")
    return out

def _compute_block(origins: List[Tuple[float, float]],
                destinations: List[Tuple[float, float]],
                departure_time_iso: Optional[str],
                routing_pref: str) -> Tuple[List[List[int]], List[List[int]]]:
    url = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _get_key(),
        "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,condition",
    }
    body = {
        "origins": [{"waypoint": {"location": {"latLng": {"latitude": o[0], "longitude": o[1]}}}} for o in origins],
        "destinations": [{"waypoint": {"location": {"latLng": {"latitude": d[0], "longitude": d[1]}}}} for d in destinations],
        "travelMode": "DRIVE",
        "routingPreference": routing_pref,
    }
    if departure_time_iso:
        body["departureTime"] = departure_time_iso

    minutes = [[None] * len(destinations) for _ in range(len(origins))]
    meters  = [[None] * len(destinations) for _ in range(len(origins))]

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=90)
        resp.raise_for_status()
    except requests.HTTPError as e:
        txt = e.response.text if getattr(e, "response", None) is not None else str(e)
        raise HTTPException(status_code=502, detail=f"Routes API HTTP {getattr(e.response,'status_code',None)}: {txt[:400]}")

    for obj in _parse_route_matrix_text(resp.text):
        oi, di = obj["originIndex"], obj["destinationIndex"]
        cond = obj.get("condition", "ROUTE_EXISTS")
        if cond == "ROUTE_EXISTS" and "duration" in obj and "distanceMeters" in obj:
            secs = float(obj["duration"].rstrip("s"))
            minutes[oi][di] = int(round(secs / 60))
            meters[oi][di]  = int(obj["distanceMeters"])
        else:
            minutes[oi][di] = 10**6
            meters[oi][di]  = 10**9

    # Fill any None
    for i in range(len(minutes)):
        for j in range(len(minutes[i])):
            if minutes[i][j] is None: minutes[i][j] = 10**6
            if meters[i][j]  is None: meters[i][j]  = 10**9
    return minutes, meters

def _chunks(lst: List, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def build_matrix(points: List[Dict],  # [{id, lat?, lng?, address?}, ...]
                departure_time: Optional[str],
                routing_preference: str = "TRAFFIC_AWARE",
                require_coords: bool = False) -> Dict:
    ids: List[str] = []
    coords: List[Tuple[float, float]] = []
    for p in points:
        pid = str(p["id"]); ids.append(pid)
        if p.get("lat") is not None and p.get("lng") is not None:
            coords.append((float(p["lat"]), float(p["lng"])))
        elif require_coords:
            raise HTTPException(status_code=400, detail=f"Point {pid} missing lat/lng (geocoding disabled)")
        elif p.get("address"):
            coords.append(geocode(str(p["address"])))
        else:
            raise HTTPException(status_code=400, detail=f"Point {pid} missing both (lat,lng) and address")

    key = _cache_key(coords, departure_time, routing_preference)
    if key in _cache:
        return _cache[key]

    N = len(coords)
    minutes = [[0]*N for _ in range(N)]
    meters  = [[0]*N for _ in range(N)]

    for oi, o_block in enumerate(_chunks(coords, MAX_BLOCK)):
        for di, d_block in enumerate(_chunks(coords, MAX_BLOCK)):
            m_blk, d_blk = _compute_block(o_block, d_block, departure_time, routing_preference)
            base_i, base_j = oi*MAX_BLOCK, di*MAX_BLOCK
            for i in range(len(o_block)):
                for j in range(len(d_block)):
                    minutes[base_i + i][base_j + j] = m_blk[i][j]
                    meters[base_i + i][base_j + j]  = d_blk[i][j]

    res = {"ids": ids, "minutes": minutes, "meters": meters}
    _cache[key] = res
    return res
