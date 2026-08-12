import pytest
from httpx import AsyncClient

from app.knowledge import search_knowledge


@pytest.mark.asyncio
async def test_bridge_query_returns_bridge_guidance_and_targets(client: AsyncClient) -> None:
    response = await client.post("/api/knowledge/search", json={"query": "28tトレーラーで橋梁の重量制限は？"})
    assert response.status_code == 200
    body = response.json()
    assert "橋梁" in body["answer"]
    assert body["reliability"] == "E"
    assert "保証するものではありません" in body["disclaimer"]
    assert "本番利用禁止" in body["sample_data_notice"]
    assert any("道路管理者" in target for target in body["confirmation_targets"])


@pytest.mark.asyncio
async def test_unknown_query_still_returns_safe_guidance(client: AsyncClient) -> None:
    response = await client.post("/api/knowledge/search", json={"query": "天気はどう？"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["confirmation_targets"]) >= 3
    assert "問題なし" in body["answer"]


@pytest.mark.asyncio
async def test_empty_query_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/knowledge/search", json={"query": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_whitespace_only_query_is_rejected(client: AsyncClient) -> None:
    for blank in ("   ", "\t", "　　"):
        response = await client.post("/api/knowledge/search", json={"query": blank})
        assert response.status_code == 422, blank


@pytest.mark.asyncio
async def test_query_is_trimmed_before_search(client: AsyncClient) -> None:
    response = await client.post("/api/knowledge/search", json={"query": "  橋梁 重量  "})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "橋梁 重量"
    assert "橋梁" in body["answer"]


def test_responder_never_asserts_passability() -> None:
    forbidden = ("通行可能です", "通行できます", "問題ありません")
    for query in ("橋梁 重量", "トンネル 高さ", "狭隘 幅員", "学校 通学", "夜間 搬入", "特殊車両 許可"):
        result = search_knowledge(query)
        answer = str(result["answer"])
        assert result["confirmation_targets"], query
        for phrase in forbidden:
            assert phrase not in answer, (query, phrase)


def test_responder_caps_confirmation_targets() -> None:
    result = search_knowledge("橋梁 トンネル 狭隘 学校 病院 踏切 災害 交通量 夜間 特殊車両")
    assert 0 < len(result["confirmation_targets"]) <= 6


@pytest.mark.asyncio
async def test_knowledge_search_stays_reachable_when_api_key_is_set(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "secret-key-123456")
    response = await client.post("/api/knowledge/search", json={"query": "橋梁 重量"})
    assert response.status_code == 200
    protected = await client.get("/api/admin/data-sources")
    assert protected.status_code == 401
