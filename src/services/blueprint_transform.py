"""Transform Source Book legacy blueprints to template-contract schema.

Maps the Source Book's SlideBlueprintEntry (slide_number, proof_points, etc.)
to the ownership-aware SlideBlueprintEntry (section_id, ownership, house_action)
required by the template contract, then validates against TEMPLATE_SECTION_ORDER.
"""

from __future__ import annotations

import logging
import re

from src.models.slide_blueprint import SlideBlueprintEntry as ContractEntry
from src.models.slide_blueprint import SlideBlueprint
from src.models.source_book import SlideBlueprintEntry as LegacyEntry
from src.models.template_contract import TEMPLATE_SECTION_ORDER, TemplateSectionSpec
from src.services.template_validator import validate_blueprint_against_template

logger = logging.getLogger(__name__)

# Map legacy slide "section" text to canonical section_id.
# Keys are lowercase substrings matched against the legacy entry's `section` field.
_SECTION_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["cover", "غلاف", "عنوان"], "S01"),
    (["executive summary", "ملخص تنفيذي", "introduction message"], "S02"),
    (["table of contents", "محتويات", "فهرس", "معايير التقييم"], "S03"),
    (["introduction", "understanding", "فهم", "تشخيص", "مقدمة"], "S05"),
    (["why strategic", "لماذا", "قدرات", "تطابق", "أرقام"], "S07"),
    (["team", "فريق", "خبرات"], "S12"),
    (["methodology", "منهجية", "مرحلة", "phase", "أدوات", "أطر"], "S09"),
    (["timeline", "جدول زمني", "زمني", "مخرجات"], "S11"),
    (["case study", "دراسة حالة", "حالة"], "S18"),
    (["governance", "حوكمة", "إدارة المخاطر"], "S13"),
    (["compliance", "امتثال", "تنظيمي"], "S14"),
    (["closing", "ختام", "شريك", "ملاحق"], "S31"),
    (["knowledge transfer", "نقل المعرفة", "بناء القدرات"], "S09"),
    (["نماذج دولية", "benchmark", "مقارن"], "S05"),
    (["نطاق العمل", "scope"], "S05"),
]

# Sections that are dynamic (LLM-generated content)
_DYNAMIC_SECTIONS = {"S02", "S05", "S07", "S09", "S11"}

# Sections that are hybrid (shell + parameterized title/key_message)
_HYBRID_SECTIONS = {"S01", "S03", "S04", "S06", "S08", "S10", "S12", "S13"}


def _classify_section_id(legacy: LegacyEntry) -> str:
    """Map a legacy blueprint entry to a canonical section_id."""
    combined = f"{legacy.section} {legacy.title} {legacy.purpose}".lower()

    for keywords, section_id in _SECTION_KEYWORD_MAP:
        for kw in keywords:
            if kw.lower() in combined:
                return section_id

    # Fallback: try to infer from slide number ranges
    sn = legacy.slide_number
    if sn <= 1:
        return "S01"
    if sn == 2:
        return "S02"
    if sn == 3:
        return "S03"
    if sn <= 8:
        return "S05"
    if sn <= 10:
        return "S07"
    if sn <= 14:
        return "S09"
    if sn <= 16:
        return "S11"
    if sn <= 17:
        return "S12"
    if sn <= 18:
        return "S13"
    return "S05"  # Default to understanding block


def _get_spec(section_id: str) -> TemplateSectionSpec | None:
    """Look up the template spec for a section_id."""
    for spec in TEMPLATE_SECTION_ORDER:
        if spec.section_id == section_id:
            return spec
    return None


def _to_contract_entry(legacy: LegacyEntry, section_id: str) -> ContractEntry:
    """Convert a single legacy entry to a contract entry."""
    spec = _get_spec(section_id)
    if spec is None:
        raise ValueError(f"Unknown section_id: {section_id}")

    section_name = spec.section_name
    ownership = spec.ownership

    # Collect evidence IDs from proof_points and must_have_evidence
    evidence_ids = list(
        dict.fromkeys(
            (legacy.proof_points or []) + (legacy.must_have_evidence or [])
        )
    ) or None

    if ownership == "house":
        return ContractEntry(
            section_id=section_id,
            section_name=section_name,
            ownership="house",
            house_action="include_as_is",
        )

    if ownership == "hybrid":
        return ContractEntry(
            section_id=section_id,
            section_name=section_name,
            ownership="hybrid",
            slide_title=legacy.title or None,
            key_message=legacy.key_message or None,
            house_action="include_as_is",
        )

    # Dynamic entry
    return ContractEntry(
        section_id=section_id,
        section_name=section_name,
        ownership="dynamic",
        slide_title=legacy.title or None,
        key_message=legacy.key_message or None,
        bullet_points=legacy.bullet_logic if legacy.bullet_logic else None,
        evidence_ids=evidence_ids,
        visual_guidance=legacy.visual_guidance or None,
    )


