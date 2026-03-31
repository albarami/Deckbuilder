"""Agent-level tests for Semantic Scholar service integration points."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.semantic_scholar import (
    MAX_QUERY_WORDS,
    SemanticScholarAPIError,
    SemanticScholarClient,
    shorten_query,
)


def test_shorten_query_handles_long_input() -> None:
    phrases = shorten_query("digital transformation advisory enterprise architecture assessment")
    assert phrases
    assert all(len(p.split()) <= MAX_QUERY_WORDS for p in phrases)


@pytest.mark.asyncio
async def test_search_papers_uses_key_header() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.json = lambda: {"total": 1, "data": []}

    captured: dict = {}

    async def fake_get(url: str, **kwargs: object) -> MagicMock:
        captured["headers"] = kwargs.get("headers")
        return mock_response

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("src.services.semantic_scholar.httpx.AsyncClient", return_value=mock_client):
        client = SemanticScholarClient("my-key")
        await client.search_papers("enterprise architecture assessment")

    assert captured["headers"] == {"x-api-key": "my-key"}


@pytest.mark.asyncio
async def test_403_raises_no_fallback() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("src.services.semantic_scholar.httpx.AsyncClient", return_value=mock_client):
        client = SemanticScholarClient("bad-key")
        with pytest.raises(SemanticScholarAPIError):
            await client.search_papers("enterprise architecture assessment")

    assert mock_client.get.call_count == 1
