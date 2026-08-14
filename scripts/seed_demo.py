"""Idempotent fictional demo-data seed for the Route Planner MVP.

All rows use the ``seed-`` id prefix and are replaced on every run, so the
local demo database can be regenerated at any time:

    python scripts/seed_demo.py           # default DATABASE_URL (./state.db)
    DATABASE_URL=sqlite+aiosqlite:///... python scripts/seed_demo.py

Every person, company, address, site, and coordinate below is fictional.
No production data, secrets, or personally identifiable information is used.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from app.db import async_session
from app.models import (
    DeliveryCondition,
    LocationInput,
    Project,
    ProjectCreate,
    ReportResponse,
    RouteType,
    VehicleCondition,
    now_utc,
)
from app.reporting import render_csv, render_markdown
from app.repository import (
    confirm_route_risk,
    create_audit_log,
    create_project,
    get_project_routes,
    save_report,
    save_routes,
)
from app.risk_engine import evaluate_route, generate_routes

SEED_USERS = [
    ("seed-admin", "佐藤 悟史", "sato.kanri@example.jp", "admin"),
    ("seed-planner", "中村 健三", "nakamura.k@example.jp", "planner"),
    ("seed-site", "田中 亮", "tanaka.r@example.jp", "site_user"),
    ("seed-viewer", "鈴木 恵", "suzuki.m@example.jp", "viewer"),
]


def _location(name: str, lat: float, lng: float, address: str | None = None) -> LocationInput:
    return LocationInput(name=name, lat=lat, lng=lng, address=address)


SEED_PROJECTS: list[dict] = [
    {
        "id": "seed-prj-001",
        "project_name": "第二東名高架下 橋梁架設資材搬入（架空）",
        "site_name": "架空市高架下ヤード",
        "owner_type": "public",
        "planner": "中村 健三",
        "owner": "seed-planner",
        "status_note": "draft",
        "start": _location("架空資材センター", 35.681236, 139.767125, "東京都架空市中央区 1-2-3"),
        "destination": _location("高架下現場ゲート", 35.658581, 139.745433, "東京都架空市南区 4-5-6"),
        "vehicle": VehicleCondition(
            vehicle_type="trailer", length_m=12.0, width_m=2.49, height_m=3.9,
            gross_weight_t=40.0, axle_weight_t=10.0, cargo_type="鋼橋桁部材",
            special_vehicle_flag=True, notes="架空デモ用。実際の橋梁とは無関係。",
        ),
        "delivery": DeliveryCondition(
            delivery_date=None, time_window="daytime", holiday=False, night_delivery_allowed=False
        ),
        "avoid": ["schools"],
        "notes": "架空デモ案件（作成中）。",
    },
    {
        "id": "seed-prj-002",
        "project_name": "臨海埠頭再開発 クローラークレーン回送（架空）",
        "site_name": "架空臨海埠頭 3号ヤード",
        "owner_type": "private",
        "planner": "中村 健三",
        "owner": "seed-planner",
        "status_note": "evaluating",
        "start": _location("架空重機センター", 35.620000, 139.780000, "東京都架空市港湾 9-8-7"),
        "destination": _location("埠頭現場入口", 35.600000, 139.760000, "東京都架空市港湾 10-11-12"),
        "vehicle": VehicleCondition(
            vehicle_type="heavy_equipment_carrier", length_m=18.0, width_m=3.0, height_m=4.0,
            gross_weight_t=60.0, axle_weight_t=14.0, cargo_type="50tクローラークレーン",
            special_vehicle_flag=True, notes="架空デモ用。",
        ),
        "delivery": DeliveryCondition(
            delivery_date=None, time_window="morning_peak", holiday=False, night_delivery_allowed=True
        ),
        "avoid": ["residential", "rail_crossings"],
        "notes": "架空デモ案件（評価中）。",
    },
    {
        "id": "seed-prj-003",
        "project_name": "河川改修 護岸ブロック搬入（架空）",
        "site_name": "架空川 右岸 2.4k",
        "owner_type": "public",
        "planner": "中村 健三",
        "owner": "seed-planner",
        "status_note": "review_required",
        "start": _location("架空ブロック工場", 35.720000, 139.690000, "東京都架空市北区 12-13-14"),
        "destination": _location("右岸施工ヤード", 35.700000, 139.710000, "東京都架空市北区 15-16-17"),
        "vehicle": VehicleCondition(
            vehicle_type="heavy_truck", length_m=11.5, width_m=2.5, height_m=3.7,
            gross_weight_t=32.0, axle_weight_t=10.0, cargo_type="コンクリートブロック",
            special_vehicle_flag=False, notes="架空デモ用。",
        ),
        "delivery": DeliveryCondition(
            delivery_date=None, time_window="daytime", holiday=False, night_delivery_allowed=False
        ),
        "avoid": ["schools", "residential"],
        "notes": "架空デモ案件（レビュー依頼済み）。",
    },
    {
        "id": "seed-prj-004",
        "project_name": "地下鉄延伸工区 セグメント搬入（架空）",
        "site_name": "架空地下鉄 延伸工区立坑",
        "owner_type": "other",
        "planner": "中村 健三",
        "owner": "seed-planner",
        "status_note": "review_required",
        "start": _location("架空セグメントヤード", 35.640000, 139.730000, "東京都架空市中央区 21-22-23"),
        "destination": _location("延伸工区 立坑", 35.655000, 139.750000, "東京都架空市中央区 24-25-26"),
        "vehicle": VehicleCondition(
            vehicle_type="trailer", length_m=16.5, width_m=2.8, height_m=4.2,
            gross_weight_t=45.0, axle_weight_t=12.0, cargo_type="シールドセグメント",
            special_vehicle_flag=True, notes="架空デモ用。",
        ),
        "delivery": DeliveryCondition(
            delivery_date=None, time_window="night", holiday=False, night_delivery_allowed=True
        ),
        "avoid": ["schools", "steep_slopes"],
        "notes": "架空デモ案件（夜間搬入・レビュー依頼済み）。",
    },
    {
        "id": "seed-prj-005",
        "project_name": "造成地A工区 残土搬出（架空）",
        "site_name": "架空造成地 A工区",
        "owner_type": "private",
        "planner": "田中 亮",
        "owner": "seed-site",
        "status_note": "reviewed",
        "start": _location("A工区 搬出ヤード", 35.580000, 139.680000, "東京都架空市南西部 31-32-33"),
        "destination": _location("架空受入地", 35.610000, 139.660000, "東京都架空市南西部 34-35-36"),
        "vehicle": VehicleCondition(
            vehicle_type="heavy_truck", length_m=10.5, width_m=2.5, height_m=3.4,
            gross_weight_t=25.0, axle_weight_t=10.0, cargo_type="建設発生土",
            special_vehicle_flag=False, notes="架空デモ用。",
        ),
        "delivery": DeliveryCondition(
            delivery_date=None, time_window="daytime", holiday=False, night_delivery_allowed=False
        ),
        "avoid": ["residential"],
        "notes": "架空デモ案件（承認済み）。",
    },
    {
        "id": "seed-prj-006",
        "project_name": "山間部トンネル工事 生コン搬入（架空）",
        "site_name": "架空トンネル 坑口",
        "owner_type": "public",
        "planner": "中村 健三",
        "owner": "seed-planner",
        "status_note": "change_requested",
        "start": _location("架空生コン工場", 35.780000, 139.520000, "東京都架空市西部 41-42-43"),
        "destination": _location("トンネル坑口", 35.760000, 139.550000, "東京都架空市西部 44-45-46"),
        "vehicle": VehicleCondition(
            vehicle_type="other", length_m=9.0, width_m=2.5, height_m=3.8,
            gross_weight_t=24.0, axle_weight_t=10.0, cargo_type="生コンクリート",
            special_vehicle_flag=False, notes="架空デモ用。",
        ),
        "delivery": DeliveryCondition(
            delivery_date=None, time_window="morning_peak", holiday=False, night_delivery_allowed=False
        ),
        "avoid": ["steep_slopes"],
        "notes": "架空デモ案件（差戻し）。橋梁資料の再確認待ち。",
    },
    {
        "id": "seed-prj-007",
        "project_name": "駅前広場改修 舗装材搬入（架空）",
        "site_name": "架空駅前広場",
        "owner_type": "public",
        "planner": "田中 亮",
        "owner": "seed-site",
        "status_note": "reviewed",
        "start": _location("架空舗装材倉庫", 35.700000, 139.740000, "東京都架空市東部 51-52-53"),
        "destination": _location("駅前広場 施工エリア", 35.690000, 139.730000, "東京都架空市東部 54-55-56"),
        "vehicle": VehicleCondition(
            vehicle_type="ordinary_truck", length_m=7.5, width_m=2.2, height_m=3.2,
            gross_weight_t=8.0, axle_weight_t=5.0, cargo_type="アスファルト合材",
            special_vehicle_flag=False, notes="架空デモ用。",
        ),
        "delivery": DeliveryCondition(
            delivery_date=None, time_window="evening_peak", holiday=False, night_delivery_allowed=False
        ),
        "avoid": [],
        "notes": "架空デモ案件（承認済み）。",
    },
    {
        "id": "seed-prj-008",
        "project_name": "旧道拡幅 ボックスカルバート搬入（架空）",
        "site_name": "架空旧道 拡幅工区",
        "owner_type": "private",
        "planner": "中村 健三",
        "owner": "seed-planner",
        "status_note": "archived",
        "start": _location("架空PC工場", 35.660000, 139.700000, "東京都架空市中央区 61-62-63"),
        "destination": _location("拡幅工区 受入ヤード", 35.670000, 139.720000, "東京都架空市中央区 64-65-66"),
        "vehicle": VehicleCondition(
            vehicle_type="trailer", length_m=15.0, width_m=2.7, height_m=3.9,
            gross_weight_t=42.0, axle_weight_t=11.0, cargo_type="ボックスカルバート",
            special_vehicle_flag=True, notes="架空デモ用。",
        ),
        "delivery": DeliveryCondition(
            delivery_date=None, time_window="daytime", holiday=False, night_delivery_allowed=False
        ),
        "avoid": ["rail_crossings"],
        "notes": "架空デモ案件（保管・論理削除の例）。",
    },
]

SEED_DATA_SOURCES = [
    ("seed-ds-osm", "OpenStreetMap / Overpass", "osm", "https://overpass-api.de/api/interpreter", "ODbL", "C", "随時", True),
    ("seed-ds-xroad", "xROAD 道路データプラットフォーム", "api", "https://www.xroad.mlit.go.jp/", "利用規約要確認", "B", "要契約", False),
    ("seed-ds-ksj", "国土数値情報", "download", "https://nlftp.mlit.go.jp/", "国交省利用規約", "B", "月次", True),
    ("seed-ds-plateau", "PLATEAU 3D都市モデル", "download", "https://www.mlit.go.jp/plateau/open-data/", "Project PLATEAU利用規約", "B", "随時", False),
    ("seed-ds-traffic", "交通量サンプルオーバーレイ", "sample", None, "サンプル", "E", "評価用", True),
]

SEED_KNOWLEDGE_POINTS = [
    ("seed-kp-001", "bridge", "架空大橋（重量制限 要確認）", "架空の橋梁。管理者台帳で耐荷重を確認する想定。", "D"),
    ("seed-kp-002", "tunnel", "架空トンネル 高さ4.1m", "架空のトンネル。制限高4.1mの標識ありの想定。", "A"),
    ("seed-kp-003", "narrow", "架空市道 狭隘区間", "架空の狭隘区間。有効幅員2.6m・待避所2箇所の想定。", "D"),
    ("seed-kp-004", "school", "架空第一小学校", "架空の小学校。登下校 7:30-8:30 / 15:00-16:00 の想定。", "B"),
    ("seed-kp-005", "hospital", "架空市立総合病院", "架空の病院。救急動線あり。", "B"),
    ("seed-kp-006", "crossing", "架空鉄道 架空踏切", "架空の踏切。朝ピーク遮断時間が長い想定。", "D"),
    ("seed-kp-007", "disaster", "架空川 浸水想定区域", "架空の浸水想定区域。荒天時は搬入延期の想定。", "B"),
    ("seed-kp-008", "traffic", "架空国道 架空交差点", "架空の交差点。朝夕混雑・右折レーン短い想定。", "B"),
]


async def _clear_seed_rows(session) -> None:
    """Remove previous seed rows (children first) so the seed is idempotent."""

    statements = [
        "DELETE FROM risk_comments WHERE risk_id IN (SELECT id FROM route_risks WHERE route_id IN (SELECT id FROM route_candidates WHERE project_id LIKE 'seed-%'))",
        "DELETE FROM route_risks WHERE route_id IN (SELECT id FROM route_candidates WHERE project_id LIKE 'seed-%')",
        "DELETE FROM route_segments WHERE route_id IN (SELECT id FROM route_candidates WHERE project_id LIKE 'seed-%')",
        "DELETE FROM route_candidates WHERE project_id LIKE 'seed-%'",
        "DELETE FROM reports WHERE project_id LIKE 'seed-%'",
        "DELETE FROM audit_logs WHERE project_id LIKE 'seed-%' OR id LIKE 'seed-%'",
        "DELETE FROM vehicle_conditions WHERE project_id LIKE 'seed-%'",
        "DELETE FROM project_locations WHERE project_id LIKE 'seed-%'",
        "DELETE FROM projects WHERE id LIKE 'seed-%'",
        "DELETE FROM users WHERE id LIKE 'seed-%'",
        "DELETE FROM data_source_fetch_logs WHERE data_source_id LIKE 'seed-%'",
        "DELETE FROM public_geo_features WHERE data_source_id LIKE 'seed-%'",
        "DELETE FROM data_sources WHERE id LIKE 'seed-%'",
        "DELETE FROM knowledge_points WHERE id LIKE 'seed-%'",
    ]
    for statement in statements:
        await session.execute(text(statement))
    await session.commit()


async def _seed_users(session) -> None:
    for user_id, display_name, email, role in SEED_USERS:
        await session.execute(
            text(
                "INSERT INTO users (id, display_name, email, role, created_at, updated_at) "
                "VALUES (:id, :display_name, :email, :role, :now, :now)"
            ),
            {"id": user_id, "display_name": display_name, "email": email, "role": role, "now": now_utc()},
        )
    await session.commit()


async def _seed_projects(session) -> tuple[int, int, int]:
    project_count = 0
    route_count = 0
    risk_count = 0
    for spec in SEED_PROJECTS:
        payload = ProjectCreate(
            project_name=spec["project_name"],
            site_name=spec["site_name"],
            owner_type=spec["owner_type"],
            planner=spec["planner"],
            start=spec["start"],
            destination=spec["destination"],
            vehicle=spec["vehicle"],
            delivery=spec["delivery"],
            avoid_conditions=spec["avoid"],
            notes=spec["notes"],
        )
        project: Project = await create_project(session, payload, owner_user_id=spec["owner"])
        await session.execute(
            text("UPDATE projects SET id=:seed_id WHERE id=:generated_id"),
            {"seed_id": spec["id"], "generated_id": project.id},
        )
        # The generated PK is not propagated to children automatically, and
        # PostgreSQL enforces FKs; move every child row to the stable seed id.
        for table in ("project_locations", "vehicle_conditions"):
            await session.execute(
                text(f"UPDATE {table} SET project_id=:seed_id WHERE project_id=:generated_id"),
                {"seed_id": spec["id"], "generated_id": project.id},
            )
        project.id = spec["id"]
        await session.commit()

        routes = generate_routes(
            project,
            [
                RouteType.shortest,
                RouteType.fastest,
                RouteType.arterial_priority,
                RouteType.residential_avoid,
            ],
        )
        for route in routes:
            evaluate_route(project, route)
        await save_routes(session, routes)
        latest = await get_project_routes(session, spec["id"])
        route_count += len(latest)
        risk_count += sum(len(route.risks) for route in latest)

        await save_report(
            session,
            spec["id"],
            ReportResponse(
                project_id=spec["id"],
                format="markdown",
                content=render_markdown(project, latest),
                generated_at=now_utc(),
            ),
            generated_by=spec["owner"],
        )
        await save_report(
            session,
            spec["id"],
            ReportResponse(
                project_id=spec["id"],
                format="csv",
                content=render_csv(project, latest),
                generated_at=now_utc(),
            ),
            generated_by=spec["owner"],
        )

        # Confirm the first confirm_required risk for selected statuses so the
        # workflow screens show real confirmation records.
        for route in latest:
            risk = next((r for r in route.risks if r.level.value == "confirm_required"), None)
            if risk:
                await confirm_route_risk(
                    session, risk.id, user_id="seed-site", status="confirmed", comment="架空デモの現地確認"
                )
                break

        await create_audit_log(
            session,
            action="project_created",
            project_id=spec["id"],
            user_id=spec["owner"],
            user_role="planner" if spec["owner"] != "seed-site" else "site_user",
            details={"source": "demo-seed", "status_note": spec["status_note"]},
            ip_address="127.0.0.1",
            user_agent="scripts/seed_demo.py",
        )
        if spec["status_note"] != "draft":
            await session.execute(
                text("UPDATE projects SET status=:status WHERE id=:id"),
                {"status": spec["status_note"], "id": spec["id"]},
            )
            await session.commit()
        project_count += 1
    return project_count, route_count, risk_count


async def _seed_data_sources(session) -> None:
    for source_id, name, source_type, base_url, license_info, rank, freq, enabled in SEED_DATA_SOURCES:
        await session.execute(
            text(
                "INSERT INTO data_sources (id, name, source_type, base_url, license_info, "
                "reliability_rank, update_frequency, enabled, last_checked_at) "
                "VALUES (:id, :name, :type, :base_url, :license, :rank, :freq, :enabled, :checked)"
            ),
            {
                "id": source_id,
                "name": name,
                "type": source_type,
                "base_url": base_url,
                "license": license_info,
                "rank": rank,
                "freq": freq,
                "enabled": enabled,
                "checked": now_utc(),
            },
        )
    await session.commit()


async def _seed_knowledge_points(session) -> None:
    for point_id, point_type, name, description, rank in SEED_KNOWLEDGE_POINTS:
        await session.execute(
            text(
                "INSERT INTO knowledge_points (id, point_type, name, description, reliability_rank, "
                "registered_by, created_at, updated_at) "
                "VALUES (:id, :type, :name, :description, :rank, :registered_by, :now, :now)"
            ),
            {
                "id": point_id,
                "type": point_type,
                "name": name,
                "description": description,
                "rank": rank,
                "registered_by": "デモ用辞書整備担当",
                "now": now_utc(),
            },
        )
    await session.commit()


async def main() -> int:
    async with async_session() as session:
        await _clear_seed_rows(session)
        await _seed_users(session)
        project_count, route_count, risk_count = await _seed_projects(session)
        await _seed_data_sources(session)
        await _seed_knowledge_points(session)

    print(f"[seed] users={len(SEED_USERS)} projects={project_count} routes={route_count} risks={risk_count}")
    print(f"[seed] data_sources={len(SEED_DATA_SOURCES)} knowledge_points={len(SEED_KNOWLEDGE_POINTS)}")
    print("[seed] demo users: seed-admin / seed-planner / seed-site / seed-viewer")
    print("[seed] done. Rows use the `seed-` prefix and are safe to regenerate.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
