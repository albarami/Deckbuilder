"""Source Book iteration orchestrator.

Manages the Writer → Reviewer → Writer loop. Stops when:
1. Review passes threshold (overall >= 4, no section < 3), OR
2. Maximum passes reached (default 5, per approved design).

Also provides helper to convert Source Book to markdown for
populating state.report_markdown.
"""

from __future__ import annotations

import logging

from src.models.conformance import ConformanceReport
from src.models.source_book import SourceBook, SourceBookReview

logger = logging.getLogger(__name__)


def should_continue_iteration(
    review: SourceBookReview,
    current_pass: int,
    max_passes: int = 5,
) -> bool:
    """Decide whether to continue the write/review loop.

    Returns True if another pass is needed, False if done.
    """
    if current_pass >= max_passes:
        logger.info(
            "Stopping iteration: reached max passes (%d/%d)",
            current_pass,
            max_passes,
        )
        return False

    if review.pass_threshold_met and not review.rewrite_required:
        # Check for critical context contradictions in coherence issues.
        # These override the threshold — the Source Book must not pass
        # with a fundamental misread of the evaluation model, timeline,
        # or phase structure when the structured context says otherwise.
        _CRITICAL_CONTRADICTION_KEYWORDS = [
            "misreads the evaluation model",
            "evaluation model",
            "award mechanism",
            "weighted scoring",
            "pass/fail",
            "lowest price",
            "timeline contradict",
            "phase structure contradict",
        ]
        critical_contradictions = [
            issue for issue in review.coherence_issues
            if any(kw.lower() in issue.lower() for kw in _CRITICAL_CONTRADICTION_KEYWORDS)
        ]
        if critical_contradictions and current_pass < max_passes:
            logger.warning(
                "Overriding threshold: %d critical context contradiction(s) "
                "force rewrite despite score=%d. Issues: %s",
                len(critical_contradictions),
                review.overall_score,
                "; ".join(c[:100] for c in critical_contradictions),
            )
            return True  # Force another pass

        logger.info(
            "Stopping iteration: threshold met (score=%d, pass=%d)",
            review.overall_score,
            current_pass,
        )
        return False

    logger.info(
        "Continuing iteration: score=%d, threshold_met=%s, pass=%d/%d",
        review.overall_score,
        review.pass_threshold_met,
        current_pass,
        max_passes,
    )
    return True


def should_accept_source_book(
    review: SourceBookReview,
    conformance_report: ConformanceReport,
    *,
    evidence_coverage_report: dict | None = None,
    coverage_required: bool = False,
) -> bool:
    """Determine whether to accept the Source Book.

    Requires ALL:
    - review.pass_threshold_met == True
    - conformance_report.conformance_status == "pass"
    - No critical missing inputs with source_book scope
    - When ``coverage_required`` is True (Slice 3.6), the supplied
      ``evidence_coverage_report`` must parse and have status == "pass".
      Missing or malformed coverage fails closed.

    Acceptance is validator-first: if conformance fails, reviewer score
    is irrelevant. This prevents high-quality but non-conformant books
    from being accepted.
    """
    # Conformance gate (primary)
    if conformance_report.conformance_status == "blocked":
        logger.info(
            "Acceptance: BLOCKED — missing critical inputs"
        )
        return False

    if conformance_report.conformance_status == "fail":
        logger.info(
            "Acceptance: REJECTED — %d critical conformance failures "
            "(reviewer score irrelevant)",
            conformance_report.hard_requirements_failed,
        )
        return False

    # Reviewer gate (secondary)
    if not review.pass_threshold_met:
        logger.info(
            "Acceptance: REJECTED — conformance passed but reviewer "
            "threshold not met (score=%d)",
            review.overall_score,
        )
        return False

    # Slice 3.6: Evidence coverage gate (tertiary)
    # Fail closed when coverage was required but missing/malformed/fail.
    if coverage_required:
        if evidence_coverage_report is None:
            logger.info(
                "Acceptance: REJECTED — coverage required but "
                "evidence_coverage_report missing"
            )
            return False
        try:
            from src.services.artifact_gates import EvidenceCoverageReport

            parsed = EvidenceCoverageReport.model_validate(
                evidence_coverage_report,
            )
        except Exception as e:
            logger.info(
                "Acceptance: REJECTED — malformed evidence_coverage_report: %s",
                e,
            )
            return False
        if parsed.status != "pass":
            logger.info(
                "Acceptance: REJECTED — evidence_coverage status=%s",
                parsed.status,
            )
            return False

    logger.info(
        "Acceptance: ACCEPTED — conformance pass + reviewer threshold met "
        "(score=%d, checked=%d, passed=%d, coverage_required=%s)",
        review.overall_score,
        conformance_report.hard_requirements_checked,
        conformance_report.hard_requirements_passed,
        coverage_required,
    )
    return True