# Divider section content — proper proposal-grade titles and framing
# for hybrid divider sections. Keyed by section_id.
_DIVIDER_CONTENT: dict[str, dict[str, str]] = {
    "S04": {
        "slide_title": "فهم المشروع والسياق المؤسسي",
        "key_message": "تحليل شامل للوضع الراهن والاحتياجات والتحديات التي تواجه العميل",
        "visual_guidance": "Section divider with client logo and engagement context visual",
    },
    "S06": {
        "slide_title": "لماذا ستراتيجيك غيرز",
        "key_message": "القدرات والخبرات والفريق الذي يضمن نجاح المشروع",
        "visual_guidance": "Section divider with SG brand identity and capability highlights",
    },
    "S08": {
        "slide_title": "المنهجية والنهج المقترح",
        "key_message": "إطار منهجي متكامل مصمم خصيصاً لتحقيق أهداف المشروع",
        "visual_guidance": "Section divider with methodology overview icon or phase diagram",
    },
    "S10": {
        "slide_title": "الجدول الزمني والمخرجات",
        "key_message": "خارطة طريق واضحة بمراحل محددة ومخرجات قابلة للقياس",
        "visual_guidance": "Section divider with timeline preview or milestone markers",
    },
}


def _ensure_all_sections(entries: list[ContractEntry]) -> list[ContractEntry]:
    """Add missing sections from the template contract with appropriate defaults.

    For hybrid divider sections (S04, S06, S08, S10), generates proper
    proposal-grade content instead of echoing the section name as a shell.
    """
    seen = {e.section_id for e in entries}
    additions: list[ContractEntry] = []

    for spec in TEMPLATE_SECTION_ORDER:
        if spec.section_id in seen:
            continue
        if spec.ownership == "house":
            additions.append(ContractEntry(
                section_id=spec.section_id,
                section_name=spec.section_name,
                ownership="house",
                house_action="skip",
            ))
        elif spec.ownership == "hybrid":
            # Use proper divider content if available
            divider = _DIVIDER_CONTENT.get(spec.section_id, {})
            additions.append(ContractEntry(
                section_id=spec.section_id,
                section_name=spec.section_name,
                ownership="hybrid",
                slide_title=divider.get("slide_title", spec.section_name),
                key_message=divider.get("key_message", f"Transition to {spec.section_name}"),
                visual_guidance=divider.get("visual_guidance"),
                house_action="include_as_is",
            ))
        else:
            additions.append(ContractEntry(
                section_id=spec.section_id,
                section_name=spec.section_name,
                ownership="dynamic",
                slide_title=spec.section_name,
                key_message=f"{spec.section_name} content",
            ))

    return entries + additions


def _sort_by_template_order(entries: list[ContractEntry]) -> list[ContractEntry]:
    """Sort entries by canonical S01-S31 template order."""
    order_map = {
        spec.section_id: idx
        for idx, spec in enumerate(TEMPLATE_SECTION_ORDER)
    }
    return sorted(entries, key=lambda e: order_map.get(e.section_id, 999))


def transform_to_contract_blueprint(
    legacy_blueprints: list[LegacyEntry],
) -> tuple[list[ContractEntry], list[str]]:
    """Transform legacy Source Book blueprints to template-contract schema.

    Args:
        legacy_blueprints: Source Book's slide_blueprints (legacy format).

    Returns:
        Tuple of (contract_entries, validation_violations).
        Empty violations list means the blueprint passes validation.
    """
    if not legacy_blueprints:
        logger.warning("No legacy blueprints to transform")
        return [], ["No blueprints provided"]

    # Phase 1: Classify each legacy entry to a section_id
    classified: dict[str, list[LegacyEntry]] = {}
    for bp in legacy_blueprints:
        sid = _classify_section_id(bp)
        classified.setdefault(sid, []).append(bp)

    logger.info(
        "Blueprint classification: %d legacy entries -> %d sections: %s",
        len(legacy_blueprints),
        len(classified),
        ", ".join(f"{k}({len(v)})" for k, v in sorted(classified.items())),
    )

    # Phase 2: Convert to contract entries, respecting max_dynamic_slides
    contract_entries: list[ContractEntry] = []
    for sid, group in classified.items():
        spec = _get_spec(sid)
        if spec is None:
            continue

        max_slides = spec.max_dynamic_slides
        entries_to_convert = group
        if max_slides is not None and len(group) > max_slides:
            entries_to_convert = group[:max_slides]

        for legacy in entries_to_convert:
            try:
                entry = _to_contract_entry(legacy, sid)
                contract_entries.append(entry)
            except Exception as e:
                logger.warning("Failed to convert blueprint: %s", e)

    # Phase 3: Ensure all 31 sections are present
    contract_entries = _ensure_all_sections(contract_entries)

    # Phase 4: Sort by template order
    contract_entries = _sort_by_template_order(contract_entries)

    # Phase 5: Validate
    violations = validate_blueprint_against_template(
        contract_entries, TEMPLATE_SECTION_ORDER,
    )

    if violations:
        logger.warning(
            "Blueprint validation: %d violations: %s",
            len(violations),
            "; ".join(violations[:5]),
        )
    else:
        logger.info("Blueprint validation: PASSED (0 violations)")

    return contract_entries, violations
