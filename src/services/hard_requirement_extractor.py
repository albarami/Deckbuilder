"""Hard Requirement Extractor — Layer 1 (deterministic) + Layer 2 (LLM).

Extracts structured hard requirements from the RFP that the Source Book
must satisfy. These feed the Conformance Validator for deterministic
acceptance gating.

Layer 1: Scans structured RFPContext fields (no LLM).
Layer 2: Regex pre-filter + LLM extraction from raw text.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import Field

from src.models.claim_provenance import ComplianceIndex, ComplianceIndexEntry
from src.models.common import DeckForgeBaseModel
from src.models.conformance import HardRequirement
from src.models.rfp import RFPContext

logger = logging.getLogger(__name__)


# ── Compliance Arabic alias dictionary (Slice 1.3) ──────────────────────
# Maps an English compliance subject phrase (lowercased, stable enough to
# survive small wording variations) to its Arabic + English aliases. The
# ComplianceIndex builder scans the Source Book text for any alias to mark
# a compliance requirement as content-conformance-passing — replacing the
# brittle English keyword scan in the legacy validator.
_COMPLIANCE_ARABIC_ALIASES: dict[str, list[str]] = {
    "commercial registration": [
        "السجل التجاري", "سجل تجاري", "commercial registration",
    ],
    "zakat": ["الزكاة", "شهادة الزكاة", "zakat"],
    "zakat certificate": ["الزكاة", "شهادة الزكاة", "zakat"],
    "tax certificate": [
        "شهادة الضريبة", "الضريبة", "ضريبة القيمة المضافة",
        "vat certificate", "tax certificate",
    ],
    "tax": ["الضريبة", "ضريبة", "tax"],
    "vat": ["ضريبة القيمة المضافة", "vat"],
    "social insurance": [
        "التأمينات الاجتماعية", "التأمينات", "gosi", "social insurance",
    ],
    "social insurance certificate": [
        "التأمينات الاجتماعية", "التأمينات", "gosi",
    ],
    "chamber of commerce": [
        "الغرفة التجارية", "اشتراك الغرفة", "غرفة تجارية",
        "chamber of commerce",
    ],
    "chamber of commerce subscription certificate": [
        "الغرفة التجارية", "اشتراك الغرفة",
    ],
    "chamber": ["الغرفة التجارية", "اشتراك الغرفة"],
    "saudization": [
        "السعودة", "نسبة السعودة", "شهادة السعودة", "saudization",
    ],
    "saudization certificate": ["السعودة", "شهادة السعودة"],
    "iso": ["شهادة الايزو", "iso"],
}


def _aliases_for_subject(subject: str) -> list[str]:
    """Return Arabic + English aliases for a compliance subject.

    Performs (1) exact lowercased lookup, (2) substring match against keys,
    and (3) falls back to the subject itself when no alias is registered.
    The subject text itself is always included so the matcher can find a
    direct mention even when no alias dictionary entry exists.
    """
    s = subject.lower().strip()
    if s in _COMPLIANCE_ARABIC_ALIASES:
        return list(_COMPLIANCE_ARABIC_ALIASES[s]) + [subject]
    for key, aliases in _COMPLIANCE_ARABIC_ALIASES.items():
        if key in s:
            return list(aliases) + [subject]
    return [subject]


def _is_arabic_text(text: str) -> bool:
    return any("؀" <= c <= "ۿ" for c in text)


def build_compliance_index(
    hard_requirements: list[HardRequirement],
    source_book_text: str,
) -> ComplianceIndex:
    """Build a structured ComplianceIndex from compliance hard requirements.

    For each ``category="compliance"`` HR, scan ``source_book_text`` for the
    subject and its Arabic aliases. Mark ``covered_by_response_text`` when a
    match is found and ``missing`` otherwise. Non-compliance HRs are skipped.
    """
    sb_text = source_book_text or ""
    sb_lower = sb_text.lower()
    entries: list[ComplianceIndexEntry] = []

    for hr in hard_requirements:
        if hr.category != "compliance":
            continue
        aliases = _aliases_for_subject(hr.subject)

        found = False
        for alias in aliases:
            if not alias:
                continue
            if _is_arabic_text(alias):
                if alias in sb_text:
                    found = True
                    break
            else:
                if alias.lower() in sb_lower:
                    found = True
                    break

        status = "covered_by_response_text" if found else "missing"
        entries.append(
            ComplianceIndexEntry(
                requirement_id=hr.requirement_id,
                requirement_text=hr.value_text or hr.subject,
                response_status=status,
                arabic_aliases=[a for a in aliases if _is_arabic_text(a)],
                rfp_requirement_claim_id=hr.requirement_id,
            )
        )
    return ComplianceIndex(entries=entries)


# ── Obligation patterns for Layer 2 regex pre-filter ───────────────────

_OBLIGATION_PATTERNS = [
    r"لا\s+يقل\s+عن",           # no less than (Arabic)
    r"بحد\s+أدنى",              # at minimum (Arabic)
    r"عدد\s+لا\s+يقل\s+عن",     # count no less than (Arabic)
    r"يجب\s+أن\s+يشمل",         # must include (Arabic)
    r"يجب\s+أن\s+يتضمن",        # must contain (Arabic)
    r"at\s+least",
    r"minimum\s+of",
    r"no\s+fewer\s+than",
    r"must\s+include",
    r"shall\s+include",
    r"must\s+not",
    r"shall\s+not",
    r"is\s+required",
    r"are\s+required",
    r"mandatory",
]

_COMPILED_OBLIGATION_RE = re.compile(
    "|".join(f"(?:{p})" for p in _OBLIGATION_PATTERNS),
    re.IGNORECASE,
)


# ── LLM response models ───────────────────────────────────────────────


class _ExtractedRequirement(DeckForgeBaseModel):
    """Single requirement extracted by the LLM from raw text."""

    category: str = ""
    subject: str = ""
    operator: str = ""
    value_text: str = ""
    value_number: float | None = None
    dimension: Literal[
        "total", "per_sector", "per_phase", "per_deliverable", "flat"
    ] = "flat"
    unit: str = ""
    phase: str = "all"
    source_text: str = ""
    severity: Literal["critical", "major", "minor"] = "major"
    validation_scope: Literal[
        "source_book", "submission_package", "engine2_proof"
    ] = "source_book"
    confidence: Literal["high", "medium", "low"] = "medium"


class _LLMExtractionResult(DeckForgeBaseModel):
    """LLM response model for Layer 2 extraction."""

    requirements: list[_ExtractedRequirement] = Field(default_factory=list)


# ── Layer 1: Deterministic extraction from RFPContext fields ──────────


def _layer1_extract(rfp: RFPContext) -> list[HardRequirement]:
    """Extract hard requirements from structured RFPContext fields.

    All Layer 1 HRs: confidence=high, is_explicit=True,
    extraction_method=context_field, IDs=HR-L1-NNN.
    """
    reqs: list[HardRequirement] = []
    counter = 0

    def _next_id() -> str:
        nonlocal counter
        counter += 1
        return f"HR-L1-{counter:03d}"

    # ── evaluation_criteria.award_mechanism ──
    if rfp.evaluation_criteria and rfp.evaluation_criteria.award_mechanism != "unknown":
        reqs.append(HardRequirement(
            requirement_id=_next_id(),
            category="award_mechanism",
            subject="award_mechanism",
            operator="==",
            value_text=rfp.evaluation_criteria.award_mechanism,
            dimension="flat",
            unit="mechanism",
            phase="all",
            source_text=f"Award mechanism: {rfp.evaluation_criteria.award_mechanism}",
            source_location="evaluation_criteria.award_mechanism",
            confidence="high",
            is_explicit=True,
            extraction_method="context_field",
            severity="critical",
            validation_scope="source_book",
        ))

    # ── evaluation_criteria.technical_passing_threshold or passing_score ──
    if rfp.evaluation_criteria:
        threshold = (
            rfp.evaluation_criteria.technical_passing_threshold
            or rfp.evaluation_criteria.passing_score
        )
        if threshold is not None:
            reqs.append(HardRequirement(
                requirement_id=_next_id(),
                category="minimum_threshold",
                subject="technical_passing_threshold",
                operator=">=",
                value_text=str(threshold),
                value_number=float(threshold),
                dimension="flat",
                unit="percent",
                phase="all",
                source_text=f"Technical passing threshold: {threshold}%",
                source_location="evaluation_criteria.technical_passing_threshold",
                confidence="high",
                is_explicit=True,
                extraction_method="context_field",
                severity="critical",
                validation_scope="source_book",
            ))

    # ── project_timeline.total_duration_months ──
    if rfp.project_timeline and rfp.project_timeline.total_duration_months is not None:
        months = rfp.project_timeline.total_duration_months
        reqs.append(HardRequirement(
            requirement_id=_next_id(),
            category="contract_duration",
            subject="contract_duration_months",
            operator="==",
            value_text=str(months),
            value_number=float(months),
            dimension="flat",
            unit="months",
            phase="all",
            source_text=(
                f"Contract duration: {rfp.project_timeline.total_duration or str(months) + ' months'}"
            ),
            source_location="project_timeline.total_duration_months",
            confidence="high",
            is_explicit=True,
            extraction_method="context_field",
            severity="critical",
            validation_scope="source_book",
        ))

    # ── project_timeline.deliverable_schedule[] ──
    if rfp.project_timeline and rfp.project_timeline.deliverable_schedule:
        for ds in rfp.project_timeline.deliverable_schedule:
            desc_en = getattr(ds.description, "en", "") or ""
            desc_ar = getattr(ds.description, "ar", "") or ""
            desc_text = desc_en or desc_ar or ds.deliverable_id
            reqs.append(HardRequirement(
                requirement_id=_next_id(),
                category="deliverable_deadline",
                subject=ds.deliverable_id or desc_text,
                operator="==",
                value_text=ds.due_at or "unspecified",
                dimension="per_phase",
                unit="date",
                phase=ds.deliverable_id or "all",
                deliverable_ids=[ds.deliverable_id] if ds.deliverable_id else [],
                source_text=f"Deliverable '{desc_text}' due at {ds.due_at}",
                source_location="project_timeline.deliverable_schedule",
                confidence="high",
                is_explicit=True,
                extraction_method="context_field",
                severity="major",
                validation_scope="source_book",
            ))

    # ── compliance_requirements[mandatory=True] ──
    for cr in rfp.compliance_requirements:
        if not cr.mandatory:
            continue
        req_en = getattr(cr.requirement, "en", "") or ""
        req_ar = getattr(cr.requirement, "ar", "") or ""
        req_text = req_en or req_ar
        reqs.append(HardRequirement(
            requirement_id=_next_id(),
            category="compliance",
            subject=cr.id,
            operator="includes",
            value_text=req_text,
            dimension="flat",
            unit="requirement",
            phase="all",
            source_text=f"Compliance: {req_text}",
            source_location=f"compliance_requirements[{cr.id}]",
            confidence="high",
            is_explicit=True,
            extraction_method="context_field",
            severity="critical",
            validation_scope="source_book",
        ))

    # ── team_requirements[] ──
    for idx, tr in enumerate(rfp.team_requirements):
        title_en = getattr(tr.role_title, "en", "") or ""
        title_ar = getattr(tr.role_title, "ar", "") or ""
        title = title_en or title_ar or f"role_{idx + 1}"
        parts = [title]
        if tr.education:
            parts.append(tr.education)
        if tr.certifications:
            parts.append(", ".join(tr.certifications))
        if tr.min_years_experience is not None:
            parts.append(f"{tr.min_years_experience}+ years")
        reqs.append(HardRequirement(
            requirement_id=_next_id(),
            category="team_qualification",
            subject=title,
            operator="includes",
            value_text=" / ".join(parts),
            value_number=float(tr.min_years_experience) if tr.min_years_experience else None,
            dimension="flat",
            unit="role",
            phase="all",
            source_text=f"Team requirement: {' / '.join(parts)}",
            source_location=f"team_requirements[{idx}]",
            confidence="high",
            is_explicit=True,
            extraction_method="context_field",
            severity="major",
            validation_scope="source_book",
        ))

    # ── submission_format ──
    if rfp.submission_format:
        sf = rfp.submission_format
        packaging_items: list[str] = []
        if sf.bank_guarantee_required:
            packaging_items.append("bank_guarantee")
            reqs.append(HardRequirement(
                requirement_id=_next_id(),
                category="packaging",
                subject="bank_guarantee",
                operator="must_include",
                value_text="bank guarantee required",
                dimension="flat",
                unit="requirement",
                phase="all",
                source_text="Bank guarantee required for submission",
                source_location="submission_format.bank_guarantee_required",
                confidence="high",
                is_explicit=True,
                extraction_method="context_field",
                severity="critical",
                validation_scope="submission_package",
            ))
        if sf.separate_envelopes:
            packaging_items.append("separate_envelopes")
            reqs.append(HardRequirement(
                requirement_id=_next_id(),
                category="packaging",
                subject="separate_envelopes",
                operator="must_include",
                value_text="separate technical and financial envelopes",
                dimension="flat",
                unit="format",
                phase="all",
                source_text="Separate envelopes required",
                source_location="submission_format.separate_envelopes",
                confidence="high",
                is_explicit=True,
                extraction_method="context_field",
                severity="major",
                validation_scope="submission_package",
            ))
        for add_req in sf.additional_requirements:
            reqs.append(HardRequirement(
                requirement_id=_next_id(),
                category="packaging",
                subject="additional_requirement",
                operator="must_include",
                value_text=add_req,
                dimension="flat",
                unit="requirement",
                phase="all",
                source_text=f"Submission requirement: {add_req}",
                source_location="submission_format.additional_requirements",
                confidence="high",
                is_explicit=True,
                extraction_method="context_field",
                severity="major",
                validation_scope="submission_package",
            ))

    # ── deliverables[mandatory=True] ──
    for d in rfp.deliverables:
        if not d.mandatory:
            continue
        desc_en = getattr(d.description, "en", "") or ""
        desc_ar = getattr(d.description, "ar", "") or ""
        desc_text = desc_en or desc_ar
        reqs.append(HardRequirement(
            requirement_id=_next_id(),
            category="deliverable_required",
            subject=d.id,
            operator="must_include",
            value_text=desc_text,
            dimension="flat",
            unit="deliverable",
            phase="all",
            deliverable_ids=[d.id],
            source_text=f"Mandatory deliverable: {desc_text}",
            source_location=f"deliverables[{d.id}]",
            confidence="high",
            is_explicit=True,
            extraction_method="context_field",
            severity="critical",
            validation_scope="source_book",
        ))

    logger.info("Layer 1 extraction: %d hard requirements from RFPContext fields", len(reqs))
    return reqs


# ── Layer 2: LLM-assisted extraction from raw text ───────────────────


def _extract_candidate_sentences(text: str, context_chars: int = 300) -> list[str]:
    """Find sentences containing obligation patterns with surrounding context."""
    candidates: list[str] = []
    seen_spans: set[tuple[int, int]] = set()

    for match in _COMPILED_OBLIGATION_RE.finditer(text):
        start = max(0, match.start() - context_chars)
        end = min(len(text), match.end() + context_chars)
        span_key = (start // 100, end // 100)  # approximate dedup
        if span_key in seen_spans:
            continue
        seen_spans.add(span_key)
        candidates.append(text[start:end].strip())

    return candidates


def _deduplicate_layer2(
    layer2_reqs: list[HardRequirement],
    layer1_reqs: list[HardRequirement],
) -> list[HardRequirement]:
    """Remove Layer 2 requirements that duplicate Layer 1 by subject similarity."""
    l1_subjects = {r.subject.lower().strip() for r in layer1_reqs}
    l1_categories = {(r.category, r.subject.lower().strip()) for r in layer1_reqs}

    deduped: list[HardRequirement] = []
    for req in layer2_reqs:
        key = (req.category, req.subject.lower().strip())
        if key in l1_categories:
            continue
        if req.subject.lower().strip() in l1_subjects:
            continue
        deduped.append(req)

    removed = len(layer2_reqs) - len(deduped)
    if removed:
        logger.info("Layer 2 dedup: removed %d duplicates of Layer 1", removed)
    return deduped


async def _layer2_extract(
    rfp_raw_text: str,
    output_language: str,
    layer1_reqs: list[HardRequirement],
) -> list[HardRequirement]:
    """Extract additional hard requirements from raw RFP text using LLM.

    1. Regex pre-filter for obligation patterns
    2. Extract candidate sentences (300 chars context)
    3. LLM call for structured extraction
    4. Deduplicate against Layer 1
    """
    if not rfp_raw_text or not rfp_raw_text.strip():
        logger.info("Layer 2: no raw text provided, skipping")
        return []

    candidates = _extract_candidate_sentences(rfp_raw_text)
    if not candidates:
        logger.info("Layer 2: no obligation patterns found in raw text")
        return []

    logger.info("Layer 2: %d candidate sentences from regex pre-filter", len(candidates))

    # Limit candidates to avoid excessive token usage
    candidates = candidates[:30]

    candidate_text = "\n---\n".join(candidates)
    language_note = "Arabic" if output_language == "ar" else "English"

    system_prompt = f"""You are an RFP requirement extractor. Analyze the following candidate
