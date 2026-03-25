"""Proposal Language Linter \u2014 deterministic, no LLM.

Scans slide text for non-client-ready language patterns:
placeholders, consultant instructions, workflow commentary,
hedging, meta-language, internal markers, and weak claims.

Speaker notes are NEVER blocking \u2014 capped at WARNING severity.
Only visible text (title, body) can produce BLOCKER issues.
"""

import re
from dataclasses import dataclass

from src.models.enums import LintSeverity
from src.models.slides import SlideObject
from src.models.submission import LanguageLintResult, LintIssue


@dataclass(frozen=True)
class _LintRule:
    """A single lint rule with pattern, severity, and metadata."""

    name: str
    pattern: re.Pattern[str]
    severity: LintSeverity
    suggestion: str = ""


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

_PLACEHOLDER_MARKERS: list[_LintRule] = [
    _LintRule(
        name="placeholder_bracket",
        pattern=re.compile(
            r"\[(?:PLACEHOLDER|TBC|TBD|TO BE CONFIRMED|TO BE DETERMINED"
            r"|TO BE NAMED|INSERT\s|ADD\s)[^\]]*\]",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Replace with actual content or remove",
    ),
    _LintRule(
        name="placeholder_colon",
        pattern=re.compile(
            r"\[PLACEHOLDER:\s*[^\]]*\]",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Replace with actual content",
    ),
]

_CONSULTANT_INSTRUCTIONS: list[_LintRule] = [
    _LintRule(
        name="consultant_instruction",
        pattern=re.compile(
            r"(?:the consultant should|please provide|we need to obtain"
            r"|human must|fill in\b|update with\b|replace with\b"
            r"|add specific\b|obtain certificate)",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Remove internal instruction \u2014 not client-facing",
    ),
]

_WORKFLOW_COMMENTARY: list[_LintRule] = [
    _LintRule(
        name="workflow_commentary",
        pattern=re.compile(
            r"(?:Draft \d|needs review|pending approval|under development"
            r"|work in progress|\bTODO\b|\bFIXME\b|NOTE TO SELF)",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Remove workflow commentary \u2014 not client-facing",
    ),
]

_INTERNAL_MARKERS: list[_LintRule] = [
    _LintRule(
        name="internal_note",
        pattern=re.compile(
            r"\[INTERNAL NOTE:\s*[^\]]*\]",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Move internal note to speaker notes or remove",
    ),
    _LintRule(
        name="internal_marker_bracket",
        pattern=re.compile(
            r"\[(?:GENERAL|SOURCED|INTERNAL|GAP)\]",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Remove internal marker -- not client-facing",
    ),
    _LintRule(
        name="gap_id_visible",
        pattern=re.compile(
            r"\bGAP-\d+\b",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Remove gap ID -- use descriptive text instead",
    ),
    _LintRule(
        name="bd_team_instruction",
        pattern=re.compile(
            r"\[(?:BD team|CRITICAL:|Action Required|Confirm\b|Add\b)[^\]]*\]",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Remove internal instruction -- not client-facing",
    ),
    _LintRule(
        name="generic_filler",
        pattern=re.compile(
            r"Key point \d",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Replace generic filler with specific content",
    ),
    _LintRule(
        name="submission_instruction",
        pattern=re.compile(
            r"(?:(?:needs? |remains? |yet )?to be added\b(?! value| benefit| to (?:the|our|your))"
            r"|(?:must |should |needs? to ).{1,40}before submission"
            r"|no row should remain"
            r"|must be resolved before|unresolved in client version)",
            re.IGNORECASE,
        ),
        severity=LintSeverity.BLOCKER,
        suggestion="Remove submission instruction -- not client-facing",
    ),
]

_HEDGING_LANGUAGE: list[_LintRule] = [
    _LintRule(
        name="hedging",
        pattern=re.compile(
            r"(?:we believe|we think|\bpotentially\b|\bpossibly\b"
            r"|\bmaybe\b|might be able|could potentially|it is possible)",
            re.IGNORECASE,
        ),
        severity=LintSeverity.WARNING,
        suggestion="Use confident, assertive language",
    ),
]

_META_LANGUAGE: list[_LintRule] = [
    _LintRule(
        name="meta_language",
        pattern=re.compile(
            r"(?:this slide shows|as mentioned earlier|as discussed"
            r"|in this proposal|the following slide|on the next page"
            r"|as you can see)",
            re.IGNORECASE,
        ),
        severity=LintSeverity.WARNING,
        suggestion="Remove self-referential language",
    ),
]

_WEAK_CLAIMS: list[_LintRule] = [
    _LintRule(
        name="weak_claim",
        pattern=re.compile(
            r"(?:extensive experience|deep expertise"
            r"|proven track record|industry-leading)",
            re.IGNORECASE,
        ),
        severity=LintSeverity.WARNING,
        suggestion="Replace with specific data or evidence",
    ),
]

_ALL_RULES: list[_LintRule] = (
    _PLACEHOLDER_MARKERS
    + _CONSULTANT_INSTRUCTIONS
    + _WORKFLOW_COMMENTARY
    + _INTERNAL_MARKERS
    + _HEDGING_LANGUAGE
    + _META_LANGUAGE
    + _WEAK_CLAIMS
)

_NOTES_INTERNAL_SKIP_RULES: set[str] = frozenset({
    "placeholder_bracket",
    "placeholder_colon",
    "internal_marker_bracket",
    "gap_id_visible",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lint_text(
    text: str,
    slide_id: str,
    location: str,
    is_speaker_notes: bool = False,
    internal_review_mode: bool = False,
) -> list[LintIssue]:
    """Lint a single text string against all rules.

    Args:
        text: The text to lint.
        slide_id: Slide identifier (S-NNN or "global").
        location: Where in the slide ("title", "bullet 3", "speaker_notes").
        is_speaker_notes: True if this text is from speaker notes.
        internal_review_mode: True if deck is in INTERNAL_REVIEW mode.

    Returns:
        List of LintIssue objects for matches found.
    """
    if not text or not text.strip():
        return []

    issues: list[LintIssue] = []

    for rule in _ALL_RULES:
        # In internal review mode, skip certain rules for speaker notes
        if is_speaker_notes:
            if internal_review_mode:
                if rule.name in _NOTES_INTERNAL_SKIP_RULES:
                    continue

        for match in rule.pattern.finditer(text):
            # Determine severity
            severity = rule.severity
            if is_speaker_notes and severity == LintSeverity.BLOCKER:
                severity = LintSeverity.WARNING

            issues.append(LintIssue(
                slide_id=slide_id,
                location=location,
                matched_text=match.group(),
                rule=rule.name,
                severity=severity,
                suggestion=rule.suggestion,
            ))

    return issues


def lint_slides(
    slides: list[SlideObject],
    internal_review_mode: bool = False,
) -> LanguageLintResult:
    """Lint all slides for non-client-ready language.

    Args:
        slides: List of SlideObject to lint.
        internal_review_mode: True if deck is in INTERNAL_REVIEW mode.

    Returns:
        LanguageLintResult with all issues and summary counts.
    """
    all_issues: list[LintIssue] = []

    for slide in slides:
        slide_id = slide.slide_id

        # Lint title
        all_issues.extend(lint_text(
            slide.title,
            slide_id,
            "title",
            is_speaker_notes=False,
            internal_review_mode=internal_review_mode,
        ))

        # Lint body content bullets
        if slide.body_content:
            for i, element in enumerate(slide.body_content.text_elements):
                all_issues.extend(lint_text(
                    element,
                    slide_id,
                    f"bullet {i + 1}",
                    is_speaker_notes=False,
                    internal_review_mode=internal_review_mode,
                ))

        # Lint speaker notes
        if slide.speaker_notes:
            all_issues.extend(lint_text(
                slide.speaker_notes,
                slide_id,
                "speaker_notes",
                is_speaker_notes=True,
                internal_review_mode=internal_review_mode,
            ))

    # Count severities
    blocker_count = sum(
        1 for issue in all_issues
        if issue.severity == LintSeverity.BLOCKER
    )

    warning_count = sum(
        1 for issue in all_issues
        if issue.severity == LintSeverity.WARNING
    )

    # Client ready only if zero blockers
    is_client_ready = blocker_count == 0

    return LanguageLintResult(
        issues=all_issues,
        blocker_count=blocker_count,
        warning_count=warning_count,
        is_client_ready=is_client_ready,
    )
