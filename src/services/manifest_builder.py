"""Manifest builder — converts assembly plans or WrittenSlides to ProposalManifest.

Two entry points:
1. build_manifest_from_assembly_plan() — template-first: uses slide budget,
   selection results, and methodology blueprint to build a proper manifest.
2. build_manifest_from_slides() — legacy bridge: maps SlideObjects to entries.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.models.enums import LayoutType
from src.models.proposal_manifest import (
    ContentSourcePolicy,
    ManifestEntry,
    ProposalManifest,
    build_inclusion_policy,
    get_company_profile_ids,
)
from src.models.slides import SlideObject

logger = logging.getLogger(__name__)

# ── Layout → semantic_layout_id mapping ─────────────────────────────────

_LAYOUT_TO_SEMANTIC: dict[LayoutType, str] = {
    LayoutType.CONTENT_1COL: "content_heading_desc",
    LayoutType.CONTENT_2COL: "content_heading_content",
    LayoutType.FRAMEWORK: "content_heading_desc",
    LayoutType.COMPARISON: "content_heading_content",
    LayoutType.STAT_CALLOUT: "content_heading_desc",
    LayoutType.TIMELINE: "content_heading_content",
    LayoutType.COMPLIANCE_MATRIX: "content_heading_desc",
    LayoutType.DATA_CHART: "content_heading_content",
}

# Default semantic layout for types not in the map
_DEFAULT_SEMANTIC = "content_heading_desc"

# Standard section names for ToC / dividers
_SECTION_NAMES_EN = [
    "Understanding", "Why Strategic Gears", "Methodology",
    "Timeline & Outcome", "Team", "Governance",
]
_SECTION_NAMES_AR = [
    "\u0627\u0644\u0641\u0647\u0645",
    "\u0644\u0645\u0627\u0630\u0627 \u0633\u062a\u0631\u0627\u062a\u064a\u062c\u064a\u0643 \u062c\u064a\u0631\u0632",
    "\u0627\u0644\u0645\u0646\u0647\u062c\u064a\u0629",
    "\u0627\u0644\u062c\u062f\u0648\u0644 \u0627\u0644\u0632\u0645\u0646\u064a",
    "\u0627\u0644\u0641\u0631\u064a\u0642",
    "\u0627\u0644\u062d\u0648\u0643\u0645\u0629",
]

_MAX_SECTIONS = 6


def _slide_to_injection_data(slide: SlideObject) -> dict[str, Any]:
    """Extract injection_data from a SlideObject."""
    body = ""
    if slide.body_content and slide.body_content.text_elements:
        body = "\n".join(slide.body_content.text_elements)

    injection_data: dict[str, Any] = {
        "title": slide.title,
        "body": body,
    }
    if slide.key_message:
        injection_data["bold_body_lead"] = slide.key_message
    return injection_data


def _slide_to_semantic_layout(slide: SlideObject) -> str:
    """Map a SlideObject's layout_type to a semantic_layout_id."""
    return _LAYOUT_TO_SEMANTIC.get(slide.layout_type, _DEFAULT_SEMANTIC)


