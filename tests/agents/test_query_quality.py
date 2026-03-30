"""Tests for query quality — ensures generated queries meet proposal-grade standards.

Verifies:
1. No raw RFP text copy-paste ("best practices for...")
2. No noun dumps ("priorities needs, assessing current state services")
3. No trailing commas
4. No queries shorter than 5 meaningful words (unless deliberate exact terms)
5. All queries are readable English research questions
"""

import pytest

from src.models.rfp import BilingualText, Deliverable, RFPContext, ScopeItem
from src.models.state import DeckForgeState


def _make_sipa_state() -> DeckForgeState:
    """Create a state with SIPA-like RFP context for query generation testing."""
    scope_items = [
        ScopeItem(id="S1", category="analysis", description=BilingualText(
            en="Analyze priorities and identify needs, including assessment of current services, benchmarking, identifying gaps, and developing company segmentation criteria",
            ar="تحليل الأولويات وتحديد الاحتياج",
        )),
        ScopeItem(id="S2", category="design", description=BilingualText(
            en="Design a supporting service ecosystem for international expansion, including developing a service portfolio, service models, operating model, SLAs, and KPIs",
            ar="تصميم منظومة خدمات داعمة للتوسع الخارجي",
        )),
        ScopeItem(id="S3", category="framework", description=BilingualText(
            en="Establish an institutional framework for managing relationships with national companies, including communication channels, roles and responsibilities, and partner ecosystem",
            ar="إطار مؤسسي لإدارة العلاقة مع الشركات الوطنية",
        )),
        ScopeItem(id="S4", category="support", description=BilingualText(
            en="Provide strategic business and international expansion support, including continuous strategic support, activation programs, and capacity building",
            ar="دعم استراتيجي للأعمال والتوسع الخارجي",
        )),
    ]
    deliverables = [
        Deliverable(id="D1", description=BilingualText(
            en="Priorities analysis and needs identification document",
            ar="وثيقة تحليل الأولويات",
        )),
    ]
    rfp = RFPContext(
        rfp_name=BilingualText(en="Service Package Guide for International Expansion", ar="دليل باقة الخدمات"),
        issuing_entity=BilingualText(en="Investment Authority", ar="هيئة الاستثمار"),
        mandate=BilingualText(en="Design and develop a comprehensive guide", ar="تصميم وتطوير دليل شامل"),
        scope_items=scope_items,
        deliverables=deliverables,
    )
    return DeckForgeState(rfp_context=rfp)


class TestQueryQualityPplx:
    """Perplexity query quality tests."""

    def test_no_best_practices_prefix(self):
        from src.agents.external_research.agent import _generate_pplx_queries

        state = _make_sipa_state()
        queries = _generate_pplx_queries(state)

        for q in queries:
            assert "best practices for" not in q.lower(), (
                f"Query contains forbidden 'best practices for' pattern: {q}"
            )

    def test_no_noun_dumps(self):
        from src.agents.external_research.agent import _generate_pplx_queries

        state = _make_sipa_state()
        queries = _generate_pplx_queries(state)

        _KNOWN_BAD = [
            "priorities needs",
            "institutional framework managing relationships national",
            "strategic business international expansion",
        ]
        for q in queries:
            for bad in _KNOWN_BAD:
                assert bad not in q.lower(), (
                    f"Query contains known bad pattern '{bad}': {q}"
                )

    def test_no_trailing_commas(self):
        from src.agents.external_research.agent import _generate_pplx_queries

        state = _make_sipa_state()
        queries = _generate_pplx_queries(state)

        for q in queries:
            assert not q.rstrip().endswith(","), (
                f"Query ends with trailing comma: {q}"
            )

    def test_minimum_word_count(self):
        from src.agents.external_research.agent import _generate_pplx_queries

        state = _make_sipa_state()
        queries = _generate_pplx_queries(state)

        for q in queries:
            words = [w for w in q.split() if len(w) > 2]
            assert len(words) >= 5, (
                f"Query has fewer than 5 meaningful words: {q}"
            )

    def test_queries_are_reformulated(self):
        """Queries must NOT be raw copies of RFP scope text."""
        from src.agents.external_research.agent import _generate_pplx_queries

        state = _make_sipa_state()
        queries = _generate_pplx_queries(state)

        # The first scope item starts with "Analyze priorities..."
        # No query should start with that raw text
        for q in queries:
            assert not q.lower().startswith("analyze priorities"), (
                f"Query is raw RFP text copy: {q}"
            )
            assert not q.lower().startswith("design a supporting"), (
                f"Query is raw RFP text copy: {q}"
            )


class TestQueryQualityS2:
    """Semantic Scholar query quality tests."""

    def test_s2_minimum_word_count(self):
        from src.agents.external_research.agent import _generate_s2_queries

        state = _make_sipa_state()
        queries = _generate_s2_queries(state)

        for q in queries:
            words = [w for w in q.split() if len(w) > 2]
            assert len(words) >= 5, (
                f"S2 query has fewer than 5 meaningful words: {q}"
            )

    def test_s2_no_noun_dumps(self):
        from src.agents.external_research.agent import _generate_s2_queries

        state = _make_sipa_state()
        queries = _generate_s2_queries(state)

        _KNOWN_BAD = [
            "priorities needs",
            "institutional framework managing relationships national",
        ]
        for q in queries:
            for bad in _KNOWN_BAD:
                assert bad not in q.lower(), (
                    f"S2 query contains known bad pattern '{bad}': {q}"
                )
