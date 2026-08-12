from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from logging import getLogger

from app.models import DataQuality, RouteFeature, new_id, now_utc

logger = getLogger(__name__)

_OVERPASS_DEFAULT_URL = "https://overpass-api.de/api/interpreter"
_CACHE_TTL_SECONDS = 6 * 60 * 60
_overpass_cache: dict[tuple, tuple[float, list[RouteFeature]]] = {}


class DataSourceAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def fetch_features(
        self, lat: float, lng: float, radius_m: int
    ) -> list[RouteFeature]: ...

    @abstractmethod
    async def health_check(self) -> dict: ...


class OSMOverpassAdapter(DataSourceAdapter):
    @property
    def name(self) -> str:
        return "osm"

    @property
    def enabled(self) -> bool:
        return os.getenv("OSM_OVERPASS_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}

    async def fetch_features(
        self, lat: float, lng: float, radius_m: int
    ) -> list[RouteFeature]:
        if not self.enabled:
            return self._sample_features(lat, lng, radius_m)

        cache_key = (round(lat, 3), round(lng, 3), radius_m // 100)
        cached = _overpass_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

        try:
            features = await self._fetch_overpass(lat, lng, radius_m)
        except Exception:
            logger.exception("Overpass fetch failed for (%.6f, %.6f, %dm)", lat, lng, radius_m)
            features = self._sample_features(lat, lng, radius_m)
        _overpass_cache[cache_key] = (time.monotonic(), features)
        return features

    async def _fetch_overpass(self, lat: float, lng: float, radius_m: int) -> list[RouteFeature]:
        import httpx

        url = os.getenv("OSM_OVERPASS_URL", _OVERPASS_DEFAULT_URL)
        query = (
            "[out:json][timeout:25];"
            "("
            f'way["bridge"~"^(yes|viaduct)$"](around:{radius_m},{lat:.6f},{lng:.6f});'
            f'way["tunnel"~"^(yes)$"](around:{radius_m},{lat:.6f},{lng:.6f});'
            f'node["amenity"="school"](around:{radius_m},{lat:.6f},{lng:.6f});'
            f'node["amenity"="hospital"](around:{radius_m},{lat:.6f},{lng:.6f});'
            ");"
            "out center tags;"
        )
        acquired_at = now_utc()
        headers = {
            "User-Agent": "Construction-Logistics-Route-Planner/0.1 (internal MVP evaluation)"
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params={"data": query}, headers=headers)
            response.raise_for_status()
            payload = response.json()

        features: list[RouteFeature] = []
        for element in payload.get("elements") or []:
            tags = element.get("tags") or {}
            if "bridge" in tags:
                feature_type = "bridge"
                default_name = f"橋梁候補 (OSM {element['type']}/{element['id']})"
            elif "tunnel" in tags:
                feature_type = "tunnel"
                default_name = f"トンネル候補 (OSM {element['type']}/{element['id']})"
            elif tags.get("amenity") == "school":
                feature_type = "school"
                default_name = "学校（OSM）"
            elif tags.get("amenity") == "hospital":
                feature_type = "hospital"
                default_name = "病院（OSM）"
            else:
                continue

            point = element.get("center") or element
            attributes: dict[str, str | int | float | bool | None] = {
                "maxweight": tags.get("maxweight"),
                "maxheight": tags.get("maxheight"),
                "maxwidth": tags.get("maxwidth"),
                "maxspeed": tags.get("maxspeed"),
                "highway": tags.get("highway"),
            }
            features.append(
                RouteFeature(
                    id=new_id("feat"),
                    feature_type=feature_type,
                    name=tags.get("name") or default_name,
                    lat=float(point["lat"]),
                    lng=float(point["lon"]),
                    source="OpenStreetMap (Overpass API)",
                    source_url=f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
                    acquired_at=acquired_at,
                    data_quality=DataQuality.osm,
                    attributes=attributes,
                )
            )
        return features

    def _sample_features(self, lat: float, lng: float, radius_m: int) -> list[RouteFeature]:
        del radius_m
        acquired_at = now_utc()
        features: list[RouteFeature] = [
            RouteFeature(
                id=new_id("feat"),
                feature_type="bridge",
                name="橋梁候補区間",
                lat=lat + 0.002,
                lng=lng - 0.002,
                source="OpenStreetMap sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.osm,
                attributes={"max_weight_t": None, "road_name": "sample primary road"},
            ),
            RouteFeature(
                id=new_id("feat"),
                feature_type="tunnel",
                name="アンダーパス候補",
                lat=lat - 0.001,
                lng=lng + 0.001,
                source="OpenStreetMap sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.osm,
                attributes={"max_height_m": None},
            ),
            RouteFeature(
                id=new_id("feat"),
                feature_type="osm_quality",
                name="制限属性未整備区間",
                lat=lat,
                lng=lng,
                source="OpenStreetMap sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.osm,
                attributes={"missing_tags": "maxheight,maxweight,width"},
            ),
            RouteFeature(
                id=new_id("feat"),
                feature_type="school",
                name="学校近接エリア",
                lat=lat + 0.001,
                lng=lng - 0.001,
                source="国土数値情報 sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.public_authority,
                attributes={"distance_m": 220},
            ),
            RouteFeature(
                id=new_id("feat"),
                feature_type="hospital",
                name="病院近接エリア",
                lat=lat - 0.001,
                lng=lng + 0.001,
                source="国土数値情報 sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.public_authority,
                attributes={"distance_m": 280},
            ),
            RouteFeature(
                id=new_id("feat"),
                feature_type="residential",
                name="住宅地通過比率高め",
                lat=lat + 0.003,
                lng=lng - 0.003,
                source="国土数値情報 sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.public_authority,
                attributes={"residential_ratio": 0.38},
            ),
            RouteFeature(
                id=new_id("feat"),
                feature_type="traffic",
                name="交通量注意区間",
                lat=lat - 0.002,
                lng=lng + 0.002,
                source="xROAD sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.estimated,
                attributes={"peak": True},
            ),
            RouteFeature(
                id=new_id("feat"),
                feature_type="disaster",
                name="浸水想定区域近接",
                lat=lat - 0.003,
                lng=lng + 0.003,
                source="国土数値情報 sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.public_authority,
                attributes={"hazard": "flood"},
            ),
        ]
        return features

    async def health_check(self) -> dict:
        return {"status": "ok", "mode": "real" if self.enabled else "stub"}


class XROADAdapter(DataSourceAdapter):
    @property
    def name(self) -> str:
        return "xroad"

    async def fetch_features(
        self, lat: float, lng: float, radius_m: int
    ) -> list[RouteFeature]:
        return []

    async def health_check(self) -> dict:
        return {"status": "not_configured"}


class PLATEAUAdapter(DataSourceAdapter):
    @property
    def name(self) -> str:
        return "plateau"

    async def fetch_features(
        self, lat: float, lng: float, radius_m: int
    ) -> list[RouteFeature]:
        return []

    async def health_check(self) -> dict:
        return {"status": "not_configured"}


class KSJAdapter(DataSourceAdapter):
    @property
    def name(self) -> str:
        return "ksj"

    async def fetch_features(
        self, lat: float, lng: float, radius_m: int
    ) -> list[RouteFeature]:
        return []

    async def health_check(self) -> dict:
        return {"status": "not_configured"}


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, DataSourceAdapter] = {
            "osm": OSMOverpassAdapter(),
            "xroad": XROADAdapter(),
            "plateau": PLATEAUAdapter(),
            "ksj": KSJAdapter(),
        }

    def get_all(self) -> list[DataSourceAdapter]:
        return list(self._adapters.values())

    def get(self, name: str) -> DataSourceAdapter | None:
        return self._adapters.get(name)

    async def fetch_all(
        self, lat: float, lng: float, radius_m: int
    ) -> list[RouteFeature]:
        features: list[RouteFeature] = []
        for adapter in self._adapters.values():
            try:
                result = await adapter.fetch_features(lat, lng, radius_m)
                features.extend(result)
            except Exception:
                logger.exception(
                    "Adapter %s failed for (%.6f, %.6f, %dm)",
                    adapter.name,
                    lat,
                    lng,
                    radius_m,
                )
        return features
