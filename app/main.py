from __future__ import annotations

import asyncio
import csv
import json
import os
import time
from collections import defaultdict, deque
from io import StringIO
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import OSMOverpassAdapter
from app.auth import UserInfo, get_current_user, require_role
from app.db import engine, get_session
from app.knowledge import search_knowledge
from app.models import (
    DISCLAIMER,
    SAMPLE_DATA_NOTICE,
    AuditLogListResponse,
    EvaluationRequest,
    EvaluationResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    LocationInput,
    Project,
    ProjectCreate,
    ProjectListResponse,
    ProjectUpdate,
    ReportResponse,
    RiskConfirmRequest,
    RiskConfirmResponse,
    RouteCandidate,
    RouteFeature,
    RouteGenerateRequest,
    RouteGenerateResponse,
    WorkflowRequest,
    now_utc,
)
from app.reporting import (
    _csv_safe,
    render_csv,
    render_markdown,
    render_pdf,
    render_xlsx,
)
from app.repository import (
    archive_project,
    confirm_route_risk,
    create_audit_log,
    create_project,
    ensure_user,
    get_project,
    get_project_routes,
    get_route,
    list_audit_logs,
    list_knowledge_points,
    list_projects,
    project_status_counts,
    save_report,
    save_routes,
    update_project,
    update_project_status,
    update_route,
)
from app.risk_engine import evaluate_route, generate_routes, risk_counts
from app.routing import fetch_osrm_routes

app = FastAPI(
    title="Construction Logistics Route Planner",
    version="0.1.0",
    description="Initial route risk review API for construction logistics planning.",
)


DbSession = Annotated[AsyncSession, Depends(get_session)]
AuthenticatedUser = Depends(get_current_user)
PlannerRole = require_role("admin", "planner")
AdminRole = require_role("admin")
ConfirmerRole = require_role("admin", "planner", "site_user")


# Public knowledge search is the only unauthenticated write endpoint; cap it
# per client IP to keep the deterministic responder cheap and abuse-resistant.
_KNOWLEDGE_MAX_REQUESTS = 30
_KNOWLEDGE_WINDOW_SECONDS = 60.0
_KNOWLEDGE_MAX_CLIENTS = 1024
_knowledge_hits: dict[str, deque[float]] = defaultdict(deque)


def _knowledge_rate_allowed(client_ip: str) -> bool:
    now = time.monotonic()
    if client_ip not in _knowledge_hits and len(_knowledge_hits) >= _KNOWLEDGE_MAX_CLIENTS:
        _knowledge_hits.pop(next(iter(_knowledge_hits)))
    window = _knowledge_hits[client_ip]
    while window and now - window[0] > _KNOWLEDGE_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= _KNOWLEDGE_MAX_REQUESTS:
        return False
    window.append(now)
    return True


@app.middleware("http")
async def security_headers_and_limits(request: Request, call_next):
    if request.url.path == "/api/knowledge/search" and request.method == "POST":
        client_ip = request.client.host if request.client else "unknown"
        if not _knowledge_rate_allowed(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "検索リクエストが集中しています。少し待ってから再試行してください。"},
            )
    response = await call_next(request)
    if request.url.path.startswith("/assets/") or request.url.path in {"", "/"}:
        # Static assets change on every deployment. Without an explicit policy
        # Cloudflare's edge may serve a stale copy (default extension-based
        # cache TTL), which previously shipped an old component.js and broke
        # the freshly deployed UI. no-cache keeps revalidation cheap.
        response.headers.setdefault("Cache-Control", "no-cache")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://*.tile.openstreetmap.org; "
        "connect-src 'self'; "
        "base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
    )
    return response


def sample_mode_enabled() -> bool:
    """Whether the deployment is still in PoC/sample mode.

    Route/feature generation is sample-based until real data adapters are wired.
    ``PRODUCTION_MODE=1`` only removes the "sample" wording from API metadata;
    it does not make the generated routes real, so it must be set together with
    the actual data integration work.
    """

    return os.getenv("PRODUCTION_MODE", "").strip().lower() not in {"1", "true", "yes", "on"}


async def _db_healthy() -> tuple[bool, str]:
    """Best-effort database reachability probe for /api/health.

    The check is bounded to ~1.5s so the endpoint never stalls the Docker
    HEALTHCHECK or the external monitor when the database is unreachable.
    """

    try:
        async with asyncio.timeout(1.5):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True, "ok"
    except TimeoutError:
        return False, "timeout"
    except Exception:  # noqa: BLE001 - best-effort probe; any failure means "db error"
        return False, "error"