def _assign_sections(slides: list[SlideObject]) -> list[tuple[SlideObject, str, bool]]:
    """Assign each slide to a section_id.

    Returns list of (slide, section_id, is_divider).
    SECTION layout_type slides become section dividers.
    Other slides are grouped under the preceding section.
    """
    result: list[tuple[SlideObject, str, bool]] = []

    # Check if any slides have SECTION layout
    has_section_dividers = any(s.layout_type == LayoutType.SECTION for s in slides)

    if has_section_dividers:
        current_section = "section_01"
        section_counter = 0
        for slide in slides:
            if slide.layout_type == LayoutType.SECTION:
                section_counter += 1
                capped = min(section_counter, _MAX_SECTIONS)
                current_section = f"section_{capped:02d}"
                result.append((slide, current_section, True))
            elif slide.layout_type == LayoutType.TITLE:
                # Title slides go to cover section, not counted as dividers
                result.append((slide, "cover", False))
            elif slide.layout_type == LayoutType.CLOSING:
                result.append((slide, "closing", False))
            else:
                result.append((slide, current_section, False))
    else:
        # No explicit section dividers — assign sequentially
        # Skip TITLE/CLOSING, distribute remaining across sections
        content_slides = [
            s for s in slides
            if s.layout_type not in (LayoutType.TITLE, LayoutType.CLOSING)
        ]
        content_count = len(content_slides)

        # Distribute evenly across up to 6 sections
        num_sections = min(_MAX_SECTIONS, max(1, content_count))
        slides_per_section = max(1, content_count // num_sections) if num_sections > 0 else 1

        content_idx = 0
        for slide in slides:
            if slide.layout_type == LayoutType.TITLE:
                result.append((slide, "cover", False))
            elif slide.layout_type == LayoutType.CLOSING:
                result.append((slide, "closing", False))
            else:
                section_num = min(content_idx // slides_per_section + 1, _MAX_SECTIONS)
                result.append((slide, f"section_{section_num:02d}", False))
                content_idx += 1

    return result


def build_manifest_from_slides(
    slides: list[SlideObject],
    rfp_context: Any | None = None,
    catalog_lock_path: Path | None = None,
    language: str = "en",
    proposal_mode: str = "standard",
    geography: str = "ksa",
    sector: str = "",
) -> ProposalManifest:
    """Convert a list of SlideObjects into a ProposalManifest.

    Builds a complete manifest with:
    - House entries (cover, intro, ToC, section dividers)
    - B-variable entries from each SlideObject
    - Company profile A1 clones
    - Closing A1 clones
    - Optional case study and team bio pool_clones (if catalog_lock_path given)
    """
    sec_names = _SECTION_NAMES_AR if language == "ar" else _SECTION_NAMES_EN

    # Build inclusion policy
    inclusion_policy = build_inclusion_policy(
        proposal_mode=proposal_mode,
        geography=geography,
        sector=sector,
        case_study_count=(4, 12),
        team_bio_count=(2, 6),
    )
    profile_ids = get_company_profile_ids(inclusion_policy.company_profile_depth)

    entries: list[ManifestEntry] = []

    # ── Cover / house entries ────────────────────────────────────────
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="proposal_cover",
        semantic_layout_id="proposal_cover",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="cover",
        injection_data={"subtitle": "", "client_name": "", "date_text": ""},
    ))
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="intro_message",
        semantic_layout_id="intro_message",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="cover",
    ))
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="toc_agenda",
        semantic_layout_id="toc_table",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="cover",
        injection_data={
            "title": (
                "\u062c\u062f\u0648\u0644 \u0627\u0644\u0645\u062d\u062a\u0648\u064a\u0627\u062a"
                if language == "ar"
                else "Table of Contents"
            ),
            "rows": [
                [f"{i + 1:02d}", sec_names[i]] for i in range(len(sec_names))
            ],
        },
    ))

    # ── Assign slides to sections ────────────────────────────────────
    assigned = _assign_sections(slides)

    # Track which sections we've already emitted a divider for
    emitted_sections: set[str] = {"cover"}

    for slide, section_id, is_divider in assigned:
        # Skip TITLE and CLOSING layout slides — they are handled
        # by the house entries and closing entries below.
        if slide.layout_type == LayoutType.TITLE:
            continue
        if slide.layout_type == LayoutType.CLOSING:
            continue

        # Emit section divider if entering a new section
        if section_id not in emitted_sections and section_id.startswith("section_"):
            emitted_sections.add(section_id)
            sec_num_str = section_id.split("_")[-1]
            sec_idx = int(sec_num_str) - 1
            sec_label = sec_names[sec_idx] if sec_idx < len(sec_names) else f"Section {sec_num_str}"

            entries.append(ManifestEntry(
                entry_type="a2_shell",
                asset_id=f"section_divider_{sec_num_str}",
                semantic_layout_id=f"section_divider_{sec_num_str}",
                content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
                section_id=section_id,
                injection_data={"title": sec_label, "body": " "},
            ))

        if is_divider:
            # Section divider slides are emitted as a2_shell above,
            # so skip adding them again as b_variable.
            continue

        # ── B-variable entry from SlideObject ────────────────────
        semantic_layout = _slide_to_semantic_layout(slide)
        injection_data = _slide_to_injection_data(slide)

        entries.append(ManifestEntry(
            entry_type="b_variable",
            asset_id=slide.slide_id.lower().replace("-", "_"),
            semantic_layout_id=semantic_layout,
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
            section_id=section_id,
            injection_data=injection_data,
        ))

    # ── Case study and team bio pool_clones (optional) ───────────────
    if catalog_lock_path is not None and catalog_lock_path.exists():
        try:
            lock_data = json.loads(catalog_lock_path.read_text(encoding="utf-8"))
            _add_pool_clones(entries, lock_data, rfp_context, language, geography, sector)
        except Exception:
            logger.warning("Failed to load catalog lock for pool clones", exc_info=True)

    # ── Company profile A1 clones ────────────────────────────────────
    for pid in profile_ids:
        entries.append(ManifestEntry(
            entry_type="a1_clone",
            asset_id=pid,
            semantic_layout_id=pid,
            content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
            section_id="company_profile",
        ))

    # ── Closing A1 clones ────────────────────────────────────────────
    for cid in ["know_more", "contact"]:
        entries.append(ManifestEntry(
            entry_type="a1_clone",
            asset_id=cid,
            semantic_layout_id=cid,
            content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
            section_id="closing",
        ))

    return ProposalManifest(entries=entries, inclusion_policy=inclusion_policy)


