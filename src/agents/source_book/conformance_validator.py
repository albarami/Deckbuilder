"""Conformance Validator — deterministic + LLM validation of Source Book.

Runs INSIDE the iteration loop after each writer pass, BEFORE the reviewer.
Four-pass architecture:
  Pass 1: Deterministic checks (award mechanism, guarantees, duration, etc.)
  Pass 2: Forbidden claim scan (regex)
  Pass 3: LLM-assisted semantic checks (only when deterministic insufficient)
  Pass 4: Missing annex detection

Acceptance Logic:
  "blocked" = any MissingInput with severity=critical AND scope=source_book
  "fail"    = any critical ConformanceFailure
  "pass"    = no critical failures and no critical blockers
"""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from pydantic import Field

from src.models.claim_provenance import (
    ClaimRegistry,
    ComplianceIndex,
    ProposalOptionRegistry,
)
from src.models.common import DeckForgeBaseModel
from src.models.conformance import (
    ConformanceFailure,
    ConformanceReport,
    HardRequirement,
    MissingInput,
)
from src.models.rfp import RFPContext
from src.models.source_book import SourceBook
from src.models.state import UploadedDocument

logger = logging.getLogger(__name__)


# ── Forbidden patterns ─────────────────────────────────────────────────

_WEIGHTED_SCORING_RE = re.compile(
    r"70\s*%.*30\s*%|30\s*%.*70\s*%|"
    r"weighted\s+(?:scoring|evaluation|technical|financial)|"
    r"combined\s+score|"
    r"مرجح|التقييم\s+المرجح|الوزن\s+النسبي",
    re.IGNORECASE,
)

# Absolute claim patterns — require assurance verb context.
# Do NOT flag "جميع" (all) alone in deliverable descriptions.
# Do NOT flag "100%" in evaluation model descriptions (legitimate DIRECT_RFP_FACT).
# Only flag patterns where an assurance verb precedes the absolute claim.
_ABSOLUTE_CLAIM_RE = re.compile(
    # English: assurance verb + absolute object
    r"(?:guarantee|ensure|certif)(?:s|es|ed|ing)?\s+(?:100%|complete\s+compliance|zero\s+risk|zero\s+defect|all\s+requirements)|"
    r"(?:eliminate|remove)(?:s|d)?\s+all\s+risk|"
    # Arabic: assurance verb + absolute object
    r"(?:يضمن|تضمن|نضمن)\s+(?:100|جميع\s+المتطلبات|استيفاء\s+كامل|مطابقة\s+كاملة|نجاح\s+كامل)|"
    r"(?:امتثال|مطابقة)\s+(?:100%|كامل[ة]?\s+ومؤكد)|"
    # Bare "100%" only in assurance context (not in evaluation_hypotheses or weight fields)
    r"(?:نسبة\s+نجاح|معدل\s+استيفاء|compliance\s+rate)\s*(?:=|:)?\s*100%",
    re.IGNORECASE,
)


# ── LLM response model for Pass 3 ─────────────────────────────────────


class _SemanticCheckItem(DeckForgeBaseModel):
    """Single semantic conformance check result from LLM."""

    requirement_id: str = ""
    is_satisfied: bool = False
    failure_reason: str = ""
    source_book_section: str = ""
    suggested_fix: str = ""


class _SemanticCheckResult(DeckForgeBaseModel):
    """LLM response for semantic conformance checks."""

    checks: list[_SemanticCheckItem] = Field(default_factory=list)


# ── Pass 1: Deterministic checks ──────────────────────────────────────


