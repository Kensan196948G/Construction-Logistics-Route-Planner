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


def test_whitespace_only_query_is_rejected() -> None:
    # "   " satisfies min_length=1 but is semantically empty; the validator must
    # reject it instead of letting the responder return a generic 200.
    for blank in ("   ", "\t", "　　"):  # spaces, tab, full-width spaces
        response = client.post("/api/knowledge/search", json={"query": blank})
        assert response.status_code == 422, blank


def test_query_is_trimmed_before_search() -> None:
    # A padded query is normalized: the echoed query is trimmed and the topic
    # still matches (leading/trailing whitespace must not defeat keyword search).
    response = client.post("/api/knowledge/search", json={"query": "  橋梁 重量  "})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "橋梁 重量"
    assert "橋梁" in body["answer"]


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


def test_knowledge_search_stays_reachable_when_api_key_is_set(monkeypatch) -> None:
    # The endpoint is intentionally ungated: the embedded UI cannot send the
    # bearer token, so knowledge search must keep working in a keyed deployment.
    monkeypatch.setenv("APP_API_KEY", "secret-key-123456")
    response = client.post("/api/knowledge/search", json={"query": "橋梁 重量"})
    assert response.status_code == 200
    # Contrast: a protected data endpoint still requires the bearer token.
    protected = client.get("/api/admin/data-sources")
    assert protected.status_code == 401
