"""Tests for src/services/perplexity.py — Perplexity API service."""

from unittest.mock import MagicMock, patch

import httpx

from src.services.perplexity import (
    PerplexityResult,
    search_web,
)


class TestSearchWeb:
    def test_empty_query_returns_none(self):
        assert search_web("") is None
        assert search_web("   ") is None

    def test_no_api_key_returns_none(self):
        assert search_web("test query") is None

    @patch("src.services.perplexity.httpx.Client")
    def test_successful_search(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Saudi Arabia's Vision 2030...",
                    },
                },
            ],
            "citations": [
                "https://vision2030.gov.sa",
                "https://example.com/report",
            ],
            "model": "llama-3.1-sonar-large-128k-online",
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = search_web("Saudi Arabia digital", api_key="test-key")
        assert isinstance(result, PerplexityResult)
        assert "Vision 2030" in result.content
        assert len(result.citations) == 2
        assert result.citations[0].url == "https://vision2030.gov.sa"

    @patch("src.services.perplexity.httpx.Client")
    def test_api_error_returns_none(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "unauthorized", request=MagicMock(), response=mock_response,
        )
        mock_client_cls.return_value = mock_client

        result = search_web("test", api_key="bad-key")
        assert result is None

    @patch("src.services.perplexity.httpx.Client")
    def test_connection_error_returns_none(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client_cls.return_value = mock_client

        result = search_web("test", api_key="key")
        assert result is None

    @patch("src.services.perplexity.httpx.Client")
    def test_empty_choices_returns_none(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = search_web("test", api_key="key")
        assert result is None

    @patch("src.services.perplexity.httpx.Client")
    def test_system_context_passed(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "result"}}],
            "citations": [],
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        search_web(
            "test", api_key="key",
            system_context="You are a consulting research assistant",
        )
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {}))
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