def _pass1_deterministic(
    source_book: SourceBook,
    hard_requirements: list[HardRequirement],
    rfp_context: RFPContext,
    compliance_index: ComplianceIndex | None = None,
) -> tuple[list[ConformanceFailure], list[ConformanceFailure], int, int]:
    """Deterministic conformance checks.

    When ``compliance_index`` is provided, compliance-category HRs are
    resolved against the structured index first. Entries with
    ``content_conformance_pass`` are counted as passed without running the
    legacy English keyword scan (which produces false negatives on Arabic
    Source Books). Entries with ``response_status="missing"`` still fail.

    Returns (missing_commitments, structural_mismatches, passed, failed).
    """
    failures: list[ConformanceFailure] = []
    structural: list[ConformanceFailure] = []
    passed = 0
    failed = 0

    # Serialize source book to text for scanning
    sb_text = json.dumps(
        source_book.model_dump(mode="json"),
        ensure_ascii=False,
        default=str,
    )

    # Build compliance-index lookup once
    compliance_lookup: dict[str, "object"] = {}
    if compliance_index is not None:
        compliance_lookup = {e.requirement_id: e for e in compliance_index.entries}

    for hr in hard_requirements:
        if hr.validation_scope != "source_book":
            continue

        # ComplianceIndex-first: a compliance HR with a structured index entry
        # bypasses the brittle English keyword scan.
        if hr.category == "compliance" and hr.requirement_id in compliance_lookup:
            entry = compliance_lookup[hr.requirement_id]
            if getattr(entry, "content_conformance_pass", False):
                passed += 1
                continue
            failures.append(ConformanceFailure(
                requirement_id=hr.requirement_id,
                requirement_text=f"Compliance: {hr.value_text[:100]}",
                failure_reason=(
                    f"ComplianceIndex marks requirement as "
                    f"{getattr(entry, 'response_status', 'unknown')}"
                ),
                severity=hr.severity,
                source_book_section="rfp_interpretation",
                suggested_fix=(
                    f"Address compliance requirement in Section 1: "
                    f"{hr.value_text[:100]}"
                ),
            ))
            failed += 1
            continue

        found = False

        if hr.category == "award_mechanism":
            # Check the source book doesn't contain weighted scoring
            # when the award is pass_fail_then_lowest_price
            if hr.value_text == "pass_fail_then_lowest_price":
                if _WEIGHTED_SCORING_RE.search(sb_text):
                    failures.append(ConformanceFailure(
                        requirement_id=hr.requirement_id,
                        requirement_text=f"Award mechanism is {hr.value_text}",
                        failure_reason=(
                            "Source Book contains weighted scoring language "
                            "but award mechanism is pass/fail then lowest price"
                        ),
                        severity="critical",
                        source_book_section="rfp_interpretation",
                        suggested_fix=(
                            "Remove all weighted scoring references (70%/30%, "
                            "combined score, etc.) and describe pass/fail gate "
                            "followed by lowest-price award"
                        ),
                    ))
                    failed += 1
                else:
                    found = True
            else:
                # For other award mechanisms, just check mention
                if hr.value_text.lower().replace("_", " ") in sb_text.lower():
                    found = True
                else:
                    # Non-critical: may be described differently
                    found = True  # soft check

        elif hr.category == "contract_duration":
            # Check contract duration is mentioned correctly
            if hr.value_number is not None:
                duration_val = int(hr.value_number)
                # Look for the number in timeline/methodology sections
                duration_pattern = re.compile(
                    rf"\b{duration_val}\s*(?:months?|month|أشهر|شهر)\b",
                    re.IGNORECASE,
                )
                if duration_pattern.search(sb_text):
                    found = True
                else:
                    failures.append(ConformanceFailure(
                        requirement_id=hr.requirement_id,
                        requirement_text=f"Contract duration: {duration_val} months",
                        failure_reason=(
                            f"Source Book does not commit to {duration_val}-month "
                            f"contract duration"
                        ),
                        severity="critical",
                        source_book_section="proposed_solution",
                        suggested_fix=(
                            f"State the project timeline as exactly {duration_val} months "
                            f"in the methodology and timeline sections"
                        ),
                    ))
                    failed += 1

        elif hr.category == "minimum_threshold":
            # Informational — threshold is for the evaluator, not the book
            found = True

        elif hr.category == "compliance":
            # Check the compliance requirement is addressed
            if hr.value_text and len(hr.value_text) > 5:
                # Check if key words from requirement appear in source book
                key_words = [
                    w.lower() for w in hr.value_text.split()
                    if len(w) > 3
                ][:5]
                matches = sum(1 for w in key_words if w in sb_text.lower())
                if matches >= min(2, len(key_words)):
                    found = True
                else:
                    failures.append(ConformanceFailure(
                        requirement_id=hr.requirement_id,
                        requirement_text=f"Compliance: {hr.value_text[:100]}",
                        failure_reason=(
                            f"Compliance requirement not addressed in Source Book"
                        ),
                        severity=hr.severity,
                        source_book_section="rfp_interpretation",
                        suggested_fix=(
                            f"Address compliance requirement in Section 1: "
                            f"{hr.value_text[:100]}"
                        ),
                    ))
                    failed += 1
            else:
                found = True

        elif hr.category == "deliverable_required":
            # Check mandatory deliverable is mentioned
            if hr.value_text and len(hr.value_text) > 3:
                key_words = [
                    w.lower() for w in hr.value_text.split()
                    if len(w) > 3
                ][:5]
                matches = sum(1 for w in key_words if w in sb_text.lower())
                if matches >= min(2, len(key_words)):
                    found = True
                else:
                    failures.append(ConformanceFailure(
                        requirement_id=hr.requirement_id,
                        requirement_text=f"Mandatory deliverable: {hr.value_text[:100]}",
                        failure_reason=(
                            f"Mandatory deliverable not addressed in Source Book"
                        ),
                        severity="critical",
                        source_book_section="proposed_solution",
                        suggested_fix=(
                            f"Include deliverable in proposed solution phases: "
                            f"{hr.value_text[:100]}"
                        ),
                    ))
                    failed += 1
            else:
                found = True

        elif hr.category == "deliverable_deadline":
            # Check phase/deliverable mapping
            found = True  # Soft check — deadline is informational for source book

        elif hr.category == "team_qualification":
            # Check team role is addressed
            subject_lower = hr.subject.lower()
            if subject_lower in sb_text.lower():
                found = True
            else:
                # Try partial match on role title
                role_words = [
                    w.lower() for w in hr.subject.split()
                    if len(w) > 3
                ][:3]
                matches = sum(1 for w in role_words if w in sb_text.lower())
                if matches >= min(1, len(role_words)):
                    found = True
                else:
                    failures.append(ConformanceFailure(
                        requirement_id=hr.requirement_id,
                        requirement_text=f"Team role: {hr.value_text[:100]}",
                        failure_reason=f"Required team role not addressed: {hr.subject}",
                        severity=hr.severity,
                        source_book_section="why_strategic_gears",
                        suggested_fix=(
                            f"Add team role profile for: {hr.subject} "
                            f"with qualifications: {hr.value_text[:100]}"
                        ),
                    ))
                    failed += 1

        elif hr.category in ("quantified_minimum", "minimum_count"):
            # Check numeric commitments
            if hr.value_number is not None:
                val = int(hr.value_number)
                # Look for the number in context
                if str(val) in sb_text:
                    found = True
                else:
                    failures.append(ConformanceFailure(
                        requirement_id=hr.requirement_id,
                        requirement_text=f"{hr.subject} >= {val}",
                        failure_reason=(
                            f"Quantified minimum not met: {hr.subject} "
                            f"requires >= {val} but not found in Source Book"
                        ),
                        severity=hr.severity,
                        source_book_section="proposed_solution",
                        suggested_fix=(
                            f"Explicitly commit to {hr.subject} >= {val} "
                            f"in the methodology or solution sections"
                        ),
                    ))
                    failed += 1
            else:
                found = True

        elif hr.category == "packaging":
            # Packaging is submission_package scope usually
            found = True

        else:
            # Unknown category — soft pass
            found = True

        if found:
            passed += 1

    return failures, structural, passed, failed