@app.get("/api/health")
async def health() -> dict[str, object]:
    _, db_status = await _db_healthy()
    return {
        "status": "ok",
        "service": "construction-logistics-route-planner",
        "version": "0.1.0",
        "db": {"status": db_status, "dialect": engine.dialect.name},
        "sample_mode": sample_mode_enabled(),
        "sample_data_notice": SAMPLE_DATA_NOTICE,
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/me")
def api_me(user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
    return user


@app.get("/api/projects", dependencies=[AuthenticatedUser])
async def api_list_projects(
    session: DbSession,
    q: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ProjectListResponse:
    items, total = await list_projects(
        session,
        q=q,
        status=status,
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    return ProjectListResponse(items=items, total=total, limit=limit, offset=offset)


@app.get("/api/projects/stats", dependencies=[AuthenticatedUser])
async def api_project_stats(session: DbSession) -> dict[str, int]:
    return await project_status_counts(session)


@app.post("/api/projects", status_code=status.HTTP_201_CREATED, dependencies=[PlannerRole])
async def api_create_project(
    payload: ProjectCreate,
    request: Request,
    session: DbSession,
    user: Annotated[UserInfo, Depends(get_current_user)],
) -> Project:
    await ensure_user(
        session,
        user_id=user.user_id,
        display_name=user.display_name,
        email=user.email,
        role=user.role,
    )
    project = await create_project(session, payload, owner_user_id=user.user_id)
    await _audit(session, "project_created", project.id, request)
    return project


@app.get("/api/projects/{project_id}", dependencies=[AuthenticatedUser])
async def api_get_project(project_id: str, session: DbSession) -> Project:
    return await _require_project(project_id, session)


@app.patch("/api/projects/{project_id}", dependencies=[PlannerRole])
async def api_update_project(
    project_id: str,
    payload: ProjectUpdate,
    request: Request,
    session: DbSession,
) -> Project:
    project = await _require_project(project_id, session)
    if project.status not in {"draft", "evaluating", "change_requested"}:
        raise HTTPException(
            status_code=409,
            detail="Only draft, evaluating, or change_requested projects can be edited.",
        )
    updated = await update_project(session, project_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    await _audit(session, "project_updated", project_id, request)
    return updated


@app.delete("/api/projects/{project_id}", dependencies=[PlannerRole])
async def api_archive_project(
    project_id: str,
    request: Request,
    session: DbSession,
) -> Project:
    await _require_project(project_id, session)
    archived = await archive_project(session, project_id)
    if archived is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    await _audit(session, "project_archived", project_id, request)
    return archived


@app.post("/api/projects/{project_id}/routes/generate", dependencies=[PlannerRole])
async def api_generate_project_routes(
    project_id: str, payload: RouteGenerateRequest, request: Request, session: DbSession
) -> RouteGenerateResponse:
    project = await _require_project(project_id, session)
    await update_project_status(session, project_id, "evaluating")

    mode = "sample"
    notes: list[str] = []
    routes: list[RouteCandidate] | None = None
    if os.getenv("ROUTING_PROVIDER", "sample").strip().lower() == "osrm":
        routes = await fetch_osrm_routes(
            project_id=project.id,
            start=project.start,
            destination=project.destination,
            route_types=payload.route_types,
        )
        if routes:
            mode = "osrm"
        else:
            notes.append("OSRM実ルート取得に失敗したため、サンプルルートで代替しました。")
    if routes is None:
        routes = generate_routes(project, payload.route_types)

    if os.getenv("OSM_OVERPASS_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}:
        osm_features = await _fetch_osm_project_features(
            project.start, project.destination, radius_m=payload.buffer_m
        )
        if osm_features:
            for route in routes:
                route.features = osm_features
            mode = f"{mode}+osm"
        else:
            notes.append("OSM地物の取得結果が0件だったため、サンプル地物のままです。")

    await save_routes(session, routes)
    await _audit(session, "routes_generated", project_id, request, {"count": len(routes)})
    return RouteGenerateResponse(
        project_id=project_id,
        generated_count=len(routes),
        routes=routes,
        mode=mode,
        notes=notes,
    )


@app.get("/api/projects/{project_id}/routes", dependencies=[AuthenticatedUser])
async def api_list_project_routes(project_id: str, session: DbSession) -> list[RouteCandidate]:
    await _require_project(project_id, session)
    return await get_project_routes(session, project_id)


@app.get("/api/routes/{route_id}", dependencies=[AuthenticatedUser])
async def api_get_route(route_id: str, session: DbSession) -> RouteCandidate:
    return await _require_route(route_id, session)


@app.post("/api/routes/{route_id}/evaluate", dependencies=[PlannerRole])
async def api_evaluate_project_route(
    route_id: str, payload: EvaluationRequest, request: Request, session: DbSession
) -> EvaluationResponse:
    route = await _require_route(route_id, session)
    project = await _require_project(route.project_id, session)
    evaluated = evaluate_route(project, route, payload)
    await update_route(session, evaluated)
    await update_project_status(session, route.project_id, "review_required")
    await _audit(session, "route_evaluated", route.project_id, request, {"route_id": route_id})
    # Re-read from the repository so carried-over confirmation statuses (and
    # any persistence-level defaults) are part of the response contract.
    fresh = await get_route(session, route_id)
    if fresh is not None:
        evaluated = fresh
    return EvaluationResponse(
        route_id=route_id,
        risk_score=evaluated.risk_score,
        risk_level=evaluated.risk_level,
        summary=evaluated.summary,
        risk_counts=risk_counts(evaluated.risks),
        risks=evaluated.risks,
    )


@app.post("/api/routes/{route_id}/risks/{risk_id}/confirm", dependencies=[ConfirmerRole])
async def api_confirm_route_risk(
    route_id: str,
    risk_id: str,
    payload: RiskConfirmRequest,
    request: Request,
    session: DbSession,
    user: Annotated[UserInfo, Depends(get_current_user)],
) -> RiskConfirmResponse:
    route = await _require_route(route_id, session)
    if not any(risk.id == risk_id for risk in route.risks):
        raise HTTPException(status_code=404, detail="Risk not found in route.")
    try:
        confirmed = await confirm_route_risk(
            session=session,
            risk_id=risk_id,
            user_id=user.user_id,
            status=payload.status,
            comment=payload.comment,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Risk not found.")
    await _audit(
        session,
        "risk_confirmed",
        route.project_id,
        request,
        {"route_id": route_id, "risk_id": risk_id, "status": payload.status},
    )
    return RiskConfirmResponse(**confirmed)


@app.post("/api/projects/{project_id}/submit", dependencies=[PlannerRole])
async def api_submit_project(
    project_id: str,
    payload: WorkflowRequest,
    request: Request,
    session: DbSession,
) -> Project:
    await _require_project(project_id, session)
    routes = await get_project_routes(session, project_id)
    if not any(route.evaluation_status == "evaluated" for route in routes):
        raise HTTPException(status_code=409, detail="Evaluate at least one route before submitting.")
    await update_project_status(session, project_id, "review_required")
    await _audit(session, "project_submitted", project_id, request, {"comment": payload.comment})
    return await _require_project(project_id, session)


@app.post("/api/projects/{project_id}/approve", dependencies=[AdminRole])
async def api_approve_project(
    project_id: str,
    payload: WorkflowRequest,
    request: Request,
    session: DbSession,
) -> Project:
    project = await _require_project(project_id, session)
    if project.status not in {"review_required", "change_requested"}:
        raise HTTPException(status_code=409, detail="Only submitted projects can be approved.")
    await update_project_status(session, project_id, "reviewed")
    await _audit(session, "project_approved", project_id, request, {"comment": payload.comment})
    return await _require_project(project_id, session)


@app.post("/api/projects/{project_id}/request-changes", dependencies=[PlannerRole])
async def api_request_project_changes(
    project_id: str,
    payload: WorkflowRequest,
    request: Request,
    session: DbSession,
) -> Project:
    project = await _require_project(project_id, session)
    if project.status not in {"review_required", "evaluating"}:
        raise HTTPException(status_code=409, detail="Only submitted or evaluated projects can be sent back.")
    await update_project_status(session, project_id, "change_requested")
    await _audit(session, "project_changes_requested", project_id, request, {"comment": payload.comment})
    return await _require_project(project_id, session)


@app.get("/api/routes/{route_id}/risks", dependencies=[AuthenticatedUser])
async def api_list_route_risks(route_id: str, session: DbSession):
    route = await _require_route(route_id, session)
    return route.risks


@app.get("/api/projects/{project_id}/report", dependencies=[AuthenticatedUser])
async def api_project_report(
    project_id: str,
    session: DbSession,
    format: Literal["markdown", "csv", "pdf", "xlsx"] = "markdown",
):
    project = await _require_project(project_id, session)
    routes = await get_project_routes(session, project_id)
    if not routes:
        raise HTTPException(status_code=409, detail="Generate routes before requesting a report.")
    for route in routes:
        if route.evaluation_status != "evaluated":
            evaluate_route(project, route)
            await update_route(session, route)
    if format == "pdf":
        pdf_bytes = render_pdf(project, routes)
        await save_report(
            session,
            project_id,
            ReportResponse(project_id=project_id, format="pdf", content="PDF (binary)", generated_at=now_utc()),
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="route-report-{project_id}.pdf"',
            },
        )
    if format == "xlsx":
        xlsx_bytes = render_xlsx(project, routes)
        await save_report(
            session,
            project_id,
            ReportResponse(project_id=project_id, format="xlsx", content="Excel (binary)", generated_at=now_utc()),
        )
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="route-report-{project_id}.xlsx"',
            },
        )
    content = render_markdown(project, routes) if format == "markdown" else render_csv(project, routes)
    report_response = ReportResponse(project_id=project_id, format=format, content=content, generated_at=now_utc())
    await save_report(session, project_id, report_response)
    return report_response


@app.get("/api/admin/audit-logs", dependencies=[AdminRole])
async def api_audit_logs(
    session: DbSession,
    q: str | None = None,
    action: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AuditLogListResponse:
    items, total = await list_audit_logs(
        session,
        q=q,
        action=action,
        user_id=user_id,
        limit=min(max(limit, 1), 500),
        offset=max(offset, 0),
    )
    return AuditLogListResponse(items=items, total=total, limit=limit, offset=offset)


@app.get("/api/admin/audit-logs/export", dependencies=[AdminRole])
async def api_audit_logs_export(session: DbSession, limit: int = 500) -> Response:
    """Admin-only CSV export of the durable audit trail."""

    logs, _ = await list_audit_logs(session, limit=min(max(limit, 1), 5000))
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "created_at",
            "user_id",
            "user_role",
            "action",
            "project_id",
            "target_type",
            "target_id",
            "ip_address",
            "user_agent",
            "details",
        ]
    )
    for log in logs:
        writer.writerow(
            [
                _csv_safe(log["id"] or ""),
                _csv_safe(str(log["created_at"] or "")),
                _csv_safe(log["user_id"] or ""),
                _csv_safe(log["user_role"] or ""),
                _csv_safe(log["action"] or ""),
                _csv_safe(log["project_id"] or ""),
                _csv_safe(log["target_type"] or ""),
                _csv_safe(log["target_id"] or ""),
                _csv_safe(log["ip_address"] or ""),
                _csv_safe(log["user_agent"] or ""),
                _csv_safe(json.dumps(log["details"] or {}, ensure_ascii=False)),
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )


@app.get("/api/facilities", dependencies=[AuthenticatedUser])
async def api_facilities(session: DbSession) -> list[dict]:
    """Durable facilities dictionary (seeded with fictional demo points)."""

    return await list_knowledge_points(session)


@app.get("/api/admin/data-sources", dependencies=[AuthenticatedUser])
def data_sources() -> list[dict[str, str]]:
    routing = os.getenv("ROUTING_PROVIDER", "sample").strip().lower()
    osm_enabled = os.getenv("OSM_OVERPASS_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    return [
        {
            "id": "routing-osrm",
            "name": "OSRM real routing",
            "status": "configured" if routing == "osrm" else "sample",
            "note": "実道路ネットワークによるルート候補生成（低頻度利用）。",
        },
        {
            "id": "sample-osm",
            "name": "OpenStreetMap / Overpass",
            "status": "configured" if osm_enabled else "stub",
            "note": "実地物（橋梁・トンネル・学校・病院）取得。",
        },
        {
            "id": "sample-xroad",
            "name": "xROAD sample overlay",
            "status": "stub",
            "note": "実API接続、キャッシュ、利用条件確認は次フェーズ対象です。",
        },
        {
            "id": "sample-ksj",
            "name": "国土数値情報 sample overlay",
            "status": "stub",
            "note": "施設・災害リスクのサンプル抽出を行います。",
        },
    ]


@app.post("/api/knowledge/search")
def knowledge_search(payload: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    result = search_knowledge(payload.query)
    return KnowledgeSearchResponse(
        query=payload.query,
        answer=str(result["answer"]),
        confirmation_targets=list(result["confirmation_targets"]),
        generated_at=now_utc(),
    )


app.mount("/assets", StaticFiles(directory="app/static"), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


async def _require_project(project_id: str, session: AsyncSession) -> Project:
    project = await get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


async def _require_route(route_id: str, session: AsyncSession) -> RouteCandidate:
    route = await get_route(session, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found.")
    return route


async def _fetch_osm_project_features(
    start: LocationInput, destination: LocationInput, radius_m: int = 500
) -> list[RouteFeature]:
    """Fetch real OSM features around the origin and destination (max 2 requests)."""

    adapter = OSMOverpassAdapter()
    merged: list[RouteFeature] = []
    seen: set[str] = set()
    for point in (start, destination):
        for feature in await adapter.fetch_features(point.lat, point.lng, radius_m):
            if feature.id not in seen:
                seen.add(feature.id)
                merged.append(feature)
    return merged


async def _audit(
    session: AsyncSession, action: str, subject_id: str, request: Request, details: dict | None = None
) -> None:
    if hasattr(request.state, "user"):
        user_id = request.state.user.user_id
        user_role = request.state.user.role
    else:
        # Never derive identity from client-supplied headers; unauthenticated
        # operations are recorded as anonymous only.
        user_id = "anonymous"
        user_role = "planner"
    await create_audit_log(
        session=session,
        action=action,
        project_id=subject_id,
        user_id=user_id,
        user_role=user_role,
        details=details,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
