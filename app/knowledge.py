"""Deterministic, safety-first knowledge responder.

The Knowledge screen in the UI offers a search box. Rather than depend on an
external LLM, this module returns conservative, rule-based guidance for the
initial route-review context. Two invariants hold for every response:

1. Missing public-data attributes are never treated as "passable" / "no problem".
2. Every answer carries confirmation targets (road administrator, police, etc.).

The output is intentionally generated reference material (reliability tier "E");
it does not assert passability or any permit outcome.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _Rule:
    topic: str
    keywords: tuple[str, ...]
    guidance: str
    targets: tuple[str, ...]


_RULES: tuple[_Rule, ...] = (
    _Rule(
        topic="橋梁・重量制限",
        keywords=("橋", "橋梁", "耐荷重", "重量制限", "総重量", "bridge"),
        guidance=(
            "橋梁を通過する場合、公開データに重量制限の属性が無くても「制限なし」とは"
            "判断しません。設計荷重・耐荷重は道路管理者の台帳・設計図書で確認します。"
        ),
        targets=("道路管理者への橋梁の耐荷重・通行可否・設計図書の照会",),
    ),
    _Rule(
        topic="高さ制限",
        keywords=("トンネル", "アンダーパス", "高架", "高さ", "全高", "制限高", "tunnel"),
        guidance=(
            "トンネル・アンダーパス・高架下は、公開データに制限高の属性が欠けることが"
            "あります。車両全高に余裕を見て、現地標識と道路台帳の両方で確認します。"
        ),
        targets=("現地標識・道路台帳での制限高の確認",),
    ),
    _Rule(
        topic="狭隘道路・幅員",
        keywords=("狭隘", "幅員", "すれ違い", "幅", "narrow"),
        guidance=(
            "幅員属性が無い区間は狭隘の可能性として扱います。有効幅員・待避所・隅切りを"
            "現地で実測し、誘導員配置とすれ違い計画を準備します。"
        ),
        targets=(
            "現地での有効幅員・待避所の実測",
            "協力会社への誘導員手配の確認",
        ),
    ),
    _Rule(
        topic="学校・通学路",
        keywords=("学校", "通学", "登下校", "school"),
        guidance=(
            "学校周辺は登下校時間帯（おおむね 7:30-8:30 / 15:00-16:00）を回避する計画と"
            "し、通学路との重複区間を確認します。"
        ),
        targets=("学校・教育委員会との搬入時間帯の調整",),
    ),
    _Rule(
        topic="病院・救急動線",
        keywords=("病院", "救急", "hospital"),
        guidance=(
            "病院周辺では救急出入口・救急動線を回避し、正面前での停車・待機を避けます。"
            "搬入時間帯は病院運用に合わせて調整します。"
        ),
        targets=("病院との搬入時間帯・動線の調整",),
    ),
    _Rule(
        topic="踏切",
        keywords=("踏切", "鉄道", "crossing"),
        guidance=(
            "踏切は遮断時間と前後の取り回しに注意します。大型車は通過可否と待機位置を"
            "事前に確認します。"
        ),
        targets=("鉄道事業者・警察への踏切通過の協議",),
    ),
    _Rule(
        topic="災害・気象リスク",
        keywords=("災害", "浸水", "土砂", "気象", "河川", "disaster", "flood"),
        guidance=(
            "浸水想定区域・土砂災害警戒区域に近接する場合、荒天時は搬入延期を判断します。"
            "搬入日の気象・河川水位を確認し代替日を準備します。"
        ),
        targets=("搬入日の気象・河川水位の確認と代替日の準備",),
    ),
    _Rule(
        topic="交通量・混雑",
        keywords=("交通量", "渋滞", "ピーク", "混雑", "traffic"),
        guidance=(
            "交通量の多い区間・交差点は朝夕ピークを回避します。右左折負荷の高い箇所は"
            "誘導員と待機場所を確保します。"
        ),
        targets=("警察への交通誘導・道路使用許可の協議",),
    ),
    _Rule(
        topic="夜間搬入",
        keywords=("夜間", "深夜", "night"),
        guidance=(
            "夜間搬入は騒音・照明・近隣への影響に配慮します。発注者・近隣との合意と、"
            "夜間作業の可否確認が前提です。"
        ),
        targets=("発注者・近隣との夜間搬入の合意",),
    ),
    _Rule(
        topic="特殊車両通行許可",
        keywords=("特殊車両", "特車", "通行許可", "許可", "special"),
        guidance=(
            "寸法・重量が一般制限値を超える場合は特殊車両通行許可の対象です。経路・条件"
            "付き許可の有無を事前に確認します。"
        ),
        targets=(
            "道路管理者への特殊車両通行許可の申請・確認",
            "警察への道路使用許可の確認",
        ),
    ),
)

# Confirmation targets appended to every answer, regardless of matched topics.
_BASE_TARGETS: tuple[str, ...] = (
    "道路管理者（国・県・市）への通行可否・道路占用の確認",
    "警察署交通課への道路使用許可・交通誘導の協議",
    "協力会社・運送会社への通行実績・誘導員の確認",
)

_INTRO = "公開データに基づく初期検討の参考情報です。通行可否や各種許可は保証しません。"

_NO_MATCH = (
    "該当する具体的な論点を特定できませんでした。一般に、公開データに制限属性が無い"
    "場合も「問題なし」とは扱わず、現地確認と関係機関への照会を前提に計画します。"
)

_MAX_TARGETS = 6


def search_knowledge(query: str) -> dict[str, object]:
    """Return safety-first guidance for ``query``.

    The result is a plain dict with ``answer`` (str) and ``confirmation_targets``
    (list[str], always non-empty).
    """

    text = (query or "").strip()
    lowered = text.lower()
    matched = [
        rule
        for rule in _RULES
        if any(keyword.lower() in lowered for keyword in rule.keywords)
    ]

    lines = [_INTRO]
    targets: list[str] = []
    if matched:
        for rule in matched:
            lines.append(f"【{rule.topic}】{rule.guidance}")
            for target in rule.targets:
                if target not in targets:
                    targets.append(target)
    else:
        lines.append(_NO_MATCH)

    for target in _BASE_TARGETS:
        if target not in targets:
            targets.append(target)

    return {
        "answer": "\n".join(lines),
        "confirmation_targets": targets[:_MAX_TARGETS],
    }