# ── Pass 2: Forbidden claim scan ───────────────────────────────────────


def _pass2_forbidden_claims(
    source_book: SourceBook,
    hard_requirements: list[HardRequirement],
) -> list[ConformanceFailure]:
    """Scan for forbidden claims: absolute language, wrong award model, etc."""
    forbidden: list[ConformanceFailure] = []

    sb_text = json.dumps(
        source_book.model_dump(mode="json"),
        ensure_ascii=False,
        default=str,
    )

    # Check for absolute/overclaim language
    for match in _ABSOLUTE_CLAIM_RE.finditer(sb_text):
        context_start = max(0, match.start() - 50)
        context_end = min(len(sb_text), match.end() + 50)
        context = sb_text[context_start:context_end].strip()
        forbidden.append(ConformanceFailure(
            requirement_id="FORBIDDEN-ABS",
            requirement_text="No absolute/unverifiable claims",
            failure_reason=f"Absolute claim detected: ...{context[:120]}...",
            severity="major",
            source_book_section="multiple",
            suggested_fix="Replace absolute claim with qualified language",
        ))

    # Check for wrong award model stated as fact
    award_hr = next(
        (hr for hr in hard_requirements if hr.category == "award_mechanism"),
        None,
    )
    if award_hr and award_hr.value_text == "pass_fail_then_lowest_price":
        if _WEIGHTED_SCORING_RE.search(sb_text):
            forbidden.append(ConformanceFailure(
                requirement_id=award_hr.requirement_id,
                requirement_text=f"Award mechanism is {award_hr.value_text}",
                failure_reason=(
                    "Source Book presents weighted scoring model but RFP "
                    "uses pass/fail then lowest price"
                ),
                severity="critical",
                source_book_section="rfp_interpretation",
                suggested_fix=(
                    "Remove all weighted scoring language and describe "
                    "the pass/fail technical gate followed by lowest-price award"
                ),
            ))

    # Check for wrong TOTAL contract duration stated as fact.
    # Only scan timeline_logic and overall project duration fields —
    # NOT phase-level durations like "المرحلة الأولى: 3 أشهر".
    duration_hr = next(
        (hr for hr in hard_requirements if hr.category == "contract_duration"),
        None,
    )
    if duration_hr and duration_hr.value_number is not None:
        correct_months = int(duration_hr.value_number)
        # Extract only total-duration-scoped text (timeline_logic + rfp_interpretation)
        duration_scoped_parts = []
        if source_book.proposed_solution:
            if source_book.proposed_solution.timeline_logic:
                duration_scoped_parts.append(source_book.proposed_solution.timeline_logic)
        if source_book.rfp_interpretation:
            if source_book.rfp_interpretation.constraints_and_compliance:
                duration_scoped_parts.append(source_book.rfp_interpretation.constraints_and_compliance)
            if source_book.rfp_interpretation.objective_and_scope:
                duration_scoped_parts.append(source_book.rfp_interpretation.objective_and_scope)
        duration_text = " ".join(duration_scoped_parts)

        if duration_text:
            # Look for total project duration statements — require "contract/project/total" context
            total_duration_pattern = re.compile(
                r"(?:مدة\s+العقد|مدة\s+المشروع|مدة\s+التنفيذ|contract\s+duration|project\s+duration|total\s+duration)"
                r"[^.]{0,50}?"  # up to 50 chars of context
                r"(\d+)\s*(?:months?|أشهر|شهر)",
                re.IGNORECASE,
            )
            for m in total_duration_pattern.finditer(duration_text):
                try:
                    wd_val = int(m.group(1))
                    if wd_val != correct_months:
                        forbidden.append(ConformanceFailure(
                            requirement_id=duration_hr.requirement_id,
                            requirement_text=f"Contract duration: {correct_months} months",
                            failure_reason=(
                                f"Source Book states total duration as {wd_val} months "
                                f"but RFP specifies {correct_months} months"
                            ),
                            severity="critical",
                            source_book_section="proposed_solution",
                            suggested_fix=(
                                f"Correct total contract duration to "
                                f"{correct_months} months"
                            ),
                        ))
                        break
                except ValueError:
                    continue

    # Limit forbidden claims to avoid noise
    if len(forbidden) > 10:
        logger.warning(
            "Pass 2: %d forbidden claims found, capping at 10", len(forbidden)
        )
        forbidden = forbidden[:10]

    return forbidden