def build_reviewer_feedback(review: SourceBookReview) -> str:
    """Build a structured feedback string from a SourceBookReview.

    Used as input to the Writer on rewrite passes.
    """
    lines: list[str] = []

    lines.append(f"Overall score: {review.overall_score}/5")
    lines.append(f"Competitive viability: {review.competitive_viability}")
    lines.append("")

    # Per-section feedback
    for critique in review.section_critiques:
        lines.append(f"=== {critique.section_id} (score: {critique.score}/5) ===")
        if critique.issues:
            lines.append("Issues:")
            for issue in critique.issues:
                lines.append(f"  - {issue}")
        if critique.rewrite_instructions:
            lines.append("Rewrite instructions:")
            for instr in critique.rewrite_instructions:
                lines.append(f"  - {instr}")
        if critique.unsupported_claims:
            lines.append("Unsupported claims:")
            for claim in critique.unsupported_claims:
                lines.append(f"  - {claim}")
        if critique.fluff_detected:
            lines.append("Fluff detected:")
            for fluff in critique.fluff_detected:
                lines.append(f"  - {fluff}")
        lines.append("")

    # Cross-section issues
    if review.coherence_issues:
        lines.append("=== Coherence Issues ===")
        for issue in review.coherence_issues:
            lines.append(f"  - {issue}")
        lines.append("")

    if review.repetition_detected:
        lines.append("=== Repetition Detected ===")
        for rep in review.repetition_detected:
            lines.append(f"  - {rep}")
        lines.append("")

    return "\n".join(lines)


