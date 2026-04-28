"""Proposal option registrar — Slice 4.5 wiring.

Reflects every :class:`ProposalOption` that lives in
``state.proposal_options`` (the metadata sidecar registry) into the
canonical ``state.claim_registry`` as a ``ClaimProvenance`` with
``claim_kind="proposal_option"``.

This is the wiring contract: a ProposalOption only enters the
proposal-option universe by passing through this helper, so that
downstream gates (Pass 6 of validate_conformance, the orchestrator
acceptance gate) see a single source of truth for what options exist,
which are approved, and which are externally publishable.

The helper is idempotent — calling it multiple times preserves the
existing ClaimProvenance entries (ClaimRegistry.register replaces by
id). It does not touch any other claim_kind.
"""
from __future__ import annotations

from src.models.claim_provenance import ClaimProvenance, SourceReference
from src.models.state import DeckForgeState


def register_proposal_options(state: DeckForgeState) -> None:
    """Reflect ``state.proposal_options`` into ``state.claim_registry``.

    For each :class:`ProposalOption` in ``state.proposal_options``,
    register (or refresh) a ``ClaimProvenance`` keyed by the option's
    ``claim_provenance_id`` with::

        claim_kind         = "proposal_option"
        source_kind        = "model_generated"
        verification_status = "proposal_option"

    The option's metadata (approved_for_external_use, priced, etc.) is
    NOT copied onto the ClaimProvenance — it remains in the option
    registry. This keeps the gates' contract simple: claim_registry
    answers "what claim_kind is this?", proposal_options answers "is
    this option externally publishable?".
    """
    for option in state.proposal_options.options:
        claim_id = option.claim_provenance_id or option.option_id
        # Build the canonical ClaimProvenance. Idempotent: register
        # replaces any existing entry under the same id.
        state.claim_registry.register(ClaimProvenance(
            claim_id=claim_id,
            text=option.text,
            claim_kind="proposal_option",
            source_kind="model_generated",
            verification_status="proposal_option",
            evidence_role="proposal_design_option",
            source_refs=[SourceReference(
                file="proposal_option_registry",
                evidence_id=option.option_id,
            )],
        ))
