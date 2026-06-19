from __future__ import annotations

import csv
from io import StringIO

from app.models import DISCLAIMER, Project, RouteCandidate, RiskLevel
from app.risk_engine import risk_counts


LEVEL_LABELS = {
    RiskLevel.candidate: "利用候補",
    RiskLevel.caution: "注意",
    RiskLevel.confirm_required: "要確認",
    RiskLevel.exclusion_consideration: "除外検討",
    RiskLevel.data_insufficient: "データ不足",
}


def render_markdown(project: Project, routes: list[RouteCandidate]) -> str:
    lines = [
        "# 搬入ルート初期検討メモ",
        "",
        "## 1. 案件概要",
        "",
        f"- 工事件名: {project.project_name}",
        f"- 現場名: {project.site_name}",
        f"- 担当者: {project.planner}",
        f"- 発注者区分: {project.owner_type or '未入力'}",
        f"- 出発地: {project.start.name} ({project.start.lat:.6f}, {project.start.lng:.6f})",
        f"- 到着地: {project.destination.name} ({project.destination.lat:.6f}, {project.destination.lng:.6f})",
        "",
        "## 2. 搬入条件",
        "",
        f"- 車両種別: {project.vehicle.vehicle_type}",
        f"- 全長/全幅/全高: {_value(project.vehicle.length_m, 'm')} / {_value(project.vehicle.width_m, 'm')} / {_value(project.vehicle.height_m, 'm')}",
        f"- 総重量/軸重: {_value(project.vehicle.gross_weight_t, 't')} / {_value(project.vehicle.axle_weight_t, 't')}",
        f"- 積載物: {project.vehicle.cargo_type or '未入力'}",
        f"- 特車該当可能性: {'あり' if project.vehicle.special_vehicle_flag else '未指定'}",
        f"- 搬入日: {project.delivery.delivery_date or '未指定'}",
        f"- 時間帯: {project.delivery.time_window}",
        "",
        "## 3. ルート候補比較",
        "",
        "| 候補 | 距離 | 時間 | 評価 | スコア | 注意 | 要確認 | データ不足 | コメント |",
        "|---|---:|---:|---|---:|---:|---:|---:|---|",
    ]

    for route in routes:
        counts = risk_counts(route.risks)
        lines.append(
            "| "
            f"{route.name} | "
            f"{route.distance_km:.1f} km | "
            f"{route.duration_min} 分 | "
            f"{LEVEL_LABELS[route.risk_level]} | "
            f"{route.risk_score} | "
            f"{counts[RiskLevel.caution.value]} | "
            f"{counts[RiskLevel.confirm_required.value]} | "
            f"{counts[RiskLevel.data_insufficient.value]} | "
            f"{route.summary} |"
        )

    lines.extend(["", "## 4. 主な注意箇所", ""])
    for route in routes:
        lines.extend([f"### {route.name}", ""])
        if not route.risks:
            lines.append("- 評価済みの注意箇所はありません。ただし正式確認は必要です。")
            continue
        for risk in route.risks:
            location = ""
            if risk.feature:
                location = f" / 位置: {risk.feature.lat:.6f}, {risk.feature.lng:.6f}"
            lines.append(
                f"- [{LEVEL_LABELS[risk.level]}] {risk.title}: {risk.message} "
                f"確認先: {risk.confirmation_target}. 根拠: {risk.evidence}{location}"
            )

    lines.extend(
        [
            "",
            "## 5. 追加確認事項",
            "",
            "- 道路管理者へ橋梁、幅員、高さ、重量、時間帯規制の確認",
            "- 警察または関係機関へ道路使用、誘導、時間帯条件の確認",
            "- 協力会社へ車両諸元、待機場所、転回可否、過去通行実績の確認",
            "- 現地踏査で学校、病院、住宅地、交差点、踏切、急勾配の確認",
            "",
            "## 6. 注意文",
            "",
            DISCLAIMER,
        ]
    )
    return "\n".join(lines) + "\n"


def render_csv(project: Project, routes: list[RouteCandidate]) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "project_id",
            "project_name",
            "route_id",
            "route_name",
            "distance_km",
            "duration_min",
            "risk_level",
            "risk_score",
            "risk_title",
            "risk_message",
            "confirmation_target",
            "evidence",
        ]
    )
    for route in routes:
        if not route.risks:
            writer.writerow(
                [
                    project.id,
                    project.project_name,
                    route.id,
                    route.name,
                    route.distance_km,
                    route.duration_min,
                    route.risk_level.value,
                    route.risk_score,
                    "",
                    "",
                    "",
                    "",
                ]
            )
            continue
        for risk in route.risks:
            writer.writerow(
                [
                    project.id,
                    project.project_name,
                    route.id,
                    route.name,
                    route.distance_km,
                    route.duration_min,
                    route.risk_level.value,
                    route.risk_score,
                    risk.title,
                    risk.message,
                    risk.confirmation_target,
                    risk.evidence,
                ]
            )
    return output.getvalue()


def _value(value: float | None, unit: str) -> str:
    return f"{value:g} {unit}" if value is not None else "未入力"
