from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import (
    AuditLog,
)
from app.db_models import (
    Project as DBProject,
)
from app.db_models import (
    ProjectLocation as DBProjectLocation,
)
from app.db_models import (
    Report as DBReport,
)
from app.db_models import (
    RiskComment as DBRiskComment,
)
from app.db_models import (
    RouteCandidate as DBRouteCandidate,
)
from app.db_models import (
    RouteRisk as DBRouteRisk,
)
from app.db_models import (
    RouteSegment as DBRouteSegment,
)
from app.db_models import (
    User as DBUser,
)
from app.db_models import (
    VehicleCondition as DBVehicleCondition,
)
from app.models import (
    DeliveryCondition,
    LocationInput,
    Project,
    ProjectCreate,
    ReportResponse,
    RiskItem,
    RouteCandidate,
    RouteFeature,
    VehicleCondition,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _db_project_to_pydantic(db: DBProject) -> Project:
    vc = db.vehicle_condition
    start_loc = next((loc for loc in db.locations if loc.location_type == "origin"), None)
    dest_loc = next((loc for loc in db.locations if loc.location_type == "destination"), None)

    delivery = DeliveryCondition(
        delivery_date=db.delivery_date,
        time_window=db.time_window or "daytime",
        holiday=bool(db.holiday),
        night_delivery_allowed=bool(db.night_delivery_allowed),
    )

    return Project(
        id=db.id,
        project_name=db.project_name,
        site_name=db.site_name,
        owner_type=db.owner_type,
        planner=db.planner,
        status=db.status,
        created_at=db.created_at,
        updated_at=db.updated_at,
        start=LocationInput(
            name=start_loc.name if start_loc else "",
            lat=start_loc.lat if start_loc else 0,
            lng=start_loc.lng if start_loc else 0,
            address=start_loc.address if start_loc else None,
        ),
        destination=LocationInput(
            name=dest_loc.name if dest_loc else "",
            lat=dest_loc.lat if dest_loc else 0,
            lng=dest_loc.lng if dest_loc else 0,
            address=dest_loc.address if dest_loc else None,
        ),
        vehicle=VehicleCondition(
            vehicle_type=vc.vehicle_type if vc else "heavy_truck",
            length_m=vc.length_m if vc else None,
            width_m=vc.width_m if vc else None,
            height_m=vc.height_m if vc else None,
            gross_weight_t=vc.gross_weight_t if vc else None,
            axle_weight_t=vc.axle_weight_t if vc else None,
            cargo_type=vc.cargo_type if vc else None,
            special_vehicle_flag=vc.special_vehicle_flag if vc else False,
            notes=vc.notes if vc else None,
        ),
        delivery=delivery,
        avoid_conditions=list(db.avoid_conditions or []),
        notes=db.notes,
    )


def _db_route_to_pydantic(db: DBRouteCandidate) -> RouteCandidate:
    geometry = [
        LocationInput(name=seg.name or f"point-{seg.sort_order}", lat=seg.lat, lng=seg.lng)
        for seg in sorted(db.segments, key=lambda s: s.sort_order)
    ]
    # Feature-less risks (e.g. "車両高さ未入力") have no lat/lng/source and must
    # not be materialized as a RouteFeature: their stored risk_type may be
    # "unknown", which is not a valid RouteFeature.feature_type literal.
    features_by_risk: dict[str, RouteFeature] = {}
    for risk in db.risks:
        if risk.lat is None and risk.lng is None and not risk.source_name:
            continue
        feature_type = (
            risk.risk_type
            if risk.risk_type
            in {
                "bridge",
                "tunnel",
                "school",
                "hospital",
                "residential",
                "traffic",
                "disaster",
                "osm_quality",
            }
            else "osm_quality"
        )
        features_by_risk[risk.id] = RouteFeature(
            id=risk.id,
            feature_type=feature_type,
            name=risk.title,
            lat=risk.lat or 0,
            lng=risk.lng or 0,
            source=risk.source_name or "",
            source_url=risk.source_url,
            acquired_at=risk.fetched_at or _utcnow(),
            data_quality=risk.source_rank or "C",
            attributes={},
        )
    risks = [
        RiskItem(
            id=risk.id,
            rule_id=risk.rule_id,
            level=risk.risk_level,
            title=risk.title,
            message=risk.description,
            score=risk.score,
            feature=features_by_risk.get(risk.id),
            confirmation_target=risk.confirmation_target or "",
            evidence=risk.evidence or "",
            confirmation_status=risk.confirmation_status,
        )
        for risk in db.risks
    ]

    return RouteCandidate(
        id=db.id,
        project_id=db.project_id,
        route_type=db.route_type,
        name=db.name,
        distance_km=db.distance_km,
        duration_min=db.duration_min,
        geometry=geometry,
        features=list(features_by_risk.values()),
        risk_score=db.risk_score,
        risk_level=db.risk_level,
        evaluation_status=db.evaluation_status,
        summary=db.summary or "",
        risks=risks,
    )


def _pydantic_route_to_db(route: RouteCandidate) -> DBRouteCandidate:
    db_route = DBRouteCandidate(
        id=route.id,
        project_id=route.project_id,
        route_type=route.route_type.value,
        name=route.name,
        distance_km=route.distance_km,
        duration_min=route.duration_min,
        risk_score=route.risk_score,
        risk_level=route.risk_level.value,
        evaluation_status=route.evaluation_status,
        summary=route.summary,
    )
    db_route.segments = [
        DBRouteSegment(
            route_id=route.id,
            sort_order=i,
            name=pt.name,
            lat=pt.lat,
            lng=pt.lng,
        )
        for i, pt in enumerate(route.geometry)
    ]
    db_route.risks = [
        DBRouteRisk(
            route_id=route.id,
            rule_id="",
            risk_type=feat.feature_type,
            risk_level="caution",
            title=feat.name,
            description="",
            score=0,
            source_name=feat.source,
            source_rank=feat.data_quality.value,
            lat=feat.lat,
            lng=feat.lng,
            confirmation_target="",
            evidence="",
        )
        for feat in route.features
    ]
    return db_route


async def create_project(
    session: AsyncSession,
    payload: ProjectCreate,
    owner_user_id: str | None = None,
) -> Project:
    now = _utcnow()
    db_project = DBProject(
        project_name=payload.project_name,
        site_name=payload.site_name,
        owner_type=payload.owner_type,
        planner=payload.planner,
        status="draft",
        owner_user_id=owner_user_id,
        delivery_date=payload.delivery.delivery_date,
        time_window=payload.delivery.time_window,
        holiday=payload.delivery.holiday,
        night_delivery_allowed=payload.delivery.night_delivery_allowed,
        avoid_conditions=list(payload.avoid_conditions or []),
        notes=payload.notes,
        created_at=now,
        updated_at=now,
    )
    db_project.locations = [
        DBProjectLocation(
            location_type="origin",
            name=payload.start.name,
            address=payload.start.address,
            lat=payload.start.lat,
            lng=payload.start.lng,
            sort_order=0,
        ),
        DBProjectLocation(
            location_type="destination",
            name=payload.destination.name,
            address=payload.destination.address,
            lat=payload.destination.lat,
            lng=payload.destination.lng,
            sort_order=1,
        ),
    ]
    db_project.vehicle_condition = DBVehicleCondition(
        vehicle_type=payload.vehicle.vehicle_type,
        length_m=payload.vehicle.length_m,
        width_m=payload.vehicle.width_m,
        height_m=payload.vehicle.height_m,
        gross_weight_t=payload.vehicle.gross_weight_t,
        axle_weight_t=payload.vehicle.axle_weight_t,
        cargo_type=payload.vehicle.cargo_type,
        special_vehicle_flag=payload.vehicle.special_vehicle_flag,
        notes=payload.vehicle.notes,
    )
    session.add(db_project)
    await session.commit()
    _ = db_project.vehicle_condition
    _ = db_project.locations
    return _db_project_to_pydantic(db_project)


async def ensure_user(
    session: AsyncSession,
    *,
    user_id: str,
    display_name: str,
    email: str | None,
    role: str,
) -> None:
    """Upsert an authenticated user so project ownership FK holds on PostgreSQL.

    SQLite does not enforce foreign keys by default, so the missing user row
    only surfaced as a 500 on PostgreSQL (asyncpg ForeignKeyViolationError).
    API-key and Entra identities must exist in ``users`` before a project can
    reference ``owner_user_id``.
    """

    stmt = select(DBUser).where(DBUser.id == user_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        session.add(
            DBUser(
                id=user_id,
                display_name=display_name,
                email=email,
                role=role,
            )
        )
        await session.commit()
        return
    if existing.role != role or existing.display_name != display_name:
        existing.role = role
        existing.display_name = display_name
        if email:
            existing.email = email
        await session.commit()


async def get_project(session: AsyncSession, project_id: str) -> Project | None:
    from sqlalchemy.orm import selectinload

    stmt = (
        select(DBProject)
        .where(DBProject.id == project_id)
        .options(
            selectinload(DBProject.locations),
            selectinload(DBProject.vehicle_condition),
        )
    )
    result = await session.execute(stmt)
    db_project = result.scalar_one_or_none()
    if db_project is None:
        return None
    return _db_project_to_pydantic(db_project)


async def list_projects(session: AsyncSession) -> list[Project]:
    from sqlalchemy.orm import selectinload

    stmt = (
        select(DBProject)
        .order_by(DBProject.created_at.desc())
        .options(
            selectinload(DBProject.locations),
            selectinload(DBProject.vehicle_condition),
        )
    )
    result = await session.execute(stmt)
    return [_db_project_to_pydantic(p) for p in result.scalars().all()]


async def update_project_status(session: AsyncSession, project_id: str, status: str) -> None:
    stmt = select(DBProject).where(DBProject.id == project_id)
    result = await session.execute(stmt)
    db_project = result.scalar_one_or_none()
    if db_project:
        db_project.status = status
        db_project.updated_at = _utcnow()
        await session.commit()


async def save_routes(session: AsyncSession, routes: list[RouteCandidate]) -> None:
    """Save a new generation of route candidates for a project.

    Old generations are kept as history (audit trail) instead of being deleted,
    so risk confirmations attached to earlier evaluations are never destroyed.
    List/report queries only expose the latest generation.
    """

    if not routes:
        return
    project_id = routes[0].project_id
    max_generation = await session.scalar(
        select(func.max(DBRouteCandidate.generation)).where(DBRouteCandidate.project_id == project_id)
    )
    generation = (max_generation or 0) + 1
    for route in routes:
        db_route = _pydantic_route_to_db(route)
        db_route.generation = generation
        session.add(db_route)
    await session.commit()


async def get_project_routes(session: AsyncSession, project_id: str) -> list[RouteCandidate]:
    from sqlalchemy.orm import selectinload

    max_generation = (
        select(func.max(DBRouteCandidate.generation))
        .where(DBRouteCandidate.project_id == project_id)
        .scalar_subquery()
    )
    stmt = (
        select(DBRouteCandidate)
        .where(
            DBRouteCandidate.project_id == project_id,
            DBRouteCandidate.generation == max_generation,
        )
        .order_by(DBRouteCandidate.created_at.asc())
        .options(
            selectinload(DBRouteCandidate.segments),
            selectinload(DBRouteCandidate.risks),
        )
    )
    result = await session.execute(stmt)
    return [_db_route_to_pydantic(r) for r in result.scalars().all()]


async def get_route(session: AsyncSession, route_id: str) -> RouteCandidate | None:
    from sqlalchemy.orm import selectinload

    stmt = (
        select(DBRouteCandidate)
        .where(DBRouteCandidate.id == route_id)
        .options(
            selectinload(DBRouteCandidate.segments),
            selectinload(DBRouteCandidate.risks),
        )
    )
    result = await session.execute(stmt)
    db_route = result.scalar_one_or_none()
    if db_route is None:
        return None
    return _db_route_to_pydantic(db_route)


async def update_route(session: AsyncSession, route: RouteCandidate) -> None:
    from sqlalchemy.orm import selectinload

    stmt = (
        select(DBRouteCandidate)
        .where(DBRouteCandidate.id == route.id)
        .options(selectinload(DBRouteCandidate.risks).selectinload(DBRouteRisk.comments))
    )
    result = await session.execute(stmt)
    db_route = result.scalar_one_or_none()
    if db_route is None:
        return

    # Preserve confirmation results across re-evaluations: the risk rows are
    # replaced (new ids, fresh evidence), but a confirmed/needs_review status
    # must not silently disappear. Matching is by rule + feature coordinates,
    # which are stable across evaluations of the same candidate.
    carry = _confirmation_carry_map(db_route.risks)
    for existing_risk in list(db_route.risks):
        await session.delete(existing_risk)

    db_route.risk_score = route.risk_score
    db_route.risk_level = route.risk_level.value
    db_route.evaluation_status = route.evaluation_status
    db_route.summary = route.summary

    for risk in route.risks:
        db_risk = DBRouteRisk(
            id=risk.id,
            route_id=route.id,
            rule_id=risk.rule_id,
            risk_type=risk.feature.feature_type if risk.feature else "unknown",
            risk_level=risk.level.value,
            title=risk.title,
            description=risk.message,
            score=risk.score,
            source_name=risk.feature.source if risk.feature else None,
            source_rank=risk.feature.data_quality.value if risk.feature else None,
            lat=risk.feature.lat if risk.feature else None,
            lng=risk.feature.lng if risk.feature else None,
            confirmation_target=risk.confirmation_target,
            evidence=risk.evidence,
        )
        carried = carry.get(_risk_carry_key(risk.rule_id, risk.feature))
        if carried:
            db_risk.confirmation_status = carried["status"]
            if carried["comment"]:
                db_risk.comments.append(
                    DBRiskComment(
                        user_id=carried["user_id"] or "system",
                        comment=f"[再評価により確認状態を引き継ぎ] {carried['comment']}",
                        confirmation_result=carried["status"],
                        created_at=_utcnow(),
                    )
                )
        session.add(db_risk)
    await session.commit()
    # The route object may already be in this session's identity map with a
    # stale ``risks`` collection (old primary keys). Expire everything so the
    # next read from the same session returns the freshly replaced rows.
    session.expire_all()


def _confirmation_carry_map(risks: list[DBRouteRisk]) -> dict[tuple, dict]:
    """Map stable risk keys to their latest confirmation state."""

    carry: dict[tuple, dict] = {}
    for risk in risks:
        if risk.confirmation_status in (None, "", "unconfirmed"):
            continue
        key = (
            risk.rule_id or "",
            risk.risk_type or "",
            round(risk.lat or 0.0, 6),
            round(risk.lng or 0.0, 6),
        )
        latest_comment = None
        if risk.comments:
            latest_comment = max(risk.comments, key=lambda c: c.created_at or _utcnow())
        carry[key] = {
            "status": risk.confirmation_status,
            "comment": latest_comment.comment if latest_comment else "",
            "user_id": latest_comment.user_id if latest_comment else None,
        }
    return carry


def _risk_carry_key(rule_id: str, feature) -> tuple:
    """Build the same stable key used by _confirmation_carry_map."""

    return (
        rule_id or "",
        feature.feature_type if feature else "unknown",
        round(feature.lat if feature else 0.0, 6),
        round(feature.lng if feature else 0.0, 6),
    )


async def create_audit_log(
    session: AsyncSession,
    action: str,
    project_id: str | None,
    user_id: str,
    user_role: str,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    log = AuditLog(
        project_id=project_id,
        user_id=user_id,
        user_role=user_role,
        action=action,
        target_type="project",
        target_id=project_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(log)
    await session.commit()


async def confirm_route_risk(
    session: AsyncSession,
    risk_id: str,
    user_id: str,
    status: str,
    comment: str,
) -> dict:
    """Update a risk's confirmation status and append a confirmation comment."""

    stmt = select(DBRouteRisk).where(DBRouteRisk.id == risk_id)
    result = await session.execute(stmt)
    db_risk = result.scalar_one_or_none()
    if db_risk is None:
        raise KeyError(risk_id)

    now = _utcnow()
    db_risk.confirmation_status = status
    session.add(
        DBRiskComment(
            risk_id=risk_id,
            user_id=user_id,
            comment=comment,
            confirmation_result=status,
            created_at=now,
        )
    )
    await session.commit()
    return {
        "risk_id": risk_id,
        "status": status,
        "confirmed_by": user_id,
        "comment": comment,
        "confirmed_at": now,
    }


async def list_audit_logs(session: AsyncSession, limit: int = 100) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    logs = []
    for log in result.scalars().all():
        logs.append(
            {
                "id": log.id,
                "project_id": log.project_id,
                "user_id": log.user_id,
                "user_role": log.user_role,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "created_at": log.created_at,
            }
        )
    return logs


async def save_report(
    session: AsyncSession,
    project_id: str,
    report_response: ReportResponse,
    generated_by: str | None = None,
) -> None:
    report = DBReport(
        project_id=project_id,
        report_type="route_comparison",
        format=report_response.format,
        content=report_response.content,
        generated_by=generated_by,
        generated_at=report_response.generated_at,
    )
    session.add(report)
    await session.commit()
