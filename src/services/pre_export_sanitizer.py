"""Pre-export sanitizer — remove forbidden leakage from client-facing sections.

Runs BEFORE DOCX export. Walks every field of the SourceBook pydantic
model and removes forbidden patterns from client-facing content.

Each removal is recorded as a SanitizationRemoval so the conformance
gate can enforce fail-closed behavior: removing forbidden content does
not make the section "clean" — it makes it "sanitized with gaps."

The gate must treat sanitized sections as having unsupported proof,
not as passing.

No RFP-specific logic. Uses the same forbidden patterns as
artifact_gates.py.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

from pydantic import Field

from src.models.common import DeckForgeBaseModel
from src.services.artifact_gates import FORBIDDEN_ID_PATTERNS, FORBIDDEN_SEMANTIC_PHRASES

logger = logging.getLogger(__name__)

# Compiled from the canonical patterns in artifact_gates.py.
# Single source of truth — no pattern duplication.
# ID patterns are regex-compiled; semantic phrases are plain substring matches.
_FORBIDDEN_ID_COMPILED = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_ID_PATTERNS]
_FORBIDDEN_SEMANTIC = list(FORBIDDEN_SEMANTIC_PHRASES)

# Sections/fields that are internal-only — never sanitized
_INTERNAL_FIELD_NAMES = {
    "internal_gap_appendix",
    "drafting_notes",
    "evidence_gap_register",
    "internal_bid_notes",
}


class SanitizationRemoval(DeckForgeBaseModel):
    """One forbidden pattern removed from a client-facing section."""

    section_path: str
    matched_text: str
    pattern: str
    action: str = "removed"


class SanitizationResult(DeckForgeBaseModel):
    """Result of pre-export sanitization."""

    sanitized: dict[str, Any] = Field(default_factory=dict)
    removals: list[SanitizationRemoval] = Field(default_factory=list)
    total_removals: int = 0


def _has_forbidden(text: str) -> list[tuple[str, str]]:
    """Return list of (pattern_str, matched_text) for forbidden matches."""
    hits: list[tuple[str, str]] = []
    for pat in _FORBIDDEN_ID_COMPILED:
        for m in pat.finditer(text):
            hits.append((pat.pattern, m.group()))
    for phrase in _FORBIDDEN_SEMANTIC:
        if phrase in text:
            hits.append((f"semantic:{phrase}", phrase))
    return hits


def _sanitize_string(
    text: str,
    path: str,
    removals: list[SanitizationRemoval],
) -> str:
    """Remove forbidden patterns from a string. Record each removal."""
    result = text
    # ID patterns (regex)
    for pat in _FORBIDDEN_ID_COMPILED:
        for m in pat.finditer(result):
            removals.append(SanitizationRemoval(
                section_path=path,
                matched_text=m.group(),
                pattern=pat.pattern,
            ))
        result = pat.sub("", result)
    # Semantic phrases (plain substring)
    for phrase in _FORBIDDEN_SEMANTIC:
        if phrase in result:
            removals.append(SanitizationRemoval(
                section_path=path,
                matched_text=phrase,
                pattern=f"semantic:{phrase}",
            ))
            result = result.replace(phrase, "")
    # Clean up leftover brackets/whitespace from removed IDs
    result = re.sub(r"\[\s*\]", "", result)
    result = re.sub(r"\s{2,}", " ", result).strip()
    return result


def _sanitize_list(
    items: list,
    path: str,
    removals: list[SanitizationRemoval],
) -> list:
    """Sanitize each item in a list. Remove items that become empty."""
    result = []
    for i, item in enumerate(items):
        if isinstance(item, str):
            cleaned = _sanitize_string(item, f"{path}[{i}]", removals)
            if cleaned:  # drop items that are entirely forbidden content
                result.append(cleaned)
        elif isinstance(item, dict):
            result.append(_sanitize_dict(item, f"{path}[{i}]", removals))
        elif isinstance(item, list):
            result.append(_sanitize_list(item, f"{path}[{i}]", removals))
        else:
            result.append(item)
    return result


def _sanitize_dict(
    data: dict,
    path: str,
    removals: list[SanitizationRemoval],
) -> dict:
    """Recursively sanitize all string/list values in a dict."""
    result = {}
    for key, value in data.items():
        field_path = f"{path}/{key}" if path else key
        # Skip internal-only fields
        if key in _INTERNAL_FIELD_NAMES:
            result[key] = value
            continue
        if isinstance(value, str):
            result[key] = _sanitize_string(value, field_path, removals)
        elif isinstance(value, list):
            result[key] = _sanitize_list(value, field_path, removals)
        elif isinstance(value, dict):
            result[key] = _sanitize_dict(value, field_path, removals)
        else:
            result[key] = value
    return result


def sanitize_source_book_sections(
    sections: dict[str, Any],
) -> SanitizationResult:
    """Sanitize all client-facing sections of a Source Book dict.

    Args:
        sections: Dict representation of Source Book sections
                  (e.g. from source_book.model_dump()).

    Returns:
        SanitizationResult with sanitized dict and removal records.
    """
    removals: list[SanitizationRemoval] = []
    sanitized = _sanitize_dict(copy.deepcopy(sections), "", removals)
    return SanitizationResult(
        sanitized=sanitized,
        removals=removals,
        total_removals=len(removals),
    )
