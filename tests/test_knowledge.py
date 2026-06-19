from fastapi.testclient import TestClient

from app.knowledge import search_knowledge
from app.main import app


client = TestClient(app)


def test_bridge_query_returns_bridge_guidance_and_targets() -> None:
    response = client.post("/api/knowledge/search", json={"query": "28tトレーラーで橋梁の重量制限は？"})
    assert response.status_code == 200
    body = response.json()
    assert "橋梁" in body["answer"]
    assert body["reliability"] == "E"
    assert "保証するものではありません" in body["disclaimer"]
    assert any("道路管理者" in target for target in body["confirmation_targets"])


def test_unknown_query_still_returns_safe_guidance() -> None:
    response = client.post("/api/knowledge/search", json={"query": "天気はどう？"})
    assert response.status_code == 200
    body = response.json()
    # Even with no topic match, the response must carry confirmation targets.
    assert len(body["confirmation_targets"]) >= 3
    assert "問題なし" in body["answer"]  # appears only as the safety caveat


def test_empty_query_is_rejected() -> None:
    response = client.post("/api/knowledge/search", json={"query": ""})
    assert response.status_code == 422


def test_responder_never_asserts_passability() -> None:
    # The responder must not produce affirmative passability claims for any topic.
    forbidden = ("通行可能です", "通行できます", "問題ありません")
    for query in ("橋梁 重量", "トンネル 高さ", "狭隘 幅員", "学校 通学", "夜間 搬入", "特殊車両 許可"):
        result = search_knowledge(query)
        answer = str(result["answer"])
        assert result["confirmation_targets"], query
        for phrase in forbidden:
            assert phrase not in answer, (query, phrase)


def test_responder_caps_confirmation_targets() -> None:
    # A query that matches several rules must not explode the target list.
    result = search_knowledge("橋梁 トンネル 狭隘 学校 病院 踏切 災害 交通量 夜間 特殊車両")
    assert 0 < len(result["confirmation_targets"]) <= 6
