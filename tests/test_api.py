from fastapi.testclient import TestClient

from app.main import PROJECTS, ROUTES, app


client = TestClient(app)


def setup_function() -> None:
    PROJECTS.clear()
    ROUTES.clear()


def payload() -> dict:
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


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_generate_evaluate_report_flow() -> None:
    project_response = client.post("/api/projects", json=payload())
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    generate_response = client.post(f"/api/projects/{project_id}/routes/generate", json={})
    assert generate_response.status_code == 200
    routes = generate_response.json()["routes"]
    assert len(routes) >= 3

    for route in routes:
        evaluation_response = client.post(f"/api/routes/{route['id']}/evaluate", json={})
        assert evaluation_response.status_code == 200
        body = evaluation_response.json()
        assert body["risk_score"] > 0
        assert body["risk_level"] in {
            "caution",
            "confirm_required",
            "exclusion_consideration",
            "data_insufficient",
        }

    report_response = client.get(f"/api/projects/{project_id}/report?format=markdown")
    assert report_response.status_code == 200
    content = report_response.json()["content"]
    assert "搬入ルート初期検討メモ" in content
    assert "保証するものではありません" in content
    assert "追加確認事項" in content


def test_validation_rejects_invalid_coordinates() -> None:
    bad_payload = payload()
    bad_payload["start"]["lat"] = 120
    response = client.post("/api/projects", json=bad_payload)
    assert response.status_code == 422
