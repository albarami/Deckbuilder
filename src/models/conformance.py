"""Conformance architecture models — hard requirements + validation reports.

The conformance system extracts structured hard requirements from the RFP
and validates the Source Book against them deterministically. Acceptance
requires BOTH reviewer quality threshold AND zero critical conformance failures.

Architecture:
  RFP → HardRequirement extraction (Layer 1 deterministic + Layer 2 LLM)
  Source Book → ConformanceValidator → ConformanceReport
  Acceptance = conformance_status == "pass" AND reviewer.pass_threshold_met
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import DeckForgeBaseModel


# ── Hard Requirement ────────────────────────────────────────────────────


class HardRequirement(DeckForgeBaseModel):
    """A single extracted obligation from the RFP.

    Represents a verifiable contract condition that the Source Book must
    address. Examples: "minimum 5 priority sectors", "contract duration 12 months",
    "award mechanism is pass/fail then lowest price".

    Two extraction layers:
    - Layer 1 (HR-L1-*): deterministic, from structured RFPContext fields
    - Layer 2 (HR-L2-*): LLM-assisted, from RFP prose text
    """

    requirement_id: str = ""  # HR-L1-001 or HR-L2-001
    category: str = ""  # minimum_count, packaging, guarantee, award_mechanism, etc.
    subject: str = ""  # priority_sectors, workshops_per_sector, activated_services, etc.
    operator: str = ""  # >=, ==, includes, must_include
    value_text: str = ""  # Human-readable: "5", "pass_fail_then_lowest_price"
    value_number: float | None = None  # Normalized numeric (None for non-numeric)
    dimension: Literal[
        "total",  # absolute count (>= 15 activated services)
        "per_sector",  # per-sector (>= 2 workshops per sector)
        "per_phase",  # per-phase (>= 3 deliverables per phase)
        "per_deliverable",  # per-deliverable
        "flat",  # non-numeric (award_mechanism == pass_fail)
    ] = "flat"
    unit: str = ""  # count, percent, months, items
    phase: str = "all"  # all, phase_1, phase_3, etc.
    deliverable_ids: list[str] = Field(default_factory=list)
    source_text: str = ""  # Verbatim from RFP
    source_location: str = ""  # Field path or section reference
    confidence: Literal["high", "medium", "low"] = "high"
    is_explicit: bool = True
    extraction_method: str = ""  # context_field, regex_pattern, llm_structured
    severity: Literal["critical", "major", "minor"] = "major"
    validation_scope: Literal[
        "source_book",  # validated by Engine 1 conformance checker
        "submission_package",  # validated at submission time
        "engine2_proof",  # validated by Engine 2 (firm-specific proof)
    ] = "source_book"


# ── Conformance Failures ────────────────────────────────────────────────


class ConformanceFailure(DeckForgeBaseModel):
    """A single failed conformance check."""

    requirement_id: str = ""
    requirement_text: str = ""  # Human-readable obligation
    failure_reason: str = ""  # What was expected vs found
    severity: Literal["critical", "major", "minor"] = "major"
    source_book_section: str = ""  # Which section should address this
    suggested_fix: str = ""  # Actionable fix for the writer


class MissingInput(DeckForgeBaseModel):
    """A blocked dependency (e.g., annex referenced but not provided).

    blocker_type values:
    - missing_annex: referenced annex/attachment not in uploaded documents
    - missing_context: required context field not extractable from provided text
    - ambiguous_rfp: RFP text is contradictory or unclear on this requirement

    severity and validation_scope are derived from the originating HardRequirement(s).
    Only blocks final acceptance when severity=critical AND validation_scope=source_book.
    """

    input_name: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    blocker_type: Literal[
        "missing_annex",
        "missing_context",
        "ambiguous_rfp",
    ] = "missing_context"
    message: str = ""
    severity: Literal["critical", "major", "minor"] = "major"
    validation_scope: Literal[
        "source_book", "submission_package", "engine2_proof"
    ] = "source_book"


# ── Conformance Report ──────────────────────────────────────────────────


class ConformanceReport(DeckForgeBaseModel):
    """Aggregate conformance validation result.

    conformance_status:
    - "pass": no critical failures, no critical blockers
    - "fail": at least one critical ConformanceFailure
    - "blocked": at least one MissingInput with severity=critical AND
                 validation_scope=source_book

    final_acceptance_decision:
    - "accept": conformance pass + reviewer threshold met
    - "reject": conformance fail OR reviewer threshold not met
    - "blocked_missing_input": conformance blocked by missing annex/input
    """

    missing_required_commitments: list[ConformanceFailure] = Field(
        default_factory=list
    )
    forbidden_claims: list[ConformanceFailure] = Field(default_factory=list)
    structural_mismatches: list[ConformanceFailure] = Field(default_factory=list)
    missing_inputs: list[MissingInput] = Field(default_factory=list)
    conformance_status: Literal["pass", "fail", "blocked"] = "pass"
    final_acceptance_decision: Literal[
        "accept", "reject", "blocked_missing_input"
    ] = "accept"
    hard_requirements_checked: int = 0
    hard_requirements_passed: int = 0
    hard_requirements_failed: int = 0


# ── Hard Requirements Summary (compact for writer context) ──────────────


class HardRequirementSummaryItem(DeckForgeBaseModel):
    """One-line summary of a hard requirement for writer context injection."""

    id: str = ""
    obligation: str = ""  # "priority_sectors >= 5 (count)"
    severity: str = ""  # "critical" | "major" | "minor"
    phase: str = "all"


class HardRequirementsSummary(DeckForgeBaseModel):
    """Compact representation for writer context. NEVER truncated.

    ~60 bytes per item × 30 items = ~1800 bytes = ~450 tokens.
    """

    requirements: list[HardRequirementSummaryItem] = Field(default_factory=list)
    total_count: int = 0
    critical_count: int = 0
