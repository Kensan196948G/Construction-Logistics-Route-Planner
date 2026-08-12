"""Real road-network routing adapters (Phase 1 sprint).

The default deployment stays on the deterministic sample generator until
``ROUTING_PROVIDER=osrm`` is set. The OSRM adapter calls a configurable OSRM
server (default: public demo server, low-volume use only) and returns real
road-network candidates with geometry, distance, and duration.
"""

from __future__ import annotations

import logging
import os

from app.models import LocationInput, RouteCandidate, RouteType, new_id
from app.risk_engine import ROUTE_LABELS

logger = logging.getLogger(__name__)

OSRM_DEFAULT_URL = "https://router.project-osrm.org"
MAX_GEOMETRY_POINTS = 200


async def fetch_osrm_routes(
    project_id: str,
    start: LocationInput,
    destination: LocationInput,
    route_types: list[RouteType],
    *,
    url: str | None = None,
    timeout: float = 10.0,
) -> list[RouteCandidate] | None:
    """Fetch real route alternatives from an OSRM server.

    Returns ``None`` when the server is unreachable or returns no route so the
    caller can fall back to the sample generator without failing the request.
    """

    import httpx

    base = (url or os.getenv("OSRM_URL") or OSRM_DEFAULT_URL).rstrip("/")
    endpoint = (
        f"{base}/route/v1/driving/{start.lng:.6f},{start.lat:.6f};"
        f"{destination.lng:.6f},{destination.lat:.6f}"
    )
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        logger.exception("OSRM routing failed for %s -> %s", start.name, destination.name)
        return None

    alternatives = payload.get("routes") or []
    if not alternatives:
        logger.warning("OSRM returned no routes for %s -> %s", start.name, destination.name)
        return None

    candidates: list[RouteCandidate] = []
    for index, route_type in enumerate(route_types):
        alternative = alternatives[min(index, len(alternatives) - 1)]
        coordinates = alternative.get("geometry", {}).get("coordinates") or []
        if len(coordinates) < 2:
            continue
        step = max(1, len(coordinates) // MAX_GEOMETRY_POINTS)
        geometry = [
            LocationInput(
                name=f"route-point-{point_index}",
                lat=float(point[1]),
                lng=float(point[0]),
            )
            for point_index, point in enumerate(coordinates[::step])
        ]
        candidates.append(
            RouteCandidate(
                id=new_id("route"),
                project_id=project_id,
                route_type=route_type,
                name=ROUTE_LABELS[route_type],
                distance_km=round(float(alternative.get("distance", 0)) / 1000, 1),
                duration_min=max(1, round(float(alternative.get("duration", 0)) / 60)),
                geometry=geometry,
            )
        )
    return candidates or None
