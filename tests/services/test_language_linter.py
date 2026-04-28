"""Tests for the language linter — deterministic, no LLM."""


from src.models.enums import LintSeverity
from src.services.language_linter import lint_text


class TestInternalNoteDetection:
    """[INTERNAL NOTE:] must be caught as BLOCKER in visible text."""

    def test_internal_note_detected_in_visible_text(self):
        issues = lint_text(
            "[INTERNAL NOTE: This needs client approval before submission]",
            slide_id="S-001",
            location="body",
            is_speaker_notes=False,
        )
        matching = [i for i in issues if i.rule == "internal_note"]
        assert len(matching) == 1
        assert matching[0].severity == LintSeverity.BLOCKER

    def test_internal_note_case_insensitive(self):
        issues = lint_text(
            "[internal note: lowercase version]",
            slide_id="S-001",
            location="body",
            is_speaker_notes=False,
        )
        matching = [i for i in issues if i.rule == "internal_note"]
        assert len(matching) == 1

    def test_internal_note_in_speaker_notes_is_warning(self):
        """Speaker notes never produce BLOCKER — capped at WARNING."""
        issues = lint_text(
            "[INTERNAL NOTE: For presenter only]",
            slide_id="S-001",
            location="speaker_notes",
            is_speaker_notes=True,
        )
        matching = [i for i in issues if i.rule == "internal_note"]
        assert len(matching) == 1
        assert matching[0].severity == LintSeverity.WARNING

    def test_clean_text_no_issues(self):
        issues = lint_text(
            "Our methodology ensures comprehensive coverage.",
            slide_id="S-001",
            location="body",
            is_speaker_notes=False,
        )
        # No internal_note matches
        matching = [i for i in issues if i.rule == "internal_note"]
        assert len(matching) == 0

    def test_internal_note_with_empty_content(self):
        issues = lint_text(
            "[INTERNAL NOTE: ]",
            slide_id="S-001",
            location="title",
            is_speaker_notes=False,
        )
        matching = [i for i in issues if i.rule == "internal_note"]
        assert len(matching) == 1


class TestExistingPlaceholderRules:
    """Existing rules must still work."""

    def test_placeholder_bracket_detected(self):
        issues = lint_text(
            "[PLACEHOLDER: client name]",
            slide_id="S-001",
            location="body",
        )
        matching = [i for i in issues if i.rule == "placeholder_colon"]
        assert len(matching) == 1
        assert matching[0].severity == LintSeverity.BLOCKER

    def test_tbd_detected(self):
        issues = lint_text(
            "[TBD]",
            slide_id="S-001",
            location="body",
        )
        matching = [i for i in issues if i.rule == "placeholder_bracket"]
        assert len(matching) == 1

    def test_gap_id_detected(self):
        issues = lint_text(
            "GAP-0012 needs resolution",
            slide_id="S-001",
            location="body",
        )
        matching = [i for i in issues if i.rule == "gap_id_visible"]
        assert len(matching) == 1
