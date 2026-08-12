from app.models import (
    DeliveryCondition,
    EvaluationRequest,
    LocationInput,
    Project,
    VehicleCondition,
    now_utc,
)
from app.risk_engine import evaluate_route, generate_routes


def project(vehicle: VehicleCondition | None = None) -> Project:
    now = now_utc()
    return Project(
        id="prj_test",
        project_name="テスト工事",
        site_name="テスト現場",
        planner="qa",
        start=LocationInput(name="start", lat=35.681236, lng=139.767125),
        destination=LocationInput(name="dest", lat=35.658581, lng=139.745433),
        vehicle=vehicle or VehicleCondition(height_m=3.8, gross_weight_t=32),
        delivery=DeliveryCondition(time_window="morning_peak"),
        created_at=now,
        updated_at=now,
    )


def test_generate_routes_creates_multiple_candidates() -> None:
    routes = generate_routes(project(), [])
    assert routes == []

    routes = generate_routes(project(), ["shortest", "fastest", "arterial_priority"])
    assert len(routes) == 3
    assert all(route.features for route in routes)
    assert all(route.distance_km > 0 for route in routes)


def test_evaluate_route_never_treats_missing_weight_as_candidate() -> None:
    prj = project(VehicleCondition(height_m=None, gross_weight_t=None))
    route = generate_routes(prj, ["shortest"])[0]
    evaluated = evaluate_route(prj, route)

    assert evaluated.risk_score > 0
    assert evaluated.risk_level != "candidate"
    assert any(risk.rule_id == "RR-WEIGHT-001" for risk in evaluated.risks)
    assert any(risk.rule_id == "RR-HEIGHT-001" for risk in evaluated.risks)


def test_high_weight_bridge_adds_exclusion_consideration() -> None:
    prj = project(VehicleCondition(height_m=4.0, gross_weight_t=50))
    route = generate_routes(prj, ["shortest"])[0]
    evaluated = evaluate_route(prj, route)

    assert evaluated.risk_level == "exclusion_consideration"
    assert any(risk.rule_id == "RR-BRIDGE-002" for risk in evaluated.risks)


def test_sample_features_are_ranked_estimated() -> None:
    prj = project()
    route = generate_routes(prj, ["shortest"])[0]

    assert route.features
    assert all(feature.data_quality.value == "E" for feature in route.features)
    assert all(feature.attributes.get("sample") is True for feature in route.features)


def test_include_sources_filters_evaluation_inputs() -> None:
    prj = project()
    route = generate_routes(prj, ["shortest"])[0]

    osm_only = evaluate_route(prj, route, EvaluationRequest(include_sources=["osm"]))
    assert not any(risk.rule_id.startswith("RR-SCHOOL") for risk in osm_only.risks)
    assert any(risk.rule_id == "RR-BRIDGE-001" for risk in osm_only.risks)

    ksj_only = evaluate_route(prj, route, EvaluationRequest(include_sources=["ksj"]))
    assert any(risk.rule_id.startswith("RR-SCHOOL") for risk in ksj_only.risks)
    assert not any(risk.rule_id == "RR-BRIDGE-001" for risk in ksj_only.risks)
