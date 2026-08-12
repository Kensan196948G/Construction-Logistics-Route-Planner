"""API-level E2E: fictional site -> routes -> evaluation -> confirmation -> approval -> PDF."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_fictional_site_input_to_pdf_output(client: AsyncClient, monkeypatch) -> None:
    payload = {
        "project_name": "検証用 架空現場（E2E）",
        "site_name": "E2E検証ヤード",
        "planner": "e2e-runner",
        "start": {"name": "E2E資材置場", "lat": 35.7010, "lng": 139.7021},
        "destination": {"name": "E2E現場ゲート", "lat": 35.6550, "lng": 139.7500},
        "vehicle": {
            "vehicle_type": "trailer",
            "length_m": 12.0,
            "width_m": 2.5,
            "height_m": 3.9,
            "gross_weight_t": 40,
            "special_vehicle_flag": True,
        },
        "delivery": {"time_window": "daytime", "holiday": False},
        "notes": "実在しない検証用現場。本番判断には使用しない。",
    }

    # 1. Input
    created = await client.post("/api/projects", json=payload)
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    # 2. Route generation
    generated = await client.post(f"/api/projects/{project_id}/routes/generate", json={})
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["mode"] in {"sample", "sample+osm", "osrm", "osrm+osm"}
    assert len(body["routes"]) >= 3
    route_ids = [route["id"] for route in body["routes"]]

    # 3. Evaluation
    risk_refs = []
    for route_id in route_ids:
        evaluated = await client.post(f"/api/routes/{route_id}/evaluate", json={})
        assert evaluated.status_code == 200, evaluated.text
        risks = evaluated.json()["risks"]
        assert risks, "every evaluated route must produce at least one risk"
        risk_refs.append((route_id, risks[0]["id"]))

    # 4. Confirmation (planner / anonymous)
    route_id, risk_id = risk_refs[0]
    confirmed = await client.post(
        f"/api/routes/{route_id}/risks/{risk_id}/confirm",
        json={"status": "confirmed", "comment": "E2E: 現地確認（架空）"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"

    # 5. Submit + approve (admin)
    submitted = await client.post(f"/api/projects/{project_id}/submit", json={"comment": "E2E提出"})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "review_required"

    monkeypatch.setenv("APP_API_KEY", "e2e-secret-123456")
    monkeypatch.setenv("APP_API_KEY_USER_ROLE", "admin")
    headers = {"Authorization": "Bearer e2e-secret-123456"}
    approved = await client.post(f"/api/projects/{project_id}/approve", json={"comment": "E2E承認"}, headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "reviewed"

    # 6. Reports: markdown + PDF
    md = await client.get(f"/api/projects/{project_id}/report?format=markdown", headers=headers)
    assert md.status_code == 200
    assert "本番利用禁止（PoC・サンプル）" in md.json()["content"]

    pdf = await client.get(f"/api/projects/{project_id}/report?format=pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 1000
