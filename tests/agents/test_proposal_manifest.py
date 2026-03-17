"""Tests for Phase 5 — proposal_manifest.py.

Tests ProposalManifest, HouseInclusionPolicy, ContentSourcePolicy,
section ordering, budget range validation, and KSA exclusion rules.
All semantic-ID-only — no raw slide indices or display names.
"""

from __future__ import annotations

import pytest

from src.models.proposal_manifest import (
    ContentSourcePolicy,
    HouseInclusionPolicy,
    ManifestEntry,
    ManifestValidationError,
    ProposalManifest,
    build_inclusion_policy,
    get_company_profile_ids,
    get_ksa_context_ids,
    validate_manifest,
)

# ── ContentSourcePolicy ──────────────────────────────────────────────────


class TestContentSourcePolicy:
    def test_all_values(self):
        assert ContentSourcePolicy.INSTITUTIONAL_REUSE == "institutional_reuse"
        assert ContentSourcePolicy.APPROVED_ASSET_POOL == "approved_asset_pool"
        assert ContentSourcePolicy.PROPOSAL_SPECIFIC == "proposal_specific"
        assert ContentSourcePolicy.FORBIDDEN_TEMPLATE_EXAMPLE == "forbidden_template_example"


# ── ManifestEntry ─────────────────────────────────────────────────────────


class TestManifestEntry:
    def test_frozen(self):
        entry = ManifestEntry(
            entry_type="a1_clone",
            asset_id="overview",
            semantic_layout_id="overview",
            content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
            section_id="company_profile",
        )
        with pytest.raises(AttributeError):
            entry.asset_id = "hacked"  # type: ignore[misc]

    def test_methodology_phase_optional(self):
        entry = ManifestEntry(
            entry_type="b_variable",
            asset_id="meth_overview",
            semantic_layout_id="methodology_overview_4",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
            section_id="section_03",
            methodology_phase="phase_01",
        )
        assert entry.methodology_phase == "phase_01"

    def test_no_slide_idx_field(self):
        """ManifestEntry intentionally has no slide_idx."""
        entry = ManifestEntry(
            entry_type="a1_clone",
            asset_id="overview",
            semantic_layout_id="overview",
            content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
            section_id="company_profile",
        )
        assert not hasattr(entry, "slide_idx")


# ── HouseInclusionPolicy ─────────────────────────────────────────────────


class TestHouseInclusionPolicy:
    def test_frozen(self):
        policy = HouseInclusionPolicy(
            proposal_mode="standard",
            geography="ksa",
            sector="banking",
        )
        with pytest.raises(AttributeError):
            policy.proposal_mode = "full"  # type: ignore[misc]

    def test_defaults(self):
        policy = HouseInclusionPolicy(
            proposal_mode="standard",
            geography="ksa",
            sector="banking",
        )
        assert policy.case_study_count == (4, 12)
        assert policy.team_bio_count == (2, 6)


# ── build_inclusion_policy ───────────────────────────────────────────────


class TestBuildInclusionPolicy:
    def test_ksa_standard(self):
        policy = build_inclusion_policy("standard", "ksa", "banking")
        assert policy.include_ksa_context is True
        assert policy.include_vision_slides is True
        assert policy.company_profile_depth == "standard"
        assert policy.include_leadership is True
        assert policy.include_services_overview is False

    def test_international_lite(self):
        policy = build_inclusion_policy("lite", "international", "tech")
        assert policy.include_ksa_context is False
        assert policy.include_vision_slides is False
        assert policy.company_profile_depth == "lite"
        assert policy.include_leadership is False
        assert policy.include_services_overview is False

    def test_ksa_full(self):
        policy = build_inclusion_policy("full", "ksa", "energy")
        assert policy.include_ksa_context is True
        assert policy.include_services_overview is True
        assert policy.include_leadership is True
        assert policy.company_profile_depth == "full"

    def test_gcc_standard(self):
        policy = build_inclusion_policy("standard", "gcc", "finance")
        assert policy.include_ksa_context is False
        assert policy.include_leadership is True

    def test_invalid_mode_raises(self):
        with pytest.raises(ManifestValidationError, match="proposal_mode"):
            build_inclusion_policy("mega", "ksa", "banking")

    def test_invalid_geography_raises(self):
        with pytest.raises(ManifestValidationError, match="geography"):
            build_inclusion_policy("standard", "mars", "banking")

    def test_custom_counts(self):
        policy = build_inclusion_policy(
            "standard", "ksa", "banking",
            case_study_count=(6, 10),
            team_bio_count=(3, 5),
        )
        assert policy.case_study_count == (6, 10)
        assert policy.team_bio_count == (3, 5)