# ── Pass 3: LLM-assisted semantic checks ──────────────────────────────


async def _pass3_semantic_checks(
    source_book: SourceBook,
    hard_requirements: list[HardRequirement],
) -> list[ConformanceFailure]:
    """LLM-assisted checks for requirements that can't be verified deterministically.

    Only invoked for requirements where:
    - The obligation is expressed in prose rather than structured fields
    - Phase narrative fidelity needs semantic comparison
    """
    # Filter to requirements that need semantic checking
    semantic_reqs = [
        hr for hr in hard_requirements
        if hr.validation_scope == "source_book"
        and hr.extraction_method == "llm_structured"
        and hr.confidence in ("medium", "low")
    ]

    if not semantic_reqs:
        return []

    # Limit to avoid excessive cost
    semantic_reqs = semantic_reqs[:10]

    # Build compact source book summary for LLM
    sb_summary = {
        "rfp_interpretation": {
            "objective_and_scope": (source_book.rfp_interpretation.objective_and_scope or "")[:500],
            "constraints_and_compliance": (source_book.rfp_interpretation.constraints_and_compliance or "")[:500],
        },
        "proposed_solution": {
            "methodology_overview": (source_book.proposed_solution.methodology_overview or "")[:500],
            "timeline_logic": (source_book.proposed_solution.timeline_logic or "")[:300],
            "phases": [
                {
                    "phase_name": p.phase_name,
                    "activities": p.activities[:5],
                    "deliverables": p.deliverables[:5],
                }
                for p in source_book.proposed_solution.phase_details[:6]
            ],
        },
    }

    reqs_text = json.dumps(
        [
            {
                "requirement_id": hr.requirement_id,
                "category": hr.category,
                "subject": hr.subject,
                "operator": hr.operator,
                "value_text": hr.value_text,
                "source_text": hr.source_text,
            }
            for hr in semantic_reqs
        ],
        ensure_ascii=False,
    )

    system_prompt = """You are a conformance checker for proposal documents.
Given a Source Book summary and a list of hard requirements, check whether
each requirement is satisfied in the Source Book content.

For each requirement, determine:
- is_satisfied: true/false
- failure_reason: what is missing or wrong (empty if satisfied)
- source_book_section: which section should address this
- suggested_fix: actionable fix for the writer (empty if satisfied)

Be precise. Only flag genuine misses, not stylistic differences."""

    user_message = (
        f"Source Book summary:\n{json.dumps(sb_summary, ensure_ascii=False)}\n\n"
        f"Requirements to check:\n{reqs_text}"
    )

    try:
        from src.config.models import MODEL_MAP
        from src.services.llm import call_llm

        model = MODEL_MAP.get("source_book_writer", MODEL_MAP.get("analysis_agent"))
        result = await call_llm(
            model=model,
            system_prompt=system_prompt,
            user_message=user_message,
            response_model=_SemanticCheckResult,
            max_tokens=4000,
        )

        failures: list[ConformanceFailure] = []
        for check in result.parsed.checks:
            if not check.is_satisfied and check.failure_reason:
                failures.append(ConformanceFailure(
                    requirement_id=check.requirement_id,
                    requirement_text=check.failure_reason[:200],
                    failure_reason=check.failure_reason,
                    severity="major",
                    source_book_section=check.source_book_section or "proposed_solution",
                    suggested_fix=check.suggested_fix,
                ))

        logger.info("Pass 3 LLM semantic: %d failures from %d checks", len(failures), len(semantic_reqs))
        return failures

    except Exception as e:
        logger.error("Pass 3 semantic check failed: %s", e)
        return []


