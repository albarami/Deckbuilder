"""Tests for Semantic Scholar client — auth header and response handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.semantic_scholar import (
    SemanticScholarAPIError,
    SemanticScholarClient,
    keyword_phrases_from_queries,
    normalize_semantic_scholar_api_key,
    reset_semantic_scholar_key_probe_cache,
    resolve_use_x_api_key_header,
)


def test_normalize_api_key_strips_bearer_prefix() -> None:
    assert normalize_semantic_scholar_api_key("Bearer abc123") == "abc123"
    assert normalize_semantic_scholar_api_key("  xyz  ") == "xyz"


def test_keyword_phrases_truncates_long_queries() -> None:
    """Long planner strings should become short 5-word phrases."""
    q = "Provide digital transformation advisory enterprise architecture assessment automation strategy"
    phrases = keyword_phrases_from_queries([q])
    assert len(phrases) == 1
    assert len(phrases[0].split()) <= 5


def test_keyword_phrases_splits_semicolon_sections() -> None:
    phrases = keyword_phrases_from_queries(["alpha beta; gamma delta epsilon zeta eta"])
    assert len(phrases) >= 2


@pytest.mark.asyncio
async def test_search_papers_uses_x_api_key_header() -> None:
    """Bulk search must use x-api-key (Bearer causes 403)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.json = lambda: {
        "data": [
            {
                "paperId": "p1",
                "title": "Paper One",
                "year": 2022,
                "abstract": "Abstract text.",
                "citationCount": 10,
                "url": "https://example.org/p1",
            },
        ],
        "total": 1,
    }

    captured: dict = {}

    async def fake_get(url: str, **kwargs: object) -> MagicMock:
        captured["headers"] = kwargs.get("headers")
        return mock_response

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("src.services.semantic_scholar.httpx.AsyncClient", return_value=mock_client):
        client = SemanticScholarClient("my-secret-key", use_auth_header=True)
        papers = await client.search_papers("digital transformation")

    assert captured.get("headers", {}).get("x-api-key") == "my-secret-key"
    assert papers[0]["paperId"] == "p1"


@pytest.mark.asyncio
async def test_search_papers_403_raises_no_fallback() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "forbidden"

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.services.semantic_scholar.httpx.AsyncClient", return_value=mock_client):
        client = SemanticScholarClient("bad-key", use_auth_header=True)
        with pytest.raises(SemanticScholarAPIError) as exc_info:
            await client.search_papers("test")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_recommendations_posts_json_body() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.json = lambda: {"recommendedPapers": []}

    captured: dict = {}

    async def fake_post(url: str, **kwargs: object) -> MagicMock:
        captured.update(kwargs)
        return mock_response

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=fake_post)

    with patch("src.services.semantic_scholar.httpx.AsyncClient", return_value=mock_client):
        client = SemanticScholarClient("k", use_auth_header=True)
        await client.get_recommendations(["seed1"], max_results=5)

    assert captured["headers"].get("x-api-key") == "k"
    assert captured["json"] == {"positivePaperIds": ["seed1"], "negativePaperIds": []}


@pytest.mark.asyncio
async def test_public_tier_sends_no_auth_header() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.json = lambda: {"data": [], "total": 0}

    captured: dict = {}

    async def fake_get(url: str, **kwargs: object) -> MagicMock:
        captured["headers"] = kwargs.get("headers") or {}
        return mock_response

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("src.services.semantic_scholar.httpx.AsyncClient", return_value=mock_client):
        client = SemanticScholarClient(use_auth_header=False)
        await client.search_papers("q")

    assert captured["headers"] == {}


@pytest.mark.asyncio
async def test_resolve_403_caches_public_tier() -> None:
    reset_semantic_scholar_key_probe_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "forbidden"
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("src.services.semantic_scholar.httpx.AsyncClient", return_value=mock_client):
        assert await resolve_use_x_api_key_header("bad-key") is False
        assert await resolve_use_x_api_key_header("bad-key") is False

    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_resolve_200_uses_auth_header() -> None:
    reset_semantic_scholar_key_probe_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = ""
    mock_resp.json = lambda: {"total": 0, "data": []}
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("src.services.semantic_scholar.httpx.AsyncClient", return_value=mock_client):
        assert await resolve_use_x_api_key_header("good-key") is True
