import pytest
from httpx import AsyncClient

from app.main import _knowledge_hits


def _payload() -> dict:
    return {
        "project_name": "中央区仮設材搬入計画",
        "site_name": "中央区施工ヤード",
        "planner": "qa",
        "start": {"name": "資材センター", "lat": 35.681236, "lng": 139.767125},
        "destination": {"name": "現場ゲート", "lat": 35.658581, "lng": 139.745433},
        "vehicle": {
            "vehicle_type": "heavy_truck",
            "height_m": 3.8,
            "gross_weight_t": 32,
            "special_vehicle_flag": True,
        },
        "delivery": {"time_window": "morning_peak", "holiday": False, "night_delivery_allowed": False},
    }


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["sample_mode"] is True
    assert "本番利用禁止" in body["sample_data_notice"]


@pytest.mark.asyncio
async def test_create_generate_evaluate_report_flow(client: AsyncClient) -> None:
    project_response = await client.post("/api/projects", json=_payload())
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    generate_response = await client.post(f"/api/projects/{project_id}/routes/generate", json={})
    assert generate_response.status_code == 200
    routes = generate_response.json()["routes"]
    assert len(routes) >= 3

    for route in routes:
        evaluation_response = await client.post(f"/api/routes/{route['id']}/evaluate", json={})
        assert evaluation_response.status_code == 200
        body = evaluation_response.json()
        assert body["risk_score"] > 0
        assert body["risk_level"] in {
            "caution",
            "confirm_required",
            "exclusion_consideration",
            "data_insufficient",
        }

    report_response = await client.get(f"/api/projects/{project_id}/report?format=markdown")
    assert report_response.status_code == 200
    content = report_response.json()["content"]
    assert "搬入ルート初期検討メモ" in content
    assert "本番利用禁止（PoC・サンプル）" in content
    assert "サンプル生成" in content
    assert "保証するものではありません" in content
    assert "追加確認事項" in content


@pytest.mark.asyncio
async def test_validation_rejects_invalid_coordinates(client: AsyncClient) -> None:
    bad_payload = _payload()
    bad_payload["start"]["lat"] = 120
    response = await client.post("/api/projects", json=bad_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_featureless_risks_survive_db_round_trip(client: AsyncClient) -> None:
    """Risks without a feature (missing vehicle height/weight) must round-trip."""

    payload = _payload()
    payload["vehicle"] = {}  # no height / weight -> RR-HEIGHT-001 / RR-WEIGHT-001
    created = await client.post("/api/projects", json=payload)
    assert created.status_code == 201
    project_id = created.json()["id"]

    generated = await client.post(f"/api/projects/{project_id}/routes/generate", json={})
    assert generated.status_code == 200
    route_id = generated.json()["routes"][0]["id"]

    evaluated = await client.post(f"/api/routes/{route_id}/evaluate", json={})
    assert evaluated.status_code == 200, evaluated.text
    rules = {risk["rule_id"] for risk in evaluated.json()["risks"]}
    assert "RR-HEIGHT-001" in rules
    assert "RR-WEIGHT-001" in rules

    # Re-read from the repository (this previously raised a 500 because the
    # stored risk_type "unknown" was materialized as an invalid feature).
    fetched = await client.get(f"/api/routes/{route_id}")
    assert fetched.status_code == 200, fetched.text
    fetched_rules = {risk["rule_id"] for risk in fetched.json()["risks"]}
    assert "RR-HEIGHT-001" in fetched_rules
    assert all(
        (risk.get("feature") is None) == (risk["rule_id"] in {"RR-HEIGHT-001", "RR-WEIGHT-001"})
        for risk in fetched.json()["risks"]
    )


@pytest.mark.asyncio
async def test_security_headers_are_present(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_static_assets_are_not_edge_cached(client: AsyncClient) -> None:
    """Cloudflare may serve a stale component.js otherwise; force revalidation."""

    page = await client.get("/")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-cache"

    asset = await client.get("/assets/styles.css")
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_production_mode_blocks_unauthenticated_write(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCTION_MODE", "1")
    monkeypatch.delenv("APP_API_KEY", raising=False)

    response = await client.post("/api/projects", json=_payload())

    assert response.status_code == 503
    assert "Authentication is not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_knowledge_search_is_rate_limited(client: AsyncClient) -> None:
    _knowledge_hits.clear()
    statuses = []
    for _ in range(31):
        response = await client.post("/api/knowledge/search", json={"query": "橋梁 重量"})
        statuses.append(response.status_code)

    assert statuses[0] == 200
    assert statuses[-1] == 429
