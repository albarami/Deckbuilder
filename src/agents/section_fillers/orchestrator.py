"""Section Fill Orchestrator — dispatches fillers and collects results.

Wires all section fillers together.  Given a SlideBudget and evidence
inputs, dispatches each filler with its section's exact slide_count
from the budget, then collects all ManifestEntry results.

The orchestrator does NOT build the full ProposalManifest — that
remains in manifest_builder.py.  The orchestrator only produces the
b_variable entries that the manifest builder inserts into their
correct positions.

Unit-tested with mocked fillers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from src.models.enums import Language
from src.models.methodology_blueprint import MethodologyBlueprint
from src.models.proposal_manifest import ManifestEntry
from src.models.rfp import RFPContext
from src.models.source_book import SlideBlueprintEntry
from src.services.slide_budgeter import SlideBudget
from src.services.source_pack import SourcePack

from .base import SectionFillerInput, SectionFillerOutput
from .governance import GovernanceFiller
from .methodology import MethodologyFiller
from .timeline import TimelineFiller
from .understanding import UnderstandingFiller
from .why_sg import WhySGFiller

logger = logging.getLogger(__name__)


# ── Result ───────────────────────────────────────────────────────────


@dataclass
class OrchestratorResult:
    """Result from running all section fillers."""

    entries_by_section: dict[str, list[ManifestEntry]] = field(
        default_factory=dict,
    )
    filler_outputs: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def all_entries(self) -> list[ManifestEntry]:
        """All entries across all sections, in section order."""
        result: list[ManifestEntry] = []
        for section_id in sorted(self.entries_by_section.keys()):
            result.extend(self.entries_by_section[section_id])
        return result

    @property
    def success(self) -> bool:
        return len(self.all_entries) > 0


# ── Orchestrator ─────────────────────────────────────────────────────


# Section ID → filler class mapping
# NOTE: IntroductionFiller (section_00) is NOT registered here.
# The intro slide is architecturally a hard-coded a2_shell in the "cover"
# section (budgeter allocates it as a fixed house asset, manifest_builder
# creates it as entry_type="a2_shell" with section_id="cover").
# section_fill_node only replaces b_variable entries, so registering
# IntroductionFiller here would be dead code — the filler output would
# never reach the rendered slide.
# IntroductionFiller integration requires refactoring the budgeter +
# manifest_builder + section_fill_node to treat intro as a b_variable.
# This is deferred to a future step.
FILLER_REGISTRY: dict[str, type] = {
    "section_01": UnderstandingFiller,
    "section_02": WhySGFiller,
    "section_03": MethodologyFiller,
    "section_04": TimelineFiller,
    "section_06": GovernanceFiller,
}

# Section ID → budget breakdown key for content slides
BUDGET_CONTENT_KEY: dict[str, str] = {
    "section_01": "content",
    "section_02": "why_sg_variable",
    "section_03": "methodology_total",
    "section_04": "content",
    "section_06": "content",
}


def _get_slide_count(
    budget: SlideBudget,
    section_id: str,
) -> int:
    """Extract the variable slide count from the budget for a section.

    For methodology (section_03), the budget breakdown uses separate keys
    (overview, focused, detail) instead of a single "content" key.
    We sum those to get the total methodology slide count.
    """
    if section_id not in budget.section_budgets:
        return 0

    section_budget = budget.section_budgets[section_id]
    content_key = BUDGET_CONTENT_KEY.get(section_id, "content")

    # Methodology uses split keys — sum the components
    if content_key == "methodology_total":
        return (
            section_budget.breakdown.get("overview", 0)
            + section_budget.breakdown.get("focused", 0)
            + section_budget.breakdown.get("detail", 0)
        )

    return section_budget.breakdown.get(content_key, 0)


def _get_recommended_layouts(section_id: str) -> list[str]:
    """Default recommended layouts per section.

    Each layout must be compatible with the injection contract of its filler:
    - title/body fillers → _TITLE_BODY_LAYOUTS only (content_heading_desc, etc.)
    - multi_body fillers → _MULTI_BODY_LAYOUTS only (methodology_*, etc.)
    """
    return {
        "section_01": ["content_heading_desc"],
        "section_02": ["content_heading_desc"],
        "section_03": [
            "methodology_overview_4",
            "methodology_focused_4",
            "methodology_detail",
        ],
        "section_04": ["content_heading_desc"],
        "section_06": ["content_heading_desc"],
    }.get(section_id, ["content_heading_desc"])


async def run_section_fillers(
    budget: SlideBudget,
    *,
    rfp_context: RFPContext | None = None,
    source_pack: SourcePack | None = None,
    win_themes: list[str] | None = None,
    output_language: Language = Language.EN,
    methodology_blueprint: MethodologyBlueprint | None = None,
    blueprint_entries: list[SlideBlueprintEntry] | None = None,
) -> OrchestratorResult:
    """Run all section fillers and collect results.

    Parameters
    ----------
    budget : SlideBudget
        Complete slide budget with per-section breakdowns.
    rfp_context : RFPContext, optional
        Parsed RFP context for evidence.
    source_pack : SourcePack, optional
        Full evidence pack from knowledge graph + documents.
    win_themes : list[str], optional
        Win themes for the proposal.
    output_language : Language
        Output language (EN or AR).
    methodology_blueprint : MethodologyBlueprint, optional
        Methodology blueprint (required for section_03, section_04).

    Returns
    -------
    OrchestratorResult
        Collected ManifestEntry objects grouped by section_id.
    """
    result = OrchestratorResult()
    tasks: list[tuple[str, asyncio.Task]] = []

    for section_id, filler_cls in FILLER_REGISTRY.items():
        slide_count = _get_slide_count(budget, section_id)
        if slide_count <= 0:
            logger.info(
                "Skipping %s — slide_count=%d", section_id, slide_count,
            )
            continue

        # Filter blueprint entries for this section
        section_blueprint = [
            e for e in (blueprint_entries or [])
            if e.section == section_id
        ]

        filler_input = SectionFillerInput(
            section_id=section_id,
            slide_count=slide_count,
            recommended_layouts=_get_recommended_layouts(section_id),
            rfp_context=rfp_context,
            source_pack=source_pack,
            win_themes=win_themes or [],
            output_language=output_language,
            methodology_blueprint=methodology_blueprint,
            blueprint_entries=section_blueprint,
        )

        filler = filler_cls()
        task = asyncio.create_task(
            filler.fill(filler_input),
            name=f"filler_{section_id}",
        )
        tasks.append((section_id, task))

    # Await all fillers concurrently
    for section_id, task in tasks:
        try:
            output: SectionFillerOutput = await task
            if output.entries:
                result.entries_by_section[section_id] = output.entries
            if output.raw_output is not None:
                result.filler_outputs[section_id] = output.raw_output
            if output.errors:
                result.errors.extend(output.errors)
                logger.warning(
                    "Filler %s had errors: %s", section_id, output.errors,
                )
        except Exception as exc:
            error_msg = f"Filler {section_id} crashed: {exc}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)

    logger.info(
        "Orchestrator: %d sections filled, %d total entries, %d errors",
        len(result.entries_by_section),
        len(result.all_entries),
        len(result.errors),
    )

    return result
