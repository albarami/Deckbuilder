"""Waiver governance models."""

from datetime import UTC, datetime

from pydantic import Field

from .common import DeckForgeBaseModel
from .enums import ApprovalLevel, GapSeverity


class WaiverObject(DeckForgeBaseModel):
    """
    Created when a human waives a gap.
    Waivers are logged, visible in export, and require explicit confirmation for critical gaps.

    Permissions by severity:
      - low: consultant or admin may waive
      - medium: consultant or admin with approval_level >= pillar_lead
      - critical: admin with approval_level >= pillar_lead
    """
    waiver_id: str  # WVR-NNN
    gap_id: str  # GAP-NNN
    gap_description: str
    rfp_criterion: str
    severity: GapSeverity
    waived_by: str  # User email
    waiver_reason: str  # Required for critical gaps
    waiver_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approval_level: ApprovalLevel
    scope: str = ""  # e.g., "This RFP only"
    visible_in_export: bool = True
    export_note: str = ""