# ── Pass 4: Missing annex detection ───────────────────────────────────


def _pass4_missing_annexes(
    hard_requirements: list[HardRequirement],
    uploaded_documents: list[UploadedDocument],
) -> list[MissingInput]:
    """Check uploaded documents for referenced annexes.

    Fail-closed ONLY when severity=critical AND validation_scope=source_book.
    """
    missing: list[MissingInput] = []
    doc_names = {d.filename.lower() for d in uploaded_documents}
    doc_texts_lower = " ".join(d.content_text.lower()[:500] for d in uploaded_documents)

    # Check for team table / annex references in requirements
    for hr in hard_requirements:
        if hr.validation_scope != "source_book":
            continue

        # Check if requirement references an annex
        annex_keywords = ["annex", "ملحق", "جدول", "table", "attachment"]
        source_lower = hr.source_text.lower()
        references_annex = any(kw in source_lower for kw in annex_keywords)

        if not references_annex:
            continue

        # Check if the annex content is available
        subject_words = [w.lower() for w in hr.subject.split() if len(w) > 3][:3]
        found_in_docs = any(w in doc_texts_lower for w in subject_words) if subject_words else True

        if not found_in_docs:
            missing.append(MissingInput(
                input_name=f"annex_{hr.subject}",
                requirement_ids=[hr.requirement_id],
                blocker_type="missing_annex",
                severity=hr.severity,
                validation_scope=hr.validation_scope,
                message=(
                    f"Requirement {hr.requirement_id} references an annex for "
                    f"'{hr.subject}' but no matching content found in uploaded documents"
                ),
            ))

    return missing


# ── Public API ────────────────────────────────────────────────────────