def _add_pool_clones(
    entries: list[ManifestEntry],
    lock_data: dict[str, Any],
    rfp_context: Any | None,
    language: str,
    geography: str,
    sector: str,
) -> None:
    """Add case study and team bio pool_clone entries from catalog lock."""
    from src.services.selection_policies import (
        select_case_studies,
        select_team_members,
    )

    # Extract services/keywords from RFP context when available.
    # Never hardcode domain-specific defaults — the pipeline must be RFP-agnostic.
    rfp_services: list[str] = []
    rfp_keywords: list[str] = []
    rfp_capabilities: list[str] = []
    if rfp_context is not None:
        scope_items = getattr(rfp_context, "scope_items", []) or []
        for item in scope_items:
            desc = getattr(item, "description", None)
            if desc:
                text = getattr(desc, "en", "") or ""
                if text:
                    rfp_capabilities.append(text.lower())
        mandate = getattr(rfp_context, "mandate", None)
        if mandate:
            mandate_text = getattr(mandate, "en", "") or ""
            if mandate_text:
                rfp_services.append(mandate_text.lower())

    rfp_ctx: dict[str, Any] = {
        "sector": sector,
        "services": rfp_services,
        "geography": geography,
        "technology_keywords": rfp_keywords,
        "capability_tags": rfp_capabilities,
        "language": language,
    }

    # Build case study candidates
    cs_candidates: list[dict[str, Any]] = []
    cs_idx_map: dict[str, int] = {}
    for _cat, cat_entries in lock_data.get("case_study_pool", {}).items():
        for entry in cat_entries:
            sid = entry["semantic_id"]
            cs_candidates.append({
                "asset_id": sid,
                "slide_idx": entry["slide_idx"],
                "semantic_layout_id": entry["semantic_layout_id"],
                "sector": sector,
                "services": rfp_services,
                "geography": geography,
                "technology_keywords": rfp_keywords,
                "capability_tags": rfp_capabilities,
                "language": language,
            })
            cs_idx_map[sid] = entry["slide_idx"]

    # Build team candidates
    team_candidates: list[dict[str, Any]] = []
    team_idx_map: dict[str, int] = {}
    for entry in lock_data.get("team_bio_pool", []):
        sid = entry["semantic_id"]
        team_candidates.append({
            "asset_id": sid,
            "slide_idx": entry["slide_idx"],
            "semantic_layout_id": entry["semantic_layout_id"],
            "sector_experience": [sector] if sector else [],
            "services": rfp_services,
            "roles": ["lead", "analyst"],
            "geography_experience": [geography] if geography else [],
            "technology_keywords": rfp_keywords,
            "language": language,
        })
        team_idx_map[sid] = entry["slide_idx"]

    # Select and add case studies
    if cs_candidates:
        try:
            cs_result = select_case_studies(
                cs_candidates, rfp_ctx, min_count=4, max_count=8,
            )
            # Find section_02 for case studies or fall back
            target_section = "section_02"
            for sa in cs_result.selected:
                slide_idx = cs_idx_map.get(sa.asset_id)
                if slide_idx is not None:
                    entries.append(ManifestEntry(
                        entry_type="pool_clone",
                        asset_id=sa.asset_id,
                        semantic_layout_id="case_study_cases",
                        content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
                        section_id=target_section,
                        injection_data={"source_slide_idx": slide_idx},
                    ))
        except Exception:
            logger.warning("Failed to select case studies", exc_info=True)

    # Select and add team bios
    if team_candidates:
        try:
            team_result = select_team_members(
                team_candidates, rfp_ctx, min_count=2, max_count=4,
            )
            target_section = "section_05"
            for sa in team_result.selected:
                slide_idx = team_idx_map.get(sa.asset_id)
                if slide_idx is not None:
                    entries.append(ManifestEntry(
                        entry_type="pool_clone",
                        asset_id=sa.asset_id,
                        semantic_layout_id="team_two_members",
                        content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
                        section_id=target_section,
                        injection_data={"source_slide_idx": slide_idx},
                    ))
        except Exception:
            logger.warning("Failed to select team members", exc_info=True)