# ── Company profile IDs ──────────────────────────────────────────────────


class TestCompanyProfileIds:
    def test_lite_has_3(self):
        ids = get_company_profile_ids("lite")
        assert len(ids) == 3
        assert ids[0] == "main_cover"

    def test_standard_has_8(self):
        ids = get_company_profile_ids("standard")
        assert len(ids) == 8

    def test_full_has_13(self):
        ids = get_company_profile_ids("full")
        assert len(ids) == 13

    def test_invalid_depth_raises(self):
        with pytest.raises(ManifestValidationError, match="company_profile_depth"):
            get_company_profile_ids("mega")

    def test_no_raw_display_names(self):
        """All IDs must be semantic, not display names."""
        for depth in ("lite", "standard", "full"):
            for sid in get_company_profile_ids(depth):
                assert sid.islower() or "_" in sid, (
                    f"'{sid}' looks like a display name"
                )


# ── KSA context IDs ──────────────────────────────────────────────────────


class TestKsaContextIds:
    def test_returns_4_ids(self):
        ids = get_ksa_context_ids()
        assert len(ids) == 4
        assert "ksa_context" in ids
        assert "vision_pillars" in ids


# ── ProposalManifest ──────────────────────────────────────────────────────


def _entry(
    entry_type: str = "b_variable",
    asset_id: str = "slide_1",
    layout_id: str = "content_heading_desc",
    policy: ContentSourcePolicy = ContentSourcePolicy.PROPOSAL_SPECIFIC,
    section_id: str = "section_01",
    **kwargs,
) -> ManifestEntry:
    return ManifestEntry(
        entry_type=entry_type,
        asset_id=asset_id,
        semantic_layout_id=layout_id,
        content_source_policy=policy,
        section_id=section_id,
        **kwargs,
    )


class TestProposalManifest:
    def test_total_slides(self):
        m = ProposalManifest(entries=[_entry(), _entry()])
        assert m.total_slides == 2

    def test_section_ids_ordered(self):
        m = ProposalManifest(entries=[
            _entry(section_id="cover"),
            _entry(section_id="cover"),
            _entry(section_id="section_01"),
            _entry(section_id="section_03"),
        ])
        assert m.section_ids == ["cover", "section_01", "section_03"]

    def test_empty_manifest(self):
        m = ProposalManifest()
        assert m.total_slides == 0
        assert m.section_ids == []


# ── Validation ────────────────────────────────────────────────────────────


class TestValidateManifest:
    def test_valid_minimal_manifest(self):
        m = ProposalManifest(entries=[
            _entry(
                entry_type="a2_shell",
                asset_id="proposal_cover",
                layout_id="proposal_cover",
                section_id="cover",
            ),
            _entry(section_id="section_01"),
        ])
        errors = validate_manifest(m)
        assert errors == []

    def test_missing_layout_id_flagged(self):
        m = ProposalManifest(entries=[
            _entry(layout_id=""),
        ])
        errors = validate_manifest(m)
        assert any("semantic_layout_id" in e for e in errors)

    def test_missing_section_id_flagged(self):
        m = ProposalManifest(entries=[
            _entry(section_id=""),
        ])
        errors = validate_manifest(m)
        assert any("section_id" in e for e in errors)

    def test_forbidden_template_example_flagged(self):
        m = ProposalManifest(entries=[
            _entry(policy=ContentSourcePolicy.FORBIDDEN_TEMPLATE_EXAMPLE),
        ])
        errors = validate_manifest(m)
        assert any("FORBIDDEN" in e for e in errors)

    def test_a1_wrong_policy_flagged(self):
        m = ProposalManifest(entries=[
            _entry(
                entry_type="a1_clone",
                asset_id="overview",
                layout_id="overview",
                policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
                section_id="company_profile",
            ),
        ])
        errors = validate_manifest(m)
        assert any("INSTITUTIONAL_REUSE" in e for e in errors)

    def test_a1_correct_policy_passes(self):
        m = ProposalManifest(entries=[
            _entry(
                entry_type="a1_clone",
                asset_id="overview",
                layout_id="overview",
                policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
                section_id="company_profile",
            ),
        ])
        errors = validate_manifest(m)
        assert errors == []

    def test_a2_wrong_policy_flagged(self):
        m = ProposalManifest(entries=[
            _entry(
                entry_type="a2_shell",
                asset_id="proposal_cover",
                layout_id="proposal_cover",
                policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
                section_id="cover",
            ),
        ])
        errors = validate_manifest(m)
        assert any("PROPOSAL_SPECIFIC" in e for e in errors)

    def test_pool_clone_wrong_policy_flagged(self):
        m = ProposalManifest(entries=[
            _entry(
                entry_type="pool_clone",
                asset_id="case_study_9",
                layout_id="case_study_detailed",
                policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
                section_id="section_02",
            ),
        ])
        errors = validate_manifest(m)
        assert any("APPROVED_ASSET_POOL" in e for e in errors)

    def test_section_order_violation_flagged(self):
        m = ProposalManifest(entries=[
            _entry(section_id="section_03"),
            _entry(section_id="section_01"),
        ])
        errors = validate_manifest(m)
        assert any("out of order" in e for e in errors)

    def test_correct_section_order_passes(self):
        m = ProposalManifest(entries=[
            _entry(
                entry_type="a2_shell",
                asset_id="proposal_cover",
                layout_id="proposal_cover",
                section_id="cover",
            ),
            _entry(section_id="section_01"),
            _entry(section_id="section_03"),
            _entry(
                entry_type="a1_clone",
                asset_id="overview",
                layout_id="overview",
                policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
                section_id="company_profile",
            ),
        ])
        errors = validate_manifest(m)
        assert errors == []


