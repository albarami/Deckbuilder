"""Tests for src/config/settings.py and src/config/models.py."""

import importlib
import os
import sys
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_config():
    """Clear settings cache and reload models before each test."""
    if "src.config.settings" in sys.modules:
        from src.config.settings import get_settings

        get_settings.cache_clear()
    yield
    if "src.config.settings" in sys.modules:
        from src.config.settings import get_settings

        get_settings.cache_clear()
    if "src.config.models" in sys.modules:
        import src.config.models

        importlib.reload(src.config.models)


# ── Settings tests ──


def test_settings_defaults():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-openai-key",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
    }, clear=True):
        from src.config.settings import Settings

        s = Settings()
        assert s.environment == "local"
        assert s.log_level == "DEBUG"
        assert s.local_docs_path == "data test"
        assert s.template_dir == "PROPOSAL_TEMPLATE"
        assert s.output_path == "./output"
        assert s.state_path == "./state"
        assert s.storage_backend == "local"
        assert s.search_backend == "local"
        assert s.state_backend == "local"


def test_settings_loads_api_keys():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test-123",
        "ANTHROPIC_API_KEY": "sk-ant-test-456",
    }, clear=True):
        from src.config.settings import Settings

        s = Settings()
        assert s.openai_api_key.get_secret_value() == "sk-test-123"
        assert s.anthropic_api_key.get_secret_value() == "sk-ant-test-456"


def test_settings_model_name_defaults():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import Settings

        s = Settings()
        assert s.openai_model_gpt54 == "gpt-5.4"
        assert s.anthropic_model_opus == "claude-opus-4-6"
        assert s.anthropic_model_sonnet == "claude-sonnet-4-6"


def test_settings_env_override():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
        "ENVIRONMENT": "production",
        "LOG_LEVEL": "INFO",
    }, clear=True):
        from src.config.settings import Settings

        s = Settings()
        assert s.environment == "production"
        assert s.log_level == "INFO"


def test_get_settings_returns_cached_instance():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


# ── MODEL_MAP tests ──


def test_model_map_has_10_entries():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        import src.config.models

        importlib.reload(src.config.models)
        assert len(src.config.models.MODEL_MAP) == 13


def test_model_map_keys_match_agents():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        import src.config.models

        importlib.reload(src.config.models)
        expected_keys = {
            "context_agent", "retrieval_planner", "retrieval_ranker",
            "analysis_agent", "research_agent", "structure_agent",
            "content_agent", "qa_agent", "conversation_manager",
            "indexing_classifier", "submission_transform_agent",
            "assembly_plan_agent", "external_research_agent",
        }
        assert set(src.config.models.MODEL_MAP.keys()) == expected_keys


def test_model_map_openai_agents_use_gpt():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        import src.config.models

        importlib.reload(src.config.models)
        gpt_agents = [
            "context_agent", "retrieval_planner", "retrieval_ranker",
            "structure_agent", "content_agent", "qa_agent", "indexing_classifier",
        ]
        for agent in gpt_agents:
            assert "gpt" in src.config.models.MODEL_MAP[agent].lower(), f"{agent} should use GPT"


def test_model_map_anthropic_agents_use_claude():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test",
        "ANTHROPIC_API_KEY": "test",
    }, clear=True):
        from src.config.settings import get_settings

        get_settings.cache_clear()
        import src.config.models

        importlib.reload(src.config.models)
        m = src.config.models.MODEL_MAP
        assert "opus" in m["analysis_agent"].lower()
        assert "opus" in m["research_agent"].lower()
        assert "sonnet" in m["conversation_manager"].lower()
