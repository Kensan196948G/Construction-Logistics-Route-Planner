from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from app.models import (
    DataQuality,
    EvaluationRequest,
    LocationInput,
    Project,
    RiskItem,
    RiskLevel,
    RouteCandidate,
    RouteFeature,
    RouteType,
    new_id,
    now_utc,
)

ROUTE_LABELS = {
    RouteType.shortest: "候補A 距離優先",
    RouteType.fastest: "候補B 時間優先",
    RouteType.arterial_priority: "候補C 幹線道路優先",
    RouteType.residential_avoid: "候補D 住宅地回避",
    RouteType.bridge_tunnel_caution: "候補E 橋梁・トンネル確認重視",
}

ROUTE_FACTORS = {
    RouteType.shortest: (1.00, 30),
    RouteType.fastest: (1.12, 42),
    RouteType.arterial_priority: (1.22, 38),
    RouteType.residential_avoid: (1.30, 34),
    RouteType.bridge_tunnel_caution: (1.18, 32),
}


def haversine_km(a: LocationInput, b: LocationInput) -> float:
    radius_km = 6371.0
    dlat = radians(b.lat - a.lat)
    dlng = radians(b.lng - a.lng)
    lat1 = radians(a.lat)
    lat2 = radians(b.lat)
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * radius_km * asin(sqrt(h))


def generate_routes(project: Project, route_types: list[RouteType]) -> list[RouteCandidate]:
    base_distance = max(haversine_km(project.start, project.destination), 0.1)
    routes: list[RouteCandidate] = []
    for index, route_type in enumerate(route_types):
        distance_factor, speed_kmh = ROUTE_FACTORS[route_type]
        distance_km = round(base_distance * distance_factor, 1)
        duration_min = max(1, round(distance_km / speed_kmh * 60))
        geometry = _route_geometry(project.start, project.destination, index)
        routes.append(
            RouteCandidate(
                id=new_id("route"),
                project_id=project.id,
                route_type=route_type,
                name=ROUTE_LABELS[route_type],
                distance_km=distance_km,
                duration_min=duration_min,
                geometry=geometry,
                features=sample_overlay_features(project, route_type, geometry),
            )
        )
    return routes


