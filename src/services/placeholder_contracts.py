"""Phase 9 — Placeholder Contract Validation.

Before any injector writes content, the target layout is validated
against a contract.  Each contract specifies required and optional
placeholders by index, keyed by **semantic layout ID** (never raw
display names).

On contract violation:
- Fail closed for that slide
- Log exact missing/mismatched placeholder indices
- Produce PlaceholderContractViolation in render result
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Exceptions ──────────────────────────────────────────────────────────


class ContractViolationError(RuntimeError):
    """Raised when a placeholder contract is violated."""


# ── Data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PlaceholderContractViolation:
    """A single contract violation for one slide."""

    semantic_layout_id: str
    violation_type: str       # "missing_required" | "wrong_type" | "unknown_layout"
    detail: str               # human-readable description
    placeholder_idx: int | None = None


@dataclass(frozen=True)
class PlaceholderContract:
    """Contract for a single layout's placeholder structure.

    Keyed by semantic layout ID.  Required placeholders must be present
    for the layout to be valid.  Optional placeholders may be missing
    without error.

    Table requirements specify (min_rows, min_cols) for table placeholders.
    """

    semantic_layout_id: str
    required_placeholders: dict[int, str]       # idx -> expected type (TITLE, BODY, etc.)
    optional_placeholders: dict[int, str] = field(default_factory=dict)
    table_requirements: dict[int, tuple[int, int]] | None = None  # idx -> (min_rows, min_cols)


@dataclass(frozen=True)
class ContractValidationResult:
    """Result of validating a slide against its contract."""

    semantic_layout_id: str
    is_valid: bool
    violations: tuple[PlaceholderContractViolation, ...] = ()


# ── Contract registry ───────────────────────────────────────────────────


def build_contracts_from_catalog_lock(
    catalog_lock_path: Path,
) -> dict[str, PlaceholderContract]:
    """Build placeholder contracts from a catalog lock file.

    Each layout in the catalog lock becomes a contract where all
    placeholders listed are required.

    Parameters
    ----------
    catalog_lock_path : Path
        Path to catalog_lock_en.json or catalog_lock_ar.json.

    Returns
    -------
    dict[str, PlaceholderContract]
        Contracts keyed by semantic layout ID.

    Raises
    ------
    ContractViolationError
        If catalog lock is missing or malformed.
    """
    if not catalog_lock_path.exists():
        raise ContractViolationError(
            f"Catalog lock not found: {catalog_lock_path}"
        )

    with open(catalog_lock_path, encoding="utf-8") as f:
        lock = json.load(f)

    layouts = lock.get("layouts", {})
    if not layouts:
        raise ContractViolationError(
            "Catalog lock has no 'layouts' section"
        )

    contracts: dict[str, PlaceholderContract] = {}
    for semantic_id, layout_data in layouts.items():
        placeholders = layout_data.get("placeholders", {})
        required: dict[int, str] = {}
        for idx_str, ph_type in placeholders.items():
            required[int(idx_str)] = ph_type

        contracts[semantic_id] = PlaceholderContract(
            semantic_layout_id=semantic_id,
            required_placeholders=required,
        )

    return contracts


def get_contract(
    contracts: dict[str, PlaceholderContract],
    semantic_layout_id: str,
) -> PlaceholderContract:
    """Look up a contract by semantic layout ID.  Fail-closed.

    Raises
    ------
    ContractViolationError
        If no contract exists for this layout ID.
    """
    if semantic_layout_id not in contracts:
        raise ContractViolationError(
            f"No placeholder contract for layout '{semantic_layout_id}'"
        )
    return contracts[semantic_layout_id]


# ── Validation ──────────────────────────────────────────────────────────


def validate_placeholders(
    contract: PlaceholderContract,
    actual_placeholders: dict[int, str],
) -> ContractValidationResult:
    """Validate actual placeholders against a contract.

    Parameters
    ----------
    contract : PlaceholderContract
        The expected contract for this layout.
    actual_placeholders : dict[int, str]
        Actual placeholder indices and types found on the slide.
        Keys are placeholder indices, values are type strings
        (TITLE, BODY, TABLE, PICTURE, OBJECT, etc.).

    Returns
    -------
    ContractValidationResult
        Validation result with any violations.
    """
    violations: list[PlaceholderContractViolation] = []

    # Check required placeholders
    for idx, expected_type in contract.required_placeholders.items():
        if idx not in actual_placeholders:
            violations.append(PlaceholderContractViolation(
                semantic_layout_id=contract.semantic_layout_id,
                violation_type="missing_required",
                detail=(
                    f"Required placeholder idx={idx} ({expected_type}) "
                    f"missing from slide"
                ),
                placeholder_idx=idx,
            ))
        elif actual_placeholders[idx] != expected_type:
            violations.append(PlaceholderContractViolation(
                semantic_layout_id=contract.semantic_layout_id,
                violation_type="wrong_type",
                detail=(
                    f"Placeholder idx={idx} expected type '{expected_type}', "
                    f"got '{actual_placeholders[idx]}'"
                ),
                placeholder_idx=idx,
            ))

    # Check table requirements
    # (Table size validation is deferred to render time when actual
    # table dimensions are known.  The contract records expectations.)

    return ContractValidationResult(
        semantic_layout_id=contract.semantic_layout_id,
        is_valid=len(violations) == 0,
        violations=tuple(violations),
    )


def validate_slide_against_catalog(
    semantic_layout_id: str,
    actual_placeholders: dict[int, str],
    contracts: dict[str, PlaceholderContract],
) -> ContractValidationResult:
    """Validate a slide's placeholders against the catalog lock contract.

    Convenience function that combines lookup + validation.

    Parameters
    ----------
    semantic_layout_id : str
        The layout's semantic ID.
    actual_placeholders : dict[int, str]
        Actual placeholders found on the slide.
    contracts : dict[str, PlaceholderContract]
        All loaded contracts.

    Returns
    -------
    ContractValidationResult
        Result with violations if any.
    """
    if semantic_layout_id not in contracts:
        violation = PlaceholderContractViolation(
            semantic_layout_id=semantic_layout_id,
            violation_type="unknown_layout",
            detail=f"No contract for layout '{semantic_layout_id}'",
        )
        return ContractValidationResult(
            semantic_layout_id=semantic_layout_id,
            is_valid=False,
            violations=(violation,),
        )

    contract = contracts[semantic_layout_id]
    return validate_placeholders(contract, actual_placeholders)
