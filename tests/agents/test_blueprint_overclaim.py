"""Tests for blueprint claim discipline — ensures S07/S12 do not overclaim.

Verifies:
1. S07 key_message does not contain forbidden certainty terms when KG is empty
2. S12 key_message does not contain forbidden certainty terms when KG is empty
3. No blueprint entry contains "100%" when proof is absent
4. The overclaim guard rewrites forbidden terms to conditional language
"""

import re

import pytest

from src.models.knowledge import KnowledgeGraph
from src.models.source_book import (
    SlideBlueprintEntry,
    SourceBook,
)
from src.models.state import DeckForgeState


def _make_overclaiming_blueprints() -> list[SlideBlueprintEntry]:
    """Create blueprints with forbidden overclaim language."""
    return [
        SlideBlueprintEntry(
            slide_number=7,
            section="Why Strategic Gears",
            title="مطابقة القدرات",
            key_message="كل متطلب مغطى بقدرة مثبتة وخبرة مباشرة موثقة",
            purpose="Show SG capabilities",
        ),
        SlideBlueprintEntry(
            slide_number=12,
            section="فريق العمل",
            title="فريق مؤكد",
            key_message="يستوفي كل عضو جميع الشروط الإلزامية — مطابقة 100%",
            purpose="Show team compliance",
        ),
        SlideBlueprintEntry(
            slide_number=1,
            section="Cover",
            title="Cover Slide",
            key_message="Proposal for the RFP",
            purpose="Cover page",
        ),
    ]


# Forbidden patterns for team/capability sections when KG is empty
_FORBIDDEN_PATTERNS = re.compile(
    r"(100%|مطابقة\s*100|يستوفي\s+كل\s+عضو|خبرة\s+مباشرة\s+موثقة|"
    r"مثبتة|كل\s+متطلب\s+مغطى|استيفاء\s+كامل|فريق\s+مؤكد)",
    re.IGNORECASE,
)


class TestBlueprintOverclaimGuard:
    """Test that the Engine 1 guard catches and rewrites overclaimed blueprints."""

    def test_s07_overclaim_rewritten(self):
        """S07 forbidden terms must be rewritten when KG has 0 people."""
        from src.agents.source_book.writer import _engine1_blueprint_overclaim_scan

        source_book = SourceBook(
            slide_blueprints=_make_overclaiming_blueprints(),
        )
        state = DeckForgeState(
            knowledge_graph=KnowledgeGraph(people=[], projects=[], clients=[]),
        )

        result = _engine1_blueprint_overclaim_scan(source_book, state)

        # Find S07-like entry (Why Strategic Gears section)
        s07_entries = [
            bp for bp in result.slide_blueprints
            if "why" in bp.section.lower() or "strategic" in bp.section.lower()
            or "قدرات" in bp.section or "لماذا" in bp.section
        ]
        assert len(s07_entries) > 0, "S07-type entry not found"

        for bp in s07_entries:
            km = bp.key_message or ""
            matches = _FORBIDDEN_PATTERNS.findall(km)
            assert len(matches) == 0, (
                f"S07 still contains forbidden terms: {matches} in: {km[:100]}"
            )

    def test_s12_overclaim_rewritten(self):
        """S12 forbidden terms must be rewritten when KG has 0 people."""
        from src.agents.source_book.writer import _engine1_blueprint_overclaim_scan

        source_book = SourceBook(
            slide_blueprints=_make_overclaiming_blueprints(),
        )
        state = DeckForgeState(
            knowledge_graph=KnowledgeGraph(people=[], projects=[], clients=[]),
        )

        result = _engine1_blueprint_overclaim_scan(source_book, state)

        # Find S12-like entry (team section)
        s12_entries = [
            bp for bp in result.slide_blueprints
            if "فريق" in bp.section or "team" in bp.section.lower()
        ]
        assert len(s12_entries) > 0, "S12-type entry not found"

        for bp in s12_entries:
            km = bp.key_message or ""
            matches = _FORBIDDEN_PATTERNS.findall(km)
            assert len(matches) == 0, (
                f"S12 still contains forbidden terms: {matches} in: {km[:100]}"
            )

    def test_no_100_percent_when_kg_empty(self):
        """No blueprint should contain '100%' when KG is empty."""
        from src.agents.source_book.writer import _engine1_blueprint_overclaim_scan

        source_book = SourceBook(
            slide_blueprints=_make_overclaiming_blueprints(),
        )
        state = DeckForgeState(
            knowledge_graph=KnowledgeGraph(people=[], projects=[], clients=[]),
        )

        result = _engine1_blueprint_overclaim_scan(source_book, state)

        for bp in result.slide_blueprints:
            for field in [bp.title, bp.key_message]:
                if field:
                    assert "100%" not in field, (
                        f"Slide {bp.slide_number} still has '100%': {field[:80]}"
                    )

    def test_non_proof_sections_untouched(self):
        """Cover slide and other non-proof sections should not be modified."""
        from src.agents.source_book.writer import _engine1_blueprint_overclaim_scan

        source_book = SourceBook(
            slide_blueprints=_make_overclaiming_blueprints(),
        )
        state = DeckForgeState(
            knowledge_graph=KnowledgeGraph(people=[], projects=[], clients=[]),
        )

        result = _engine1_blueprint_overclaim_scan(source_book, state)

        cover = [bp for bp in result.slide_blueprints if bp.section == "Cover"]
        assert len(cover) == 1
        assert cover[0].key_message == "Proposal for the RFP"
