from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


DISCLAIMER = (
    "本システムは、公開データに基づく搬入ルートの初期検討支援ツールです。"
    "表示されるルート、注意箇所、リスク評価は、通行可否、特殊車両通行許可、"
    "道路使用許可、道路占用許可、現地安全性を保証するものではありません。"
    "最終判断には、道路管理者、警察、発注者、協力会社、現地確認等による"
    "追加確認を行ってください。"
)


class RiskLevel(StrEnum):
    candidate = "candidate"
    caution = "caution"
    confirm_required = "confirm_required"
    exclusion_consideration = "exclusion_consideration"
    data_insufficient = "data_insufficient"


class RouteType(StrEnum):
    shortest = "shortest"
    fastest = "fastest"
    arterial_priority = "arterial_priority"
    residential_avoid = "residential_avoid"
    bridge_tunnel_caution = "bridge_tunnel_caution"


class DataQuality(StrEnum):
    official = "A"
    public_authority = "B"
    osm = "C"
    internal = "D"
    estimated = "E"


class LocationInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class AvoidPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_m: int = Field(default=300, ge=50, le=3000)
    reason: str | None = Field(default=None, max_length=200)


class VehicleCondition(BaseModel):
    vehicle_type: Literal[
        "ordinary_truck",
        "heavy_truck",
        "trailer",
        "heavy_equipment_carrier",
        "other",
    ] = "heavy_truck"
    length_m: float | None = Field(default=None, gt=0, le=30)
    width_m: float | None = Field(default=None, gt=0, le=5)
    height_m: float | None = Field(default=None, gt=0, le=6)
    gross_weight_t: float | None = Field(default=None, gt=0, le=80)
    axle_weight_t: float | None = Field(default=None, gt=0, le=20)
    cargo_type: str | None = Field(default=None, max_length=200)
    special_vehicle_flag: bool = False
    notes: str | None = Field(default=None, max_length=1000)


class DeliveryCondition(BaseModel):
    delivery_date: date | None = None
    time_window: Literal["morning_peak", "daytime", "evening_peak", "night"] = "daytime"
    holiday: bool = False
    night_delivery_allowed: bool = False


class ProjectCreate(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=200)
    site_name: str = Field(..., min_length=1, max_length=200)
    owner_type: str | None = Field(default=None, max_length=100)
    planner: str = Field(..., min_length=1, max_length=100)
    start: LocationInput
    destination: LocationInput
    vehicle: VehicleCondition = Field(default_factory=VehicleCondition)
    delivery: DeliveryCondition = Field(default_factory=DeliveryCondition)
    avoid_conditions: list[Literal["schools", "residential", "rail_crossings", "steep_slopes"]] = Field(
        default_factory=list
    )
    notes: str | None = Field(default=None, max_length=2000)


class Project(ProjectCreate):
    id: str
    status: Literal["draft", "evaluating", "review_required", "reviewed", "archived"] = "draft"
    created_at: datetime
    updated_at: datetime


class RouteGenerateRequest(BaseModel):
    route_types: list[RouteType] = Field(
        default_factory=lambda: [
            RouteType.shortest,
            RouteType.fastest,
            RouteType.arterial_priority,
            RouteType.residential_avoid,
        ],
        min_length=1,
        max_length=5,
    )
    avoid_points: list[AvoidPoint] = Field(default_factory=list, max_length=20)

    @field_validator("route_types")
    @classmethod
    def unique_route_types(cls, value: list[RouteType]) -> list[RouteType]:
        if len(value) != len(set(value)):
            raise ValueError("route_types must not contain duplicates")
        return value


class RouteFeature(BaseModel):
    id: str
    feature_type: Literal[
        "bridge",
        "tunnel",
        "school",
        "hospital",
        "residential",
        "traffic",
        "disaster",
        "osm_quality",
    ]
    name: str
    lat: float
    lng: float
    source: str
    source_url: str | None = None
    acquired_at: datetime
    data_quality: DataQuality
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class RiskItem(BaseModel):
    id: str
    rule_id: str
    level: RiskLevel
    title: str
    message: str
    score: int = Field(..., ge=0, le=100)
    feature: RouteFeature | None = None
    confirmation_target: str
    evidence: str


class RouteCandidate(BaseModel):
    id: str
    project_id: str
    route_type: RouteType
    name: str
    distance_km: float
    duration_min: int
    geometry: list[LocationInput]
    features: list[RouteFeature] = Field(default_factory=list)
    risk_score: int = 0
    risk_level: RiskLevel = RiskLevel.data_insufficient
    evaluation_status: Literal["pending", "evaluated"] = "pending"
    summary: str = "評価未実行です。"
    risks: list[RiskItem] = Field(default_factory=list)


class RouteGenerateResponse(BaseModel):
    project_id: str
    generated_count: int
    routes: list[RouteCandidate]


class EvaluationRequest(BaseModel):
    evaluation_profile: str = "default_heavy_vehicle_initial_check"
    include_sources: list[Literal["osm", "xroad", "ksj", "plateau", "sample"]] = Field(
        default_factory=lambda: ["osm", "xroad", "ksj", "plateau", "sample"]
    )
    buffer_m: int = Field(default=300, ge=50, le=1000)


class EvaluationResponse(BaseModel):
    route_id: str
    risk_score: int
    risk_level: RiskLevel
    summary: str
    risk_counts: dict[str, int]
    risks: list[RiskItem]


class ReportResponse(BaseModel):
    project_id: str
    format: Literal["markdown", "csv"]
    content: str
    generated_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=400)

    @field_validator("query")
    @classmethod
    def strip_non_blank(cls, value: str) -> str:
        # `min_length=1` alone lets whitespace-only input ("   ") through; the
        # responder then strips it to "" and returns a generic 200. Reject blank
        # queries here so the non-empty contract is enforced (-> 422), and store
        # the trimmed value so the echoed query and search input stay clean.
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


class KnowledgeSearchResponse(BaseModel):
    query: str
    answer: str
    confirmation_targets: list[str]
    # Generated reference guidance is always the lowest reliability tier ("E"),
    # mirroring the "信頼度 E · 要レビュー" badge in the UI.
    reliability: DataQuality = DataQuality.estimated
    disclaimer: str = DISCLAIMER
    generated_at: datetime


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
