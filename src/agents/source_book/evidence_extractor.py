"""Dedicated evidence ledger extractor.

After the Writer/Reviewer loop produces Sections 1-6, this module makes
a separate LLM call to audit every factual claim, statistic, case study
reference, framework citation, and capability assertion — producing a
rich evidence ledger with real claim text, specific source references,
and verifiability descriptions.

This replaces the generic auto-builder that produced
"Auto-extracted citation CLM-xxxx" placeholder entries.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.models.source_book import (
    EvidenceLedgerEntry,
    SourceBook,
)

logger = logging.getLogger(__name__)

EVIDENCE_EXTRACTOR_PROMPT = """\
You are an evidence auditor for a management consulting proposal.

Below is a completed Proposal Source Book (Sections 1-6). Your job is to
scan EVERY factual claim, statistic, case study reference, framework
citation, and capability assertion, and produce a structured evidence
ledger entry for each one.

For EACH claim you find, produce a JSON object with these fields:
- claim_id: Sequential ID (CLAIM-001, CLAIM-002, etc.)
- claim_text: The EXACT sentence or phrase from the Source Book that
  makes the claim. Copy it verbatim — do NOT paraphrase or summarize.
  NEVER write "Auto-extracted citation" — use the real text.
- source_type: "internal" if it references SG internal data (CLM-xxxx,
  knowledge graph, project records, team profiles) or "external" if it
  references external sources (EXT-xxx, Semantic Scholar papers,
  Perplexity web results, industry reports, frameworks)
- source_reference: The specific source. For internal: the CLM-xxxx ID
  and/or document name. For external: the paper title, report name, or
  framework standard (e.g., "TOGAF 9.2", "Gartner 2024 Report",
  "ISO 27001:2022"). Be specific — not just "internal document".
- confidence: "high" if directly cited with evidence ID, "medium" if
  the claim is specific but source is implied, "low" if the claim is
  an assertion without clear backing
- verifiability_status: A brief description of how a reviewer could
  verify this claim. Examples:
  "Check CLM-0005 in reference_index for SAP migration details"
  "Verify ISO 27001 certification on SG corporate website"
  "Cross-reference ADNOC project in KG project records"
  "Validate against Gartner 2024 Digital Transformation report"

RULES:
1. Extract 15-25 entries minimum. Aim for completeness.
2. Include claims from ALL sections — not just Section 3.
3. Prioritize: statistics, named projects, named people with
   credentials, specific outcomes, framework references, compliance
   assertions, partnership claims, certification claims.
4. claim_text MUST be the actual text from the Source Book, not a
   description of what it says. Copy the sentence.
5. Do NOT produce generic entries like "Auto-extracted citation CLM-0001"

Output a JSON array of objects. Example:
[
  {
    "claim_id": "CLAIM-001",
    "claim_text": "SG deployed AI-driven automation across 15 \
processes at ADNOC, achieving 10M AED annual savings",
    "source_type": "internal",
    "source_reference": "CLM-0012, KG project: ADNOC Automation",
    "confidence": "high",
    "verifiability_status": "Cross-reference CLM-0012 and KG project \
record for ADNOC. Savings figure from project outcome data."
  },
  {
    "claim_id": "CLAIM-002",
    "claim_text": "Strategic Gears holds Platinum ranking among \
top 100 consulting firms in the Middle East (2024)",
    "source_type": "external",
    "source_reference": "Consultancy.me Middle East rankings 2024",
    "confidence": "high",
    "verifiability_status": "Verify on consultancy.me/rankings or \
SG corporate website press releases."
  }
]

