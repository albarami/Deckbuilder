"""Phase 5 — Proposal Manifest and House Inclusion Policy.

ProposalManifest is the per-proposal assembly plan using semantic IDs
only (both asset IDs and layout IDs).  Built from a SlideBudget (Phase 7).
Never contains raw slide indices or raw layout display names.

HouseInclusionPolicy determines which A1/A2 house slides are included
in each proposal based on deterministic rules (geography, proposal mode,
sector).

ContentSourcePolicy declares the origin of every ManifestEntry's content,
validated before render.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ── ContentSourcePolicy ──────────────────────────────────────────────────


class ContentSourcePolicy(StrEnum):
    """Content origin classification for every ManifestEntry."""

    INSTITUTIONAL_REUSE = "institutional_reuse"
    APPROVED_ASSET_POOL = "approved_asset_pool"
    PROPOSAL_SPECIFIC = "proposal_specific"
    FORBIDDEN_TEMPLATE_EXAMPLE = "forbidden_template_example"


# ── ManifestEntry ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ManifestEntry:
    """One slide in the proposal manifest.

    All references use semantic IDs.  ``slide_idx`` is intentionally
    absent — slide position is determined by list order in the manifest.
    """

    entry_type: str                        # "a1_clone" | "a2_shell" | "b_variable" | "pool_clone"
    asset_id: str                          # semantic asset ID
    semantic_layout_id: str                # semantic layout ID (from catalog lock)
    content_source_policy: ContentSourcePolicy
    section_id: str                        # which proposal section this belongs to
    methodology_phase: str | None = None   # e.g. "phase_01" if applicable
    injection_data: dict[str, Any] | None = None


# ── ManifestValidationError ──────────────────────────────────────────────


class ManifestValidationError(RuntimeError):
    """Raised when manifest fails structural validation."""


# ── HouseInclusionPolicy ─────────────────────────────────────────────────


@dataclass(frozen=True)
class HouseInclusionPolicy:
    """Deterministic rules for which house slides to include."""

    proposal_mode: str                     # "lite" | "standard" | "full"
    geography: str                         # "ksa" | "gcc" | "mena" | "international"
    sector: str                            # RFP sector/industry
    include_ksa_context: bool = False      # Only when geography == "ksa"
    include_vision_slides: bool = False    # Only when geography == "ksa" + sector relevance
    company_profile_depth: str = "standard"  # "lite" | "standard" | "full"
    case_study_count: tuple[int, int] = (4, 12)
    team_bio_count: tuple[int, int] = (2, 6)
    include_services_overview: bool = False  # Only in full mode
    include_leadership: bool = False        # Only in standard/full mode


# Company profile A1 asset IDs by depth
_COMPANY_PROFILE_LITE: tuple[str, ...] = (
    "main_cover", "overview", "why_sg",
)

_COMPANY_PROFILE_STANDARD: tuple[str, ...] = (
    "main_cover", "overview", "what_drives_us", "at_a_glance",
    "why_sg", "expertise", "vast_network", "purpose_1",
)

_COMPANY_PROFILE_FULL: tuple[str, ...] = (
    "main_cover", "overview", "what_drives_us", "at_a_glance",
    "why_sg", "deep_experience_1", "deep_experience_2",
    "deep_experience_3", "deep_experience_4", "expertise",
    "vast_network", "purpose_1", "purpose_2",
)

# KSA context A1 asset IDs
_KSA_CONTEXT_IDS: tuple[str, ...] = (
    "ksa_context", "vision_pillars",
    "vision_programs_numbers", "vision_programs",
)


def get_company_profile_ids(depth: str) -> tuple[str, ...]:
    """Return A1 asset IDs for the given company profile depth."""
    if depth == "lite":
        return _COMPANY_PROFILE_LITE
    elif depth == "standard":
        return _COMPANY_PROFILE_STANDARD
    elif depth == "full":
        return _COMPANY_PROFILE_FULL
    else:
        raise ManifestValidationError(
            f"Invalid company_profile_depth: '{depth}'. "
            f"Must be 'lite', 'standard', or 'full'."
        )


def get_ksa_context_ids() -> tuple[str, ...]:
    """Return A1 asset IDs for KSA context slides."""
    return _KSA_CONTEXT_IDS


# ── Policy construction helper ────────────────────────────────────────────


def build_inclusion_policy(
    proposal_mode: str,
    geography: str,
    sector: str,
    *,
    case_study_count: tuple[int, int] = (4, 12),
    team_bio_count: tuple[int, int] = (2, 6),
) -> HouseInclusionPolicy:
    """Build a HouseInclusionPolicy from proposal parameters.

    Applies deterministic rules from the approved plan:
    - KSA context: only when geography == "ksa"
    - Vision slides: only when geography == "ksa"
    - Company profile depth: matches proposal_mode
    - Services overview: only in full mode
    - Leadership: only in standard/full mode
    """
    if proposal_mode not in ("lite", "standard", "full"):
        raise ManifestValidationError(
            f"Invalid proposal_mode: '{proposal_mode}'"
        )
    if geography not in ("ksa", "gcc", "mena", "international"):
        raise ManifestValidationError(
            f"Invalid geography: '{geography}'"
        )

    is_ksa = geography == "ksa"

    return HouseInclusionPolicy(
        proposal_mode=proposal_mode,
        geography=geography,
        sector=sector,
        include_ksa_context=is_ksa,
        include_vision_slides=is_ksa,
        company_profile_depth=proposal_mode,
        case_study_count=case_study_count,
        team_bio_count=team_bio_count,
        include_services_overview=(proposal_mode == "full"),
        include_leadership=(proposal_mode in ("standard", "full")),
    )


# ── ProposalManifest ──────────────────────────────────────────────────────


@dataclass
class ProposalManifest:
    """Per-proposal assembly plan.

    Entries are ordered — list position determines slide position.
    All references use semantic IDs only.
    """

    entries: list[ManifestEntry] = field(default_factory=list)
    inclusion_policy: HouseInclusionPolicy | None = None

    @property
    def total_slides(self) -> int:
        return len(self.entries)

    @property
    def section_ids(self) -> list[str]:
        """Ordered unique section IDs in the manifest."""
        seen: set[str] = set()
        result: list[str] = []
        for e in self.entries:
            if e.section_id not in seen:
                seen.add(e.section_id)
                result.append(e.section_id)
        return result


# ── Validation ────────────────────────────────────────────────────────────


def validate_manifest(manifest: ProposalManifest) -> list[str]:
    """Validate structural integrity of a ProposalManifest.

    Returns a list of error messages (empty if valid).
    Checks:
    1. Every entry has a ContentSourcePolicy
    2. Every entry has a semantic_layout_id
    3. Every entry has a section_id
    4. A1 clones use INSTITUTIONAL_REUSE
    5. A2 shells use PROPOSAL_SPECIFIC
    6. Pool clones use APPROVED_ASSET_POOL
    7. B variable slides use PROPOSAL_SPECIFIC
    8. No entry uses FORBIDDEN_TEMPLATE_EXAMPLE
    9. Section order follows MANDATORY_SECTION_ORDER
    10. Case study and team bio counts within policy ranges
    """
    from src.models.section_blueprint import (
        validate_section_order,
    )

    errors: list[str] = []

    for i, entry in enumerate(manifest.entries):
        prefix = f"Entry {i} ({entry.asset_id})"

        # Must have semantic_layout_id
        if not entry.semantic_layout_id:
            errors.append(f"{prefix}: missing semantic_layout_id")

        # Must have section_id
        if not entry.section_id:
            errors.append(f"{prefix}: missing section_id")

        # Content source policy validation by entry type
        if entry.content_source_policy == ContentSourcePolicy.FORBIDDEN_TEMPLATE_EXAMPLE:
            errors.append(
                f"{prefix}: uses FORBIDDEN_TEMPLATE_EXAMPLE — "
                f"template example content must never appear in output"
            )

        if entry.entry_type == "a1_clone":
            if entry.content_source_policy != ContentSourcePolicy.INSTITUTIONAL_REUSE:
                errors.append(
                    f"{prefix}: A1 clone must use INSTITUTIONAL_REUSE, "
                    f"got {entry.content_source_policy}"
                )
        elif entry.entry_type == "a2_shell":
            if entry.content_source_policy != ContentSourcePolicy.PROPOSAL_SPECIFIC:
                errors.append(
                    f"{prefix}: A2 shell must use PROPOSAL_SPECIFIC, "
                    f"got {entry.content_source_policy}"
                )
        elif entry.entry_type == "pool_clone":
            if entry.content_source_policy != ContentSourcePolicy.APPROVED_ASSET_POOL:
                errors.append(
                    f"{prefix}: pool clone must use APPROVED_ASSET_POOL, "
                    f"got {entry.content_source_policy}"
                )
        elif entry.entry_type == "b_variable":
            if entry.content_source_policy != ContentSourcePolicy.PROPOSAL_SPECIFIC:
                errors.append(
                    f"{prefix}: B variable must use PROPOSAL_SPECIFIC, "
                    f"got {entry.content_source_policy}"
                )

    # Section ordering
    order_errors = validate_section_order(manifest.section_ids)
    errors.extend(order_errors)

    # Inclusion policy range checks
    if manifest.inclusion_policy:
        policy = manifest.inclusion_policy
        cs_count = sum(
            1 for e in manifest.entries
            if e.entry_type == "pool_clone"
            and e.semantic_layout_id in ("case_study_cases", "case_study_detailed")
        )
        min_cs, max_cs = policy.case_study_count
        if cs_count < min_cs or cs_count > max_cs:
            errors.append(
                f"Case study count {cs_count} outside policy range "
                f"[{min_cs}, {max_cs}]"
            )

        team_count = sum(
            1 for e in manifest.entries
            if e.entry_type == "pool_clone"
            and e.semantic_layout_id == "team_two_members"
        )
        min_t, max_t = policy.team_bio_count
        if team_count < min_t or team_count > max_t:
            errors.append(
                f"Team bio count {team_count} outside policy range "
                f"[{min_t}, {max_t}]"
            )

        # KSA exclusion: no KSA slides when geography != "ksa"
        if not policy.include_ksa_context:
            for entry in manifest.entries:
                if entry.asset_id in _KSA_CONTEXT_IDS:
                    errors.append(
                        f"KSA slide '{entry.asset_id}' included but "
                        f"geography is '{policy.geography}' (not ksa)"
                    )

    return errors
