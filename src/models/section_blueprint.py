"""Phase 3a — Section Blueprints.

Defines the mandatory proposal section structure derived from template
section dividers and grammar artifacts.  Each SectionBlueprint captures
the narrative function, evidence style, expected slide patterns, and
recommended layouts (by semantic layout ID — never raw display names).

The MANDATORY_SECTION_ORDER is the fixed flow enforced by the manifest
builder and validated before every render.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Mandatory section flow ────────────────────────────────────────────────

MANDATORY_SECTION_ORDER: tuple[str, ...] = (
    "cover",              # Proposal cover + intro letter + ToC
    "section_01",         # Understanding
    "section_02",         # Why Strategic Gears
    "section_03",         # Methodology
    "section_04",         # Timeline & Outcome
    "section_05",         # Team
    "section_06",         # Governance
    "company_profile",    # Company profile block (depth varies)
    "closing",            # Know More + Contact
)


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SectionBlueprint:
    """Blueprint for one proposal section."""

    section_id: str
    section_number: int                     # 1-6 for divider sections, 0 for non-divider
    section_name_en: str
    section_name_ar: str
    narrative_function: str                 # e.g. "client understanding", "methodology"
    evidence_style: str                     # e.g. "proof_by_case", "structured_framework"
    expected_slide_pattern: list[str]       # e.g. ["understanding_overview", "key_challenges"]
    content_density: str                    # "lean" | "standard" | "detailed"
    slide_class: str                        # "a1" | "a2" | "b_variable" | "mixed"
    expects_methodology: bool = False
    expects_governance: bool = False
    expects_timeline: bool = False
    expects_proof: bool = False
    expects_team: bool = False
    expects_case_studies: bool = False
    template_framing_language: list[str] = field(default_factory=list)
    recommended_layouts: list[str] = field(default_factory=list)  # semantic layout IDs


# ── Section definitions ───────────────────────────────────────────────────
# These are the canonical section blueprints derived from the template
# structure and all 3 real example decks.

_SECTION_DEFS: dict[str, dict[str, Any]] = {
    "cover": {
        "section_number": 0,
        "section_name_en": "Cover & Introduction",
        "section_name_ar": "الغلاف والمقدمة",
        "narrative_function": "first_impression",
        "evidence_style": "institutional_branding",
        "expected_slide_pattern": ["proposal_cover", "intro_message", "toc_agenda"],
        "content_density": "lean",
        "slide_class": "a2",
        "recommended_layouts": [
            "proposal_cover", "intro_message", "toc_table",
        ],
    },
    "section_01": {
        "section_number": 1,
        "section_name_en": "Introduction and Our Understanding of the Project",
        "section_name_ar": "المقدمة وفهمنا للمشروع",
        "narrative_function": "client_understanding",
        "evidence_style": "analytical_synthesis",
        "expected_slide_pattern": [
            "understanding_overview", "key_challenges", "strategic_context",
        ],
        "content_density": "standard",
        "slide_class": "b_variable",
        "expects_proof": True,
        "recommended_layouts": [
            "content_heading_desc", "content_heading_content",
            "content_heading_only", "layout_heading_and_4_boxes_of_content",
        ],
    },
    "section_02": {
        "section_number": 2,
        "section_name_en": "Why Strategic Gears",
        "section_name_ar": "لماذا ستراتيجيك قيرز",
        "narrative_function": "credibility_and_differentiation",
        "evidence_style": "proof_by_case",
        "expected_slide_pattern": [
            "company_credentials", "relevant_experience", "case_studies",
        ],
        "content_density": "standard",
        "slide_class": "mixed",
        "expects_case_studies": True,
        "recommended_layouts": [
            "content_heading_desc", "content_heading_content",
            "case_study_cases", "case_study_detailed",
        ],
    },
    "section_03": {
        "section_number": 3,
        "section_name_en": "Methodology",
        "section_name_ar": "المنهجية",
        "narrative_function": "methodology_and_approach",
        "evidence_style": "structured_framework",
        "expected_slide_pattern": [
            "methodology_overview", "phase_focused", "phase_detail",
        ],
        "content_density": "detailed",
        "slide_class": "b_variable",
        "expects_methodology": True,
        "recommended_layouts": [
            "methodology_overview_4", "methodology_overview_3",
            "methodology_focused_4", "methodology_focused_3",
            "methodology_detail",
        ],
    },
    "section_04": {
        "section_number": 4,
        "section_name_en": "Project Timeline & Outcome",
        "section_name_ar": "الجدول الزمني والمخرجات",
        "narrative_function": "timeline_and_deliverables",
        "evidence_style": "tabular_structured",
        "expected_slide_pattern": [
            "timeline_overview", "deliverables_table",
        ],
        "content_density": "standard",
        "slide_class": "b_variable",
        "expects_timeline": True,
        "recommended_layouts": [
            "content_heading_content",
            "layout_heading_description_and_content_box",
        ],
    },
    "section_05": {
        "section_number": 5,
        "section_name_en": "Proposed Project Team",
        "section_name_ar": "فريق المشروع المقترح",
        "narrative_function": "team_credentials",
        "evidence_style": "biographical",
        "expected_slide_pattern": [
            "team_overview", "team_bios",
        ],
        "content_density": "standard",
        "slide_class": "mixed",
        "expects_team": True,
        "recommended_layouts": [
            "team_two_members", "content_heading_desc",
        ],
    },
    "section_06": {
        "section_number": 6,
        "section_name_en": "Project Governance",
        "section_name_ar": "حوكمة المشروع",
        "narrative_function": "governance_framework",
        "evidence_style": "structured_framework",
        "expected_slide_pattern": [
            "governance_tiers", "escalation_path",
        ],
        "content_density": "lean",
        "slide_class": "b_variable",
        "expects_governance": True,
        "recommended_layouts": [
            "content_heading_content",
            "layout_heading_and_4_boxes_of_content",
        ],
    },
    "company_profile": {
        "section_number": 0,
        "section_name_en": "Company Profile",
        "section_name_ar": "ملف الشركة",
        "narrative_function": "institutional_identity",
        "evidence_style": "institutional_branding",
        "expected_slide_pattern": [
            "main_cover", "overview", "credentials",
        ],
        "content_density": "standard",
        "slide_class": "a1",
        "recommended_layouts": [],  # A1 clones — no layout routing needed
    },
    "closing": {
        "section_number": 0,
        "section_name_en": "Closing",
        "section_name_ar": "الختام",
        "narrative_function": "call_to_action",
        "evidence_style": "institutional_branding",
        "expected_slide_pattern": ["know_more", "contact"],
        "content_density": "lean",
        "slide_class": "a1",
        "recommended_layouts": [],  # A1 clones — no layout routing needed
    },
}


def build_section_blueprints(
    grammar_dir: Path | None = None,
) -> dict[str, SectionBlueprint]:
    """Build all section blueprints.

    Parameters
    ----------
    grammar_dir : Path, optional
        Path to template_grammar directory.  If provided, section naming
        grammar is loaded to enrich template_framing_language fields.

    Returns
    -------
    dict[str, SectionBlueprint]
        Section ID -> SectionBlueprint mapping.
    """
    framing: dict[str, list[str]] = {}
    if grammar_dir and grammar_dir.exists():
        naming_path = grammar_dir / "section_naming_grammar.json"
        if naming_path.exists():
            with open(naming_path, encoding="utf-8") as f:
                naming = json.load(f)
            for num_str, entry in naming.items():
                sid = f"section_{num_str.zfill(2)}"
                title = entry.get("title", "")
                subtitle = entry.get("subtitle", "")
                parts = [p for p in (title, subtitle) if p]
                if parts:
                    framing[sid] = parts

    blueprints: dict[str, SectionBlueprint] = {}
    for sid, defn in _SECTION_DEFS.items():
        blueprints[sid] = SectionBlueprint(
            section_id=sid,
            section_number=defn["section_number"],
            section_name_en=defn["section_name_en"],
            section_name_ar=defn["section_name_ar"],
            narrative_function=defn["narrative_function"],
            evidence_style=defn["evidence_style"],
            expected_slide_pattern=defn["expected_slide_pattern"],
            content_density=defn["content_density"],
            slide_class=defn["slide_class"],
            expects_methodology=defn.get("expects_methodology", False),
            expects_governance=defn.get("expects_governance", False),
            expects_timeline=defn.get("expects_timeline", False),
            expects_proof=defn.get("expects_proof", False),
            expects_team=defn.get("expects_team", False),
            expects_case_studies=defn.get("expects_case_studies", False),
            template_framing_language=framing.get(sid, []),
            recommended_layouts=defn.get("recommended_layouts", []),
        )
    return blueprints


def get_section_for_divider(divider_number: int) -> str:
    """Map a divider number (1-6) to a section ID.

    Raises
    ------
    ValueError
        If divider_number is not 1-6.
    """
    if not 1 <= divider_number <= 6:
        raise ValueError(
            f"Divider number must be 1-6, got {divider_number}"
        )
    return f"section_{divider_number:02d}"


def validate_section_order(section_ids: list[str]) -> list[str]:
    """Validate that section_ids follow MANDATORY_SECTION_ORDER.

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []
    order_index = {sid: i for i, sid in enumerate(MANDATORY_SECTION_ORDER)}

    prev_idx = -1
    for sid in section_ids:
        if sid not in order_index:
            errors.append(f"Unknown section ID: {sid}")
            continue
        idx = order_index[sid]
        if idx <= prev_idx:
            errors.append(
                f"Section '{sid}' is out of order "
                f"(must come after '{MANDATORY_SECTION_ORDER[prev_idx]}')"
            )
        prev_idx = idx

    return errors
