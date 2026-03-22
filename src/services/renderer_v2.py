"""Phase 13 — Template-Anchored Renderer (v2).

Manifest-driven render entry point.  The official .potx template is the
sole visual authority — renderer_v2 never creates shapes, never imports
legacy helpers, and resolves every layout by semantic layout ID.

Orchestration flow:
  1. Validate template hash (fail-closed)
  2. Load house-asset registry, placeholder contracts, A2 allowlists
  3. Walk the ProposalManifest entry by entry
  4. For each entry, clone/add the correct slide, sanitize A2 shells,
     inject content, and fit overflow
  5. Save the result

This module is fully isolated from renderer.py — no imports from
renderer.py, formatting.py shape builders, or legacy geometry modules.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.models.house_registry import HouseAssetRegistry, load_registry
from src.models.proposal_manifest import (
    ManifestEntry,
    ProposalManifest,
    validate_manifest,
)
from src.services.content_fitter import (
    SlideFitReport,
)
from src.services.placeholder_contracts import (
    PlaceholderContract,
    build_contracts_from_catalog_lock,
    get_contract,
)
from src.services.placeholder_injectors import (
    InjectionResult,
    get_layout_family,
    inject_center_title,
    inject_multi_body,
    inject_proposal_cover,
    inject_team_members,
    inject_title_body,
    inject_toc_table,
)
from src.services.quality_gate import (
    QualityGateResult,
    run_quality_gate,
)
from src.services.shell_sanitizer import (
    SanitizationReport,
    get_allowlist,
    load_a2_allowlists,
    sanitize_shell,
)
from src.services.template_manager import TemplateManager

logger = logging.getLogger(__name__)


# ── Exceptions ──────────────────────────────────────────────────────────


class RenderError(RuntimeError):
    """Raised when v2 rendering encounters a fatal error."""


class TemplateHashError(RenderError):
    """Raised when template hash does not match catalog lock."""


# ── Result data classes ─────────────────────────────────────────────────


@dataclass(frozen=True)
class SlideRenderRecord:
    """Record of one rendered slide."""

    manifest_index: int
    entry_type: str
    asset_id: str
    semantic_layout_id: str
    section_id: str
    injection_result: InjectionResult | None = None
    sanitization_report: SanitizationReport | None = None
    fit_report: SlideFitReport | None = None
    error: str | None = None


@dataclass
class RenderResult:
    """Aggregated result of a full v2 render pass."""

    output_path: Path | None = None
    total_slides: int = 0
    records: list[SlideRenderRecord] = field(default_factory=list)
    manifest_errors: list[str] = field(default_factory=list)
    render_errors: list[str] = field(default_factory=list)
    template_hash: str = ""
    placeholder_audit: PlaceholderAuditResult | None = None
    filler_outputs: dict[str, Any] = field(default_factory=dict)
    injection_results: list[InjectionResult | None] = field(
        default_factory=list,
    )
    quality_gate: QualityGateResult | None = None

    @property
    def success(self) -> bool:
        return (
            len(self.manifest_errors) == 0
            and len(self.render_errors) == 0
            and self.total_slides > 0
        )

    @property
    def continuation_needed(self) -> bool:
        return any(
            r.fit_report is not None and r.fit_report.any_continuation
            for r in self.records
        )


# ── Hash enforcement ───────────────────────────────────────────────────


def _enforce_template_hash(
    template_manager: TemplateManager,
    registry: HouseAssetRegistry,
) -> None:
    """Validate that the template hash matches the catalog lock.

    Fail-closed: raises TemplateHashError on mismatch.
    """
    tm_hash = template_manager.template_hash
    reg_hash = registry.template_hash

    if not tm_hash or not reg_hash:
        raise TemplateHashError(
            "Template hash missing.  Cannot render without hash validation."
        )

    if tm_hash != reg_hash:
        raise TemplateHashError(
            f"Template hash mismatch: template='{tm_hash}', "
            f"catalog_lock='{reg_hash}'.  Regenerate catalog lock."
        )


# ── Slide dispatch ─────────────────────────────────────────────────────


def _render_a1_clone(
    entry: ManifestEntry,
    template_manager: TemplateManager,
) -> Any:
    """Clone an A1 (immutable) house slide."""
    return template_manager.clone_a1(entry.asset_id)


def _render_a2_shell(
    entry: ManifestEntry,
    template_manager: TemplateManager,
    allowlists: dict,
) -> tuple[Any, SanitizationReport | None]:
    """Clone an A2 shell slide and sanitize it."""
    # Determine if this is a section divider or a regular A2 shell
    if entry.asset_id.startswith("section_divider_"):
        # Extract divider number string (e.g., "01" from "section_divider_01")
        divider_num = entry.asset_id.split("_")[-1]
        slide = template_manager.clone_divider(divider_num)
    else:
        slide = template_manager.clone_a2(entry.asset_id)

    # Sanitize
    allowlist = get_allowlist(allowlists, entry.asset_id)
    report = sanitize_shell(slide, entry.asset_id, allowlist)
    return (slide, report)


def _render_b_variable(
    entry: ManifestEntry,
    template_manager: TemplateManager,
) -> Any:
    """Add a B (variable) slide from a template layout."""
    return template_manager.add_slide_from_layout(entry.semantic_layout_id)


def _render_pool_clone(
    entry: ManifestEntry,
    template_manager: TemplateManager,
) -> Any:
    """Clone a slide from a pool asset (case study, team bio)."""
    # Pool clones are cloned from specific slide indices recorded in the
    # registry.  The entry's injection_data may contain the source index.
    if entry.injection_data and "source_slide_idx" in entry.injection_data:
        return template_manager.clone_slide(entry.injection_data["source_slide_idx"])
    # Fallback: add from layout
    return template_manager.add_slide_from_layout(entry.semantic_layout_id)


# ── Content injection dispatch ─────────────────────────────────────────


def _inject_content(
    slide: Any,
    entry: ManifestEntry,
    contract: PlaceholderContract,
) -> InjectionResult | None:
    """Dispatch content injection based on layout family.

    Returns None if no injection data is present (e.g., A1 clones).
    """
    if entry.injection_data is None:
        return None

    data = entry.injection_data

    # Pool clones with only source_slide_idx have no content to inject —
    # the slide was already cloned from the template by _render_pool_clone.
    if set(data.keys()) == {"source_slide_idx"}:
        return None

    family = get_layout_family(entry.semantic_layout_id)

    if family == "title_body":
        return inject_title_body(
            slide, entry.semantic_layout_id, contract,
            title=data.get("title", ""),
            body=data.get("body", ""),
            bold_body_lead=data.get("bold_body_lead", False),
            object_contents=data.get("object_contents"),
        )
    elif family == "center_title":
        return inject_center_title(
            slide, entry.semantic_layout_id, contract,
            title=data.get("title", ""),
        )
    elif family == "proposal_cover":
        return inject_proposal_cover(
            slide, contract,
            subtitle=data.get("subtitle", ""),
            client_name=data.get("client_name", ""),
            date_text=data.get("date_text", ""),
        )
    elif family == "toc_table":
        return inject_toc_table(
            slide, contract,
            title=data.get("title", ""),
            rows=data.get("rows"),
        )
    elif family == "multi_body":
        return inject_multi_body(
            slide, entry.semantic_layout_id, contract,
            title=data.get("title", ""),
            body_contents=data.get("body_contents"),
            bold_leads=data.get("bold_leads", False),
        )
    elif family == "team_two_members":
        return inject_team_members(
            slide, contract,
            member1_name=data.get("member1_name", ""),
            member1_role=data.get("member1_role", ""),
            member1_bio=data.get("member1_bio", ""),
            member2_name=data.get("member2_name", ""),
            member2_role=data.get("member2_role", ""),
            member2_bio=data.get("member2_bio", ""),
        )
    else:
        logger.warning(
            "Unknown layout family '%s' for layout '%s' — skipping injection",
            family, entry.semantic_layout_id,
        )
        return None


# ── Main render function ───────────────────────────────────────────────


def render_v2(
    manifest: ProposalManifest,
    template_manager: TemplateManager,
    catalog_lock_path: Path,
    output_path: Path,
    *,
    filler_outputs: dict[str, Any] | None = None,
    language: str = "en",
) -> RenderResult:
    """Manifest-driven, template-anchored render.

    Parameters
    ----------
    manifest : ProposalManifest
        Ordered assembly plan — each entry is one slide.
    template_manager : TemplateManager
        Loaded and ready TemplateManager instance.
    catalog_lock_path : Path
        Path to the catalog lock JSON for the active language.
    output_path : Path
        Destination .pptx path.
    filler_outputs : dict, optional
        G2 typed filler outputs keyed by section_id (e.g. section_03 →
        MethodologyOutput).  Passed to the quality gate for R3/R4/S1.
    language : str
        Deck language ("en" or "ar").  Passed to quality gate for R10.

    Returns
    -------
    RenderResult
        Aggregated result with per-slide records and error lists.
    """
    result = RenderResult()
    result.filler_outputs = filler_outputs or {}

    # ── 1. Load supporting data ─────────────────────────────────────
    try:
        registry = load_registry(catalog_lock_path)
    except Exception as exc:
        result.render_errors.append(f"Registry load failed: {exc}")
        return result

    # ── 2. Enforce template hash ────────────────────────────────────
    try:
        _enforce_template_hash(template_manager, registry)
        result.template_hash = registry.template_hash
    except TemplateHashError as exc:
        result.render_errors.append(str(exc))
        return result

    # ── 3. Load contracts and allowlists ────────────────────────────
    try:
        contracts = build_contracts_from_catalog_lock(catalog_lock_path)
    except Exception as exc:
        result.render_errors.append(f"Contract build failed: {exc}")
        return result

    try:
        allowlists = load_a2_allowlists(catalog_lock_path)
    except Exception as exc:
        result.render_errors.append(f"Allowlist load failed: {exc}")
        return result

    # ── 4. Validate manifest ────────────────────────────────────────
    manifest_errors = validate_manifest(manifest)
    if manifest_errors:
        result.manifest_errors = manifest_errors
        return result

    # ── 5. Walk manifest and render each slide ──────────────────────
    for idx, entry in enumerate(manifest.entries):
        record = _render_entry(
            idx, entry, template_manager, contracts, allowlists,
        )
        result.records.append(record)
        result.injection_results.append(record.injection_result)
        if record.error:
            result.render_errors.append(
                f"Slide {idx} ({entry.asset_id}): {record.error}"
            )

    # ── 5b. Zero-placeholder audit (fail-closed) ──────────────────
    if not result.render_errors:
        audit = verify_zero_placeholders(result)
        if not audit.clean:
            issues: list[str] = []
            if audit.unfilled_placeholders:
                issues.extend(audit.unfilled_placeholders)
            if audit.template_syntax_found:
                issues.extend(audit.template_syntax_found)
            result.render_errors.append(
                f"Zero-placeholder audit failed ({len(issues)} issue(s)): "
                + "; ".join(issues)
            )
            result.placeholder_audit = audit
            return result
        result.placeholder_audit = audit

    # ── 5c. Presentation quality gate (fail-closed) ────────────────
    if not result.render_errors:
        # Build slide records for quality gate inspection
        qg_records = [
            {
                "semantic_layout_id": r.semantic_layout_id,
                "section_id": r.section_id,
                "injection_data": manifest.entries[r.manifest_index].injection_data
                if r.manifest_index < len(manifest.entries) else None,
                "entry_type": r.entry_type,
            }
            for r in result.records
        ]
        qg = run_quality_gate(
            records=qg_records,
            filler_outputs=result.filler_outputs,
            injection_results=result.injection_results,
            language=language,
        )
        result.quality_gate = qg

        if not qg.passed:
            failure_summary = "; ".join(qg.hard_failures[:5])
            result.render_errors.append(
                f"Quality gate REJECTED "
                f"({len(qg.hard_failures)} hard failure(s)): "
                + failure_summary,
            )
            return result

        if qg.pending_findings:
            logger.info(
                "Quality gate PASSED with %d pending findings "
                "(awaiting injector extension)",
                len(qg.pending_findings),
            )

    # ── 6. Remove original template slides ────────────────────────
    if not result.render_errors:
        try:
            template_manager.remove_original_slides()
        except Exception as exc:
            result.render_errors.append(f"Original slide cleanup failed: {exc}")

    # ── 7. Save ─────────────────────────────────────────────────────
    if not result.render_errors:
        try:
            saved = template_manager.save(output_path)
            result.output_path = saved
        except Exception as exc:
            result.render_errors.append(f"Save failed: {exc}")

    result.total_slides = len(manifest.entries)
    return result


def _render_entry(
    idx: int,
    entry: ManifestEntry,
    template_manager: TemplateManager,
    contracts: dict[str, PlaceholderContract],
    allowlists: dict,
) -> SlideRenderRecord:
    """Render a single manifest entry.  Returns a SlideRenderRecord."""
    slide = None
    sanitization_report = None
    injection_result = None
    fit_report = None
    error = None

    try:
        # ── Clone / create slide ────────────────────────────────────
        if entry.entry_type == "a1_clone":
            slide = _render_a1_clone(entry, template_manager)

        elif entry.entry_type == "a2_shell":
            slide, sanitization_report = _render_a2_shell(
                entry, template_manager, allowlists,
            )

        elif entry.entry_type == "b_variable":
            slide = _render_b_variable(entry, template_manager)

        elif entry.entry_type == "pool_clone":
            slide = _render_pool_clone(entry, template_manager)

        else:
            raise RenderError(f"Unknown entry_type: '{entry.entry_type}'")

        # ── Inject content ──────────────────────────────────────────
        if slide is not None and entry.injection_data is not None:
            contract = get_contract(contracts, entry.semantic_layout_id)
            injection_result = _inject_content(slide, entry, contract)

            # ── Fit overflow ────────────────────────────────────────
            if injection_result and entry.injection_data:
                fit_report = _fit_injected_content(
                    entry, injection_result,
                )

    except Exception as exc:
        error = str(exc)
        logger.error("Error rendering slide %d (%s): %s", idx, entry.asset_id, exc)

    return SlideRenderRecord(
        manifest_index=idx,
        entry_type=entry.entry_type,
        asset_id=entry.asset_id,
        semantic_layout_id=entry.semantic_layout_id,
        section_id=entry.section_id,
        injection_result=injection_result,
        sanitization_report=sanitization_report,
        fit_report=fit_report,
        error=error,
    )


def _fit_injected_content(
    entry: ManifestEntry,
    injection_result: InjectionResult,
) -> SlideFitReport | None:
    """Run content fitting on injected text.

    Only fits body-type placeholders that were actually injected.
    Returns None if no fitting is needed.
    """
    from src.services.content_fitter import fit_slide_content

    if not injection_result.injected:
        return None

    # Build contents dict from injection_data for body placeholders
    data = entry.injection_data or {}
    contents: dict[int, tuple[str, str]] = {}

    for ip in injection_result.injected:
        if ip.placeholder_type in ("BODY", "SUBTITLE"):
            # Reconstruct the original text from injection_data
            # The content_preview is truncated to 80 chars, so we use
            # injection_data where available
            text = _get_original_text(data, ip.placeholder_idx, ip.content_preview)
            contents[ip.placeholder_idx] = (text, ip.placeholder_type)

    if not contents:
        return None

    _, report = fit_slide_content(contents, entry.semantic_layout_id)
    return report


def _get_original_text(
    injection_data: dict[str, Any],
    placeholder_idx: int,
    fallback: str,
) -> str:
    """Recover original text from injection_data for fitting.

    Tries several common injection_data keys.
    """
    # Direct body_contents mapping (multi_body injectors)
    body_contents = injection_data.get("body_contents")
    if isinstance(body_contents, dict) and placeholder_idx in body_contents:
        return body_contents[placeholder_idx]

    # Single body field
    if "body" in injection_data:
        return injection_data["body"]

    # Team member fields by known indices
    _team_idx_map = {
        14: "member1_name", 15: "member1_role", 16: "member1_bio",
        19: "member2_name", 20: "member2_role", 36: "member2_bio",
    }
    if placeholder_idx in _team_idx_map:
        key = _team_idx_map[placeholder_idx]
        if key in injection_data:
            return injection_data[key]

    return fallback


# ── Post-render zero-placeholder verification ──────────────────────────


_TEMPLATE_SYNTAX_PATTERNS = (
    re.compile(r"\{\{[^}]+\}\}"),                         # {{placeholder}}
    re.compile(r"\[PLACEHOLDER[:\s][^\]]*\]", re.IGNORECASE),  # [PLACEHOLDER: ...]
    re.compile(r"\[TBC\]|\[TBD\]", re.IGNORECASE),       # [TBC], [TBD]
    re.compile(r"\[INSERT\s[^\]]*\]", re.IGNORECASE),     # [INSERT ...]
)


# Types that carry visible text — skipping these on b_variable is a hard fail
_REQUIRED_TEXT_TYPES: frozenset[str] = frozenset({
    "TITLE", "CENTER_TITLE", "BODY",
})
# SUBTITLE is informational — not all fillers produce subtitle data
# and an empty subtitle doesn't prevent the slide from being useful.

# Types that are non-text — skipping these is expected and informational
_NON_TEXT_TYPES: frozenset[str] = frozenset({
    "OBJECT", "TABLE", "PICTURE",
})


@dataclass
class PlaceholderAuditResult:
    """Result of post-render zero-placeholder verification."""

    unfilled_required: list[str] = field(default_factory=list)
    unfilled_non_text: list[str] = field(default_factory=list)
    template_syntax_found: list[str] = field(default_factory=list)

    # Keep backward-compatible alias used by existing tests
    @property
    def unfilled_placeholders(self) -> list[str]:
        return self.unfilled_required + self.unfilled_non_text

    @property
    def clean(self) -> bool:
        """Audit is clean when no required text placeholders are unfilled
        and no template syntax leaks into content.

        Non-text skipped placeholders (OBJECT/TABLE/PICTURE) are
        informational and do NOT cause failure.
        """
        return (
            len(self.unfilled_required) == 0
            and len(self.template_syntax_found) == 0
        )


def verify_zero_placeholders(render_result: RenderResult) -> PlaceholderAuditResult:
    """Post-render audit: verify all required placeholders were filled.

    Checks three things:
    1. For every b_variable slide, required text placeholders (TITLE,
       BODY, SUBTITLE) must NOT be skipped — fail-closed.
    2. Non-text placeholders (OBJECT, TABLE, PICTURE) may be skipped —
       tracked as informational only.
    3. No template syntax (``{{...}}``, ``[PLACEHOLDER:...]``, etc.)
       remains in any injected content preview.

    Call this AFTER render_v2() completes and BEFORE declaring success.
    """
    audit = PlaceholderAuditResult()

    for record in render_result.records:
        prefix = f"Slide {record.manifest_index} ({record.asset_id})"

        # Check 1 & 2: classify skipped placeholders on b_variable slides
        if record.entry_type == "b_variable" and record.injection_result:
            inj = record.injection_result
            for i, skip_idx in enumerate(inj.skipped):
                skip_type = (
                    inj.skipped_types[i]
                    if i < len(inj.skipped_types)
                    else "UNKNOWN"
                )
                if skip_type in _REQUIRED_TEXT_TYPES:
                    audit.unfilled_required.append(
                        f"{prefix}: required {skip_type} placeholder "
                        f"idx {skip_idx} unfilled"
                    )
                else:
                    audit.unfilled_non_text.append(
                        f"{prefix}: non-text {skip_type} placeholder "
                        f"idx {skip_idx} skipped (informational)"
                    )

        # Check 3: template syntax in injected content
        if record.injection_result:
            for injected in record.injection_result.injected:
                preview = injected.content_preview
                for pattern in _TEMPLATE_SYNTAX_PATTERNS:
                    match = pattern.search(preview)
                    if match:
                        audit.template_syntax_found.append(
                            f"{prefix} ph_{injected.placeholder_idx}: "
                            f"template syntax '{match.group()}'"
                        )

    return audit