def sample_overlay_features(
    project: Project,
    route_type: RouteType,
    geometry: list[LocationInput],
) -> list[RouteFeature]:
    midpoint = geometry[len(geometry) // 2]
    quarter = geometry[1]
    three_quarter = geometry[-2]
    acquired_at = now_utc()
    features = [
        RouteFeature(
            id=new_id("feat"),
            feature_type="bridge",
            name="橋梁候補区間",
            lat=quarter.lat,
            lng=quarter.lng,
            source="OpenStreetMap sample overlay",
            acquired_at=acquired_at,
            data_quality=DataQuality.estimated,
            attributes={"max_weight_t": None, "road_name": "sample primary road"},
        ),
        RouteFeature(
            id=new_id("feat"),
            feature_type="osm_quality",
            name="制限属性未整備区間",
            lat=midpoint.lat,
            lng=midpoint.lng,
            source="OpenStreetMap sample overlay",
            acquired_at=acquired_at,
            data_quality=DataQuality.estimated,
            attributes={"missing_tags": "maxheight,maxweight,width"},
        ),
    ]

    if project.vehicle.height_m is None or project.vehicle.height_m >= 3.8:
        features.append(
            RouteFeature(
                id=new_id("feat"),
                feature_type="tunnel",
                name="アンダーパス候補",
                lat=midpoint.lat,
                lng=midpoint.lng,
                source="OpenStreetMap sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.estimated,
                attributes={"max_height_m": None},
            )
        )

    if route_type in {RouteType.shortest, RouteType.fastest}:
        features.extend(
            [
                RouteFeature(
                    id=new_id("feat"),
                    feature_type="school",
                    name="学校近接エリア",
                    lat=midpoint.lat + 0.001,
                    lng=midpoint.lng - 0.001,
                    source="国土数値情報 sample overlay",
                    acquired_at=acquired_at,
                    data_quality=DataQuality.estimated,
                    attributes={"distance_m": 220},
                ),
                RouteFeature(
                    id=new_id("feat"),
                    feature_type="residential",
                    name="住宅地通過比率高め",
                    lat=three_quarter.lat,
                    lng=three_quarter.lng,
                    source="国土数値情報 sample overlay",
                    acquired_at=acquired_at,
                    data_quality=DataQuality.estimated,
                    attributes={"residential_ratio": 0.38},
                ),
            ]
        )

    if route_type in {RouteType.arterial_priority, RouteType.fastest}:
        features.append(
            RouteFeature(
                id=new_id("feat"),
                feature_type="traffic",
                name="交通量注意区間",
                lat=three_quarter.lat,
                lng=three_quarter.lng,
                source="xROAD sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.estimated,
                attributes={"peak": True},
            )
        )

    if route_type == RouteType.residential_avoid:
        features.append(
            RouteFeature(
                id=new_id("feat"),
                feature_type="hospital",
                name="病院近接エリア",
                lat=midpoint.lat - 0.001,
                lng=midpoint.lng + 0.001,
                source="国土数値情報 sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.estimated,
                attributes={"distance_m": 280},
            )
        )

    if route_type == RouteType.bridge_tunnel_caution or project.vehicle.gross_weight_t is None:
        features.append(
            RouteFeature(
                id=new_id("feat"),
                feature_type="disaster",
                name="浸水想定区域近接",
                lat=quarter.lat - 0.001,
                lng=quarter.lng + 0.001,
                source="国土数値情報 sample overlay",
                acquired_at=acquired_at,
                data_quality=DataQuality.estimated,
                attributes={"hazard": "flood"},
            )
        )

    for feature in features:
        feature.attributes["sample"] = True
    return features


def evaluate_route(
    project: Project,
    route: RouteCandidate,
    request: EvaluationRequest | None = None,
) -> RouteCandidate:
    risks: list[RiskItem] = []

    features = route.features
    if request is not None and request.include_sources:
        features = [
            feature
            for feature in route.features
            if _source_category(feature) in set(request.include_sources)
        ]

    for feature in features:
        if feature.feature_type == "bridge":
            if feature.attributes.get("max_weight_t") is None:
                risks.append(
                    _risk(
                        "RR-BRIDGE-001",
                        RiskLevel.confirm_required,
                        "橋梁重量確認",
                        "橋梁を通過する可能性がありますが、公開データ上で重量制限を確認できません。道路管理者または現地資料で追加確認してください。",
                        25,
                        feature,
                        "道路管理者",
                    )
                )
            if project.vehicle.gross_weight_t and project.vehicle.gross_weight_t >= 44:
                risks.append(
                    _risk(
                        "RR-BRIDGE-002",
                        RiskLevel.exclusion_consideration,
                        "高重量車両の橋梁通過確認",
                        "総重量が大きいため、橋梁条件が確認できるまで候補からの除外も含めて検討してください。",
                        35,
                        feature,
                        "道路管理者・協力会社",
                    )
                )

        if feature.feature_type == "tunnel":
            risks.append(
                _risk(
                    "RR-TUNNEL-001",
                    RiskLevel.confirm_required,
                    "トンネル・アンダーパス高さ確認",
                    "高さ制限情報が公開データ上で確認できません。車両全高と現地制限を追加確認してください。",
                    25,
                    feature,
                    "道路管理者・現地確認",
                )
            )

        if feature.feature_type == "osm_quality":
            risks.append(
                _risk(
                    "RR-OSM-QUALITY-001",
                    RiskLevel.data_insufficient,
                    "道路制限属性不足",
                    "高さ、重量、幅員などの OSM 属性が不足しています。公開データだけで支障なしとは扱えません。",
                    15,
                    feature,
                    "道路管理者・現地確認",
                )
            )

        if feature.feature_type == "school" and project.delivery.time_window in {
            "morning_peak",
            "evening_peak",
        }:
            risks.append(
                _risk(
                    "RR-SCHOOL-001",
                    RiskLevel.caution,
                    "学校周辺の時間帯注意",
                    "学校近接エリアで朝夕搬入条件に該当します。通学時間帯、誘導員配置、搬入時間調整を確認してください。",
                    15,
                    feature,
                    "発注者・学校周辺管理者・現地確認",
                )
            )
        elif feature.feature_type == "school":
            risks.append(
                _risk(
                    "RR-SCHOOL-002",
                    RiskLevel.caution,
                    "学校周辺注意",
                    "学校近接エリアを通過する可能性があります。歩行者安全と時間帯配慮を確認してください。",
                    10,
                    feature,
                    "発注者・現地確認",
                )
            )

        if feature.feature_type == "hospital":
            risks.append(
                _risk(
                    "RR-HOSPITAL-001",
                    RiskLevel.caution,
                    "病院周辺注意",
                    "病院近接エリアを通過する可能性があります。騒音、待機、右左折、緊急車両動線への影響を確認してください。",
                    10,
                    feature,
                    "発注者・現地確認",
                )
            )

        if feature.feature_type == "residential":
            risks.append(
                _risk(
                    "RR-RESIDENTIAL-001",
                    RiskLevel.caution,
                    "住宅地通過注意",
                    "住宅地通過比率が高い可能性があります。時間帯、騒音、待機場所、誘導員配置を確認してください。",
                    12,
                    feature,
                    "発注者・協力会社・現地確認",
                )
            )

        if feature.feature_type == "traffic":
            risks.append(
                _risk(
                    "RR-TRAFFIC-001",
                    RiskLevel.caution,
                    "交通量注意",
                    "交通量が多い区間を通過する可能性があります。ピーク時間帯の搬入可否と待機場所を確認してください。",
                    12,
                    feature,
                    "協力会社・現地確認",
                )
            )

        if feature.feature_type == "disaster":
            risks.append(
                _risk(
                    "RR-DISASTER-001",
                    RiskLevel.caution,
                    "災害リスク区域近接",
                    "浸水・土砂等の災害リスク区域に近接する可能性があります。搬入日程と気象・防災情報を確認してください。",
                    10,
                    feature,
                    "発注者・防災情報・現地確認",
                )
            )

    if project.vehicle.height_m is None:
        risks.append(
            _risk(
                "RR-HEIGHT-001",
                RiskLevel.data_insufficient,
                "車両高さ未入力",
                "車両全高が未入力です。高さ制限やアンダーパス確認の精度が不足します。",
                10,
                None,
                "協力会社",
            )
        )
    if project.vehicle.gross_weight_t is None:
        risks.append(
            _risk(
                "RR-WEIGHT-001",
                RiskLevel.data_insufficient,
                "車両総重量未入力",
                "車両総重量が未入力です。橋梁・重量制限確認の精度が不足します。",
                10,
                None,
                "協力会社",
            )
        )

    route.risks = risks
    route.risk_score = min(sum(risk.score for risk in risks), 100)
    route.risk_level = _route_level(risks)
    route.summary = _summary(route)
    route.evaluation_status = "evaluated"
    return route


def _source_category(feature: RouteFeature) -> str:
    """Map a feature's source string to the include_sources vocabulary."""

    source = (feature.source or "").lower()
    if "openstreetmap" in source or "overpass" in source:
        return "osm"
    if "xroad" in source:
        return "xroad"
    if "国土数値情報" in source or "ksj" in source:
        return "ksj"
    if "plateau" in source:
        return "plateau"
    return "sample"


def risk_counts(risks: list[RiskItem]) -> dict[str, int]:
    counts = {level.value: 0 for level in RiskLevel}
    for risk in risks:
        counts[risk.level.value] += 1
    return counts


def _route_geometry(start: LocationInput, destination: LocationInput, index: int) -> list[LocationInput]:
    offset = (index - 1.5) * 0.004
    points = [start]
    for step in range(1, 4):
        ratio = step / 4
        points.append(
            LocationInput(
                name=f"route-point-{step}",
                lat=start.lat + (destination.lat - start.lat) * ratio + offset,
                lng=start.lng + (destination.lng - start.lng) * ratio - offset,
            )
        )
    points.append(destination)
    return points


def _risk(
    rule_id: str,
    level: RiskLevel,
    title: str,
    message: str,
    score: int,
    feature: RouteFeature | None,
    confirmation_target: str,
) -> RiskItem:
    evidence = "入力条件とサンプル公開データ重ね合わせに基づく初期検討"
    if feature:
        evidence = f"{feature.source} / 品質ランク {feature.data_quality.value} / {feature.acquired_at.isoformat()}"
    return RiskItem(
        id=new_id("risk"),
        rule_id=rule_id,
        level=level,
        title=title,
        message=message,
        score=score,
        feature=feature,
        confirmation_target=confirmation_target,
        evidence=evidence,
    )


def _route_level(risks: list[RiskItem]) -> RiskLevel:
    levels = {risk.level for risk in risks}
    if RiskLevel.exclusion_consideration in levels:
        return RiskLevel.exclusion_consideration
    if RiskLevel.confirm_required in levels:
        return RiskLevel.confirm_required
    if RiskLevel.data_insufficient in levels:
        return RiskLevel.data_insufficient
    if RiskLevel.caution in levels:
        return RiskLevel.caution
    return RiskLevel.candidate


def _summary(route: RouteCandidate) -> str:
    counts = risk_counts(route.risks)
    if route.risk_level == RiskLevel.exclusion_consideration:
        return "公開データ上の不足と車両条件の不整合可能性があり、候補除外も含めた追加確認が必要です。"
    if route.risk_level == RiskLevel.confirm_required:
        return "橋梁・トンネル等の制限情報が不足しており、道路管理者または現地資料で追加確認が必要です。"
    if route.risk_level == RiskLevel.data_insufficient:
        return "判断材料が不足しています。車両条件と道路制限情報を追加してください。"
    if route.risk_level == RiskLevel.caution:
        return f"注意箇所が {counts[RiskLevel.caution.value]} 件あります。時間帯、誘導、周辺影響を確認してください。"
    return "公開データ上の大きな懸念は少ない候補です。ただし正式確認は必要です。"
