"""Claim objects and Reference Index — output of the Analysis Agent."""

from datetime import UTC, datetime

from pydantic import Field

from .common import DateRange, DeckForgeBaseModel
from .enums import (
    ClaimCategory,
    GapSeverity,
    SensitivityTag,
)


class ClaimObject(DeckForgeBaseModel):
    """
    Atomic factual claim extracted from a source document.
    Each claim represents ONE fact — never bundled.
    Confidence rubric (rule-based, not self-assessed):
      0.95-1.00: Exact explicit statement (verbatim or near-verbatim)
      0.80-0.94: Strong explicit evidence with minor normalization
      0.60-0.79: Partial evidence requiring inference
      Below 0.60: Do NOT emit — flag as gap instead
    """
    claim_id: str  # CLM-NNNN
    claim_text: str
    source_doc_id: str  # DOC-NNN
    source_location: str  # "Slide 8", "Page 3", "Section 2.1"
    evidence_span: str  # Exact text from source supporting the claim
    sensitivity_tag: SensitivityTag
    category: ClaimCategory
    confidence: float = Field(ge=0.6, le=1.0)


class GapObject(DeckForgeBaseModel):
    """Evidence gap identified during analysis."""
    gap_id: str  # GAP-NNN
    description: str
    rfp_criterion: str  # Which evaluation criterion this gap affects
    severity: GapSeverity
    action_required: str


class Contradiction(DeckForgeBaseModel):
    """Contradictory claims found across source documents."""
    claim_a_id: str
    claim_b_id: str
    description: str
    resolution_note: str | None = None


class CaseStudy(DeckForgeBaseModel):
    """Structured project reference assembled from atomic claims."""
    project_name: str
    client: str
    dates: DateRange | None = None
    scope: str
    outcomes: str | None = None
    team_size: int | None = None
    value: str | None = None  # Contract value, if known
    geography: str | None = None
    domain_tags: list[str] = Field(default_factory=list)
    source_claims: list[str] = Field(default_factory=list)  # CLM-NNNN refs


class TeamProfile(DeckForgeBaseModel):
    """Individual team member or role profile."""
    name_or_role: str  # Named person or role title
    qualifications: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    years_experience: int | None = None
    nationality: str | None = None
    current_role: str | None = None
    source_claims: list[str] = Field(default_factory=list)


class ComplianceEvidence(DeckForgeBaseModel):
    """Evidence for a specific compliance requirement."""
    requirement_id: str  # Maps to COMP-NNN from RFP
    certificate_name: str
    issuing_body: str | None = None
    date_issued: str | None = None
    expiry_date: str | None = None
    scope_level: str | None = None
    source_claims: list[str] = Field(default_factory=list)


class FrameworkReference(DeckForgeBaseModel):
    """Reusable methodology or framework from past work."""
    framework_name: str
    description: str
    applied_in: str | None = None  # Project/context where it was used
    source_claims: list[str] = Field(default_factory=list)


class SourceManifestEntry(DeckForgeBaseModel):
    """Metadata for a source document used in the Reference Index."""
    doc_id: str  # DOC-NNN
    title: str
    sharepoint_path: str
    version_id: str | None = None
    last_modified: str | None = None  # YYYY-MM-DD
    retrieval_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str | None = None  # sha256 hash for auditability


class ReferenceIndex(DeckForgeBaseModel):
    """
    The single source of truth for all downstream content generation.
    Output of the Analysis Agent. Input to the Research Agent.
    """
    claims: list[ClaimObject] = Field(default_factory=list)
    case_studies: list[CaseStudy] = Field(default_factory=list)
    team_profiles: list[TeamProfile] = Field(default_factory=list)
    compliance_evidence: list[ComplianceEvidence] = Field(default_factory=list)
    frameworks: list[FrameworkReference] = Field(default_factory=list)
    gaps: list[GapObject] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    source_manifest: list[SourceManifestEntry] = Field(default_factory=list)
