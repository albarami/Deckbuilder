"""Phase 6 — Deterministic Case-Study and Team Selection Policies.

"Select relevant" is not acceptable.  Selection must be deterministic
and auditable.  Every selected or excluded asset has a score and a
human-readable reason.

Ranking inputs for case studies:
    - Sector match
    - Service-line match
    - Geography match
    - Technology/domain keyword overlap
    - Capability tag match
    - Language suitability

Ranking inputs for team members:
    - Sector experience
    - Service-line match
    - Role coverage
    - Geography experience
    - Technology/domain keyword overlap
    - Language suitability

Output: final selected asset IDs written into the manifest.  Every
selection is auditable (score + reason).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Selection result types ──────────────────────────────────────────────


@dataclass(frozen=True)
class SelectedAsset:
    """An asset chosen for inclusion in the proposal."""

    asset_id: str
    ranking_score: float
    inclusion_reason: str  # e.g. "sector:banking + geography:ksa + service:strategy"


@dataclass(frozen=True)
class ExcludedAsset:
    """An asset excluded from the proposal."""

    asset_id: str
    ranking_score: float
    exclusion_reason: str  # e.g. "below min score 2.0" or "exceeds max count 12"


# ── Case Study Selection ────────────────────────────────────────────────


@dataclass(frozen=True)
class CaseStudySelectionPolicy:
    """Deterministic weighting policy for case study selection."""

    sector_match_weight: float = 3.0
    service_line_match_weight: float = 2.0
    geography_match_weight: float = 1.5
    technology_keyword_weight: float = 1.0
    capability_tag_weight: float = 1.0
    language_suitability_weight: float = 0.5


@dataclass(frozen=True)
class CaseStudySelectionResult:
    """Auditable result of case study selection."""

    selected: tuple[SelectedAsset, ...]
    excluded: tuple[ExcludedAsset, ...]


def _score_case_study(
    asset: dict[str, Any],
    rfp_context: dict[str, Any],
    policy: CaseStudySelectionPolicy,
) -> tuple[float, list[str]]:
    """Score a single case study asset against RFP context.

    Returns (score, list_of_matched_dimensions).
    """
    score = 0.0
    reasons: list[str] = []

    rfp_sector = rfp_context.get("sector", "").lower()
    rfp_services = {s.lower() for s in rfp_context.get("services", [])}
    rfp_geography = rfp_context.get("geography", "").lower()
    rfp_keywords = {k.lower() for k in rfp_context.get("technology_keywords", [])}
    rfp_capabilities = {c.lower() for c in rfp_context.get("capability_tags", [])}
    rfp_language = rfp_context.get("language", "en").lower()

    # Sector match
    asset_sector = asset.get("sector", "").lower()
    if asset_sector and asset_sector == rfp_sector:
        score += policy.sector_match_weight
        reasons.append(f"sector:{rfp_sector}")

    # Service-line match
    asset_services = {s.lower() for s in asset.get("services", [])}
    matched_services = asset_services & rfp_services
    if matched_services:
        score += policy.service_line_match_weight
        reasons.append(f"service:{'+'.join(sorted(matched_services))}")

    # Geography match
    asset_geography = asset.get("geography", "").lower()
    if asset_geography and asset_geography == rfp_geography:
        score += policy.geography_match_weight
        reasons.append(f"geography:{rfp_geography}")

    # Technology keyword overlap
    asset_keywords = {k.lower() for k in asset.get("technology_keywords", [])}
    matched_keywords = asset_keywords & rfp_keywords
    if matched_keywords:
        score += policy.technology_keyword_weight
        reasons.append(f"tech:{'+'.join(sorted(matched_keywords))}")

    # Capability tag match
    asset_capabilities = {c.lower() for c in asset.get("capability_tags", [])}
    matched_capabilities = asset_capabilities & rfp_capabilities
    if matched_capabilities:
        score += policy.capability_tag_weight
        reasons.append(f"capability:{'+'.join(sorted(matched_capabilities))}")

    # Language suitability
    asset_language = asset.get("language", "en").lower()
    if asset_language == rfp_language:
        score += policy.language_suitability_weight
        reasons.append(f"language:{rfp_language}")

    return score, reasons


def select_case_studies(
    candidates: list[dict[str, Any]],
    rfp_context: dict[str, Any],
    *,
    min_count: int = 4,
    max_count: int = 12,
    min_score: float = 0.0,
    policy: CaseStudySelectionPolicy | None = None,
) -> CaseStudySelectionResult:
    """Select case studies using deterministic weighted scoring.

    Parameters
    ----------
    candidates : list[dict]
        Each dict must have ``asset_id`` and may have ``sector``,
        ``services``, ``geography``, ``technology_keywords``,
        ``capability_tags``, ``language``.
    rfp_context : dict
        RFP matching context with the same possible keys.
    min_count : int
        Minimum case studies to select (fills from top scorers).
    max_count : int
        Maximum case studies to select.
    min_score : float
        Minimum score to be eligible (below this -> excluded).
    policy : CaseStudySelectionPolicy | None
        Custom weighting policy; defaults to standard weights.

    Returns
    -------
    CaseStudySelectionResult
        Auditable result with selected and excluded assets.
    """
    if policy is None:
        policy = CaseStudySelectionPolicy()

    scored: list[tuple[str, float, list[str]]] = []
    for candidate in candidates:
        asset_id = candidate["asset_id"]
        score, reasons = _score_case_study(candidate, rfp_context, policy)
        scored.append((asset_id, score, reasons))

    # Deterministic sort: descending score, then ascending asset_id for ties
    scored.sort(key=lambda x: (-x[1], x[0]))

    selected: list[SelectedAsset] = []
    excluded: list[ExcludedAsset] = []

    for asset_id, score, reasons in scored:
        if len(selected) >= max_count:
            excluded.append(ExcludedAsset(
                asset_id=asset_id,
                ranking_score=score,
                exclusion_reason=f"exceeds max count {max_count}",
            ))
        elif score < min_score and len(selected) >= min_count:
            excluded.append(ExcludedAsset(
                asset_id=asset_id,
                ranking_score=score,
                exclusion_reason=f"below min score {min_score}",
            ))
        else:
            reason_str = " + ".join(reasons) if reasons else "no matching dimensions"
            selected.append(SelectedAsset(
                asset_id=asset_id,
                ranking_score=score,
                inclusion_reason=reason_str,
            ))

    return CaseStudySelectionResult(
        selected=tuple(selected),
        excluded=tuple(excluded),
    )


# ── Team Selection ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class TeamSelectionPolicy:
    """Deterministic weighting policy for team member selection."""

    sector_experience_weight: float = 3.0
    service_line_match_weight: float = 2.5
    role_coverage_weight: float = 2.0
    geography_experience_weight: float = 1.5
    technology_keyword_weight: float = 1.0
    language_suitability_weight: float = 0.5


@dataclass(frozen=True)
class TeamSelectionResult:
    """Auditable result of team member selection."""

    selected: tuple[SelectedAsset, ...]
    excluded: tuple[ExcludedAsset, ...]


def _score_team_member(
    member: dict[str, Any],
    rfp_context: dict[str, Any],
    policy: TeamSelectionPolicy,
) -> tuple[float, list[str]]:
    """Score a single team member against RFP context.

    Returns (score, list_of_matched_dimensions).
    """
    score = 0.0
    reasons: list[str] = []

    rfp_sector = rfp_context.get("sector", "").lower()
    rfp_services = {s.lower() for s in rfp_context.get("services", [])}
    rfp_geography = rfp_context.get("geography", "").lower()
    rfp_keywords = {k.lower() for k in rfp_context.get("technology_keywords", [])}
    rfp_language = rfp_context.get("language", "en").lower()
    rfp_roles = {r.lower() for r in rfp_context.get("required_roles", [])}

    # Sector experience
    member_sectors = {s.lower() for s in member.get("sector_experience", [])}
    if rfp_sector and rfp_sector in member_sectors:
        score += policy.sector_experience_weight
        reasons.append(f"sector:{rfp_sector}")

    # Service-line match
    member_services = {s.lower() for s in member.get("services", [])}
    matched_services = member_services & rfp_services
    if matched_services:
        score += policy.service_line_match_weight
        reasons.append(f"service:{'+'.join(sorted(matched_services))}")

    # Role coverage
    member_role = member.get("role", "").lower()
    if member_role and member_role in rfp_roles:
        score += policy.role_coverage_weight
        reasons.append(f"role:{member_role}")

    # Geography experience
    member_geographies = {g.lower() for g in member.get("geography_experience", [])}
    if rfp_geography and rfp_geography in member_geographies:
        score += policy.geography_experience_weight
        reasons.append(f"geography:{rfp_geography}")

    # Technology keyword overlap
    member_keywords = {k.lower() for k in member.get("technology_keywords", [])}
    matched_keywords = member_keywords & rfp_keywords
    if matched_keywords:
        score += policy.technology_keyword_weight
        reasons.append(f"tech:{'+'.join(sorted(matched_keywords))}")

    # Language suitability
    member_languages = {l.lower() for l in member.get("languages", [])}
    if rfp_language in member_languages:
        score += policy.language_suitability_weight
        reasons.append(f"language:{rfp_language}")

    return score, reasons


def select_team_members(
    candidates: list[dict[str, Any]],
    rfp_context: dict[str, Any],
    *,
    min_count: int = 2,
    max_count: int = 6,
    min_score: float = 0.0,
    policy: TeamSelectionPolicy | None = None,
) -> TeamSelectionResult:
    """Select team members using deterministic weighted scoring.

    Parameters
    ----------
    candidates : list[dict]
        Each dict must have ``asset_id`` and may have
        ``sector_experience``, ``services``, ``role``,
        ``geography_experience``, ``technology_keywords``, ``languages``.
    rfp_context : dict
        RFP matching context.
    min_count : int
        Minimum team members to select.
    max_count : int
        Maximum team members to select.
    min_score : float
        Minimum score to be eligible.
    policy : TeamSelectionPolicy | None
        Custom weighting policy; defaults to standard weights.

    Returns
    -------
    TeamSelectionResult
        Auditable result with selected and excluded members.
    """
    if policy is None:
        policy = TeamSelectionPolicy()

    scored: list[tuple[str, float, list[str]]] = []
    for member in candidates:
        asset_id = member["asset_id"]
        score, reasons = _score_team_member(member, rfp_context, policy)
        scored.append((asset_id, score, reasons))

    # Deterministic sort: descending score, then ascending asset_id for ties
    scored.sort(key=lambda x: (-x[1], x[0]))

    selected: list[SelectedAsset] = []
    excluded: list[ExcludedAsset] = []

    for asset_id, score, reasons in scored:
        if len(selected) >= max_count:
            excluded.append(ExcludedAsset(
                asset_id=asset_id,
                ranking_score=score,
                exclusion_reason=f"exceeds max count {max_count}",
            ))
        elif score < min_score and len(selected) >= min_count:
            excluded.append(ExcludedAsset(
                asset_id=asset_id,
                ranking_score=score,
                exclusion_reason=f"below min score {min_score}",
            ))
        else:
            reason_str = " + ".join(reasons) if reasons else "no matching dimensions"
            selected.append(SelectedAsset(
                asset_id=asset_id,
                ranking_score=score,
                inclusion_reason=reason_str,
            ))

    return TeamSelectionResult(
        selected=tuple(selected),
        excluded=tuple(excluded),
    )