Output ONLY the JSON array. No markdown, no commentary."""


class _LedgerEntryRaw:
    """Lightweight holder for parsed JSON entries before Pydantic."""

    def __init__(self, d: dict[str, Any]) -> None:
        self.claim_id = d.get("claim_id", "")
        self.claim_text = d.get("claim_text", "")
        self.source_type = d.get("source_type", "internal")
        self.source_reference = d.get("source_reference", "")
        self.confidence_label = d.get("confidence", "medium")
        self.verifiability = d.get("verifiability_status", "")


def _source_book_to_text(source_book: SourceBook) -> str:
    """Serialize Sections 1-6 to a readable text blob for the auditor."""
    parts: list[str] = []

    # Section 1: RFP Interpretation
    rfp = source_book.rfp_interpretation
    parts.append("=== SECTION 1: RFP INTERPRETATION ===")
    parts.append(f"Objective: {rfp.objective_and_scope}")
    parts.append(f"Constraints: {rfp.constraints_and_compliance}")
    parts.append(f"Evaluator priorities: {rfp.unstated_evaluator_priorities}")
    parts.append(f"Scoring logic: {rfp.probable_scoring_logic}")
    if rfp.key_compliance_requirements:
        parts.append("Compliance requirements:")
        for req in rfp.key_compliance_requirements:
            parts.append(f"  - {req}")

    # Section 2: Client Problem Framing
    cpf = source_book.client_problem_framing
    parts.append("\n=== SECTION 2: CLIENT PROBLEM FRAMING ===")
    parts.append(f"Challenge: {cpf.current_state_challenge}")
    parts.append(f"Urgency: {cpf.why_it_matters_now}")
    parts.append(f"Solution logic: {cpf.transformation_logic}")
    parts.append(f"Risk: {cpf.risk_if_unchanged}")

    # Section 3: Why Strategic Gears
    wsg = source_book.why_strategic_gears
    parts.append("\n=== SECTION 3: WHY STRATEGIC GEARS ===")
    for cm in wsg.capability_mapping:
        parts.append(
            f"Capability: {cm.rfp_requirement} → {cm.sg_capability} "
            f"[{', '.join(cm.evidence_ids)}] (strength: {cm.strength})"
        )
    for nc in wsg.named_consultants:
        certs = ", ".join(nc.certifications) if nc.certifications else ""
        parts.append(
            f"Consultant: {nc.name}, {nc.role}, "
            f"{nc.years_experience}y exp, certs: {certs}. "
            f"{nc.relevance}"
        )
    for pe in wsg.project_experience:
        parts.append(
            f"Project: {pe.project_name} ({pe.client}, {pe.sector}): "
            f"{pe.outcomes} [{', '.join(pe.evidence_ids)}]"
        )
    for cert in wsg.certifications_and_compliance:
        parts.append(f"Certification: {cert}")

    # Section 4: External Evidence
    ext = source_book.external_evidence
    parts.append("\n=== SECTION 4: EXTERNAL EVIDENCE ===")
    for entry in ext.entries:
        parts.append(
            f"{entry.source_id}: {entry.title} ({entry.year}) — "
            f"{entry.key_finding}"
        )
    parts.append(f"Coverage: {ext.coverage_assessment}")

    # Section 5: Proposed Solution
    ps = source_book.proposed_solution
    parts.append("\n=== SECTION 5: PROPOSED SOLUTION ===")
    parts.append(f"Overview: {ps.methodology_overview}")
    for phase in ps.phase_details:
        parts.append(f"\nPhase: {phase.phase_name}")
        for act in phase.activities:
            parts.append(f"  Activity: {act}")
        for d in phase.deliverables:
            parts.append(f"  Deliverable: {d}")
        if phase.governance:
            parts.append(f"  Governance: {phase.governance}")
    parts.append(f"Governance framework: {ps.governance_framework}")
    parts.append(f"Timeline: {ps.timeline_logic}")
    parts.append(f"Differentiation: {ps.value_case_and_differentiation}")

    # Section 6: Slide Blueprints
    parts.append("\n=== SECTION 6: SLIDE BLUEPRINTS ===")
    for bp in source_book.slide_blueprints:
        parts.append(
            f"Slide {bp.slide_number} [{bp.section}]: {bp.title} — "
            f"{bp.key_message}"
        )

    return "\n".join(parts)


def _confidence_to_float(label: str) -> float:
    """Convert high/medium/low to numeric."""
    return {"high": 0.9, "medium": 0.6, "low": 0.3}.get(label, 0.5)


async def extract_evidence_ledger(
    source_book: SourceBook,
    model_config: dict[str, Any] | None = None,
) -> list[EvidenceLedgerEntry]:
    """Dedicated LLM-powered evidence ledger extraction.

    Takes the completed Source Book (Sections 1-6), serializes it,
    and makes a dedicated LLM call to audit every claim and produce
    rich ledger entries with real claim text and specific sources.

    Returns a list of EvidenceLedgerEntry objects.
    """
    sb_text = _source_book_to_text(source_book)
    logger.info(
        "Evidence extractor: serialized %d chars from Source Book",
        len(sb_text),
    )

    try:
        import anthropic

        from src.config.settings import get_settings

        settings = get_settings()
        client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=600.0,
        )

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            temperature=0.1,
            system=EVIDENCE_EXTRACTOR_PROMPT,
            messages=[{"role": "user", "content": sb_text}],
        )

        # Extract token usage for session accounting
        _extractor_usage = None
        if hasattr(response, "usage") and response.usage:
            from src.services.llm import _compute_cost
            _ext_in = response.usage.input_tokens
            _ext_out = response.usage.output_tokens
            _ext_cost = _compute_cost("claude-sonnet-4-20250514", _ext_in, _ext_out)
            _extractor_usage = {
                "input_tokens": _ext_in,
                "output_tokens": _ext_out,
                "cost_usd": _ext_cost,
            }

        raw_text = response.content[0].text
        # Parse the JSON array from the response
        # Strip markdown fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            # Remove ```json ... ``` wrapping
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        entries_raw: list[dict] = json.loads(text)
        logger.info(
            "Evidence extractor: LLM returned %d raw entries",
            len(entries_raw),
        )

        entries: list[EvidenceLedgerEntry] = []
        for i, raw in enumerate(entries_raw):
            parsed = _LedgerEntryRaw(raw)
            # Skip generic auto-builder style entries
            if "Auto-extracted" in parsed.claim_text:
                logger.warning(
                    "Evidence extractor: skipping generic entry %d",
                    i,
                )
                continue
            # Map confidence to verifiability_status (Literal field)
            # Engine 1 architecture:
            # - "verified" = NEVER auto-assigned (requires Engine 2 cross-check)
            # - "partially_verified" = has real CLM/EXT evidence ID
            # - "unverified" = external claim without strong backing
            # - "gap" = internal claim without evidence ID — Engine 2 must fill
            has_evidence_id = bool(
                "CLM-" in parsed.source_reference
                or "EXT-" in parsed.source_reference
            )
            is_internal = parsed.source_type == "internal"

            if has_evidence_id:
                verif_map = {
                    "high": "partially_verified",
                    "medium": "partially_verified",
                    "low": "unverified",
                }
            elif is_internal:
                # Internal claims without evidence IDs are GAPS — Engine 2
                # must provide the proof (project records, CVs, certificates)
                verif_map = {
                    "high": "gap",
                    "medium": "gap",
                    "low": "gap",
                }
            else:
                # External claims without specific IDs
                verif_map = {
                    "high": "unverified",
                    "medium": "unverified",
                    "low": "gap",
                }
            verif_status = verif_map.get(
                parsed.confidence_label, "unverified",
            )
            # Classify evidence per the 3-class policy
            if has_evidence_id and "EXT-" in parsed.source_reference:
                evidence_class = "INTERNATIONAL_BENCHMARK"
            elif has_evidence_id and "CLM-" in parsed.source_reference:
                evidence_class = "SG_INTERNAL_PROOF"
            elif is_internal:
                evidence_class = "SG_INTERNAL_PROOF"
            else:
                evidence_class = "INTERNATIONAL_BENCHMARK"

            if verif_status == "gap":
                evidence_class = "EVIDENCE_GAP"

            # Keep source_reference clean; put verification in its own field
            source_ref = parsed.source_reference
            verification_note = f"[{evidence_class}] "
            if parsed.verifiability:
                verification_note = parsed.verifiability[:200]
            entries.append(
                EvidenceLedgerEntry(
                    claim_id=parsed.claim_id or f"CLAIM-{i + 1:03d}",
                    claim_text=parsed.claim_text,
                    source_type=(
                        "internal" if parsed.source_type == "internal"
                        else "external"
                    ),
                    source_reference=source_ref,
                    confidence=_confidence_to_float(
                        parsed.confidence_label,
                    ),
                    verifiability_status=verif_status,
                    verification_note=verification_note,
                )
            )

        # Filter out leaked prompt-example residue
        _LEAKED_PATTERNS = [
            "not explicitly referenced",
            "appears to be example",
            "appears to be instruction",
            "example text",
            "not found in source",
        ]
        filtered = [
            e for e in entries
            if not any(
                p in (e.source_reference or "").lower()
                for p in _LEAKED_PATTERNS
            )
        ]
        removed = len(entries) - len(filtered)
        if removed:
            logger.info(
                "Evidence extractor: removed %d leaked prompt-example "
                "entries, keeping %d",
                removed,
                len(filtered),
            )

        logger.info(
            "Evidence extractor: produced %d valid entries",
            len(filtered),
        )
        return filtered, _extractor_usage

    except json.JSONDecodeError as e:
        logger.error("Evidence extractor: JSON parse failed: %s", e)
        # Preserve usage — the LLM call succeeded even if output was malformed
        return [], _extractor_usage
    except Exception as e:
        logger.error("Evidence extractor: failed: %s", e)
        # Preserve usage if the Anthropic call succeeded before the failure
        try:
            return [], _extractor_usage
        except NameError:
            return [], None
