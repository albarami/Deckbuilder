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

from dataclasses import dataclass
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
    member_languages = {lang.lower() for lang in member.get("languages", [])}
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


# ── Service Divider Selection ──────────────────────────────────────────


@dataclass(frozen=True)
class ServiceDividerSelectionResult:
    """Result of service-divider selection.

    Picks the single best-matching service divider from the
    ``service_divider_pool`` in the catalog lock.  Selection is
    based on sector/service keyword overlap.
    """

    selected_service_divider: str  # semantic_id of the chosen divider
    score: float
    reason: str


# Canonical keyword → service_category mapping for fuzzy matching
_SERVICE_KEYWORD_MAP: dict[str, str] = {
    "strategy": "strategy",
    "strategic": "strategy",
    "transformation": "strategy",
    "organizational": "organizational excellence",
    "organisation": "organizational excellence",
    "excellence": "organizational excellence",
    "operations": "organizational excellence",
    "marketing": "marketing",
    "brand": "marketing",
    "digital": "digital, cloud, and ai",
    "cloud": "digital, cloud, and ai",
    "ai": "digital, cloud, and ai",
    "artificial intelligence": "digital, cloud, and ai",
    "technology": "digital, cloud, and ai",
    "it": "digital, cloud, and ai",
    "ict": "digital, cloud, and ai",
    "people": "people advisory",
    "hr": "people advisory",
    "human resources": "people advisory",
    "talent": "people advisory",
    "deals": "deals advisory",
    "m&a": "deals advisory",
    "acquisition": "deals advisory",
    "research": "research",
    "study": "research",
    "survey": "research",
}


def select_service_divider(
    rfp_context: dict[str, Any],
    service_divider_pool: list[dict[str, Any]],
) -> ServiceDividerSelectionResult:
    """Select the best service divider from the pool.

    Matching logic:
      1. Exact service_category match against sector
      2. Keyword overlap against services + sector + capability tags
      3. Default to "strategy" if no match

    Parameters
    ----------
    rfp_context:
        Dict with keys: sector, services, capability_tags, etc.
    service_divider_pool:
        List of dicts with: semantic_id, service_category, display_name.

    Returns
    -------
    ServiceDividerSelectionResult with the chosen divider.
    """
    if not service_divider_pool:
        return ServiceDividerSelectionResult(
            selected_service_divider="",
            score=0.0,
            reason="empty pool",
        )

    sector = str(rfp_context.get("sector", "")).lower().strip()
    services = [
        s.lower().strip()
        for s in rfp_context.get("services", [])
    ]
    cap_tags = [
        t.lower().strip()
        for t in rfp_context.get("capability_tags", [])
    ]
    all_keywords = [sector] + services + cap_tags

    # Score each divider
    best_id = ""
    best_score = -1.0
    best_reason = "default"

    for divider in service_divider_pool:
        cat = str(divider.get("service_category", "")).lower().strip()
        sem_id = str(divider.get("semantic_id", ""))
        score = 0.0
        reasons: list[str] = []

        # Exact sector match
        if cat and sector and cat == sector:
            score += 5.0
            reasons.append(f"exact_sector:{sector}")

        # Keyword overlap
        for kw in all_keywords:
            mapped = _SERVICE_KEYWORD_MAP.get(kw, "")
            if mapped == cat:
                score += 2.0
                reasons.append(f"keyword:{kw}")

        # Partial substring match
        for kw in all_keywords:
            if kw and len(kw) > 2 and kw in cat:
                score += 1.0
                reasons.append(f"substring:{kw}")

        if score > best_score:
            best_score = score
            best_id = sem_id
            best_reason = " + ".join(reasons) if reasons else "default"

    # Fallback to first divider (strategy) if no match
    if best_score <= 0 and service_divider_pool:
        fallback = service_divider_pool[0]
        best_id = str(fallback.get("semantic_id", ""))
        best_reason = "default_fallback"

    return ServiceDividerSelectionResult(
        selected_service_divider=best_id,
        score=max(best_score, 0.0),
        reason=best_reason,
    )