# ── Inclusion policy range validation ─────────────────────────────────────


class TestInclusionPolicyValidation:
    def test_case_study_below_min_flagged(self):
        policy = build_inclusion_policy("standard", "ksa", "banking",
                                        case_study_count=(4, 12))
        m = ProposalManifest(
            entries=[
                _entry(
                    entry_type="pool_clone",
                    asset_id="cs_1",
                    layout_id="case_study_detailed",
                    policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
                    section_id="section_02",
                ),
                # Only 1 case study, min is 4
            ],
            inclusion_policy=policy,
        )
        errors = validate_manifest(m)
        assert any("Case study count" in e for e in errors)

    def test_team_below_min_flagged(self):
        policy = build_inclusion_policy("standard", "ksa", "banking",
                                        team_bio_count=(2, 6))
        m = ProposalManifest(
            entries=[
                _entry(
                    entry_type="pool_clone",
                    asset_id="team_1",
                    layout_id="team_two_members",
                    policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
                    section_id="section_05",
                ),
                # Only 1 team bio, min is 2
            ],
            inclusion_policy=policy,
        )
        errors = validate_manifest(m)
        assert any("Team bio count" in e for e in errors)

    def test_counts_within_range_passes(self):
        policy = build_inclusion_policy("standard", "ksa", "banking",
                                        case_study_count=(1, 3),
                                        team_bio_count=(1, 3))
        entries = [
            _entry(
                entry_type="pool_clone",
                asset_id=f"cs_{i}",
                layout_id="case_study_detailed",
                policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
                section_id="section_02",
            )
            for i in range(2)
        ] + [
            _entry(
                entry_type="pool_clone",
                asset_id=f"team_{i}",
                layout_id="team_two_members",
                policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
                section_id="section_05",
            )
            for i in range(2)
        ]
        m = ProposalManifest(entries=entries, inclusion_policy=policy)
        errors = validate_manifest(m)
        assert not any("count" in e.lower() for e in errors)


# ── KSA exclusion ─────────────────────────────────────────────────────────


class TestKsaExclusion:
    def test_ksa_slides_in_international_flagged(self):
        policy = build_inclusion_policy("standard", "international", "tech")
        m = ProposalManifest(
            entries=[
                _entry(
                    entry_type="a1_clone",
                    asset_id="ksa_context",
                    layout_id="ksa_context",
                    policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
                    section_id="section_01",
                ),
            ],
            inclusion_policy=policy,
        )
        errors = validate_manifest(m)
        assert any("KSA slide" in e and "ksa_context" in e for e in errors)

    def test_ksa_slides_in_ksa_allowed(self):
        policy = build_inclusion_policy("standard", "ksa", "banking")
        m = ProposalManifest(
            entries=[
                _entry(
                    entry_type="a1_clone",
                    asset_id="ksa_context",
                    layout_id="ksa_context",
                    policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
                    section_id="section_01",
                ),
            ],
            inclusion_policy=policy,
        )
        errors = validate_manifest(m)
        assert not any("KSA slide" in e for e in errors)

    def test_vision_slides_in_gcc_flagged(self):
        policy = build_inclusion_policy("standard", "gcc", "finance")
        m = ProposalManifest(
            entries=[
                _entry(
                    entry_type="a1_clone",
                    asset_id="vision_pillars",
                    layout_id="vision_pillars",
                    policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
                    section_id="section_01",
                ),
            ],
            inclusion_policy=policy,
        )
        errors = validate_manifest(m)
        assert any("KSA slide" in e and "vision_pillars" in e for e in errors)
