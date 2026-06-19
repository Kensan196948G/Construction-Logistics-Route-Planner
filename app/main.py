from __future__ import annotations

import os
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.knowledge import search_knowledge
from app.models import (
    DISCLAIMER,
    EvaluationRequest,
    EvaluationResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    Project,
    ProjectCreate,
    ReportResponse,
    RouteCandidate,
    RouteGenerateRequest,
    RouteGenerateResponse,
    new_id,
    now_utc,
)
from app.reporting import render_csv, render_markdown
from app.risk_engine import evaluate_route, generate_routes, risk_counts


app = FastAPI(
    title="Construction Logistics Route Planner",
    version="0.1.0",
    description="Initial route risk review API for construction logistics planning.",
)

PROJECTS: dict[str, Project] = {}
ROUTES: dict[str, RouteCandidate] = {}


def require_api_key(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("APP_API_KEY")
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid Authorization bearer token is required.",
        )


ApiKey = Depends(require_api_key)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "construction-logistics-route-planner",
        "version": "0.1.0",
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/projects", dependencies=[ApiKey])
def list_projects() -> list[Project]:
    return sorted(PROJECTS.values(), key=lambda project: project.created_at, reverse=True)


@app.post("/api/projects", status_code=status.HTTP_201_CREATED, dependencies=[ApiKey])
def create_project(payload: ProjectCreate, request: Request) -> Project:
    now = now_utc()
    project = Project(
        **payload.model_dump(),
        id=new_id("prj"),
        created_at=now,
        updated_at=now,
    )
    PROJECTS[project.id] = project
    _audit("project_created", project.id, request)
    return project


@app.get("/api/projects/{project_id}", dependencies=[ApiKey])
def get_project(project_id: str) -> Project:
    return _project(project_id)


@app.post("/api/projects/{project_id}/routes/generate", dependencies=[ApiKey])
def generate_project_routes(project_id: str, payload: RouteGenerateRequest, request: Request) -> RouteGenerateResponse:
    project = _project(project_id)
    project.status = "evaluating"
    project.updated_at = now_utc()
    routes = generate_routes(project, payload.route_types)
    for route in routes:
        ROUTES[route.id] = route
    _audit("routes_generated", project_id, request, {"count": len(routes)})
    return RouteGenerateResponse(project_id=project_id, generated_count=len(routes), routes=routes)


@app.get("/api/projects/{project_id}/routes", dependencies=[ApiKey])
def list_project_routes(project_id: str) -> list[RouteCandidate]:
    _project(project_id)
    return [route for route in ROUTES.values() if route.project_id == project_id]


@app.get("/api/routes/{route_id}", dependencies=[ApiKey])
def get_route(route_id: str) -> RouteCandidate:
    return _route(route_id)


@app.post("/api/routes/{route_id}/evaluate", dependencies=[ApiKey])
def evaluate_project_route(route_id: str, payload: EvaluationRequest, request: Request) -> EvaluationResponse:
    route = _route(route_id)
    project = _project(route.project_id)
    evaluated = evaluate_route(project, route, payload)
    ROUTES[route_id] = evaluated
    project.status = "review_required"
    project.updated_at = now_utc()
    _audit("route_evaluated", route.project_id, request, {"route_id": route_id})
    return EvaluationResponse(
        route_id=route_id,
        risk_score=evaluated.risk_score,
        risk_level=evaluated.risk_level,
        summary=evaluated.summary,
        risk_counts=risk_counts(evaluated.risks),
        risks=evaluated.risks,
    )


@app.get("/api/routes/{route_id}/risks", dependencies=[ApiKey])
def list_route_risks(route_id: str):
    return _route(route_id).risks


@app.get("/api/projects/{project_id}/report", dependencies=[ApiKey])
def project_report(project_id: str, format: Literal["markdown", "csv"] = "markdown") -> ReportResponse:
    project = _project(project_id)
    routes = [route for route in ROUTES.values() if route.project_id == project_id]
    if not routes:
        raise HTTPException(status_code=409, detail="Generate routes before requesting a report.")
    for route in routes:
        if route.evaluation_status != "evaluated":
            evaluate_route(project, route)
    content = render_markdown(project, routes) if format == "markdown" else render_csv(project, routes)
    return ReportResponse(project_id=project_id, format=format, content=content, generated_at=now_utc())


@app.get("/api/admin/data-sources", dependencies=[ApiKey])
def data_sources() -> list[dict[str, str]]:
    return [
        {
            "id": "sample-osm",
            "name": "OpenStreetMap sample overlay",
            "status": "stub",
            "note": "MVPでは外部APIを呼ばず、属性不足を安全側に評価します。",
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


@app.post("/api/knowledge/search", dependencies=[ApiKey])
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


def _project(project_id: str) -> Project:
    project = PROJECTS.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _route(route_id: str) -> RouteCandidate:
    route = ROUTES.get(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found.")
    return route


def _audit(action: str, subject_id: str, request: Request, details: dict | None = None) -> None:
    user = request.headers.get("x-user-id", "anonymous")
    role = request.headers.get("x-user-role", "planner")
    request.app.state.last_audit_event = {
        "action": action,
        "subject_id": subject_id,
        "user": user,
        "role": role,
        "details": details or {},
        "created_at": now_utc().isoformat(),
    }
