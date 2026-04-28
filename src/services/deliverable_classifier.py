"""Formal deliverable classifier — Slice 5.2.

The Source Book pipeline must distinguish between **formal**
deliverables — those listed in the BoQ pricing table or the
deliverables annex — and **cross-cutting workstreams** that arise
from scope clauses or special conditions but are NOT pricing-line
items. The plan's Section 4 establishes:

* ``boq_line`` / ``deliverables_annex`` → ``formal_deliverable=True``
  (and ``pricing_line_item=True`` for boq_line);
* ``scope_clause`` / ``special_condition`` → ``cross_cutting_workstream
  =True``, never formal, never priced;
* ``generated_supporting_artifact`` → none of the above.

If the LLM proposes a ``D-N`` id for a non-formal item, this module's
``normalize_to_workstream_id`` rewrites it to a workstream prefix
(KT-N, GOV-N, MGMT-N / PM-N, TRAIN-N, …) so the source book never
emits fake D-* ids that would mislead readers into pricing them.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, model_validator

from src.models.common import DeckForgeBaseModel


# Origin → workstream prefix matchers. The first match wins; the order
# encodes precedence so "training and knowledge transfer" lands as
# TRAIN- rather than KT-, which matches client-facing convention.
_WORKSTREAM_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\btrain", re.IGNORECASE), "TRAIN"),
    (re.compile(r"تدريب"), "TRAIN"),
    (re.compile(r"knowledge\s+transfer", re.IGNORECASE), "KT"),
    (re.compile(r"نقل\s+المعرفة"), "KT"),
    (re.compile(r"governance|charter|committee", re.IGNORECASE), "GOV"),
    (re.compile(r"حوكمة|لجنة"), "GOV"),
    (re.compile(r"project\s+management|management\s+method", re.IGNORECASE), "MGMT"),
    (re.compile(r"إدارة\s+المشروع"), "MGMT"),
    (re.compile(r"capacity\s+building", re.IGNORECASE), "CAP"),
    (re.compile(r"بناء\s+القدرات"), "CAP"),
]

# Origins that produce a formal D-* deliverable.
_FORMAL_ORIGINS: set[str] = {"boq_line", "deliverables_annex"}


class DeliverableClassification(DeckForgeBaseModel):
    """Sidecar classification of a deliverable item.

    The flags below are DERIVED from ``origin`` — caller-supplied
    boolean values are overwritten by the validator, so the only way
    to obtain ``formal_deliverable=True`` is to set the origin to
    ``boq_line`` or ``deliverables_annex``.
    """

    id: str
    name: str
    origin: Literal[
        "boq_line",
        "deliverables_annex",
        "scope_clause",
        "special_condition",
        "generated_supporting_artifact",
    ]
    formal_deliverable: bool = False
    pricing_line_item: bool = False
    cross_cutting_workstream: bool = False
    registered_as_claim: str = ""

    @model_validator(mode="after")
    def _derive_flags(self) -> "DeliverableClassification":
        is_formal = self.origin in _FORMAL_ORIGINS
        is_priced = self.origin == "boq_line"
        is_workstream = (
            self.origin in {"scope_clause", "special_condition"}
            and not is_formal
        )
        # Validator-set overrides any tampered manual booleans.
        object.__setattr__(self, "formal_deliverable", is_formal)
        object.__setattr__(self, "pricing_line_item", is_priced)
        object.__setattr__(self, "cross_cutting_workstream", is_workstream)
        return self


def _detect_workstream_prefix(name: str) -> str:
    for pattern, prefix in _WORKSTREAM_RULES:
        if pattern.search(name or ""):
            return prefix
    return "WS"


_D_ID_RE = re.compile(r"^D-(\d+)$", re.IGNORECASE)


def normalize_to_workstream_id(
    original_id: str,
    name: str,
    origin: str,
) -> str:
    """Rewrite a D-N id to a workstream prefix when the origin is
    non-formal. For formal origins, the original id is preserved.

    Non-D-* ids are returned unchanged. The N suffix is preserved
    when present, otherwise a default of 1 is appended.
    """
    if origin in _FORMAL_ORIGINS:
        return original_id

    m = _D_ID_RE.match(original_id or "")
    if m is None:
        # Already a workstream id (KT-3 / GOV-1) or some other shape.
        return original_id
    suffix = m.group(1)
    prefix = _detect_workstream_prefix(name)
    return f"{prefix}-{suffix}"


def classify_deliverable(
    *,
    id_hint: str,
    name: str,
    origin: str,
) -> DeliverableClassification:
    """One-shot helper: produce a fully-classified deliverable with
    its id auto-normalized when the origin is non-formal."""
    final_id = normalize_to_workstream_id(id_hint, name, origin)
    return DeliverableClassification(
        id=final_id,
        name=name,
        origin=origin,  # type: ignore[arg-type]
    )