sentences from an RFP document ({language_note}) and extract structured hard requirements.

For each obligation found, extract:
- category: one of (minimum_count, packaging, guarantee, award_mechanism, contract_duration,
  deliverable_deadline, compliance, team_qualification, deliverable_required, minimum_threshold,
  quantified_minimum, structural)
- subject: what the requirement is about (e.g., "priority_sectors", "workshops_per_sector")
- operator: (>=, ==, <=, includes, must_include)
- value_text: human-readable value
- value_number: numeric value if applicable (null otherwise)
- dimension: (total, per_sector, per_phase, per_deliverable, flat)
- unit: (count, percent, months, items, days)
- phase: which phase this applies to ("all" if global)
- source_text: the verbatim text from the RFP
- severity: (critical, major, minor)
- validation_scope: (source_book, submission_package, engine2_proof)
- confidence: (high, medium, low)

Only extract CONCRETE, VERIFIABLE obligations. Skip vague aspirational language.
Return empty list if no clear obligations found."""

    user_message = f"Candidate obligation sentences:\n\n{candidate_text}"

    try:
        from src.config.models import MODEL_MAP
        from src.services.llm import call_llm

        model = MODEL_MAP.get("source_book_writer", MODEL_MAP.get("analysis_agent"))
        result = await call_llm(
            model=model,
            system_prompt=system_prompt,
            user_message=user_message,
            response_model=_LLMExtractionResult,
            max_tokens=4000,
        )

        raw_reqs = result.parsed.requirements
        logger.info("Layer 2 LLM: extracted %d raw requirements", len(raw_reqs))

        # Convert to HardRequirement with Layer 2 IDs
        layer2_reqs: list[HardRequirement] = []
        for idx, raw in enumerate(raw_reqs, 1):
            layer2_reqs.append(HardRequirement(
                requirement_id=f"HR-L2-{idx:03d}",
                category=raw.category,
                subject=raw.subject,
                operator=raw.operator,
                value_text=raw.value_text,
                value_number=raw.value_number,
                dimension=raw.dimension,
                unit=raw.unit,
                phase=raw.phase,
                source_text=raw.source_text,
                source_location="rfp_raw_text",
                confidence=raw.confidence,
                is_explicit=True,
                extraction_method="llm_structured",
                severity=raw.severity,
                validation_scope=raw.validation_scope,
            ))

        # Deduplicate against Layer 1
        deduped = _deduplicate_layer2(layer2_reqs, layer1_reqs)
        logger.info("Layer 2: %d requirements after dedup", len(deduped))
        return deduped

    except Exception as e:
        logger.error("Layer 2 LLM extraction failed: %s", e)
        return []


# ── Public API ────────────────────────────────────────────────────────


async def extract_hard_requirements(
    rfp: RFPContext,
    rfp_raw_text: str,
    output_language: str,
) -> list[HardRequirement]:
    """Extract hard requirements from RFP using Layer 1 + Layer 2.

    Layer 1 (deterministic): from structured RFPContext fields.
    Layer 2 (LLM-assisted): from raw text via regex + LLM.

    Returns combined, deduplicated list of HardRequirements.
    """
    # Layer 1: deterministic
    layer1_reqs = _layer1_extract(rfp)

    # Layer 2: LLM-assisted
    layer2_reqs = await _layer2_extract(rfp_raw_text, output_language, layer1_reqs)

    all_reqs = layer1_reqs + layer2_reqs
    logger.info(
        "Hard requirement extraction: %d total (%d L1, %d L2)",
        len(all_reqs),
        len(layer1_reqs),
        len(layer2_reqs),
    )
    return all_reqs
