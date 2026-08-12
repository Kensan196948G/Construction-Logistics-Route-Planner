"""Regression tests for the delivery/avoid persistence fix and health/audit additions."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db_models import Project as DBProject


def _payload() -> dict:
    return {
        "project_name": "永続化検証案件",
        "site_name": "検証ヤード",
        "owner_type": "public",
        "planner": "qa",
        "start": {"name": "出発地", "lat": 35.681236, "lng": 139.767125},
        "destination": {"name": "到着地", "lat": 35.658581, "lng": 139.745433},
        "vehicle": {
            "vehicle_type": "trailer",
            "length_m": 12.0,
            "width_m": 2.5,
            "height_m": 3.9,
            "gross_weight_t": 40,
            "axle_weight_t": 10,
            "cargo_type": "PCa部材",
            "special_vehicle_flag": True,
        },
        "delivery": {
            "delivery_date": "2026-09-01",
            "time_window": "morning_peak",
            "holiday": True,
            "night_delivery_allowed": False,
        },
        "avoid_conditions": ["schools", "residential"],
        "notes": "永続化の回帰テスト",
    }


@pytest.mark.asyncio
async def test_delivery_and_avoid_conditions_round_trip(client: AsyncClient, session, monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "persist-secret-123")
    monkeypatch.setenv("APP_API_KEY_USER_ID", "owner-123")
    monkeypatch.setenv("APP_API_KEY_USER_ROLE", "planner")
    headers = {"Authorization": "Bearer persist-secret-123"}

    created = await client.post("/api/projects", json=_payload(), headers=headers)
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    fetched = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()

    delivery = body["delivery"]
    assert delivery["delivery_date"] == "2026-09-01"
    assert delivery["time_window"] == "morning_peak"
    assert delivery["holiday"] is True
    assert delivery["night_delivery_allowed"] is False
    assert body["avoid_conditions"] == ["schools", "residential"]
    assert body["notes"] == "永続化の回帰テスト"

    # Owner identity must be persisted from the authenticated user, never from
    # client-supplied headers (the API response model intentionally omits it).
    db_project = (
        await session.execute(select(DBProject).where(DBProject.id == project_id))
    ).scalar_one()
    assert db_project.owner_user_id == "owner-123"
    assert db_project.delivery_date == date(2026, 9, 1)
    assert db_project.avoid_conditions == ["schools", "residential"]


@pytest.mark.asyncio
async def test_report_auto_evaluation_is_persisted(client: AsyncClient) -> None:
    created = await client.post("/api/projects", json=_payload())
    project_id = created.json()["id"]
    await client.post(f"/api/projects/{project_id}/routes/generate", json={})

    report = await client.get(f"/api/projects/{project_id}/report?format=markdown")
    assert report.status_code == 200

    routes = await client.get(f"/api/projects/{project_id}/routes")
    assert routes.status_code == 200
    assert routes.json(), "routes must exist"
    assert all(route["evaluation_status"] == "evaluated" for route in routes.json())


@pytest.mark.asyncio
async def test_health_reports_database_status(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db"]["status"] in {"ok", "error", "timeout"}
    assert body["db"]["dialect"] in {"sqlite", "postgresql"}


@pytest.mark.asyncio
async def test_audit_logs_csv_export_requires_admin_and_is_parseable(
    client: AsyncClient, monkeypatch
) -> None:
    # Create one audited project so the export has at least one row.
    await client.post("/api/projects", json=_payload())

    monkeypatch.setenv("APP_API_KEY", "admin-secret-123")
    monkeypatch.setenv("APP_API_KEY_USER_ROLE", "viewer")
    viewer_headers = {"Authorization": "Bearer admin-secret-123"}
    denied = await client.get("/api/admin/audit-logs/export", headers=viewer_headers)
    assert denied.status_code == 403

    monkeypatch.setenv("APP_API_KEY_USER_ROLE", "admin")
    admin_headers = {"Authorization": "Bearer admin-secret-123"}
    response = await client.get("/api/admin/audit-logs/export", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    text = response.text
    assert text.startswith("id,created_at,user_id,user_role,action")
    assert "project_created" in text
