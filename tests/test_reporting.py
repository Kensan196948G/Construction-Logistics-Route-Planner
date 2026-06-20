"""Unit tests for the report renderers.

The API flow test only exercises the Markdown report through the endpoint. These
tests cover the renderers directly: the CSV writer, the empty-risk branch, the
risk-with-location branch, the disclaimer, and the `_value` "未入力" fallback.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from app.models import (
    DISCLAIMER,
    DataQuality,
    LocationInput,
    Project,
    RiskItem,
    RiskLevel,
    RouteCandidate,
    RouteFeature,
    RouteType,
)
from app.reporting import render_csv, render_markdown

NOW = datetime(2026, 6, 20, tzinfo=timezone.utc)


def _project() -> Project:
    return Project(
        id="prj_test",
        project_name="テスト案件",
        site_name="テスト現場",
        planner="qa",
        start=LocationInput(name="出発地", lat=35.681236, lng=139.767125),
        destination=LocationInput(name="到着地", lat=35.658581, lng=139.745433),
        created_at=NOW,
        updated_at=NOW,
    )


def _route_with_risk() -> RouteCandidate:
    feature = RouteFeature(
        id="feat_bridge",
        feature_type="bridge",
        name="△△大橋",
        lat=35.662000,
        lng=139.755000,
        source="OSM",
        acquired_at=NOW,
        data_quality=DataQuality.osm,
    )
    risk = RiskItem(
        id="risk_1",
        rule_id="bridge_weight",
        level=RiskLevel.confirm_required,
        title="橋梁の重量制限",
        message="公開データに重量制限属性がありません。",
        score=70,
        feature=feature,
        confirmation_target="道路管理者への耐荷重照会",
        evidence="OSM属性に maxweight 無し",
    )
    return RouteCandidate(
        id="route_a",
        project_id="prj_test",
        route_type=RouteType.shortest,
        name="候補A",
        distance_km=12.3,
        duration_min=34,
        geometry=[LocationInput(name="p0", lat=35.681236, lng=139.767125)],
        risk_score=70,
        risk_level=RiskLevel.confirm_required,
        summary="要確認の注意箇所あり",
        risks=[risk],
    )


def _route_without_risk() -> RouteCandidate:
    return RouteCandidate(
        id="route_b",
        project_id="prj_test",
        route_type=RouteType.fastest,
        name="候補B",
        distance_km=9.9,
        duration_min=28,
        geometry=[LocationInput(name="p0", lat=35.681236, lng=139.767125)],
        risk_score=10,
        risk_level=RiskLevel.candidate,
        summary="評価済みの注意箇所なし",
        risks=[],
    )


def test_render_markdown_has_sections_disclaimer_and_risk_rows() -> None:
    routes = [_route_with_risk(), _route_without_risk()]
    md = render_markdown(_project(), routes)

    assert md.startswith("# 搬入ルート初期検討メモ")
    assert md.endswith("\n")
    # Project + both candidates appear.
    assert "テスト案件" in md and "テスト現場" in md
    assert "候補A" in md and "候補B" in md
    # Risk row with its level label, confirmation target, evidence, and location.
    assert "[要確認] 橋梁の重量制限" in md
    assert "道路管理者への耐荷重照会" in md
    assert "位置: 35.662000, 139.755000" in md
    # Empty-risk branch renders the safety caveat instead of risk lines.
    assert "評価済みの注意箇所はありません" in md
    # Mandatory disclaimer is always present.
    assert DISCLAIMER in md


def test_render_markdown_uses_value_fallback_for_missing_vehicle_specs() -> None:
    # The default VehicleCondition leaves length/width/height unset -> "未入力".
    md = render_markdown(_project(), [_route_without_risk()])
    assert "未入力" in md


def test_render_csv_header_and_one_row_per_risk() -> None:
    csv_text = render_csv(_project(), [_route_with_risk(), _route_without_risk()])
    rows = list(csv.reader(io.StringIO(csv_text)))

    header = rows[0]
    assert header[:4] == ["project_id", "project_name", "route_id", "route_name"]
    assert "risk_title" in header and "confirmation_target" in header

    body = rows[1:]
    # One row for the single risk on route A, plus one blank-risk row for route B.
    assert len(body) == 2
    by_route = {r[2]: r for r in body}

    risk_row = by_route["route_a"]
    assert risk_row[header.index("risk_title")] == "橋梁の重量制限"
    assert risk_row[header.index("confirmation_target")] == "道路管理者への耐荷重照会"
    assert risk_row[header.index("project_id")] == "prj_test"

    # Route B has no risks: the row exists but risk columns are blank.
    blank_row = by_route["route_b"]
    assert blank_row[header.index("risk_title")] == ""
    assert blank_row[header.index("risk_message")] == ""


def test_render_csv_is_parseable_and_quotes_commas() -> None:
    # A message containing a comma must round-trip through the CSV quoting.
    route = _route_with_risk()
    route.risks[0].message = "幅員 2.6m, 待避所 2 箇所"
    csv_text = render_csv(_project(), [route])
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[1][rows[0].index("risk_message")] == "幅員 2.6m, 待避所 2 箇所"
