"""Section Filler Base — common interface and types for all section fillers.

Every section filler receives a ``SectionFillerInput`` and produces a
``SectionFillerOutput`` containing ManifestEntry objects with
``entry_type="b_variable"`` and populated ``injection_data``.

Fillers are responsible ONLY for variable slides.  Template-owned
content (A1 clones, pool clones, section dividers) is assembled by the
orchestrator, not by individual fillers.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.models.common import DeckForgeBaseModel
from src.models.enums import Language
from src.models.methodology_blueprint import MethodologyBlueprint
from src.models.proposal_manifest import ContentSourcePolicy, ManifestEntry
from src.models.rfp import RFPContext
from src.services.source_pack import SourcePack

logger = logging.getLogger(__name__)


# ── Input / Output models ────────────────────────────────────────────


class SectionFillerInput(DeckForgeBaseModel):
    """Input to any section filler.

    Contains everything a filler needs to generate content for its
    section's variable slides.
    """

    section_id: str
    slide_count: int  # Exact number of b_variable slides to produce
    recommended_layouts: list[str]  # Semantic layout IDs from blueprint
    rfp_context: RFPContext | None = None
    source_pack: SourcePack | None = None
    win_themes: list[str] = []
    output_language: Language = Language.EN

    # Methodology context (populated for section_03, section_04)
    methodology_blueprint: MethodologyBlueprint | None = None

    model_config = {"arbitrary_types_allowed": True}


@dataclass
class SectionFillerOutput:
    """Output from a section filler.

    Contains ManifestEntry objects ready for the ProposalManifest.
    Each entry has entry_type="b_variable" and populated injection_data.
    """

    section_id: str
    entries: list[ManifestEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_output: Any = None  # G2 typed schema (e.g. MethodologyOutput)

    @property
    def success(self) -> bool:
        return len(self.entries) > 0 and len(self.errors) == 0


# ── Helper to build ManifestEntry ─────────────────────────────────────


def make_variable_entry(
    asset_id: str,
    semantic_layout_id: str,
    section_id: str,
    injection_data: dict[str, Any],
    methodology_phase: str | None = None,
) -> ManifestEntry:
    """Create a b_variable ManifestEntry with injection data.

    This is the standard way for fillers to produce entries.
    """
    return ManifestEntry(
        entry_type="b_variable",
        asset_id=asset_id,
        semantic_layout_id=semantic_layout_id,
        content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
        section_id=section_id,
        methodology_phase=methodology_phase,
        injection_data=injection_data,
    )


# ── Abstract Base ─────────────────────────────────────────────────────


class BaseSectionFiller(ABC):
    """Abstract base for section fillers.

    Subclasses implement ``_generate`` to produce variable slide content.
    The ``fill`` method wraps it with error handling and logging.
    """

    section_id: str = ""
    model_name: str = ""
    _last_raw_output: Any = None  # Set by _generate for quality gate

    @abstractmethod
    async def _generate(
        self, filler_input: SectionFillerInput,
    ) -> list[ManifestEntry]:
        """Generate ManifestEntry objects for this section's variable slides.

        Must return exactly ``filler_input.slide_count`` entries.
        Subclasses may set ``self._last_raw_output`` to the parsed G2
        schema object so the quality gate can inspect it.
        """
        ...

    async def fill(self, filler_input: SectionFillerInput) -> SectionFillerOutput:
        """Run the filler with error handling."""
        self._last_raw_output = None
        output = SectionFillerOutput(section_id=filler_input.section_id)
        try:
            entries = await self._generate(filler_input)
            output.entries = entries
            output.raw_output = self._last_raw_output

            if len(entries) != filler_input.slide_count:
                logger.warning(
                    "%s produced %d entries but budget is %d",
                    self.__class__.__name__,
                    len(entries),
                    filler_input.slide_count,
                )
        except Exception as exc:
            logger.error(
                "%s failed: %s", self.__class__.__name__, exc, exc_info=True,
            )
            output.errors.append(f"{self.__class__.__name__}: {exc}")

        return output
