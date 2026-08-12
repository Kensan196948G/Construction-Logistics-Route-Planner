from __future__ import annotations

import httpx
import pytest

from app.models import LocationInput, RouteType
from app.routing import fetch_osrm_routes

START = LocationInput(name="出発地", lat=35.681236, lng=139.767125)
DEST = LocationInput(name="到着地", lat=35.658581, lng=139.745433)


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "code": "Ok",
            "routes": [
                {
                    "distance": 12345.6,
                    "duration": 1800,
                    "geometry": {
                        "coordinates": [
                            [139.767125, 35.681236],
                            [139.760000, 35.670000],
                            [139.745433, 35.658581],
                        ]
                    },
                },
                {
                    "distance": 11000.0,
                    "duration": 1500,
                    "geometry": {
                        "coordinates": [
                            [139.767125, 35.681236],
                            [139.755000, 35.665000],
                            [139.745433, 35.658581],
                        ]
                    },
                },
            ],
        }


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        self._fail = kwargs.pop("fail", False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def get(self, *args, **kwargs):
        if self._fail:
            raise httpx.ConnectError("no route to host")
        return _FakeResponse()


@pytest.mark.asyncio
async def test_osrm_routes_are_parsed(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    routes = await fetch_osrm_routes(
        project_id="prj_1",
        start=START,
        destination=DEST,
        route_types=[RouteType.shortest, RouteType.fastest],
    )

    assert routes is not None
    assert len(routes) == 2
    assert routes[0].route_type == RouteType.shortest
    assert routes[0].distance_km == 12.3
    assert routes[0].duration_min == 30
    assert routes[0].geometry[0].lat == 35.681236
    assert routes[0].geometry[0].lng == 139.767125
    assert routes[1].distance_km == 11.0


@pytest.mark.asyncio
async def test_osrm_failure_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **k: _FakeClient(**{**k, "fail": True})
    )

    routes = await fetch_osrm_routes(
        project_id="prj_1",
        start=START,
        destination=DEST,
        route_types=[RouteType.shortest],
    )

    assert routes is None
