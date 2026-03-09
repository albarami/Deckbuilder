"""Shared test configuration — sets dummy API keys for module imports."""

import os

# Set dummy API keys before any agent modules are imported.
# MODEL_MAP is eagerly evaluated at import time, which triggers get_settings().
# Without these, Settings() raises ValidationError for missing required fields.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy-key")
