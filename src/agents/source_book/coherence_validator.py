"""Cross-section coherence validator for Engine 1 source books.

Post-generation pass that checks:
1. Governance naming consistency across sections.
2. Evidence posture consistency (claims don't exceed available proof).
3. Compliance requirements from Section 1 are carried through Section 5/6.
4. Language strength vs proof strength alignment.
5. No section contradicts another on methodology, timeline, or team.
"""

from __future__ import annotations

import logging
import re

from src.models.source_book import (
    AssertionLabel,
    CoherenceResult,
    SourceBook,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Governance naming patterns
# ──────────────────────────────────────────────────────────────

_GOVERNANCE_TERMS_EN = [
    "steering committee", "project board", "pmo",
    "program management office", "governance board",
    "quality assurance", "escalation", "raci",
]

_GOVERNANCE_TERMS_AR = [
    "لجنة توجيهية", "مكتب إدارة المشاريع", "لجنة حوكمة",
    "ضمان الجودة", "التصعيد", "مصفوفة المسؤوليات",
]


def _extract_governance_terms(text: str) -> set[str]:
    """Extract governance-related terms from text."""
    found: set[str] = set()
    text_lower = text.lower()
    for term in _GOVERNANCE_TERMS_EN:
        if term in text_lower:
            found.add(term)
    for term in _GOVERNANCE_TERMS_AR:
        if term in text:
            found.add(term)
    return found


def _check_governance_consistency(source_book: SourceBook) -> list[str]:
    """Check governance terms are consistent across sections."""
    issues: list[str] = []

    # Section 5 governance text
    s5_gov = source_book.proposed_solution.governance_framework or ""
    s5_terms = _extract_governance_terms(s5_gov)

    # Section 5 phase governance
    phase_gov_terms: set[str] = set()
    for phase in source_book.proposed_solution.phase_details:
        if phase.governance:
            phase_gov_terms |= _extract_governance_terms(phase.governance)

    # Blueprint governance terms
    bp_terms: set[str] = set()
    for bp in source_book.slide_blueprints:
        combined = f"{bp.title} {bp.key_message} {' '.join(bp.bullet_logic or [])}"
        bp_terms |= _extract_governance_terms(combined)

    # Check: terms used in blueprints should exist in Section 5
    missing_in_s5 = bp_terms - s5_terms - phase_gov_terms
    if missing_in_s5:
        issues.append(
            f"Governance terms in blueprints but not in Section 5: "
            f"{', '.join(sorted(missing_in_s5))}"
        )

    # Check: Section 5 mentions governance body not referenced in phases
    if s5_terms and not phase_gov_terms:
        issues.append(
            "Section 5 governance_framework mentions governance bodies "
            "but individual phases have no governance detail"
        )

    return issues


def _check_evidence_posture(source_book: SourceBook) -> list[str]:
    """Check evidence posture consistency across sections.

    Detects when prose makes strong claims but evidence ledger
    shows gaps or low confidence for the same topics.
    """
    issues: list[str] = []

    # Collect gap evidence IDs
    gap_ids: set[str] = set()
    low_confidence_ids: set[str] = set()
    for entry in source_book.evidence_ledger.entries:
        if entry.verifiability_status == "gap":
            gap_ids.add(entry.claim_id)
        if entry.confidence < 0.4:
            low_confidence_ids.add(entry.claim_id)

    # Check blueprints referencing gap evidence
    for bp in source_book.slide_blueprints:
        for ref in bp.proof_points:
            if ref in gap_ids:
                issues.append(
                    f"Slide {bp.slide_number} references {ref} as proof_point "
                    f"but evidence ledger marks it as 'gap'"
                )

    # Check capability mapping references
    for cm in source_book.why_strategic_gears.capability_mapping:
        for eid in cm.evidence_ids:
            if eid in gap_ids and cm.strength in ("strong", "moderate"):
                issues.append(
                    f"Capability '{cm.rfp_requirement}' rated '{cm.strength}' "
                    f"but {eid} is an evidence gap"
                )

    return issues


def _check_compliance_carrythrough(source_book: SourceBook) -> list[str]:
    """Check compliance requirements from Section 1 appear in Section 5/6.

    Uses typed compliance_rows first, falls back to legacy
    key_compliance_requirements if typed rows are empty.
    """
    issues: list[str] = []
    rfp = source_book.rfp_interpretation

    # Build searchable text from Section 5 and blueprints
    s5_text = " ".join([
        source_book.proposed_solution.methodology_overview,
        source_book.proposed_solution.governance_framework,
        source_book.proposed_solution.timeline_logic,
        source_book.proposed_solution.value_case_and_differentiation,
    ])
    for phase in source_book.proposed_solution.phase_details:
        s5_text += " " + " ".join(phase.activities + phase.deliverables)

    bp_text = " ".join(
        f"{bp.title} {bp.key_message} {' '.join(bp.bullet_logic or [])}"
        for bp in source_book.slide_blueprints
    )
    combined = (s5_text + " " + bp_text).lower()

    # Prefer typed compliance_rows over legacy list
    if rfp.compliance_rows:
        unaddressed = []
        for row in rfp.compliance_rows:
            key_terms = [w for w in row.requirement_text.lower().split() if len(w) > 4]
            if not key_terms:
                continue
            matches = sum(1 for t in key_terms if t in combined)
            if matches < max(1, len(key_terms) // 2):
                unaddressed.append(f"{row.requirement_id}: {row.requirement_text}")
        if unaddressed:
            issues.append(
                f"{len(unaddressed)} compliance requirements from Section 1 "
                f"not addressed in Section 5/6: {'; '.join(unaddressed[:3])}"
            )
    elif rfp.key_compliance_requirements:
        unaddressed_legacy = []
        for req in rfp.key_compliance_requirements:
            key_terms = [w for w in req.lower().split() if len(w) > 4]
            if not key_terms:
                continue
            matches = sum(1 for t in key_terms if t in combined)
            if matches < max(1, len(key_terms) // 2):
                unaddressed_legacy.append(req)
        if unaddressed_legacy:
            issues.append(
                f"{len(unaddressed_legacy)} compliance requirements from Section 1 "
                f"not addressed in Section 5/6: {'; '.join(unaddressed_legacy[:3])}"
            )

    return issues


def _check_typed_field_integrity(source_book: SourceBook) -> list[str]:
    """Validate typed fields for classification correctness.

    Checks:
    - Evaluation hypotheses without explicit RFP weights must be INFERENCE
    - Explicit requirements must be DIRECT_RFP_FACT
    - External support must be EXTERNAL_BENCHMARK
    - Inferred requirements must be INFERENCE
    """
    issues: list[str] = []
    rfp = source_book.rfp_interpretation

    from src.agents.source_book.assertion_classifier import (
        _EXPLICIT_BASIS_MARKERS,
    )
    for hyp in rfp.evaluation_hypotheses:
        basis_is_explicit = bool(
            hyp.basis and _EXPLICIT_BASIS_MARKERS.search(hyp.basis)
        )
        if hyp.label == AssertionLabel.DIRECT_RFP_FACT and not basis_is_explicit:
            issues.append(
                f"Evaluation hypothesis '{hyp.criterion}' labeled DIRECT_RFP_FACT "
                f"but basis does not reference explicit RFP text — should be INFERENCE"
            )

    for claim in rfp.explicit_requirements:
        if claim.label == AssertionLabel.EXTERNAL_BENCHMARK:
            issues.append(
                f"Explicit requirement '{claim.claim_text[:60]}' labeled "
                f"EXTERNAL_BENCHMARK — should be DIRECT_RFP_FACT"
            )

    for claim in rfp.inferred_requirements:
        if claim.label == AssertionLabel.DIRECT_RFP_FACT:
            issues.append(
                f"Inferred requirement '{claim.claim_text[:60]}' labeled "
                f"DIRECT_RFP_FACT — should be INFERENCE"
            )

    for claim in rfp.external_support:
        if claim.label not in (
            AssertionLabel.EXTERNAL_BENCHMARK,
            AssertionLabel.INFERENCE,
        ):
            issues.append(
                f"External support '{claim.claim_text[:60]}' labeled "
                f"{claim.label} — should be EXTERNAL_BENCHMARK"
            )

    return issues


def _check_timeline_consistency(source_book: SourceBook) -> list[str]:
    """Check timeline references are consistent across sections."""
    issues: list[str] = []

    # Extract duration from Section 5
    timeline = source_book.proposed_solution.timeline_logic or ""
    duration_matches = re.findall(r"(\d+)\s*(?:months?|أشهر|شهر)", timeline, re.I)

    if not duration_matches:
        return issues

    s5_duration = int(duration_matches[0])

    # Check blueprints mentioning different durations
    for bp in source_book.slide_blueprints:
        bp_text = f"{bp.title} {bp.key_message} {' '.join(bp.bullet_logic or [])}"
        bp_durations = re.findall(r"(\d+)\s*(?:months?|أشهر|شهر)", bp_text, re.I)
        for d in bp_durations:
            if abs(int(d) - s5_duration) > 2 and int(d) != s5_duration:
                issues.append(
                    f"Slide {bp.slide_number} mentions {d} months but "
                    f"Section 5 timeline says {s5_duration} months"
                )

    return issues


def _detect_unsupported_absolutes(source_book: SourceBook) -> list[str]:
    """Scan all prose for remaining absolute language that escaped the sanitizer."""
    pattern = re.compile(
        r"\bguarantees?\b|\b100%\s+compliance\b|\bzero\s+risk\b|"
        r"\brisk[- ]free\b|\bwill\s+certainly\b|\bwithout\s+fail\b|"
        r"\bflawlessly\b|\bflawless\b|\bseamlessly\b|"
        r"\bzero\s+learning\s+curve\b|\bzero\s+unplanned\s+downtime\b|"
        r"\bzero\s+defects?\b|\bwith\s+zero\b|"
        r"\balmost\s+certainly\b|\bconsistently\s+require\b|"
        r"ضمان\s+كامل\s+مطلق|بدون\s+أي\s+مخاطر|خالي\s+من\s+المخاطر",
        re.IGNORECASE,
    )

    absolutes: list[str] = []

    def _scan(text: str, location: str) -> None:
        for match in pattern.finditer(text):
            absolutes.append(f"{location}: '{match.group()}'")

    rfp = source_book.rfp_interpretation
    _scan(rfp.objective_and_scope, "S1:objective_and_scope")
    _scan(rfp.probable_scoring_logic, "S1:probable_scoring_logic")

    ps = source_book.proposed_solution
    _scan(ps.methodology_overview, "S5:methodology_overview")
    _scan(ps.governance_framework, "S5:governance_framework")
    _scan(ps.value_case_and_differentiation, "S5:value_case")

    for bp in source_book.slide_blueprints:
        _scan(bp.key_message, f"S6:slide_{bp.slide_number}:key_message")
        for bullet in bp.bullet_logic or []:
            _scan(bullet, f"S6:slide_{bp.slide_number}:bullet")

    return absolutes


def validate_coherence(source_book: SourceBook) -> CoherenceResult:
    """Run full coherence validation across the source book.

    Mutates source_book.coherence in-place. Returns the result.

    Args:
        source_book: Completed source book (Sections 1-7).

    Returns:
        CoherenceResult with all issues found.
    """
    all_issues: list[str] = []

    # 1. Governance naming consistency
    gov_issues = _check_governance_consistency(source_book)
    all_issues.extend(gov_issues)
    gov_consistent = len(gov_issues) == 0

    # 2. Evidence posture consistency
    evidence_issues = _check_evidence_posture(source_book)
    all_issues.extend(evidence_issues)
    evidence_consistent = len(evidence_issues) == 0

    # 3. Compliance carry-through
    compliance_issues = _check_compliance_carrythrough(source_book)
    all_issues.extend(compliance_issues)
    compliance_ok = len(compliance_issues) == 0

    # 4. Timeline consistency
    timeline_issues = _check_timeline_consistency(source_book)
    all_issues.extend(timeline_issues)

    # 5. Typed field integrity
    typed_issues = _check_typed_field_integrity(source_book)
    all_issues.extend(typed_issues)

    # 6. Unsupported absolutes scan
    absolutes = _detect_unsupported_absolutes(source_book)

    result = CoherenceResult(
        issues=all_issues,
        governance_naming_consistent=gov_consistent,
        evidence_posture_consistent=evidence_consistent,
        compliance_carried_through=compliance_ok,
        absolutes_found=absolutes,
        absolutes_softened=source_book.coherence.absolutes_softened,
    )

    source_book.coherence = result

    logger.info(
        "Coherence validator: %d issues, governance=%s, evidence=%s, "
        "compliance=%s, absolutes_remaining=%d",
        len(all_issues),
        gov_consistent,
        evidence_consistent,
        compliance_ok,
        len(absolutes),
    )

    return result
