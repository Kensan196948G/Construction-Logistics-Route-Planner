from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    entra_object_id: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    projects: Mapped[list[Project]] = relationship(back_populates="owner", foreign_keys="Project.owner_user_id")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_name: Mapped[str] = mapped_column(String(200))
    site_name: Mapped[str] = mapped_column(String(200))
    owner_type: Mapped[str | None] = mapped_column(String(100))
    planner: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    transport_purpose: Mapped[str | None] = mapped_column(String(200))
    delivery_date: Mapped[date | None] = mapped_column(Date)
    time_window: Mapped[str | None] = mapped_column(String(50))
    holiday: Mapped[bool] = mapped_column(Boolean, default=False)
    night_delivery_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    avoid_conditions: Mapped[list | None] = mapped_column(JSON)
    planned_date: Mapped[datetime | None] = mapped_column(DateTime)
    planned_time_window: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    owner: Mapped[User | None] = relationship(back_populates="projects", foreign_keys=[owner_user_id])
    locations: Mapped[list[ProjectLocation]] = relationship(back_populates="project", cascade="all, delete-orphan")
    vehicle_condition: Mapped[VehicleCondition | None] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")
    routes: Mapped[list[RouteCandidate]] = relationship(back_populates="project", cascade="all, delete-orphan")
    reports: Mapped[list[Report]] = relationship(back_populates="project", cascade="all, delete-orphan")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectLocation(Base):
    __tablename__ = "project_locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    location_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship(back_populates="locations")


class VehicleCondition(Base):
    __tablename__ = "vehicle_conditions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, unique=True)
    vehicle_type: Mapped[str] = mapped_column(String(50), default="heavy_truck")
    length_m: Mapped[float | None] = mapped_column(Float)
    width_m: Mapped[float | None] = mapped_column(Float)
    height_m: Mapped[float | None] = mapped_column(Float)
    gross_weight_t: Mapped[float | None] = mapped_column(Float)
    axle_weight_t: Mapped[float | None] = mapped_column(Float)
    cargo_type: Mapped[str | None] = mapped_column(String(200))
    special_vehicle_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="vehicle_condition")


class RouteCandidate(Base):
    __tablename__ = "route_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    route_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    distance_km: Mapped[float] = mapped_column(Float)
    duration_min: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(50), default="data_insufficient")
    evaluation_status: Mapped[str] = mapped_column(String(50), default="pending")
    summary: Mapped[str | None] = mapped_column(Text)
    data_quality_summary: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped[Project] = relationship(back_populates="routes")
    segments: Mapped[list[RouteSegment]] = relationship(back_populates="route", cascade="all, delete-orphan")
    risks: Mapped[list[RouteRisk]] = relationship(back_populates="route", cascade="all, delete-orphan")


class RouteSegment(Base):
    __tablename__ = "route_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey("route_candidates.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str | None] = mapped_column(String(100))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)

    route: Mapped[RouteCandidate] = relationship(back_populates="segments")


class RouteRisk(Base):
    __tablename__ = "route_risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey("route_candidates.id"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(50))
    risk_type: Mapped[str] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0)
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_rank: Mapped[str | None] = mapped_column(String(10))
    source_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    confirmation_status: Mapped[str] = mapped_column(String(50), default="unconfirmed")
    confirmation_target: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)

    route: Mapped[RouteCandidate] = relationship(back_populates="risks")
    comments: Mapped[list[RiskComment]] = relationship(back_populates="risk", cascade="all, delete-orphan")


class RiskComment(Base):
    __tablename__ = "risk_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    risk_id: Mapped[str] = mapped_column(String(36), ForeignKey("route_risks.id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36))
    comment: Mapped[str] = mapped_column(Text)
    confirmation_result: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    risk: Mapped[RouteRisk] = relationship(back_populates="comments")


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(50))
    base_url: Mapped[str | None] = mapped_column(Text)
    license_info: Mapped[str | None] = mapped_column(String(200))
    reliability_rank: Mapped[str] = mapped_column(String(10), default="C")
    update_frequency: Mapped[str | None] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fetch_logs: Mapped[list[DataSourceFetchLog]] = relationship(back_populates="data_source", cascade="all, delete-orphan")
    geo_features: Mapped[list[PublicGeoFeature]] = relationship(back_populates="data_source", cascade="all, delete-orphan")


class DataSourceFetchLog(Base):
    __tablename__ = "data_source_fetch_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    data_source_id: Mapped[str] = mapped_column(String(36), ForeignKey("data_sources.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50))
    message: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    data_source: Mapped[DataSource] = relationship(back_populates="fetch_logs")


class PublicGeoFeature(Base):
    __tablename__ = "public_geo_features"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    data_source_id: Mapped[str] = mapped_column(String(36), ForeignKey("data_sources.id"), nullable=False)
    feature_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    attributes: Mapped[dict | None] = mapped_column(JSON)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    data_source: Mapped[DataSource] = relationship(back_populates="geo_features")


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    point_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    reliability_rank: Mapped[str] = mapped_column(String(10), default="D")
    registered_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50))
    format: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    generated_by: Mapped[str | None] = mapped_column(String(36))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped[Project] = relationship(back_populates="reports")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"))
    user_id: Mapped[str | None] = mapped_column(String(100))
    user_role: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(36))
    details: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(50))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped[Project | None] = relationship(back_populates="audit_logs")
