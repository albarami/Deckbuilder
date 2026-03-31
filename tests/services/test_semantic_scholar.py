"""Tests for SemanticScholarClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.semantic_scholar import (
    MAX_QUERY_WORDS,
    SemanticScholarAPIError,
    SemanticScholarClient,
    shorten_query,
)


def test_shorten_query_splits_long() -> None:
    """Long text is truncated into <=MAX_QUERY_WORDS-word phrases."""
    result = shorten_query(
        "digital transformation advisory enterprise architecture assessment",
    )
    assert len(result) >= 1
    for phrase in result:
        assert len(phrase.split()) <= MAX_QUERY_WORDS


def test_shorten_query_handles_delimiters() -> None:
    """Semicolons and commas split into multiple phrases."""
    result = shorten_query("AI automation; cloud computing, data analytics")
    assert len(result) == 3


@pytest.mark.asyncio
async def test_search_papers_sends_auth_header() -> None:
    """Search must send x-api-key header."""
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
        papers, total = await client.search_papers("digital transformation government")

    assert captured["headers"] == {"x-api-key": "my-key"}


@pytest.mark.asyncio
async def test_403_raises_error_no_fallback() -> None:
    """403 must raise SemanticScholarAPIError with no anonymous retry."""
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
            await client.search_papers("digital transformation government")

    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_get_recommendations_sends_post() -> None:
    """Recommendations call sends POST with seed paper IDs."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.json = lambda: {"recommendedPapers": []}

    captured: dict = {}

    async def fake_post(url: str, **kwargs: object) -> MagicMock:
        captured["headers"] = kwargs.get("headers")
        captured["json"] = kwargs.get("json")
        return mock_response

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=fake_post)

    with patch("src.services.semantic_scholar.httpx.AsyncClient", return_value=mock_client):
        client = SemanticScholarClient("good-key")
        await client.get_recommendations(["paper1", "paper2"], max_results=20)

    assert captured["headers"] == {"x-api-key": "good-key"}
    assert captured["json"] == {
        "positivePaperIds": ["paper1", "paper2"],
        "negativePaperIds": [],
    }


@pytest.mark.asyncio
async def test_search_and_recommend_two_step() -> None:
    """Two-step flow merges search and recommendation results.

    search_papers returns (papers, total) tuple.
    search_and_recommend returns (papers, per_query_telemetry) tuple.
    """
    client = SemanticScholarClient("good-key")

    with (
        patch.object(
            client,
            "search_papers",
            new=AsyncMock(return_value=(
                [
                    {"paperId": "p1", "citationCount": 10, "title": "Service Portfolio Design"},
                    {"paperId": "p2", "citationCount": 5, "title": "Government Framework"},
                ],
                2,  # total from bulk search
            )),
        ) as mock_search,
        patch.object(
            client,
            "get_recommendations",
            new=AsyncMock(return_value=[
                {"paperId": "p3", "citationCount": 7, "title": "Institutional Model"},
            ]),
        ) as mock_recs,
        patch.object(
            client,
            "hydrate_papers",
            new=AsyncMock(return_value=[]),
        ),
    ):
        merged, telemetry = await client.search_and_recommend(["q1", "q2"])

    ids = {p.get("paperId") for p in merged}
    assert {"p1", "p2", "p3"}.issubset(ids)
    assert mock_search.await_count == 2
    mock_recs.assert_awaited_once()
    assert isinstance(telemetry, dict)


@pytest.mark.asyncio
async def test_search_and_recommend_no_results_returns_empty_tuple() -> None:
    """When S2 finds zero papers, must return ([], {}) not bare [].

    This is the regression test for the crash bug: if search returns
    nothing, the caller unpacks (papers, telemetry) and must not get
    a ValueError from trying to unpack a bare list.
    """
    client = SemanticScholarClient("good-key")

    with patch.object(
        client,
        "search_papers",
        new=AsyncMock(return_value=([], 0)),  # zero papers
    ):
        result = await client.search_and_recommend(["nonexistent gibberish query xyz123"])

    # Must return a tuple of (list, dict), not bare list
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    papers, telemetry = result
    assert papers == []
    assert isinstance(telemetry, dict)
