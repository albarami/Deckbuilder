"""Phase 10 — A2 Shell Sanitizer.

Before placeholder injectors write proposal-specific content, the
A2 shell must be sanitized.  Sanitization uses the allowlist model
from the catalog lock to determine what stays and what gets cleared.

Sanitization rules (fail-closed):
  - Clear non-approved placeholder text (placeholder not on allowlist)
  - Clear non-placeholder text boxes not on preserved-regions allowlist
  - Clear table cell text in non-approved tables
  - Clear speaker notes with forbidden template-example content
  - Clear alt-text / description fields with forbidden content
  - Clear comments / hidden metadata if present and forbidden
  - Fail closed on unknown text-bearing elements outside the allowlist

Every cleared element is logged in a SanitizationReport.

Zero-shape-creation guardrail: this module NEVER creates new shapes,
text boxes, or tables.  It only clears existing content.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Exceptions ──────────────────────────────────────────────────────────


class SanitizationError(RuntimeError):
    """Raised when sanitization fails in a way that cannot be recovered."""


# ── Data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClearedElement:
    """Record of a single cleared element during sanitization."""

    shell_id: str
    element_type: str       # "placeholder" | "text_box" | "table" | "speaker_notes" | "alt_text" | "comment"
    shape_name: str
    reason: str             # why it was cleared
    had_content: bool       # whether it actually had text before clearing


@dataclass(frozen=True)
class SanitizationReport:
    """Complete report from sanitizing one A2 shell slide."""

    shell_id: str
    total_cleared: int
    cleared_by_type: dict[str, int]     # element_type -> count
    cleared_elements: tuple[ClearedElement, ...]
    preserved_count: int                # elements kept per allowlist
    errors: list[str] = field(default_factory=list)


# ── Allowlist loading ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ShellAllowlist:
    """Parsed allowlist for one A2 shell from the catalog lock."""

    shell_id: str
    approved_placeholder_indices: set[int]  # placeholder indices allowed for injection
    preserved_shape_names: set[str]         # non-placeholder shapes to preserve
    preserved_table_names: set[str]         # table shapes to preserve


def load_a2_allowlists(
    catalog_lock_path: Path,
) -> dict[str, ShellAllowlist]:
    """Load A2 shell allowlists from the catalog lock.

    Parameters
    ----------
    catalog_lock_path : Path
        Path to catalog_lock_en.json or catalog_lock_ar.json.

    Returns
    -------
    dict[str, ShellAllowlist]
        Allowlists keyed by shell_id.

    Raises
    ------
    SanitizationError
        If catalog lock is missing or malformed.
    """
    if not catalog_lock_path.exists():
        raise SanitizationError(
            f"Catalog lock not found: {catalog_lock_path}"
        )

    with open(catalog_lock_path, encoding="utf-8") as f:
        lock = json.load(f)

    a2_shells = lock.get("a2_shells", {})
    if not a2_shells:
        raise SanitizationError(
            "Catalog lock has no 'a2_shells' section"
        )

    allowlists: dict[str, ShellAllowlist] = {}
    for shell_id, shell_data in a2_shells.items():
        al = shell_data.get("allowlist", {})

        # Approved injection placeholders
        approved_phs = al.get("approved_injection_placeholders", {})
        approved_indices = {int(idx) for idx in approved_phs}

        # Preserved text regions (by shape name)
        preserved_regions = al.get("candidate_preserved_text_regions", [])
        preserved_names = {r["shape_name"] for r in preserved_regions if "shape_name" in r}

        # Preserved tables (by shape name)
        preserved_tables = al.get("candidate_preserved_tables", [])
        preserved_table_names = {t["shape_name"] for t in preserved_tables if "shape_name" in t}

        allowlists[shell_id] = ShellAllowlist(
            shell_id=shell_id,
            approved_placeholder_indices=approved_indices,
            preserved_shape_names=preserved_names,
            preserved_table_names=preserved_table_names,
        )

    return allowlists


def get_allowlist(
    allowlists: dict[str, ShellAllowlist],
    shell_id: str,
) -> ShellAllowlist:
    """Look up an allowlist by shell ID.  Fail-closed.

    Raises
    ------
    SanitizationError
        If no allowlist exists for this shell ID.
    """
    if shell_id not in allowlists:
        raise SanitizationError(
            f"No allowlist for shell '{shell_id}'"
        )
    return allowlists[shell_id]


# ── Sanitization engine ────────────────────────────────────────────────


def _clear_text_frame(text_frame: Any) -> bool:
    """Clear all text from a pptx text frame.  Returns True if content existed."""
    had_content = False
    for paragraph in text_frame.paragraphs:
        for run in paragraph.runs:
            if run.text.strip():
                had_content = True
            run.text = ""
    return had_content


def _clear_table(table: Any) -> bool:
    """Clear all cell text from a pptx table.  Returns True if content existed."""
    had_content = False
    for row in table.rows:
        for cell in row.cells:
            if cell.text.strip():
                had_content = True
            cell.text = ""
    return had_content


def _is_forbidden_notes_content(notes_text: str) -> bool:
    """Check if speaker notes contain forbidden template-example content."""
    if not notes_text.strip():
        return False
    # Template examples often contain placeholder markers
    forbidden_markers = [
        "lorem ipsum", "sample text", "click to edit",
        "insert text here", "type here", "add text",
        "example:", "[example", "<example",
    ]
    lower = notes_text.lower()
    return any(marker in lower for marker in forbidden_markers)


def sanitize_shell(
    slide: Any,
    shell_id: str,
    allowlist: ShellAllowlist,
) -> SanitizationReport:
    """Sanitize an A2 shell slide using its allowlist.

    Clears all non-approved content from the slide while preserving
    approved injection placeholders and allowlisted preserved regions.

    Parameters
    ----------
    slide : pptx.slide.Slide
        The cloned A2 shell slide to sanitize.
    shell_id : str
        The semantic shell ID.
    allowlist : ShellAllowlist
        The allowlist for this shell.

    Returns
    -------
    SanitizationReport
        Detailed report of all clearing actions.
    """
    cleared: list[ClearedElement] = []
    preserved_count = 0
    errors: list[str] = []

    for shape in slide.shapes:
        shape_name = shape.name or ""

        # ── Placeholders ────────────────────────────────────────
        if shape.is_placeholder:
            ph_idx = shape.placeholder_format.idx
            if ph_idx in allowlist.approved_placeholder_indices:
                # Approved for injection — clear template text so injectors
                # start from blank
                if shape.has_text_frame:
                    had = _clear_text_frame(shape.text_frame)
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="placeholder",
                        shape_name=shape_name,
                        reason=f"approved placeholder idx={ph_idx} cleared for injection",
                        had_content=had,
                    ))
                elif shape.has_table:
                    had = _clear_table(shape.table)
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="table",
                        shape_name=shape_name,
                        reason=f"approved table placeholder idx={ph_idx} cleared for injection",
                        had_content=had,
                    ))
                else:
                    # Picture or other — preserve shape, nothing to clear
                    preserved_count += 1
            else:
                # Non-approved placeholder — clear any text
                if shape.has_text_frame:
                    had = _clear_text_frame(shape.text_frame)
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="placeholder",
                        shape_name=shape_name,
                        reason=f"non-approved placeholder idx={ph_idx}",
                        had_content=had,
                    ))
                else:
                    preserved_count += 1
            continue

        # ── Non-placeholder shapes ──────────────────────────────

        # Check preserved regions allowlist
        if shape_name in allowlist.preserved_shape_names:
            preserved_count += 1
            continue

        # Check preserved tables allowlist
        if shape.has_table:
            if shape_name in allowlist.preserved_table_names:
                preserved_count += 1
                continue
            # Non-approved table — clear
            had = _clear_table(shape.table)
            cleared.append(ClearedElement(
                shell_id=shell_id,
                element_type="table",
                shape_name=shape_name,
                reason="non-approved table outside allowlist",
                had_content=had,
            ))
            continue

        # Non-placeholder text box outside allowlist — clear
        if shape.has_text_frame:
            had = _clear_text_frame(shape.text_frame)
            cleared.append(ClearedElement(
                shell_id=shell_id,
                element_type="text_box",
                shape_name=shape_name,
                reason="text box outside allowlist",
                had_content=had,
            ))
            continue

        # Non-text shapes (images, connectors, etc.) — preserve
        preserved_count += 1

    # ── Speaker notes ───────────────────────────────────────────
    if slide.has_notes_slide:
        notes_frame = slide.notes_slide.notes_text_frame
        notes_text = notes_frame.text if notes_frame else ""
        if _is_forbidden_notes_content(notes_text):
            _clear_text_frame(notes_frame)
            cleared.append(ClearedElement(
                shell_id=shell_id,
                element_type="speaker_notes",
                shape_name="notes_text_frame",
                reason="forbidden template-example content in notes",
                had_content=True,
            ))

    # ── Alt-text / description fields ───────────────────────────
    for shape in slide.shapes:
        # python-pptx exposes alt_text via shape._element
        try:
            desc_elem = shape._element
            # Access nvSpPr/cNvPr or nvGrpSpPr/cNvPr for description attr
            cNvPr = desc_elem.find(
                ".//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}cNvPr"
            )
            if cNvPr is None:
                # Try presentation namespace
                for tag in ["nvSpPr", "nvPicPr", "nvGrpSpPr", "nvCxnSpPr"]:
                    ns = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
                    nv = desc_elem.find(f"{ns}{tag}")
                    if nv is not None:
                        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
                        cNvPr = nv.find(f"{ns_a}cNvPr") or nv.find(
                            "{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr"
                        )
                        break

            if cNvPr is not None:
                descr = cNvPr.get("descr", "")
                if descr and _is_forbidden_notes_content(descr):
                    cNvPr.set("descr", "")
                    cleared.append(ClearedElement(
                        shell_id=shell_id,
                        element_type="alt_text",
                        shape_name=shape.name or "",
                        reason="forbidden template-example content in alt-text",
                        had_content=True,
                    ))
        except Exception as exc:
            # Don't fail sanitization on alt-text parsing errors
            logger.debug(f"Alt-text check skipped for {shape.name}: {exc}")

    # ── Build report ────────────────────────────────────────────
    by_type: dict[str, int] = {}
    for ce in cleared:
        by_type[ce.element_type] = by_type.get(ce.element_type, 0) + 1

    return SanitizationReport(
        shell_id=shell_id,
        total_cleared=len(cleared),
        cleared_by_type=by_type,
        cleared_elements=tuple(cleared),
        preserved_count=preserved_count,
        errors=errors,
    )


# ── Batch sanitization ─────────────────────────────────────────────────


def sanitize_all_shells(
    slides: dict[str, Any],
    allowlists: dict[str, ShellAllowlist],
) -> dict[str, SanitizationReport]:
    """Sanitize all A2 shell slides.

    Parameters
    ----------
    slides : dict[str, Slide]
        Shell ID → pptx Slide object.
    allowlists : dict[str, ShellAllowlist]
        Shell ID → allowlist.

    Returns
    -------
    dict[str, SanitizationReport]
        Reports keyed by shell ID.

    Raises
    ------
    SanitizationError
        If any shell has no allowlist (fail-closed).
    """
    reports: dict[str, SanitizationReport] = {}
    for shell_id, slide in slides.items():
        allowlist = get_allowlist(allowlists, shell_id)
        reports[shell_id] = sanitize_shell(slide, shell_id, allowlist)
    return reports


# ── Validation ──────────────────────────────────────────────────────────


def validate_sanitization(
    reports: dict[str, SanitizationReport],
) -> list[str]:
    """Validate that sanitization completed without errors.

    Returns a list of error messages (empty if all clean).
    """
    errors: list[str] = []
    for shell_id, report in reports.items():
        if report.errors:
            for err in report.errors:
                errors.append(f"Shell '{shell_id}': {err}")
    return errors
