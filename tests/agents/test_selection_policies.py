"""Tests for Phase 6 — selection_policies.py.

Tests deterministic case study and team member selection with
weighted scoring, auditable results (score + reason), min/max
count enforcement, min-score filtering, and tie-breaking by asset_id.
"""

from __future__ import annotations

import pytest

from src.services.selection_policies import (
    CaseStudySelectionPolicy,
    CaseStudySelectionResult,
    ExcludedAsset,
    SelectedAsset,
    TeamSelectionPolicy,
    TeamSelectionResult,
    select_case_studies,
    select_team_members,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _cs_candidate(
    asset_id: str,
    sector: str = "",
    services: list[str] | None = None,
    geography: str = "",
    technology_keywords: list[str] | None = None,
    capability_tags: list[str] | None = None,
    language: str = "en",
) -> dict:
    return {
        "asset_id": asset_id,
        "sector": sector,
        "services": services or [],
        "geography": geography,
        "technology_keywords": technology_keywords or [],
        "capability_tags": capability_tags or [],
        "language": language,
    }


def _team_candidate(
    asset_id: str,
    sector_experience: list[str] | None = None,
    services: list[str] | None = None,
    role: str = "",
    geography_experience: list[str] | None = None,
    technology_keywords: list[str] | None = None,
    languages: list[str] | None = None,
) -> dict:
    return {
        "asset_id": asset_id,
        "sector_experience": sector_experience or [],
        "services": services or [],
        "role": role,
        "geography_experience": geography_experience or [],
        "technology_keywords": technology_keywords or [],
        "languages": languages or ["en"],
    }


def _rfp_context(
    sector: str = "banking",
    services: list[str] | None = None,
    geography: str = "ksa",
    technology_keywords: list[str] | None = None,
    capability_tags: list[str] | None = None,
    language: str = "en",
    required_roles: list[str] | None = None,
) -> dict:
    return {
        "sector": sector,
        "services": services or ["strategy", "digital"],
        "geography": geography,
        "technology_keywords": technology_keywords or [],
        "capability_tags": capability_tags or [],
        "language": language,
        "required_roles": required_roles or ["lead", "analyst"],
    }


# ── SelectedAsset / ExcludedAsset ────────────────────────────────────────


class TestResultTypes:
    def test_selected_asset_frozen(self):
        sa = SelectedAsset(asset_id="cs_1", ranking_score=5.0, inclusion_reason="sector:banking")
        with pytest.raises(AttributeError):
            sa.asset_id = "hacked"  # type: ignore[misc]

    def test_excluded_asset_frozen(self):
        ea = ExcludedAsset(asset_id="cs_2", ranking_score=1.0, exclusion_reason="below min score 2.0")
        with pytest.raises(AttributeError):
            ea.asset_id = "hacked"  # type: ignore[misc]

    def test_selected_asset_fields(self):
        sa = SelectedAsset(asset_id="cs_1", ranking_score=5.5, inclusion_reason="sector:banking + geography:ksa")
        assert sa.asset_id == "cs_1"
        assert sa.ranking_score == 5.5
        assert "sector:banking" in sa.inclusion_reason

    def test_excluded_asset_fields(self):
        ea = ExcludedAsset(asset_id="cs_99", ranking_score=0.0, exclusion_reason="exceeds max count 12")
        assert ea.asset_id == "cs_99"
        assert ea.ranking_score == 0.0
        assert "exceeds max count" in ea.exclusion_reason


# ── CaseStudySelectionPolicy ────────────────────────────────────────────


class TestCaseStudyPolicy:
    def test_default_weights(self):
        p = CaseStudySelectionPolicy()
        assert p.sector_match_weight == 3.0
        assert p.service_line_match_weight == 2.0
        assert p.geography_match_weight == 1.5
        assert p.technology_keyword_weight == 1.0
        assert p.capability_tag_weight == 1.0
        assert p.language_suitability_weight == 0.5

    def test_frozen(self):
        p = CaseStudySelectionPolicy()
        with pytest.raises(AttributeError):
            p.sector_match_weight = 99.0  # type: ignore[misc]

    def test_custom_weights(self):
        p = CaseStudySelectionPolicy(sector_match_weight=5.0, geography_match_weight=0.5)
        assert p.sector_match_weight == 5.0
        assert p.geography_match_weight == 0.5


# ── Case Study Selection ────────────────────────────────────────────────


class TestSelectCaseStudies:
    def test_basic_selection(self):
        candidates = [
            _cs_candidate("cs_1", sector="banking", geography="ksa"),
            _cs_candidate("cs_2", sector="tech", geography="international"),
            _cs_candidate("cs_3", sector="banking", services=["strategy"]),
        ]
        result = select_case_studies(candidates, _rfp_context(), min_count=1, max_count=3)
        assert isinstance(result, CaseStudySelectionResult)
        assert len(result.selected) >= 1
        assert all(isinstance(s, SelectedAsset) for s in result.selected)

    def test_sector_match_scores_highest(self):
        candidates = [
            _cs_candidate("cs_sector", sector="banking"),
            _cs_candidate("cs_none"),
        ]
        result = select_case_studies(candidates, _rfp_context(), min_count=1, max_count=2)
        assert result.selected[0].asset_id == "cs_sector"
        assert result.selected[0].ranking_score > result.selected[1].ranking_score

    def test_all_dimensions_accumulate(self):
        perfect = _cs_candidate(
            "cs_perfect",
            sector="banking",
            services=["strategy"],
            geography="ksa",
            technology_keywords=["cloud"],
            capability_tags=["transformation"],
            language="en",
        )
        rfp = _rfp_context(
            technology_keywords=["cloud"],
            capability_tags=["transformation"],
        )
        result = select_case_studies([perfect], rfp, min_count=1, max_count=1)
        # All 6 dimensions matched: 3.0 + 2.0 + 1.5 + 1.0 + 1.0 + 0.5 = 9.0
        assert result.selected[0].ranking_score == 9.0

    def test_reasons_are_auditable(self):
        candidates = [
            _cs_candidate("cs_1", sector="banking", geography="ksa"),
        ]
        result = select_case_studies(candidates, _rfp_context(), min_count=1, max_count=1)
        reason = result.selected[0].inclusion_reason
        assert "sector:banking" in reason
        assert "geography:ksa" in reason

    def test_max_count_enforced(self):
        candidates = [_cs_candidate(f"cs_{i}", sector="banking") for i in range(10)]
        result = select_case_studies(candidates, _rfp_context(), min_count=1, max_count=3)
        assert len(result.selected) == 3
        assert len(result.excluded) == 7
        assert all("exceeds max count" in e.exclusion_reason for e in result.excluded)

    def test_min_count_fills_below_threshold(self):
        """Even if score < min_score, fill up to min_count."""
        candidates = [
            _cs_candidate("cs_low_1"),
            _cs_candidate("cs_low_2"),
        ]
        result = select_case_studies(
            candidates, _rfp_context(),
            min_count=2, max_count=5, min_score=5.0,
        )
        assert len(result.selected) == 2

    def test_min_score_excludes_beyond_min_count(self):
        """After min_count filled, candidates below min_score are excluded."""
        candidates = [
            _cs_candidate("cs_good", sector="banking", geography="ksa"),
            _cs_candidate("cs_ok", sector="banking"),
            _cs_candidate("cs_low_1"),
            _cs_candidate("cs_low_2"),
        ]
        result = select_case_studies(
            candidates, _rfp_context(),
            min_count=2, max_count=10, min_score=3.0,
        )
        selected_ids = [s.asset_id for s in result.selected]
        assert "cs_good" in selected_ids
        assert "cs_ok" in selected_ids
        excluded_ids = [e.asset_id for e in result.excluded]
        for eid in excluded_ids:
            assert eid.startswith("cs_low")

    def test_deterministic_tiebreaking(self):
        """Equal scores sort by asset_id ascending."""
        candidates = [
            _cs_candidate("cs_z", sector="banking"),
            _cs_candidate("cs_a", sector="banking"),
            _cs_candidate("cs_m", sector="banking"),
        ]
        result = select_case_studies(candidates, _rfp_context(), min_count=3, max_count=3)
        ids = [s.asset_id for s in result.selected]
        assert ids == ["cs_a", "cs_m", "cs_z"]

    def test_empty_candidates(self):
        result = select_case_studies([], _rfp_context(), min_count=0, max_count=5)
        assert len(result.selected) == 0
        assert len(result.excluded) == 0

    def test_custom_policy_changes_ranking(self):
        """Geography-heavy policy reranks assets."""
        candidates = [
            _cs_candidate("cs_sector_only", sector="banking"),
            _cs_candidate("cs_geo_only", geography="ksa"),
        ]
        geo_heavy = CaseStudySelectionPolicy(
            sector_match_weight=1.0,
            geography_match_weight=5.0,
        )
        result = select_case_studies(
            candidates, _rfp_context(),
            min_count=2, max_count=2, policy=geo_heavy,
        )
        assert result.selected[0].asset_id == "cs_geo_only"

    def test_result_tuples_are_immutable(self):
        candidates = [_cs_candidate("cs_1")]
        result = select_case_studies(candidates, _rfp_context(), min_count=1, max_count=1)
        assert isinstance(result.selected, tuple)
        assert isinstance(result.excluded, tuple)

    def test_no_matching_dimensions_reason(self):
        """Candidate with no matches still gets included if min_count demands."""
        candidates = [_cs_candidate("cs_empty", language="fr")]
        rfp = _rfp_context(language="ar")
        result = select_case_studies(candidates, rfp, min_count=1, max_count=1)
        assert result.selected[0].inclusion_reason == "no matching dimensions"
        assert result.selected[0].ranking_score == 0.0

    def test_case_insensitive_matching(self):
        """Matching is case-insensitive."""
        candidates = [
            _cs_candidate("cs_1", sector="Banking", geography="KSA"),
        ]
        result = select_case_studies(candidates, _rfp_context(), min_count=1, max_count=1)
        # Should still match banking and ksa
        assert result.selected[0].ranking_score >= 4.5  # sector + geography


# ── TeamSelectionPolicy ─────────────────────────────────────────────────


class TestTeamPolicy:
    def test_default_weights(self):
        p = TeamSelectionPolicy()
        assert p.sector_experience_weight == 3.0
        assert p.service_line_match_weight == 2.5
        assert p.role_coverage_weight == 2.0
        assert p.geography_experience_weight == 1.5
        assert p.technology_keyword_weight == 1.0
        assert p.language_suitability_weight == 0.5

    def test_frozen(self):
        p = TeamSelectionPolicy()
        with pytest.raises(AttributeError):
            p.sector_experience_weight = 99.0  # type: ignore[misc]

    def test_custom_weights(self):
        p = TeamSelectionPolicy(role_coverage_weight=5.0)
        assert p.role_coverage_weight == 5.0


# ── Team Selection ──────────────────────────────────────────────────────


class TestSelectTeamMembers:
    def test_basic_selection(self):
        candidates = [
            _team_candidate("team_1", sector_experience=["banking"], role="lead"),
            _team_candidate("team_2", role="analyst"),
        ]
        result = select_team_members(candidates, _rfp_context(), min_count=1, max_count=2)
        assert isinstance(result, TeamSelectionResult)
        assert len(result.selected) >= 1

    def test_sector_experience_scores_highest(self):
        candidates = [
            _team_candidate("team_sector", sector_experience=["banking"]),
            _team_candidate("team_none"),
        ]
        result = select_team_members(candidates, _rfp_context(), min_count=1, max_count=2)
        assert result.selected[0].asset_id == "team_sector"

    def test_all_dimensions_accumulate(self):
        perfect = _team_candidate(
            "team_perfect",
            sector_experience=["banking"],
            services=["strategy"],
            role="lead",
            geography_experience=["ksa"],
            technology_keywords=["cloud"],
            languages=["en"],
        )
        rfp = _rfp_context(technology_keywords=["cloud"])
        result = select_team_members([perfect], rfp, min_count=1, max_count=1)
        # All 6: 3.0 + 2.5 + 2.0 + 1.5 + 1.0 + 0.5 = 10.5
        assert result.selected[0].ranking_score == 10.5

    def test_reasons_auditable(self):
        candidates = [
            _team_candidate("team_1", sector_experience=["banking"], role="lead"),
        ]
        result = select_team_members(candidates, _rfp_context(), min_count=1, max_count=1)
        reason = result.selected[0].inclusion_reason
        assert "sector:banking" in reason
        assert "role:lead" in reason

    def test_max_count_enforced(self):
        candidates = [_team_candidate(f"team_{i}", sector_experience=["banking"]) for i in range(10)]
        result = select_team_members(candidates, _rfp_context(), min_count=1, max_count=3)
        assert len(result.selected) == 3
        assert len(result.excluded) == 7

    def test_min_count_fills_below_threshold(self):
        candidates = [
            _team_candidate("team_low_1"),
            _team_candidate("team_low_2"),
        ]
        result = select_team_members(
            candidates, _rfp_context(),
            min_count=2, max_count=5, min_score=5.0,
        )
        assert len(result.selected) == 2

    def test_deterministic_tiebreaking(self):
        candidates = [
            _team_candidate("team_z", sector_experience=["banking"]),
            _team_candidate("team_a", sector_experience=["banking"]),
        ]
        result = select_team_members(candidates, _rfp_context(), min_count=2, max_count=2)
        ids = [s.asset_id for s in result.selected]
        assert ids == ["team_a", "team_z"]

    def test_empty_candidates(self):
        result = select_team_members([], _rfp_context(), min_count=0, max_count=5)
        assert len(result.selected) == 0
        assert len(result.excluded) == 0

    def test_custom_policy(self):
        candidates = [
            _team_candidate("team_role", role="lead"),
            _team_candidate("team_geo", geography_experience=["ksa"]),
        ]
        role_heavy = TeamSelectionPolicy(
            role_coverage_weight=10.0,
            geography_experience_weight=0.5,
        )
        result = select_team_members(
            candidates, _rfp_context(),
            min_count=2, max_count=2, policy=role_heavy,
        )
        assert result.selected[0].asset_id == "team_role"

    def test_result_tuples_are_immutable(self):
        candidates = [_team_candidate("team_1")]
        result = select_team_members(candidates, _rfp_context(), min_count=1, max_count=1)
        assert isinstance(result.selected, tuple)
        assert isinstance(result.excluded, tuple)

    def test_language_matching(self):
        candidates = [
            _team_candidate("team_ar", languages=["ar"]),
            _team_candidate("team_en", languages=["en"]),
        ]
        rfp = _rfp_context(language="ar")
        result = select_team_members(candidates, rfp, min_count=2, max_count=2)
        assert result.selected[0].asset_id == "team_ar"
        assert result.selected[0].ranking_score > result.selected[1].ranking_score

    def test_multi_service_match(self):
        """Multiple service matches still add weight only once."""
        candidates = [
            _team_candidate("team_1", services=["strategy", "digital", "operations"]),
        ]
        rfp = _rfp_context(services=["strategy", "digital"])
        result = select_team_members(candidates, rfp, min_count=1, max_count=1)
        # Service line weight = 2.5 (applied once) + language 0.5
        assert result.selected[0].ranking_score == 3.0


# ── Cross-cutting: Auditability ─────────────────────────────────────────


class TestAuditability:
    def test_every_candidate_appears_in_result(self):
        """No candidate is silently dropped."""
        candidates = [_cs_candidate(f"cs_{i}") for i in range(5)]
        result = select_case_studies(candidates, _rfp_context(), min_count=2, max_count=3)
        all_ids = {s.asset_id for s in result.selected} | {e.asset_id for e in result.excluded}
        assert all_ids == {f"cs_{i}" for i in range(5)}

    def test_team_every_candidate_appears(self):
        candidates = [_team_candidate(f"team_{i}") for i in range(5)]
        result = select_team_members(candidates, _rfp_context(), min_count=2, max_count=3)
        all_ids = {s.asset_id for s in result.selected} | {e.asset_id for e in result.excluded}
        assert all_ids == {f"team_{i}" for i in range(5)}

    def test_scores_are_nonnegative(self):
        candidates = [_cs_candidate(f"cs_{i}") for i in range(3)]
        result = select_case_studies(candidates, _rfp_context(), min_count=3, max_count=3)
        for s in result.selected:
            assert s.ranking_score >= 0.0

    def test_selected_ordered_by_score_desc(self):
        candidates = [
            _cs_candidate("cs_low"),
            _cs_candidate("cs_mid", sector="banking"),
            _cs_candidate("cs_high", sector="banking", geography="ksa"),
        ]
        result = select_case_studies(candidates, _rfp_context(), min_count=3, max_count=3)
        scores = [s.ranking_score for s in result.selected]
        assert scores == sorted(scores, reverse=True)
