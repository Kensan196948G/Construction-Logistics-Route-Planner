from __future__ import annotations

import pytest
from httpx import AsyncClient


def _payload() -> dict:
    return {
        "project_name": "検証用現場（実在しない架空案件）",
        "site_name": "検証用ヤード",
        "planner": "qa",
        "start": {"name": "出発地", "lat": 35.681236, "lng": 139.767125},
        "destination": {"name": "到着地", "lat": 35.658581, "lng": 139.745433},
        "vehicle": {"vehicle_type": "heavy_truck", "height_m": 3.8, "gross_weight_t": 32},
        "delivery": {"time_window": "daytime"},
    }


async def _evaluated_project(client: AsyncClient, headers: dict | None = None) -> tuple[str, dict]:
    created = await client.post("/api/projects", json=_payload(), headers=headers)
    assert created.status_code == 201
    project_id = created.json()["id"]
    generated = await client.post(f"/api/projects/{project_id}/routes/generate", json={}, headers=headers)
    assert generated.status_code == 200
    route = generated.json()["routes"][0]
    evaluated = await client.post(f"/api/routes/{route['id']}/evaluate", json={}, headers=headers)
    assert evaluated.status_code == 200
    risk = evaluated.json()["risks"][0]
    return project_id, {"route_id": route["id"], "risk_id": risk["id"]}


@pytest.mark.asyncio
async def test_submit_requires_evaluated_route(client: AsyncClient) -> None:
    created = await client.post("/api/projects", json=_payload())
    project_id = created.json()["id"]

    response = await client.post(f"/api/projects/{project_id}/submit", json={"comment": "未評価のまま申請"})

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_full_workflow_confirm_submit_approve_and_audit(client: AsyncClient, monkeypatch) -> None:
    project_id, refs = await _evaluated_project(client)

    confirmed = await client.post(
        f"/api/routes/{refs['route_id']}/risks/{refs['risk_id']}/confirm",
        json={"status": "confirmed", "comment": "現場確認済み"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    submitted = await client.post(f"/api/projects/{project_id}/submit", json={"comment": "評価完了"})
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "review_required"

    monkeypatch.setenv("APP_API_KEY", "secret-key-123456")
    monkeypatch.setenv("APP_API_KEY_USER_ID", "admin-user")
    monkeypatch.setenv("APP_API_KEY_USER_ROLE", "admin")
    headers = {"Authorization": "Bearer secret-key-123456"}

    approved = await client.post(f"/api/projects/{project_id}/approve", json={"comment": "承認"}, headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "reviewed"

    logs = await client.get("/api/admin/audit-logs", headers=headers)
    assert logs.status_code == 200
    actions = [log["action"] for log in logs.json()]
    assert "project_approved" in actions
    assert "risk_confirmed" in actions
    assert "project_submitted" in actions


@pytest.mark.asyncio
async def test_request_changes_sets_change_requested(client: AsyncClient) -> None:
    project_id, _ = await _evaluated_project(client)
    await client.post(f"/api/projects/{project_id}/submit", json={})

    response = await client.post(
        f"/api/projects/{project_id}/request-changes", json={"comment": "橋梁資料を再確認"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "change_requested"


@pytest.mark.asyncio
async def test_viewer_cannot_create_project(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "secret-key-123456")
    monkeypatch.setenv("APP_API_KEY_USER_ROLE", "viewer")

    response = await client.post("/api/projects", json=_payload(), headers={"Authorization": "Bearer secret-key-123456"})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_site_user_can_confirm_but_not_approve(client: AsyncClient, monkeypatch) -> None:
    project_id, refs = await _evaluated_project(client)

    monkeypatch.setenv("APP_API_KEY", "secret-key-123456")
    monkeypatch.setenv("APP_API_KEY_USER_ID", "site-lead")
    monkeypatch.setenv("APP_API_KEY_USER_ROLE", "site_user")
    headers = {"Authorization": "Bearer secret-key-123456"}

    confirmed = await client.post(
        f"/api/routes/{refs['route_id']}/risks/{refs['risk_id']}/confirm",
        json={"status": "needs_review", "comment": "現地で要確認"},
        headers=headers,
    )
    assert confirmed.status_code == 200

    denied = await client.post(f"/api/projects/{project_id}/approve", json={}, headers=headers)
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_re_evaluation_preserves_risk_confirmation(client: AsyncClient) -> None:
    """Re-evaluating a route must not silently discard confirmation results."""

    project_id, refs = await _evaluated_project(client)

    confirmed = await client.post(
        f"/api/routes/{refs['route_id']}/risks/{refs['risk_id']}/confirm",
        json={"status": "confirmed", "comment": "道路管理者に台帳確認済み"},
    )
    assert confirmed.status_code == 200

    re_evaluated = await client.post(f"/api/routes/{refs['route_id']}/evaluate", json={})
    assert re_evaluated.status_code == 200
    body = re_evaluated.json()

    # The risk id changes after re-evaluation, but the rule+feature identity is
    # stable; the API must report the carried-over confirmation status.
    assert any(
        risk["confirmation_status"] == "confirmed"
        for risk in body["risks"]
        if risk["rule_id"] == body["risks"][0]["rule_id"]
    )

    listed = await client.get(f"/api/routes/{refs['route_id']}/risks")
    assert listed.status_code == 200
    assert any(risk["confirmation_status"] == "confirmed" for risk in listed.json())


@pytest.mark.asyncio
async def test_regenerating_routes_keeps_latest_generation_only(client: AsyncClient) -> None:
    """Repeated route generation must not duplicate candidates in list/report views."""

    created = await client.post("/api/projects", json=_payload())
    assert created.status_code == 201
    project_id = created.json()["id"]

    first = await client.post(f"/api/projects/{project_id}/routes/generate", json={})
    assert first.status_code == 200
    first_count = first.json()["generated_count"]
    assert first_count >= 3

    second = await client.post(f"/api/projects/{project_id}/routes/generate", json={})
    assert second.status_code == 200
    assert second.json()["generated_count"] == first_count

    listed = await client.get(f"/api/projects/{project_id}/routes")
    assert listed.status_code == 200
    assert len(listed.json()) == first_count