def source_book_to_markdown(source_book: SourceBook) -> str:
    """Convert a SourceBook to markdown for state.report_markdown.

    Produces a human-readable markdown document that feeds downstream
    agents (assembly plan, iterative builder).
    """
    lines: list[str] = []

    # Header
    lines.append(f"# Proposal Source Book: {source_book.client_name}")
    lines.append(f"**RFP:** {source_book.rfp_name}")
    lines.append(f"**Language:** {source_book.language}")
    lines.append("")

    # Section 1: RFP Interpretation
    lines.append("## 1. RFP Interpretation")
    rfp = source_book.rfp_interpretation
    if rfp.objective_and_scope:
        lines.append("### Objective & Scope")
        lines.append(rfp.objective_and_scope)
        lines.append("")
    if rfp.constraints_and_compliance:
        lines.append("### Constraints & Compliance")
        lines.append(rfp.constraints_and_compliance)
        lines.append("")
    if rfp.unstated_evaluator_priorities:
        lines.append("### Unstated Evaluator Priorities")
        lines.append(rfp.unstated_evaluator_priorities)
        lines.append("")
    if rfp.probable_scoring_logic:
        lines.append("### Probable Scoring Logic")
        lines.append(rfp.probable_scoring_logic)
        lines.append("")
    if rfp.key_compliance_requirements:
        lines.append("### Key Compliance Requirements")
        for req in rfp.key_compliance_requirements:
            lines.append(f"- {req}")
        lines.append("")

    # Section 2: Client Problem Framing
    lines.append("## 2. Client Problem Framing")
    cpf = source_book.client_problem_framing
    if cpf.current_state_challenge:
        lines.append("### Current-State Challenge")
        lines.append(cpf.current_state_challenge)
        lines.append("")
    if cpf.why_it_matters_now:
        lines.append("### Why It Matters Now")
        lines.append(cpf.why_it_matters_now)
        lines.append("")
    if cpf.transformation_logic:
        lines.append("### Transformation Logic")
        lines.append(cpf.transformation_logic)
        lines.append("")
    if cpf.risk_if_unchanged:
        lines.append("### Risk If Unchanged")
        lines.append(cpf.risk_if_unchanged)
        lines.append("")

    # Section 3: Why Strategic Gears
    lines.append("## 3. Why Strategic Gears")
    wsg = source_book.why_strategic_gears
    if wsg.capability_mapping:
        lines.append("### Capability-to-RFP Mapping")
        lines.append("| RFP Requirement | SG Capability | Evidence | Strength |")
        lines.append("|---|---|---|---|")
        for cm in wsg.capability_mapping:
            evidence = ", ".join(cm.evidence_ids) if cm.evidence_ids else "—"
            lines.append(
                f"| {cm.rfp_requirement} | {cm.sg_capability} | {evidence} | {cm.strength} |"
            )
        lines.append("")
    if wsg.named_consultants:
        lines.append("### Named Consultants")
        for nc in wsg.named_consultants:
            evidence = ", ".join(nc.evidence_ids) if nc.evidence_ids else ""
            lines.append(f"- **{nc.name}** — {nc.role}: {nc.relevance} [{evidence}]")
        lines.append("")
    if wsg.project_experience:
        lines.append("### Project Experience")
        for pe in wsg.project_experience:
            evidence = ", ".join(pe.evidence_ids) if pe.evidence_ids else ""
            lines.append(f"- **{pe.project_name}** ({pe.client}): {pe.outcomes} [{evidence}]")
        lines.append("")
    if wsg.certifications_and_compliance:
        lines.append("### Certifications & Compliance")
        for cert in wsg.certifications_and_compliance:
            lines.append(f"- {cert}")
        lines.append("")

    # Section 4: External Evidence
    lines.append("## 4. External Evidence")
    ext = source_book.external_evidence
    if ext.entries:
        lines.append("| Source ID | Title | Year | Key Finding |")
        lines.append("|---|---|---|---|")
        for entry in ext.entries:
            lines.append(
                f"| {entry.source_id} | {entry.title} | {entry.year} | {entry.key_finding} |"
            )
        lines.append("")
    if ext.coverage_assessment:
        lines.append(f"**Coverage:** {ext.coverage_assessment}")
        lines.append("")

    # Section 5: Proposed Solution
    lines.append("## 5. Proposed Solution")
    ps = source_book.proposed_solution
    if ps.methodology_overview:
        lines.append("### Methodology Overview")
        lines.append(ps.methodology_overview)
        lines.append("")
    if ps.phase_details:
        lines.append("### Phase Details")
        for phase in ps.phase_details:
            lines.append(f"**{phase.phase_name}**")
            if phase.activities:
                lines.append("Activities:")
                for act in phase.activities:
                    lines.append(f"  - {act}")
            if phase.deliverables:
                lines.append("Deliverables:")
                for d in phase.deliverables:
                    lines.append(f"  - {d}")
            if phase.governance:
                lines.append(f"Governance: {phase.governance}")
            lines.append("")
    if ps.governance_framework:
        lines.append("### Governance Framework")
        lines.append(ps.governance_framework)
        lines.append("")
    if ps.timeline_logic:
        lines.append("### Timeline Logic")
        lines.append(ps.timeline_logic)
        lines.append("")
    if ps.value_case_and_differentiation:
        lines.append("### Value Case & Differentiation")
        lines.append(ps.value_case_and_differentiation)
        lines.append("")

    # Section 6: Slide Blueprints
    lines.append("## 6. Slide-by-Slide Blueprint")
    if source_book.slide_blueprints:
        for bp in source_book.slide_blueprints:
            lines.append(f"### Slide {bp.slide_number}: {bp.title}")
            lines.append(f"- **Section:** {bp.section}")
            lines.append(f"- **Layout:** {bp.layout}")
            lines.append(f"- **Purpose:** {bp.purpose}")
            lines.append(f"- **Key Message:** {bp.key_message}")
            if bp.bullet_logic:
                lines.append("- **Bullets:**")
                for bullet in bp.bullet_logic:
                    lines.append(f"  - {bullet}")
            if bp.proof_points:
                lines.append(f"- **Proof Points:** {', '.join(bp.proof_points)}")
            if bp.visual_guidance:
                lines.append(f"- **Visual:** {bp.visual_guidance}")
            lines.append("")

    # Section 7: Evidence Ledger
    lines.append("## 7. Evidence Ledger")
    if source_book.evidence_ledger.entries:
        lines.append("| Claim ID | Claim | Source | Confidence | Status |")
        lines.append("|---|---|---|---|---|")
        for entry in source_book.evidence_ledger.entries:
            lines.append(
                f"| {entry.claim_id} | {entry.claim_text} | "
                f"{entry.source_reference} | {entry.confidence:.2f} | "
                f"{entry.verifiability_status} |"
            )
        lines.append("")

    return "\n".join(lines)
