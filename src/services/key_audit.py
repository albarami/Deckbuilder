"""D3: API key provenance diagnostic.

Prints a masked fingerprint of each API key, its source (.env vs process env),
and whether it is set. MUST be called BEFORE load_dotenv(override=True) to
distinguish .env keys from pre-existing process env keys.

Usage in scripts/source_book_only.py:
    from src.services.key_audit import print_key_diagnostic
    print_key_diagnostic()  # BEFORE load_dotenv
    load_dotenv(override=True)
"""

from __future__ import annotations

import os


def _mask_key(value: str) -> str:
    """Return last 4 chars with prefix mask."""
    if not value or len(value) < 8:
        return "(too short to mask)"
    return f"...{value[-4:]}"


def print_key_diagnostic(env_file: str = ".env") -> dict[str, dict]:
    """Print and return API key provenance before load_dotenv merges sources.

    Returns a dict of key_name -> {source, masked_value}.
    """
    # Read .env file values WITHOUT loading into process env
    dotenv_values: dict[str, str] = {}
    try:
        from dotenv import dotenv_values as _dotenv_values
        dotenv_values = _dotenv_values(env_file) or {}
    except ImportError:
        # If python-dotenv not installed, just check process env
        pass
    except Exception:
        pass

    keys_to_check = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "PERPLEXITY_API_KEY",
        "S2_API_KEY",
    ]

    results: dict[str, dict] = {}
    print("\nAPI Keys:")

    for key_name in keys_to_check:
        in_dotenv = dotenv_values.get(key_name, "")
        in_process = os.environ.get(key_name, "")

        if in_dotenv and in_process:
            source = ".env (overrides process)"
            value = in_dotenv
        elif in_dotenv:
            source = ".env"
            value = in_dotenv
        elif in_process:
            source = "process env"
            value = in_process
        else:
            source = "not set"
            value = ""

        masked = _mask_key(value) if value else "(not set)"
        if source == "not set" and key_name == "S2_API_KEY":
            note = " (using unauthenticated access)"
        else:
            note = ""

        print(f"  {key_name:25s} {source:30s} ({masked}){note}")
        results[key_name] = {"source": source, "masked_value": masked}

    print()
    return results