# ── Assembly-plan-driven manifest builder ────────────────────────────


def build_manifest_from_assembly_plan(
    assembly_plan: Any,
    catalog_lock_path: Path | None = None,
    language: str = "en",
) -> ProposalManifest:
    """Build a ProposalManifest from an AssemblyPlanResult.

    This is the template-first path: the assembly plan contains the
    inclusion policy, methodology blueprint, selection results, and
    slide budget.  The manifest is built deterministically from these.

    Parameters
    ----------
    assembly_plan : AssemblyPlanResult
        Complete assembly plan from the assembly_plan agent.
    catalog_lock_path : Path, optional
        Path to catalog lock JSON for slide_idx lookups.
    language : str
        "en" or "ar".

    Returns
    -------
    ProposalManifest
        Ordered list of ManifestEntry objects ready for renderer_v2.
    """
    from src.models.proposal_manifest import (
        get_company_profile_ids,
        get_ksa_context_ids,
    )

    policy = assembly_plan.inclusion_policy
    budget = assembly_plan.slide_budget
    meth_bp = assembly_plan.methodology_blueprint
    cs_result = assembly_plan.case_study_result
    team_result = assembly_plan.team_result
    llm_output = assembly_plan.llm_output

    sec_names = _SECTION_NAMES_AR if language == "ar" else _SECTION_NAMES_EN

    # Load catalog lock for slide_idx lookups
    lock_data: dict[str, Any] = {}
    if catalog_lock_path and catalog_lock_path.exists():
        try:
            lock_data = json.loads(catalog_lock_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load catalog lock", exc_info=True)

    # Build slide_idx lookup maps
    cs_idx_map: dict[str, int] = {}
    cs_pool_raw = lock_data.get("case_study_pool", {})
    if isinstance(cs_pool_raw, dict):
        for entries in cs_pool_raw.values():
            for entry in entries:
                cs_idx_map[entry["semantic_id"]] = entry["slide_idx"]
    elif isinstance(cs_pool_raw, list):
        for entry in cs_pool_raw:
            cs_idx_map[entry["semantic_id"]] = entry["slide_idx"]

    team_idx_map: dict[str, int] = {}
    for entry in lock_data.get("team_bio_pool", []):
        team_idx_map[entry["semantic_id"]] = entry["slide_idx"]

    entries: list[ManifestEntry] = []

    # ── Cover section (3 A2 shells) ────────────────────────────────
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="proposal_cover",
        semantic_layout_id="proposal_cover",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="cover",
        injection_data={
            "subtitle": llm_output.rfp_summary[:100] if llm_output.rfp_summary else "",
            "client_name": llm_output.client_name,
            "date_text": "",
        },
    ))
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="intro_message",
        semantic_layout_id="intro_message",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="cover",
    ))
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="toc_agenda",
        semantic_layout_id="toc_table",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="cover",
        injection_data={
            "title": (
                "\u062c\u062f\u0648\u0644 \u0627\u0644\u0645\u062d\u062a\u0648\u064a\u0627\u062a"
                if language == "ar"
                else "Table of Contents"
            ),
            "rows": [
                [f"{i + 1:02d}", sec_names[i]] for i in range(len(sec_names))
            ],
        },
    ))

    # ── Section 01: Understanding (divider + b_variable content) ───
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="section_divider_01",
        semantic_layout_id="section_divider_01",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="section_01",
        injection_data={"title": sec_names[0], "body": " "},
    ))
    understanding_count = budget.section_budgets["section_01"].breakdown.get("content", 3)
    for i in range(understanding_count):
        entries.append(ManifestEntry(
            entry_type="b_variable",
            asset_id=f"understanding_{i + 1:02d}",
            semantic_layout_id="content_heading_desc",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
            section_id="section_01",
        ))

    # ── Section 02: Why Strategic Gears ────────────────────────────
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="section_divider_02",
        semantic_layout_id="section_divider_02",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="section_02",
        injection_data={"title": sec_names[1], "body": " "},
    ))

    # KSA context A1 clones (only for geography=ksa)
    if policy.include_ksa_context:
        for kid in get_ksa_context_ids():
            entries.append(ManifestEntry(
                entry_type="a1_clone",
                asset_id=kid,
                semantic_layout_id=kid,
                content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
                section_id="section_02",
            ))

    # Case study pool clones (deterministically selected)
    for sa in cs_result.selected:
        slide_idx = cs_idx_map.get(sa.asset_id)
        layout_id = "case_study_cases"
        # Check if it's the detailed layout
        if slide_idx is not None:
            for entries_list in (cs_pool_raw.values() if isinstance(cs_pool_raw, dict) else [cs_pool_raw]):
                for e in entries_list:
                    if e.get("semantic_id") == sa.asset_id:
                        layout_id = e.get("semantic_layout_id", "case_study_cases")
                        break
        entries.append(ManifestEntry(
            entry_type="pool_clone",
            asset_id=sa.asset_id,
            semantic_layout_id=layout_id,
            content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
            section_id="section_02",
            injection_data={"source_slide_idx": slide_idx} if slide_idx else None,
        ))

    # Service divider pool clone (selected by deterministic policy)
    svc_result = getattr(assembly_plan, "service_divider_result", None)
    svc_divider_id = ""
    if svc_result:
        svc_divider_id = getattr(svc_result, "selected_service_divider", "")
    svc_divider_pool = lock_data.get("service_divider_pool", [])
    if svc_divider_id:
        # Find matching pool entry for slide_idx
        svc_layout = svc_divider_id
        svc_slide_idx = None
        for sd in svc_divider_pool:
            if sd.get("semantic_id") == svc_divider_id:
                svc_layout = sd.get("semantic_layout_id", svc_divider_id)
                svc_slide_idx = sd.get("slide_idx")
                break
        entries.append(ManifestEntry(
            entry_type="pool_clone",
            asset_id=svc_divider_id,
            semantic_layout_id=svc_layout,
            content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
            section_id="section_02",
            injection_data=(
                {"source_slide_idx": svc_slide_idx}
                if svc_slide_idx else None
            ),
        ))
    elif svc_divider_pool:
        # Fallback: use first service divider
        fallback = svc_divider_pool[0]
        entries.append(ManifestEntry(
            entry_type="pool_clone",
            asset_id=fallback.get("semantic_id", "svc_divider_strategy"),
            semantic_layout_id=fallback.get(
                "semantic_layout_id", "svc_strategy"
            ),
            content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
            section_id="section_02",
            injection_data=(
                {"source_slide_idx": fallback.get("slide_idx")}
                if fallback.get("slide_idx") else None
            ),
        ))

    # ── Section 03: Methodology ────────────────────────────────────
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="section_divider_03",
        semantic_layout_id="section_divider_03",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="section_03",
        injection_data={"title": sec_names[2], "body": " "},
    ))

    # Methodology overview slide
    overview_layout = meth_bp.phases[0].overview_layout if meth_bp.phases else "methodology_overview_4"
    entries.append(ManifestEntry(
        entry_type="b_variable",
        asset_id="methodology_overview",
        semantic_layout_id=overview_layout,
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="section_03",
    ))

    # Per-phase focused + detail slides
    for phase in meth_bp.phases:
        for fl in phase.focused_layouts:
            entries.append(ManifestEntry(
                entry_type="b_variable",
                asset_id=f"methodology_{phase.phase_id}_focused",
                semantic_layout_id=fl,
                content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
                section_id="section_03",
                methodology_phase=phase.phase_id,
            ))
        for dl in phase.detail_layouts:
            entries.append(ManifestEntry(
                entry_type="b_variable",
                asset_id=f"methodology_{phase.phase_id}_detail",
                semantic_layout_id=dl,
                content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
                section_id="section_03",
                methodology_phase=phase.phase_id,
            ))

    # ── Section 04: Timeline & Outcome ─────────────────────────────
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="section_divider_04",
        semantic_layout_id="section_divider_04",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="section_04",
        injection_data={"title": sec_names[3], "body": " "},
    ))
    timeline_count = budget.section_budgets["section_04"].breakdown.get("content", 2)
    for i in range(timeline_count):
        entries.append(ManifestEntry(
            entry_type="b_variable",
            asset_id=f"timeline_{i + 1:02d}",
            semantic_layout_id="content_heading_content",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
            section_id="section_04",
        ))

    # ── Section 05: Team ───────────────────────────────────────────
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="section_divider_05",
        semantic_layout_id="section_divider_05",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="section_05",
        injection_data={"title": sec_names[4], "body": " "},
    ))

    # Leadership A1 clone (standard/full mode)
    if policy.include_leadership:
        entries.append(ManifestEntry(
            entry_type="a1_clone",
            asset_id="our_leadership",
            semantic_layout_id="our_leadership",
            content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
            section_id="section_05",
        ))

    # Team bio pool clones (deterministically selected)
    for sa in team_result.selected:
        slide_idx = team_idx_map.get(sa.asset_id)
        entries.append(ManifestEntry(
            entry_type="pool_clone",
            asset_id=sa.asset_id,
            semantic_layout_id="team_two_members",
            content_source_policy=ContentSourcePolicy.APPROVED_ASSET_POOL,
            section_id="section_05",
            injection_data={"source_slide_idx": slide_idx} if slide_idx else None,
        ))

    # ── Section 06: Governance ─────────────────────────────────────
    entries.append(ManifestEntry(
        entry_type="a2_shell",
        asset_id="section_divider_06",
        semantic_layout_id="section_divider_06",
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id="section_06",
        injection_data={"title": sec_names[5], "body": " "},
    ))
    governance_count = budget.section_budgets["section_06"].breakdown.get("content", 1)
    for i in range(governance_count):
        entries.append(ManifestEntry(
            entry_type="b_variable",
            asset_id=f"governance_{i + 1:02d}",
            semantic_layout_id="content_heading_content",
            content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
            section_id="section_06",
        ))

    # ── Company Profile A1 clones ──────────────────────────────────
    for pid in get_company_profile_ids(policy.company_profile_depth):
        entries.append(ManifestEntry(
            entry_type="a1_clone",
            asset_id=pid,
            semantic_layout_id=pid,
            content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
            section_id="company_profile",
        ))

    # Services overview (full mode only)
    if policy.include_services_overview:
        entries.append(ManifestEntry(
            entry_type="a1_clone",
            asset_id="services_overview",
            semantic_layout_id="services_overview",
            content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
            section_id="company_profile",
        ))

    # ── Closing A1 clones ──────────────────────────────────────────
    for cid in ["know_more", "contact"]:
        entries.append(ManifestEntry(
            entry_type="a1_clone",
            asset_id=cid,
            semantic_layout_id=cid,
            content_source_policy=ContentSourcePolicy.INSTITUTIONAL_REUSE,
            section_id="closing",
        ))

    manifest = ProposalManifest(entries=entries, inclusion_policy=policy)

    # ── Invariant: manifest.total_slides must equal slide budget ───
    budget = assembly_plan.slide_budget
    if budget is not None:
        budget_total = getattr(budget, "total_slides", None)
        if budget_total is not None and manifest.total_slides != budget_total:
            raise ValueError(
                f"Manifest/budget mismatch: manifest has "
                f"{manifest.total_slides} entries but slide budget "
                f"expects {budget_total}. This is a pipeline invariant "
                f"violation — the manifest builder must produce exactly "
                f"as many entries as the slide budgeter computed."
            )

    return manifest
