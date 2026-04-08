"""Assertion classification and rendering enforcement for Engine 1.

Post-generation pass that:
1. Validates every ClassifiedClaim carries a correct AssertionLabel.
2. Enforces rendering policy: INFERENCE never presented as fact,
   EXTERNAL_BENCHMARK framed as supporting analogues, and
   INTERNAL_PROOF_PLACEHOLDER flags future proof needs only.
3. Sanitizes absolute language not grounded in uploaded text.
4. Applies benchmark-governance rules limiting external research framing.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from src.models.source_book import (
    AssertionLabel,
    ClassifiedClaim,
    EvaluationHypothesis,
    SourceBook,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Absolute language patterns (English + Arabic)
# ──────────────────────────────────────────────────────────────

_ABSOLUTE_PATTERNS = re.compile(
    # English certainty absolutes
    r"\bguarantees?\b|\bensures?\s+100%|\bcompletely\s+eliminates?\b|"
    r"\bwill\s+certainly\b|\bwithout\s+fail\b|\bno\s+risk\b|"
    r"\bwill\s+guarantee\b|\babsolutely\b|\bundoubtedly\b|"
    r"\bwill\s+always\b|\bnever\s+fail\b|\bfull\s+compliance\b|"
    r"\bzero\s+risk\b|\brisk[- ]free\b|\bfailure[- ]proof\b|"
    # Missed patterns from artifact review
    r"\bflawlessly\b|\bflawless\b|\bseamlessly\b|"
    r"\bzero\s+learning\s+curve\b|\bzero\s+unplanned\s+downtime\b|"
    r"\bzero\s+defects?\b|\bwith\s+zero\b|"
    r"\balmost\s+certainly\b|\bconsistently\s+require\b|"
    # Arabic certainty absolutes
    r"يضمن\s+بالكامل|ضمان\s+كامل|بدون\s+أي\s+مخاطر|"
    r"خالي\s+من\s+المخاطر|يقضي\s+تماماً|بلا\s+شك|"
    r"نضمن\s+تحقيق|امتثال\s+كامل\s+مطلق",
    re.IGNORECASE,
)

# Softening replacements for common absolute patterns
_SOFTENING_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bguarantees?\b", re.I), "is designed to deliver"),
    (re.compile(r"\bensures?\s+100%", re.I), "is structured to maximize"),
    (re.compile(r"\bcompletely\s+eliminates?\b", re.I), "significantly mitigates"),
    (re.compile(r"\bwill\s+certainly\b", re.I), "is expected to"),
    (re.compile(r"\bwithout\s+fail\b", re.I), "with high reliability"),
    (re.compile(r"\bno\s+risk\b", re.I), "minimal risk"),
    (re.compile(r"\babsolutely\b", re.I), "substantially"),
    (re.compile(r"\bundoubtedly\b", re.I), "with strong confidence"),
    (re.compile(r"\bfull\s+compliance\b", re.I), "comprehensive compliance"),
    (re.compile(r"\bzero\s+risk\b", re.I), "minimal residual risk"),
    (re.compile(r"\brisk[- ]free\b", re.I), "risk-mitigated"),
    # Missed patterns from artifact review
    (re.compile(r"\bflawlessly\b", re.I), "effectively"),
    (re.compile(r"\bflawless\b", re.I), "robust"),
    (re.compile(r"\bseamlessly\b", re.I), "with minimal disruption"),
    (re.compile(r"\bzero\s+learning\s+curve\b", re.I), "minimal adoption effort"),
    (re.compile(r"\bzero\s+unplanned\s+downtime\b", re.I), "minimal unplanned downtime"),
    (re.compile(r"\bzero\s+defects?\b", re.I), "near-zero defects"),
    (re.compile(r"\bwith\s+zero\b", re.I), "with minimal"),
    (re.compile(r"\balmost\s+certainly\b", re.I), "with high probability"),
    (re.compile(r"\bconsistently\s+require\b", re.I), "typically expect"),
    # Arabic
    (re.compile(r"يضمن\s+بالكامل"), "مُصمَّم لتحقيق"),
    (re.compile(r"ضمان\s+كامل"), "تصميم يستهدف تحقيق"),
    (re.compile(r"بدون\s+أي\s+مخاطر"), "بأدنى مستوى من المخاطر"),
    (re.compile(r"خالي\s+من\s+المخاطر"), "بمخاطر محدودة"),
    (re.compile(r"نضمن\s+تحقيق"), "نستهدف تحقيق"),
    (re.compile(r"امتثال\s+كامل\s+مطلق"), "امتثال شامل مُصمَّم"),
]

# ──────────────────────────────────────────────────────────────
# Benchmark-governance patterns
# ──────────────────────────────────────────────────────────────

_BENCHMARK_AS_PROOF_PATTERNS = re.compile(
    r"\bproves?\s+that\s+SG\b|\bdemonstrates?\s+SG\s+capability\b|"
    r"\bconfirms?\s+SG\b|\bvalidates?\s+SG\s+experience\b|"
    r"يثبت\s+أن\s+.*ستراتيجيك|يؤكد\s+قدرة\s+.*ستراتيجيك",
    re.IGNORECASE,
)

_BENCHMARK_GOVERNANCE_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bproves?\s+that\s+SG\b", re.I), "supports the approach where SG"),
    (re.compile(r"\bdemonstrates?\s+SG\s+capability\b", re.I),
     "aligns with the methodology SG proposes"),
    (re.compile(r"\bconfirms?\s+SG\b", re.I), "is consistent with SG's proposed"),
    (re.compile(r"\bvalidates?\s+SG\s+experience\b", re.I),
     "provides international precedent supporting SG's approach"),
]


@dataclass
class ClassificationReport:
    """Summary of classification enforcement pass."""

    total_claims_checked: int = 0
    misclassified_fixed: int = 0
    absolutes_softened: int = 0
    benchmark_governance_fixes: int = 0
    inference_rendering_fixes: int = 0


def soften_absolutes(text: str) -> tuple[str, int]:
    """Replace unsupported absolute language with evidence-safe alternatives.

    Args:
        text: Input prose text.

    Returns:
        Tuple of (softened text, count of replacements made).
    """
    count = 0
    result = text
    for pattern, replacement in _SOFTENING_MAP:
        new_result, n = pattern.subn(replacement, result)
        count += n
        result = new_result
    return result, count


def apply_benchmark_governance(text: str) -> tuple[str, int]:
    """Enforce benchmark-governance rules on prose text.

    External benchmarks must be framed as supporting analogues,
    never as proof of SG capability.

    Args:
        text: Input prose text.

    Returns:
        Tuple of (governed text, count of fixes).
    """
    count = 0
    result = text
    for pattern, replacement in _BENCHMARK_GOVERNANCE_REPLACEMENTS:
        new_result, n = pattern.subn(replacement, result)
        count += n
        result = new_result
    return result, count


def _validate_claim_label(claim: ClassifiedClaim) -> ClassifiedClaim:
    """Validate and correct a single claim's label based on content heuristics.

    Rules:
    - Claims referencing RFP text directly → DIRECT_RFP_FACT
    - Claims with EXT-xxx references → EXTERNAL_BENCHMARK
    - Claims with CLM-xxxx references → INTERNAL_PROOF_PLACEHOLDER
    - Everything else stays as labeled (usually INFERENCE)
    """
    text_lower = claim.claim_text.lower() + " " + claim.basis.lower()

    if claim.label == AssertionLabel.INFERENCE:
        if any(phrase in text_lower for phrase in [
            "rfp states", "rfp requires", "rfp specifies",
            "per the rfp", "as stated in the rfp",
            "وفقاً للكراسة", "تنص الكراسة", "كما ورد في",
            "يتطلب المشروع", "حسب المتطلبات",
        ]):
            claim.label = AssertionLabel.DIRECT_RFP_FACT
            return claim

    if claim.label != AssertionLabel.EXTERNAL_BENCHMARK:
        if re.search(r"EXT-\d{3}", claim.basis) or re.search(r"EXT-\d{3}", claim.claim_text):
            claim.label = AssertionLabel.EXTERNAL_BENCHMARK
            return claim

    if claim.label != AssertionLabel.INTERNAL_PROOF_PLACEHOLDER:
        if re.search(r"CLM-\d{4}", claim.basis) or re.search(r"CLM-\d{4}", claim.claim_text):
            claim.label = AssertionLabel.INTERNAL_PROOF_PLACEHOLDER
            return claim

    return claim


# ──────────────────────────────────────────────────────────────
# Fact-citation guards
# ──────────────────────────────────────────────────────────────

# Sentence-level fact-citation prefixes that protect the rest of the
# sentence from inference softening.  If a sentence contains one of
# these explicit-source markers, it is reporting an RFP fact.
_FACT_CITATION_GUARDS = re.compile(
    # English explicit-source forms
    r"\bthe\s+rfp\s+(?:states?|requires?|specifies?|mandates?|stipulates?)\b|"
    r"\bsection\s+\d+(?:\.\d+)?\s+(?:states?|requires?|specifies?)\b|"
    r"\bper\s+the\s+rfp\b|\bas\s+stated\s+in\s+the\s+rfp\b|"
    r"\bthe\s+rfp\s+explicitly\b|\baccording\s+to\s+the\s+rfp\b|"
    # Arabic explicit-source forms
    r"وفقاً\s+للكراسة|تنص\s+الكراسة|كما\s+ورد\s+في|حسب\s+المتطلبات",
    re.IGNORECASE,
)

# ──────────────────────────────────────────────────────────────
# Stacked-hedge deduplication
# ──────────────────────────────────────────────────────────────

_STACKED_HEDGE_FIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\blikely\s+with\s+high\s+probability\b", re.I), "likely"),
    (re.compile(r"\bwith\s+high\s+probability\s+likely\b", re.I), "likely"),
    (re.compile(r"\bprobably\s+likely\b", re.I), "likely"),
    (re.compile(r"\blikely\s+probably\b", re.I), "likely"),
    (re.compile(r"\btypically\s+likely\s+expected\b", re.I), "typically expected"),
    (re.compile(r"\btypically\s+likely\b", re.I), "typically"),
    (re.compile(r"\blikely\s+typically\b", re.I), "typically"),
    (re.compile(r"\bwill\s+likely\s+with\s+high\s+probability\b", re.I), "will likely"),
    (re.compile(r"\bwill\s+likely\s+likely\b", re.I), "will likely"),
]


def _is_fact_grounded_sentence(sentence: str) -> bool:
    """Return True if the sentence contains an explicit source citation."""
    return bool(_FACT_CITATION_GUARDS.search(sentence))


def _collapse_stacked_hedges(text: str) -> tuple[str, int]:
    """Remove awkward stacked hedging produced by chained sanitizers.

    Returns:
        Tuple of (cleaned text, count of collapses).
    """
    count = 0
    result = text
    for pattern, replacement in _STACKED_HEDGE_FIXES:
        new_result, n = pattern.subn(replacement, result)
        count += n
        result = new_result
    return result, count


# Clause boundary: conjunctions that may separate a fact clause from
# an inference clause within the same sentence.  Capturing group so
# re.split keeps the delimiters for faithful reconstruction.
_CLAUSE_SPLITTER = re.compile(r"(,?\s*\b(?:and|but)\b\s+)", re.IGNORECASE)

# Sentence boundary that preserves section numbers (3.1, 5.3.1).
# (?!\d) prevents splitting on a period followed by a digit.
_SENTENCE_BOUNDARY = re.compile(r"(?<=\.)(?!\d)\s*|(?<=[;\n])\s*")


def _enforce_inference_rendering(text: str) -> tuple[str, int]:
    """Ensure inferred content is not presented with factual certainty.

    Catches patterns where inference language reads as established fact.
    Preserves **clauses** that are explicitly source-grounded (e.g.
    "The RFP states ...") while still softening adjacent inference
    clauses in the same sentence joined by "and" / "but".

    Returns:
        Tuple of (fixed text, count of fixes).
    """
    count = 0
    inference_as_fact = [
        (re.compile(r"\bthe\s+evaluators?\s+will\s+prioritize\b", re.I),
         "the evaluators are likely to prioritize"),
        (re.compile(r"\bthe\s+scoring\s+will\s+favor\b", re.I),
         "the scoring is likely to favor"),
        (re.compile(r"\bthe\s+evaluation\s+committee\s+requires\b", re.I),
         "the evaluation committee likely expects"),
        (re.compile(r"\bthe\s+client\s+expects\b(?!\s*\()", re.I),
         "the client likely expects"),
        (re.compile(r"\bthe\s+evaluation\s+committee\s+will\b", re.I),
         "the evaluation committee will likely"),
        (re.compile(r"\bevaluators?\s+will\s+almost\s+certainly\b", re.I),
         "evaluators will likely"),
        (re.compile(r"\bprocurement\s+patterns?\s+consistently\s+require\b", re.I),
         "procurement patterns typically expect"),
        (re.compile(r"\bwill\s+almost\s+certainly\s+include\b", re.I),
         "will likely include"),
        (re.compile(r"\blikely\s+the\s+Deputy\b", re.I),
         "possibly the Deputy"),
        (re.compile(r"\bprojected\s+\d+/\d+\s+scoring", re.I),
         "estimated scoring"),
        # Arabic inference-as-fact
        (re.compile(r"سيعطي\s+المقيّمون\s+أولوية"), "من المرجح أن يعطي المقيّمون أولوية"),
        (re.compile(r"ستفضّل\s+لجنة\s+التقييم"), "من المرجح أن تفضّل لجنة التقييم"),
    ]

    def _soften_clause(clause: str) -> str:
        """Apply inference patterns to a single non-guarded clause."""
        nonlocal count
        result = clause
        for pattern, replacement in inference_as_fact:
            new_result, n = pattern.subn(replacement, result)
            count += n
            result = new_result
        return result

    # Split into sentences (section numbers like 3.1 are preserved)
    sentences = _SENTENCE_BOUNDARY.split(text)
    rebuilt_sentences: list[str] = []

    for sentence in sentences:
        # Split sentence into clauses on conjunctions
        clause_parts = _CLAUSE_SPLITTER.split(sentence)
        rebuilt_clauses: list[str] = []

        for i, part in enumerate(clause_parts):
            # Odd indices are conjunction delimiters — pass through
            if i % 2 == 1:
                rebuilt_clauses.append(part)
                continue
            # Even indices are clauses — check fact guard per clause
            if _is_fact_grounded_sentence(part):
                rebuilt_clauses.append(part)
                continue
            rebuilt_clauses.append(_soften_clause(part))

        rebuilt_sentences.append("".join(rebuilt_clauses))

    joined = " ".join(p for p in rebuilt_sentences if p)
    # Collapse any stacked hedges from chained sanitizer passes
    joined, hedge_fixes = _collapse_stacked_hedges(joined)
    count += hedge_fixes
    return joined, count


# Basis strings that indicate the hypothesis is grounded in explicit
# RFP text, not inferred from patterns.  These protect the label.
_EXPLICIT_BASIS_MARKERS = re.compile(
    r"\brfp\s+(?:states?|requires?|specifies?|section)\b|"
    r"\bper\s+the\s+rfp\b|\bas\s+stated\b|"
    r"\bexplicitly\s+(?:listed|stated|defined|specified)\b|"
    r"وفقاً\s+للكراسة|تنص\s+الكراسة|حسب\s+المتطلبات",
    re.IGNORECASE,
)


def validate_evaluation_hypotheses(
    hypotheses: list[EvaluationHypothesis],
) -> list[EvaluationHypothesis]:
    """Validate evaluation hypothesis labels.

    Rules:
    - If basis references explicit RFP text -> preserve DIRECT_RFP_FACT
    - If basis is absent or references patterns/structure -> set INFERENCE
    - Always ensure a non-empty basis string
    """
    for hyp in hypotheses:
        basis_is_explicit = bool(
            hyp.basis and _EXPLICIT_BASIS_MARKERS.search(hyp.basis)
        )
        if basis_is_explicit:
            if hyp.label != AssertionLabel.DIRECT_RFP_FACT:
                hyp.label = AssertionLabel.DIRECT_RFP_FACT
        else:
            if hyp.label != AssertionLabel.INFERENCE:
                hyp.label = AssertionLabel.INFERENCE
        if not hyp.basis:
            hyp.basis = "Inferred from RFP structure and evaluation patterns"
    return hypotheses


def enforce_classification(source_book: SourceBook) -> ClassificationReport:
    """Run full assertion classification enforcement on a completed source book.

    Mutates the source book in-place. Returns a classification report.
    """
    report = ClassificationReport()

    # ── 1. Validate ClassifiedClaim labels ────────────────
    all_claims: list[ClassifiedClaim] = []
    rfp = source_book.rfp_interpretation
    all_claims.extend(rfp.explicit_requirements)
    all_claims.extend(rfp.inferred_requirements)
    all_claims.extend(rfp.external_support)
    all_claims.extend(source_book.proposed_solution.benchmark_references)

    for claim in all_claims:
        original = claim.label
        _validate_claim_label(claim)
        if claim.label != original:
            report.misclassified_fixed += 1
    report.total_claims_checked = len(all_claims)

    # ── 2. Enforce evaluation hypotheses are INFERENCE ────
    if rfp.evaluation_hypotheses:
        validate_evaluation_hypotheses(rfp.evaluation_hypotheses)

    # ── 3. Soften absolutes in all prose fields ───────────
    prose_fields = [
        (rfp, "objective_and_scope"),
        (rfp, "constraints_and_compliance"),
        (rfp, "unstated_evaluator_priorities"),
        (rfp, "probable_scoring_logic"),
        (source_book.client_problem_framing, "current_state_challenge"),
        (source_book.client_problem_framing, "why_it_matters_now"),
        (source_book.client_problem_framing, "transformation_logic"),
        (source_book.client_problem_framing, "risk_if_unchanged"),
        (source_book.proposed_solution, "methodology_overview"),
        (source_book.proposed_solution, "governance_framework"),
        (source_book.proposed_solution, "timeline_logic"),
        (source_book.proposed_solution, "value_case_and_differentiation"),
        (source_book.external_evidence, "coverage_assessment"),
    ]
    for obj, field_name in prose_fields:
        text = getattr(obj, field_name, "")
        if not text:
            continue
        softened, n = soften_absolutes(text)
        if n > 0:
            setattr(obj, field_name, softened)
            report.absolutes_softened += n

    # ── 4. Benchmark-governance on prose ──────────────────
    benchmark_fields = [
        (source_book.external_evidence, "coverage_assessment"),
        (source_book.proposed_solution, "value_case_and_differentiation"),
        (source_book.proposed_solution, "methodology_overview"),
    ]
    for obj, field_name in benchmark_fields:
        text = getattr(obj, field_name, "")
        if not text:
            continue
        governed, n = apply_benchmark_governance(text)
        if n > 0:
            setattr(obj, field_name, governed)
            report.benchmark_governance_fixes += n

    # ── 5. Inference rendering on Section 1 prose ─────────
    inference_fields = [
        (rfp, "unstated_evaluator_priorities"),
        (rfp, "probable_scoring_logic"),
    ]
    for obj, field_name in inference_fields:
        text = getattr(obj, field_name, "")
        if not text:
            continue
        fixed, n = _enforce_inference_rendering(text)
        if n > 0:
            setattr(obj, field_name, fixed)
            report.inference_rendering_fixes += n

    # ── 6. Soften absolutes in slide blueprints ───────────
    for bp in source_book.slide_blueprints:
        for field_name in ("title", "key_message"):
            text = getattr(bp, field_name, "")
            if not text:
                continue
            softened, n = soften_absolutes(text)
            if n > 0:
                setattr(bp, field_name, softened)
                report.absolutes_softened += n
        if bp.bullet_logic:
            for i, bullet in enumerate(bp.bullet_logic):
                softened, n = soften_absolutes(bullet)
                if n > 0:
                    bp.bullet_logic[i] = softened
                    report.absolutes_softened += n

    # Store absolutes found in coherence result
    source_book.coherence.absolutes_softened = report.absolutes_softened

    logger.info(
        "Assertion classifier: checked=%d, misclassified_fixed=%d, "
        "absolutes_softened=%d, benchmark_gov=%d, inference_render=%d",
        report.total_claims_checked,
        report.misclassified_fixed,
        report.absolutes_softened,
        report.benchmark_governance_fixes,
        report.inference_rendering_fixes,
    )

    return report
