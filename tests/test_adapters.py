from __future__ import annotations

import httpx
import pytest

from app.adapters import OSMOverpassAdapter


class _FakeOverpassResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "elements": [
                {
                    "type": "way",
                    "id": 1001,
                    "tags": {"bridge": "yes", "name": "△△大橋", "maxweight": "25"},
                    "center": {"lat": 35.001, "lon": 139.001},
                },
                {
                    "type": "node",
                    "id": 2002,
                    "tags": {"amenity": "school", "name": "××小学校"},
                    "lat": 35.002,
                    "lon": 139.002,
                },
            ]
        }


class _FakeOverpassClient:
    def __init__(self, *args, **kwargs) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def get(self, *args, **kwargs) -> _FakeOverpassResponse:
        return _FakeOverpassResponse()


@pytest.mark.asyncio
async def test_overpass_fetch_parses_bridge_and_school(monkeypatch) -> None:
    monkeypatch.setenv("OSM_OVERPASS_ENABLED", "1")
    monkeypatch.setenv("OSM_OVERPASS_URL", "https://example.invalid/api/interpreter")
    monkeypatch.setattr(httpx, "AsyncClient", _FakeOverpassClient)

    features = await OSMOverpassAdapter().fetch_features(35.001, 139.001, 500)

    assert len(features) == 2
    by_type = {f.feature_type: f for f in features}
    assert by_type["bridge"].name == "△△大橋"
    assert by_type["bridge"].source_url == "https://www.openstreetmap.org/way/1001"
    assert by_type["bridge"].attributes["maxweight"] == "25"
    assert by_type["school"].name == "××小学校"
    assert by_type["school"].data_quality.value == "C"


@pytest.mark.asyncio
async def test_overpass_disabled_returns_sample(monkeypatch) -> None:
    monkeypatch.delenv("OSM_OVERPASS_ENABLED", raising=False)

    features = await OSMOverpassAdapter().fetch_features(35.001, 139.001, 500)

    assert features
    assert "sample overlay" in features[0].source
    # Sample-generated features must never masquerade as official/community
    # data: the reliability rank is E (estimated) and a sample flag is set.
    assert all(feature.data_quality.value == "E" for feature in features)
    assert all(feature.attributes.get("sample") is True for feature in features)