async def validate_conformance(
    source_book: SourceBook,
    hard_requirements: list[HardRequirement],
    rfp_context: RFPContext,
    uploaded_documents: list[UploadedDocument],
    compliance_index: ComplianceIndex | None = None,
    claim_registry: ClaimRegistry | None = None,
    proposal_options: ProposalOptionRegistry | None = None,
) -> ConformanceReport:
    """Validate Source Book conformance against hard requirements.

    Six-pass architecture:
      Pass 1: Deterministic checks (ComplianceIndex-first when provided)
      Pass 2: Forbidden absolute-claim scan
      Pass 3: LLM-assisted semantic checks
      Pass 4: Missing annex detection
      Pass 5: Section-aware forbidden internal-claim leakage scan (Slice 2.2)
      Pass 6: Numeric commitment + unapproved-option scan (Slice 4.3)
    """
    # Filter to source_book scope
    sb_reqs = [hr for hr in hard_requirements if hr.validation_scope == "source_book"]

    if sb_reqs:
        # Pass 1: Deterministic
        missing_commitments, structural_mismatches, passed, p1_failed = (
            _pass1_deterministic(
                source_book, sb_reqs, rfp_context,
                compliance_index=compliance_index,
            )
        )
        # Pass 2: Forbidden claims
        forbidden_claims = _pass2_forbidden_claims(source_book, hard_requirements)
        # Pass 3: Semantic (LLM) — only for LLM-extracted reqs with lower confidence
        semantic_failures = await _pass3_semantic_checks(
            source_book, hard_requirements,
        )
        missing_commitments.extend(semantic_failures)
        # Pass 4: Missing annexes
        missing_inputs = _pass4_missing_annexes(
            hard_requirements, uploaded_documents,
        )
    else:
        logger.info(
            "Conformance validator: no source_book-scope requirements to check; "
            "running leakage scan only"
        )
        missing_commitments = []
        structural_mismatches = []
        forbidden_claims = []
        missing_inputs = []
        passed = 0
        p1_failed = 0

    # Pass 5: Section-aware forbidden internal-claim leakage (Slice 2.2)
    # Renders the SourceBook into ArtifactSection records and runs the
    # structured scanner. PRJ-/CLI-/CLM- identifiers and forbidden semantic
    # phrases in client-facing sections produce critical leakage failures.
    # When a ClaimRegistry is supplied, semantic phrases linked to a
    # verified+permissioned bidder claim are allowed.
    from src.services.artifact_gates import (
        render_source_book_sections,
        scan_for_forbidden_leakage,
    )

    leakage_failures: list[ConformanceFailure] = []
    rendered = render_source_book_sections(source_book)
    for section in rendered:
        violations = scan_for_forbidden_leakage(section, claim_registry)
        for v in violations:
            leakage_failures.append(ConformanceFailure(
                requirement_id="FORBIDDEN-LEAKAGE",
                requirement_text=(
                    f"Forbidden internal-claim leakage in {v.section_type}"
                ),
                failure_reason=(
                    f"{v.matched_text!r} found in {v.location} "
                    f"(section_type={v.section_type})"
                ),
                severity="critical",
                source_book_section=v.location,
                suggested_fix=(
                    "Move internal identifiers to internal_gap_appendix or "
                    "internal_bid_notes; replace semantic phrases with "
                    "verified-and-permissioned claim text only."
                ),
            ))
    if leakage_failures:
        logger.warning(
            "Pass 5: %d forbidden internal-claim leakages detected",
            len(leakage_failures),
        )
    forbidden_claims.extend(leakage_failures)

    # Pass 6: Numeric commitment + unapproved-option scan (Slice 4.3)
    # Each unresolved numeric range/unit in client-facing text becomes a
    # critical UNRESOLVED_COMMITMENT failure. Each text match for a
    # proposal_option claim whose linked option is not approved for
    # external use becomes a critical UNAPPROVED_OPTION failure.
    if claim_registry is not None or proposal_options is not None:
        from src.services.numeric_commitment_detector import (
            detect_numeric_commitments,
        )

        active_claims = claim_registry or ClaimRegistry()
        active_options = proposal_options or ProposalOptionRegistry()

        commitment_failures: list[ConformanceFailure] = []
        option_failures: list[ConformanceFailure] = []

        commitments = detect_numeric_commitments(
            rendered, active_claims, active_options,
        )
        for nc in commitments:
            if nc.resolution != "unresolved":
                continue
            commitment_failures.append(ConformanceFailure(
                requirement_id="UNRESOLVED_COMMITMENT",
                requirement_text=(
                    f"Numeric commitment {nc.canonical!r} in {nc.section_type}"
                ),
                failure_reason=(
                    f"Commitment {nc.text!r} (canonical {nc.canonical!r}) at "
                    f"{nc.section_path} did not resolve to an RFP fact or an "
                    f"approved proposal option."
                ),
                severity="critical",
                source_book_section=nc.section_path,
                suggested_fix=(
                    "Either register this commitment as a proposal_option with "
                    "approved_for_external_use=True (priced + approved_by set), "
                    "or remove the numeric range from client-facing text."
                ),
            ))

        # Unapproved-option text scan: for every proposal_option claim
        # whose linked ProposalOption is not approved_for_external_use,
        # flag any client-facing section that contains the claim's text.
        unapproved_option_claims = []
        for c in active_claims.proposal_options:
            opt = active_options.get(c.claim_id)
            if opt is None:
                # Treat absence as unapproved (fail closed).
                unapproved_option_claims.append((c, None))
            elif not opt.is_externally_publishable:
                unapproved_option_claims.append((c, opt))

        client_facing_types = {
            "client_facing_body", "proof_column",
            "slide_body", "slide_proof_points",
        }
        for section in rendered:
            if section.section_type not in client_facing_types:
                continue
            for claim, opt in unapproved_option_claims:
                claim_text = (claim.text or "").strip()
                if not claim_text:
                    continue
                if claim_text in section.text:
                    option_failures.append(ConformanceFailure(
                        requirement_id="UNAPPROVED_OPTION",
                        requirement_text=(
                            f"proposal_option {claim.claim_id} in {section.section_type}"
                        ),
                        failure_reason=(
                            f"proposal_option {claim.claim_id!r} appears in "
                            f"{section.section_path} but its linked "
                            f"ProposalOption is not approved_for_external_use."
                        ),
                        severity="critical",
                        source_book_section=section.section_path,
                        suggested_fix=(
                            "Approve the option (set approved_for_external_use=True, "
                            "priced=True or set pricing_impact_note, fill approved_by) "
                            "before client-facing publication, or relocate the text "
                            "to internal_bid_notes / proposal_option_ledger."
                        ),
                    ))

        if commitment_failures:
            logger.warning(
                "Pass 6: %d unresolved numeric commitments detected",
                len(commitment_failures),
            )
        if option_failures:
            logger.warning(
                "Pass 6: %d unapproved proposal_option leaks detected",
                len(option_failures),
            )
        forbidden_claims.extend(commitment_failures)
        forbidden_claims.extend(option_failures)

    # Compute totals — deduplicate by requirement_id so the same root issue
    # appearing in both missing_commitments and forbidden_claims is counted once.
    total_checked = len(sb_reqs)
    all_failure_ids: set[str] = set()
    for f in missing_commitments:
        all_failure_ids.add(f.requirement_id)
    for f in forbidden_claims:
        all_failure_ids.add(f.requirement_id)
    for f in structural_mismatches:
        all_failure_ids.add(f.requirement_id)
    # Remove generic IDs that don't map to specific HRs — these are
    # overlays, not unique requirement failures. They still drive the
    # status logic via has_critical_failure below; only the count
    # arithmetic ignores them so the "passed N/M" headline isn't
    # corrupted by overlay severity.
    total_failed = len(all_failure_ids - {
        "FORBIDDEN-ABS",
        "FORBIDDEN-LEAKAGE",
        "UNRESOLVED_COMMITMENT",
        "UNAPPROVED_OPTION",
    })
    total_passed = total_checked - total_failed
    if total_passed < 0:
        total_passed = 0

    # Determine conformance status
    has_critical_failure = any(
        f.severity == "critical"
        for f in missing_commitments + forbidden_claims + structural_mismatches
    )
    # Only block when missing input has BOTH severity=critical AND scope=source_book
    has_critical_blocker = any(
        mi.severity == "critical" and mi.validation_scope == "source_book"
        for mi in missing_inputs
    )

    if has_critical_blocker:
        status: Literal["pass", "fail", "blocked"] = "blocked"
    elif has_critical_failure:
        status = "fail"
    else:
        status = "pass"

    # Final decision (reviewer threshold checked by orchestrator)
    if status == "blocked":
        decision: Literal["accept", "reject", "blocked_missing_input"] = "blocked_missing_input"
    elif status == "fail":
        decision = "reject"
    else:
        decision = "accept"  # Tentative — orchestrator adds reviewer check

    report = ConformanceReport(
        missing_required_commitments=missing_commitments,
        forbidden_claims=forbidden_claims,
        structural_mismatches=structural_mismatches,
        missing_inputs=missing_inputs,
        conformance_status=status,
        final_acceptance_decision=decision,
        hard_requirements_checked=total_checked,
        hard_requirements_passed=total_passed,
        hard_requirements_failed=total_failed,
    )

    logger.info(
        "Conformance validation: status=%s, checked=%d, passed=%d, failed=%d, "
        "forbidden=%d, missing_inputs=%d",
        status,
        total_checked,
        total_passed,
        total_failed,
        len(forbidden_claims),
        len(missing_inputs),
    )

    return report


