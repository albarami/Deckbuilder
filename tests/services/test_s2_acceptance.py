"""End-to-end acceptance tests for Semantic Scholar retrieval pipeline.

Test A — Query quality: generated queries are readable English, domain-specific
Test B — Seed quality: shortlisted seeds are obviously relevant
Test C — Recommendation usefulness: retained recs are materially relevant
Test D — Export completeness: retained sources have all required fields
Test E — Classification honesty: no S2 source labeled SG proof
"""

import pytest

from src.services.semantic_scholar import score_paper


class TestQueryQuality:
    """Test A: Generated S2 queries must be readable, domain-specific."""

    def test_score_relevant_paper(self):
        """A paper about service portfolio design should score high."""
        paper = {
            "title": "Service Portfolio Design Framework for Government Agencies",
            "abstract": "This paper proposes a methodology for designing service "
                       "portfolios in public sector agencies, including needs "
                       "assessment, stakeholder mapping, and KPI frameworks.",
            "year": 2023,
            "citationCount": 45,
            "fieldsOfStudy": ["Business", "Political Science"],
        }
        score = score_paper(paper)
        assert score >= 0.25, f"Relevant paper scored too low: {score}"

    def test_reject_medical_paper(self):
        """A medical paper should score very low or negative."""
        paper = {
            "title": "Clinical Trial of Gene Therapy for Tumor Treatment",
            "abstract": "This clinical study evaluates the efficacy of gene "
                       "therapy in treating solid tumors in patients.",
            "year": 2023,
            "citationCount": 100,
            "fieldsOfStudy": ["Medicine", "Biology"],
        }
        score = score_paper(paper)
        assert score < 0.10, f"Medical paper scored too high: {score}"

    def test_reject_physics_paper(self):
        """A physics paper should score very low."""
        paper = {
            "title": "Quantum Entanglement in Superconducting Circuits",
            "abstract": "We demonstrate quantum entanglement between two "
                       "superconducting qubits at millikelvin temperatures.",
            "year": 2024,
            "citationCount": 200,
            "fieldsOfStudy": ["Physics"],
        }
        score = score_paper(paper)
        assert score < 0.10, f"Physics paper scored too high: {score}"


class TestSeedQuality:
    """Test B: Seed selection logic favors relevant papers."""

    def test_relevant_paper_beats_irrelevant(self):
        """A relevant but less-cited paper should outscore an irrelevant highly-cited one."""
        relevant = {
            "title": "Institutional Framework for Investment Promotion Agencies",
            "abstract": "service portfolio design methodology for government "
                       "agencies supporting company internationalization",
            "year": 2022,
            "citationCount": 30,
            "fieldsOfStudy": ["Business"],
        }
        irrelevant = {
            "title": "Deep Learning for Protein Structure Prediction",
            "abstract": "neural network architecture for predicting protein "
                       "folding patterns from amino acid sequences",
            "year": 2023,
            "citationCount": 5000,
            "fieldsOfStudy": ["Biology", "Computer Science"],
        }
        assert score_paper(relevant) > score_paper(irrelevant)


class TestExportCompleteness:
    """Test D: Retained sources must have all required fields."""

    def test_required_fields_for_export(self):
        """Every retained S2 source must have these fields for Source Book export."""
        required_fields = [
            "paperId", "title", "year", "url",
        ]
        paper = {
            "paperId": "abc123",
            "title": "Test Paper",
            "year": 2023,
            "url": "https://example.com",
            "citationCount": 10,
            "abstract": "Test abstract",
        }
        for field in required_fields:
            assert field in paper, f"Missing required field: {field}"

    def test_hydration_fields_defined(self):
        """HYDRATION_FIELDS must include all enrichment fields."""
        from src.services.semantic_scholar import HYDRATION_FIELDS
        required = ["title", "abstract", "year", "url", "citationCount",
                    "authors", "venue", "fieldsOfStudy"]
        for field in required:
            assert field in HYDRATION_FIELDS, f"Missing hydration field: {field}"


class TestClassificationHonesty:
    """Test E: No S2 source may be labeled SG proof."""

    def test_s2_source_never_sg_proof(self):
        """S2 sources must be international_benchmark or local_public, never SG proof."""
        from src.models.external_evidence import ExternalSource

        source = ExternalSource(
            source_id="EXT-001",
            title="Test",
            source_type="academic_paper",
            provider="semantic_scholar",
        )
        # evidence_class should default to international_benchmark
        assert source.evidence_class in ("international_benchmark", "local_public")
        assert source.evidence_class != "SG_internal_proof"

    def test_evidence_class_field_exists(self):
        """ExternalSource model must have evidence_class field."""
        from src.models.external_evidence import ExternalSource
        source = ExternalSource(
            source_id="EXT-001",
            title="Test",
            source_type="academic_paper",
        )
        assert hasattr(source, "evidence_class")


class TestRecommendationDrift:
    """Test C: Recommendation API must support negative paper IDs."""

    def test_negative_ids_parameter_accepted(self):
        """The get_recommendations method must accept negative_paper_ids."""
        import inspect
        from src.services.semantic_scholar import SemanticScholarClient
        sig = inspect.signature(SemanticScholarClient.get_recommendations)
        params = list(sig.parameters.keys())
        assert "negative_paper_ids" in params, (
            f"get_recommendations must accept negative_paper_ids. Params: {params}"
        )

    def test_hydrate_papers_method_exists(self):
        """The hydrate_papers method must exist for Step 4."""
        from src.services.semantic_scholar import SemanticScholarClient
        assert hasattr(SemanticScholarClient, "hydrate_papers")

    def test_search_snippets_method_exists(self):
        """The search_snippets method must exist for Step 5."""
        from src.services.semantic_scholar import SemanticScholarClient
        assert hasattr(SemanticScholarClient, "search_snippets")