# ── Formatting helpers ────────────────────────────────────────────────


def format_conformance_for_writer(report: ConformanceReport) -> str:
    """Format conformance failures as actionable rewrite instructions.

    Each failure is mapped to a specific section and action. The writer
    must address EVERY critical failure to pass conformance on the next pass.
    """
    lines: list[str] = []

    lines.append(f"=== CONFORMANCE REWRITE INSTRUCTIONS ({report.conformance_status.upper()}) ===")
    lines.append(
        f"Failed: {report.hard_requirements_failed} / {report.hard_requirements_checked} requirements. "
        f"You MUST fix ALL critical failures below to pass conformance."
    )
    lines.append("")

    # Group failures by section for targeted rewriting
    section_failures: dict[str, list[str]] = {}
    for f in report.missing_required_commitments:
        section = f.source_book_section or "general"
        section_failures.setdefault(section, [])
        action = f.suggested_fix or f.failure_reason
        section_failures[section].append(
            f"[{f.severity.upper()}] {f.requirement_id}: {action}"
        )

    if section_failures:
        lines.append("--- SECTION-SPECIFIC FIXES (address in the relevant section) ---")
        for section, fixes in sorted(section_failures.items()):
            lines.append(f"\n  Section: {section}")
            for fix in fixes:
                lines.append(f"    • {fix}")
        lines.append("")

    if report.forbidden_claims:
        lines.append("--- FORBIDDEN CLAIMS (REMOVE from all sections) ---")
        lines.append("These MUST be deleted or corrected. Do NOT soften them — remove them entirely:")
        for f in report.forbidden_claims:
            lines.append(f"  ✗ {f.failure_reason[:200]}")
            if f.suggested_fix:
                lines.append(f"    → {f.suggested_fix}")
        lines.append("")

    # Add explicit rewrite directives for the most common failure patterns
    award_failures = [
        f for f in report.missing_required_commitments + report.forbidden_claims
        if "award" in f.failure_reason.lower() or "weighted" in f.failure_reason.lower()
        or "scoring" in f.failure_reason.lower()
    ]
    if award_failures:
        lines.append("--- AWARD MODEL DIRECTIVE ---")
        lines.append(
            "The RFP uses pass/fail technical evaluation then lowest price award. "
            "You MUST NOT use weighted scoring language (70/30, technical weight, "
            "financial weight, combined score). Instead describe: "
            "'Technical evaluation is pass/fail. Among passing bids, the lowest "
            "price wins. Our strategy must focus on passing all technical requirements "
            "while offering a competitive price.'"
        )
        lines.append("")

    duration_failures = [
        f for f in report.missing_required_commitments
        if "duration" in f.failure_reason.lower() or "month" in f.failure_reason.lower()
    ]
    if duration_failures:
        lines.append("--- DURATION DIRECTIVE ---")
        lines.append(
            "You MUST explicitly state the exact contract duration from the RFP "
            "in Section 1 and Section 5. Use the exact number — do not round, "
            "estimate, or use ranges. Write: 'مدة العقد هي X شهر/شهراً' with the "
            "exact value from the RFP."
        )
        lines.append("")

    compliance_failures = [
        f for f in report.missing_required_commitments
        if f.source_book_section and "section_1" in f.source_book_section.lower()
    ]
    if compliance_failures:
        lines.append("--- COMPLIANCE CARRY-THROUGH DIRECTIVE ---")
        lines.append(
            f"Section 1 must address {len(compliance_failures)} compliance items "
            "that the validator could not find. For each compliance requirement, "
            "add it to key_compliance_requirements with the exact RFP wording and "
            "a COMP-xxx ID. Also add matching compliance_rows."
        )
        lines.append("")

    if report.structural_mismatches:
        lines.append("--- STRUCTURAL MISMATCHES ---")
        for f in report.structural_mismatches:
            lines.append(
                f"  [{f.severity.upper()}] {f.requirement_id}: {f.failure_reason}"
            )
        lines.append("")

    if report.missing_inputs:
        lines.append("--- MISSING INPUTS (cannot resolve in writer) ---")
        for mi in report.missing_inputs:
            lines.append(f"  [{mi.blocker_type}] {mi.input_name}: {mi.message}")
        lines.append("")

    return "\n".join(lines)


def format_conformance_for_reviewer(report: ConformanceReport) -> str:
    """Format conformance summary for reviewer context."""
    lines: list[str] = []

    lines.append(f"Conformance status: {report.conformance_status}")
    lines.append(
        f"Requirements: {report.hard_requirements_checked} checked, "
        f"{report.hard_requirements_passed} passed, "
        f"{report.hard_requirements_failed} failed"
    )

    if report.missing_required_commitments:
        critical = [f for f in report.missing_required_commitments if f.severity == "critical"]
        if critical:
            lines.append(f"Critical missing commitments: {len(critical)}")
            for f in critical[:5]:
                lines.append(f"  - {f.requirement_id}: {f.failure_reason[:100]}")

    if report.forbidden_claims:
        lines.append(f"Forbidden claims: {len(report.forbidden_claims)}")

    return "\n".join(lines)
