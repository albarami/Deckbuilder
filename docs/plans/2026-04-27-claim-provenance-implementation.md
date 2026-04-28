# Claim Provenance, Evidence Fidelity, and Artifact Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current loosely-typed evidence system with a strict claim-provenance model that prevents unverified internal claims from leaking into proposal-facing content, separates RFP facts from bidder proof gaps, and gates every artifact through structured validation.

**Architecture:** Vertical slices per claim kind. Each slice implements one `claim_kind` end-to-end (model → extraction → ledger → writer → validator → gate → tests), then proves it against frozen regression fixtures. Cross-cutting concerns (routing, conformance index, final gate) are woven into each slice. Design doc: `docs/plans/2026-04-27-claim-provenance-architecture-design.md`.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, python-docx, LangGraph, Claude API via `src.services.llm.call_llm`.

**Branch:** `claude/agitated-williamson` only. All paths relative to worktree root.

**Regression fixtures:** `sb-ar-1776112115` (NCNP), `sb-ar-1777280086` (UNESCO AI Ethics).

---

## Slice 0: Foundation — Models, Registry, Fixtures

### Task 0.1: Create ClaimProvenance and SourceReference models

**Files:**
- Create: `src/models/claim_provenance.py`
- Test: `tests/models/test_claim_provenance.py`

**Step 1: Write failing tests**

```python
# tests/models/test_claim_provenance.py
import pytest
from src.models.claim_provenance import ClaimProvenance, SourceReference

def test_rfp_fact_defaults():
    c = ClaimProvenance(
        claim_id="RFP-FACT-001",
        text="مدة العقد 12 شهراً",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
    )
    assert c.usage_allowed == ["internal_gap_appendix"]  # default before normalization
    assert c.formal_deliverable is False
    assert c.requires_client_naming_permission is False

def test_internal_claim_defaults_to_unverified():
    c = ClaimProvenance(
        claim_id="BIDDER-CLAIM-001",
        text="SG has prior SDAIA experience",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_unverified",
    )
    assert c.verification_status == "internal_unverified"
    assert c.client_naming_permission is None
    assert c.requested_external_contexts == []  # empty until bid team sets intent

def test_requested_external_contexts_preserved():
    c = ClaimProvenance(
        claim_id="BIDDER-CLAIM-002",
        text="SG prior SDAIA project",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_unverified",
        requested_external_contexts=["source_book", "slide_blueprint"],
    )
    # requested_external_contexts preserved even though usage_allowed is normalized away
    assert c.requested_external_contexts == ["source_book", "slide_blueprint"]
    assert c.usage_allowed == ["internal_gap_appendix"]  # default, before normalize

def test_usage_allowed_accepts_internal_destinations():
    c = ClaimProvenance(
        claim_id="OPT-001",
        text="5-8 countries",
        claim_kind="proposal_option",
        source_kind="model_generated",
        verification_status="proposal_option",
        usage_allowed=["internal_bid_notes", "proposal_option_ledger"],
    )
    assert "internal_bid_notes" in c.usage_allowed
    assert "proposal_option_ledger" in c.usage_allowed

def test_deliverable_flags_derived_from_origin():
    c = ClaimProvenance(
        claim_id="RFP-FACT-010",
        text="D-1 Design document",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
        deliverable_origin="boq_line",
    )
    assert c.formal_deliverable is True
    assert c.pricing_line_item is True
    assert c.cross_cutting_workstream is False

def test_special_condition_is_workstream_not_deliverable():
    c = ClaimProvenance(
        claim_id="RFP-FACT-011",
        text="Training and knowledge transfer",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
        deliverable_origin="special_condition",
    )
    assert c.formal_deliverable is False
    assert c.pricing_line_item is False
    assert c.cross_cutting_workstream is True

def test_source_refs_list_based():
    c = ClaimProvenance(
        claim_id="RFP-FACT-002",
        text="test",
        claim_kind="rfp_fact",
        source_kind="rfp_document",
        verification_status="verified_from_rfp",
        source_refs=[
            SourceReference(file="rfp.pdf", page="7", clause="جدول المواعيد"),
            SourceReference(file="rfp.pdf", page="12", clause="شروط التقديم"),
        ],
    )
    assert len(c.source_refs) == 2
    assert c.source_refs[0].page == "7"
```

**Step 2:** Run: `pytest tests/models/test_claim_provenance.py -v` → Expected: FAIL (module not found)

**Step 3:** Create `src/models/claim_provenance.py` with full `ClaimProvenance` and `SourceReference` models from design doc Section 1.

**Step 4:** Run: `pytest tests/models/test_claim_provenance.py -v` → Expected: PASS

**Step 5:** Commit: `git commit -m "feat(models): add ClaimProvenance and SourceReference core models"`

---

### Task 0.2: Create context-specific usage gates

**Files:**
- Create: `src/services/artifact_gates.py`
- Test: `tests/services/test_artifact_gates.py`

**Step 1: Write failing tests**

```python
# tests/services/test_artifact_gates.py
import pytest
from src.models.claim_provenance import ClaimProvenance
from src.services.artifact_gates import (
    can_use_as_proof_point,
    can_use_in_source_book_analysis,
    can_use_in_slide_blueprint,
    can_use_in_speaker_notes,
    normalize_usage_allowed,
)

def test_rfp_fact_is_proof_point():
    c = ClaimProvenance(
        claim_id="RFP-FACT-001", text="test",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    )
    assert can_use_as_proof_point(c) is True

def test_unverified_internal_not_proof_point():
    c = ClaimProvenance(
        claim_id="BIDDER-001", text="SG experience",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_unverified",
    )
    assert can_use_as_proof_point(c) is False

def test_verified_internal_needs_client_permission():
    c = ClaimProvenance(
        claim_id="BIDDER-002", text="SDAIA project",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_verified",
        requires_client_naming_permission=True,
        client_naming_permission=False,
    )
    assert can_use_as_proof_point(c) is False

def test_verified_internal_with_permissions_is_proof():
    c = ClaimProvenance(
        claim_id="BIDDER-003", text="SDAIA project",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_verified",
        requires_client_naming_permission=True,
        client_naming_permission=True,
        requires_partner_naming_permission=True,
        partner_naming_permission=True,
        scope_summary_allowed_for_proposal=True,
    )
    assert can_use_as_proof_point(c) is True

def test_external_methodology_only_as_methodology_support():
    c = ClaimProvenance(
        claim_id="EXT-001", text="UNESCO RAM framework",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="direct_topic",
        evidence_role="bidder_capability_proof",  # WRONG role
    )
    assert can_use_as_proof_point(c) is False

def test_external_methodology_correct_role():
    c = ClaimProvenance(
        claim_id="EXT-002", text="UNESCO RAM framework",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
        relevance_class="direct_topic",
        evidence_role="methodology_support",
    )
    assert can_use_as_proof_point(c) is True

def test_proposal_option_never_proof():
    c = ClaimProvenance(
        claim_id="OPT-001", text="5-8 countries",
        claim_kind="proposal_option", source_kind="model_generated",
        verification_status="proposal_option",
    )
    assert can_use_as_proof_point(c) is False

def test_generated_inference_never_proof():
    c = ClaimProvenance(
        claim_id="INF-001", text="Portal: EXPRO",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
    )
    assert can_use_as_proof_point(c) is False

def test_generated_inference_in_source_book_needs_label():
    c = ClaimProvenance(
        claim_id="INF-002", text="Award mechanism likely pass/fail",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=False,
    )
    assert can_use_in_source_book_analysis(c, "client_facing_body") is False

def test_generated_inference_labelled_allowed_in_analysis():
    c = ClaimProvenance(
        claim_id="INF-003", text="Award mechanism likely pass/fail",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=True,
        inference_allowed_context=["source_book_analysis"],
    )
    assert can_use_in_source_book_analysis(c, "client_facing_body") is True

def test_normalize_blocks_unverified():
    c = ClaimProvenance(
        claim_id="BIDDER-004", text="test",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_unverified",
        usage_allowed=["source_book", "slide_blueprint"],  # manually set wrong
    )
    assert normalize_usage_allowed(c) == ["internal_gap_appendix"]

def test_analogical_partially_verified_blocked_in_source_book():
    c = ClaimProvenance(
        claim_id="EXT-010", text="WHO health workforce governance",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="partially_verified",
        relevance_class="analogical",
        evidence_role="methodology_support",
    )
    assert can_use_in_source_book_analysis(c, "client_facing_body") is False

def test_slide_blueprint_blocks_generated_inference():
    c = ClaimProvenance(
        claim_id="INF-004", text="inferred",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=True,
    )
    assert can_use_in_slide_blueprint(c) is False

def test_speaker_notes_allows_labelled_inference():
    c = ClaimProvenance(
        claim_id="INF-005", text="inferred",
        claim_kind="generated_inference", source_kind="model_generated",
        verification_status="generated_inference",
        inference_label_present=True,
        inference_allowed_context=["speaker_notes"],
    )
    assert can_use_in_speaker_notes(c) is True
```

**Step 2:** Run: `pytest tests/services/test_artifact_gates.py -v` → Expected: FAIL

**Step 3:** Create `src/services/artifact_gates.py` with all gate functions from design doc Section 1 + Section 3.

**Step 4:** Run → Expected: PASS

**Step 5:** Commit: `git commit -m "feat(gates): add context-specific usage gates — can_use_as_proof_point, source_book, slide, speaker_notes"`

---

### Task 0.3: Create ClaimRegistry and typed ledgers

**Files:**
- Add to: `src/models/claim_provenance.py`
- Test: `tests/models/test_claim_registry.py`

**Step 1: Write failing tests**

```python
# tests/models/test_claim_registry.py
import pytest
from src.models.claim_provenance import (
    ClaimProvenance, ClaimRegistry,
    RFPFactLedger, BidderEvidenceLedger,
    ExternalMethodologyLedger, ProposalOptionLedger,
    ClaimLedgerBundle,
)

def test_registry_register_and_get():
    reg = ClaimRegistry()
    c = ClaimProvenance(
        claim_id="RFP-FACT-001", text="test",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    )
    reg.register(c)
    assert reg.get("RFP-FACT-001") is not None
    assert reg.get("NONEXISTENT") is None

def test_registry_views():
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="RFP-001", text="t", claim_kind="rfp_fact",
        source_kind="rfp_document", verification_status="verified_from_rfp",
    ))
    reg.register(ClaimProvenance(
        claim_id="BIDDER-001", text="t", claim_kind="internal_company_claim",
        source_kind="internal_backend", verification_status="internal_unverified",
    ))
    reg.register(ClaimProvenance(
        claim_id="EXT-001", text="t", claim_kind="external_methodology",
        source_kind="external_source", verification_status="externally_verified",
    ))
    assert len(reg.rfp_facts) == 1
    assert len(reg.bidder_claims) == 1
    assert len(reg.external_methodology) == 1

def test_rfp_fact_ledger_rejects_wrong_kind():
    with pytest.raises(AssertionError):
        RFPFactLedger(entries=[ClaimProvenance(
            claim_id="BAD", text="t", claim_kind="internal_company_claim",
            source_kind="internal_backend", verification_status="internal_unverified",
        )])

def test_rfp_fact_ledger_accepts_correct_kind():
    ledger = RFPFactLedger(entries=[ClaimProvenance(
        claim_id="RFP-001", text="t", claim_kind="rfp_fact",
        source_kind="rfp_document", verification_status="verified_from_rfp",
    )])
    assert len(ledger.entries) == 1

def test_resolve_proof_point_by_id():
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="EXT-007", text="UNESCO RAM",
        claim_kind="external_methodology", source_kind="external_source",
        verification_status="externally_verified",
    ))
    assert reg.resolve_proof_point("EXT-007") is not None

def test_resolve_proof_point_by_text():
    reg = ClaimRegistry()
    reg.register(ClaimProvenance(
        claim_id="RFP-002", text="مدة العقد 12 شهراً",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    assert reg.resolve_proof_point("مدة العقد 12 شهراً") is not None
```

**Step 2:** Run → FAIL
**Step 3:** Add ClaimRegistry, typed ledgers, ClaimLedgerBundle to `src/models/claim_provenance.py`
**Step 4:** Run → PASS
**Step 5:** Commit: `git commit -m "feat(models): add ClaimRegistry, typed ledgers, ClaimLedgerBundle"`

---

### Task 0.4: Create ComplianceIndex model

**Files:**
- Add to: `src/models/claim_provenance.py`
- Test: `tests/models/test_compliance_index.py`

**Step 1: Write failing tests**

```python
# tests/models/test_compliance_index.py
from src.models.claim_provenance import ComplianceIndexEntry, ComplianceIndex

def test_covered_by_declaration_passes_content():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-002",
        requirement_text="Commercial registration",
        response_status="covered_by_declaration",
        arabic_aliases=["السجل التجاري"],
    )
    assert e.content_conformance_pass is True
    assert e.submission_pack_ready is False

def test_covered_pending_attachment_passes_content_not_submission():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-003",
        requirement_text="Zakat certificate",
        response_status="covered_pending_attachment",
        attachment_required=True,
        attachment_verified=False,
    )
    assert e.content_conformance_pass is True
    assert e.submission_pack_ready is False

def test_attachment_verified_passes_both():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-003",
        requirement_text="Zakat certificate",
        response_status="covered_pending_attachment",
        attachment_required=True,
        attachment_verified=True,
    )
    assert e.content_conformance_pass is True
    assert e.submission_pack_ready is True

def test_missing_fails_content():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-099",
        requirement_text="Unknown",
        response_status="missing",
    )
    assert e.content_conformance_pass is False

def test_not_applicable_needs_rationale():
    e = ComplianceIndexEntry(
        requirement_id="HR-L1-050",
        requirement_text="NA item",
        response_status="not_applicable",
        not_applicable_rationale="",
    )
    assert e.content_conformance_pass is False

    e2 = ComplianceIndexEntry(
        requirement_id="HR-L1-050",
        requirement_text="NA item",
        response_status="not_applicable",
        not_applicable_rationale="Not relevant to this bid type",
    )
    assert e2.content_conformance_pass is True
```

**Step 2:** Run → FAIL
**Step 3:** Add ComplianceIndexEntry and ComplianceIndex to `src/models/claim_provenance.py`
**Step 4:** Run → PASS
**Step 5:** Commit: `git commit -m "feat(models): add ComplianceIndex with content_conformance_pass / submission_pack_ready gates"`

---

### Task 0.5: Create ArtifactSection, ForbiddenLeakageViolation, forbidden scanner

**Files:**
- Add to: `src/services/artifact_gates.py`
- Test: `tests/services/test_forbidden_scanner.py`

**Step 1: Write failing tests**

```python
# tests/services/test_forbidden_scanner.py
import pytest
from src.models.claim_provenance import ClaimProvenance, ClaimRegistry
from src.services.artifact_gates import (
    ArtifactSection, scan_for_forbidden_leakage,
)

def test_prj_id_rejected_in_client_body():
    section = ArtifactSection(
        section_path="why_sg/capability_mapping",
        section_type="client_facing_body",
        text="خبرة موثقة في العمل مع سدايا [PRJ-001]",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1
    assert any("PRJ-001" in v.matched_text for v in violations)

def test_prj_id_allowed_in_internal_gap_appendix():
    section = ArtifactSection(
        section_path="appendix/engine2_requirements",
        section_type="internal_gap_appendix",
        text="PRJ-001: requires verification",
    )
    violations = scan_for_forbidden_leakage(section)
    assert violations == []

def test_cli_id_rejected_in_slide_body():
    section = ArtifactSection(
        section_path="slide_8/body",
        section_type="slide_body",
        text="CLI-002 confirmed partnership",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1

def test_semantic_phrase_rejected():
    section = ArtifactSection(
        section_path="why_sg/experience",
        section_type="client_facing_body",
        text="خبرة موثقة في العمل مع سدايا واليونسكو",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1

def test_semantic_phrase_allowed_if_verified_in_registry():
    registry = ClaimRegistry()
    registry.register(ClaimProvenance(
        claim_id="BIDDER-001",
        text="خبرة موثقة في العمل مع سدايا",
        claim_kind="internal_company_claim",
        source_kind="internal_backend",
        verification_status="internal_verified",
        requires_client_naming_permission=True,
        client_naming_permission=True,
        scope_summary_allowed_for_proposal=True,
    ))
    section = ArtifactSection(
        section_path="why_sg/experience",
        section_type="client_facing_body",
        text="خبرة موثقة في العمل مع سدايا",
    )
    violations = scan_for_forbidden_leakage(section, registry)
    assert violations == []

def test_engine2_required_rejected():
    section = ArtifactSection(
        section_path="section_3/capabilities",
        section_type="proof_column",
        text="Team assignment ENGINE 2 REQUIRED",
    )
    violations = scan_for_forbidden_leakage(section)
    assert len(violations) >= 1
```

**Step 2:** Run → FAIL
**Step 3:** Add ArtifactSection, ForbiddenLeakageViolation, scan_for_forbidden_leakage, FORBIDDEN_ID_PATTERNS, FORBIDDEN_SEMANTIC_PHRASES, INTERNAL_ONLY_SECTION_TYPES to `src/services/artifact_gates.py`
**Step 4:** Run → PASS
**Step 5:** Commit: `git commit -m "feat(gates): add forbidden internal-claim leakage scanner with section-type awareness"`

---

### Task 0.6: Create final artifact gate

**Files:**
- Add to: `src/services/artifact_gates.py`
- Test: `tests/services/test_final_gate.py`

**Step 1: Write failing tests**

```python
# tests/services/test_final_gate.py
from src.models.claim_provenance import ClaimRegistry, ClaimProvenance
from src.models.conformance import ConformanceReport
from src.models.source_book import SourceBookReview
from src.services.artifact_gates import (
    ArtifactSection, GateFailure, ArtifactGateDecision,
    EvidenceCoverageReport, EvidenceCoverageRequirement,
    final_artifact_gate,
)

def _passing_conformance():
    return ConformanceReport(
        conformance_status="pass",
        final_acceptance_decision="accept",
        hard_requirements_checked=10,
        hard_requirements_passed=10,
        hard_requirements_failed=0,
    )

def _passing_review():
    return SourceBookReview(overall_score=4, pass_threshold_met=True, competitive_viability="adequate")

def _passing_coverage():
    return EvidenceCoverageReport(
        requirements=[EvidenceCoverageRequirement(topic="test", minimum_direct_sources=1, found_direct=2, status="met")],
        status="pass",
    )

def test_all_pass_approves():
    decision = final_artifact_gate(
        _passing_conformance(), _passing_review(), _passing_coverage(),
        [], ClaimRegistry(), [],
    )
    assert decision.decision == "approve"
    assert decision.proposal_ready is True
    assert decision.artifact_label == "PROPOSAL READY"

def test_conformance_fail_rejects():
    cr = ConformanceReport(conformance_status="fail", final_acceptance_decision="reject",
                           hard_requirements_checked=10, hard_requirements_passed=5, hard_requirements_failed=5)
    decision = final_artifact_gate(cr, _passing_review(), _passing_coverage(), [], ClaimRegistry(), [])
    assert decision.decision == "reject"
    assert decision.proposal_ready is False
    assert "DRAFT" in decision.artifact_label

def test_forbidden_leakage_rejects():
    from src.services.artifact_gates import ForbiddenLeakageViolation
    violations = [ForbiddenLeakageViolation(
        pattern=r"\bPRJ-\d+\b", matched_text="PRJ-001",
        location="why_sg", section_type="client_facing_body",
    )]
    decision = final_artifact_gate(
        _passing_conformance(), _passing_review(), _passing_coverage(),
        violations, ClaimRegistry(), [],
    )
    assert decision.decision == "reject"

def test_evidence_coverage_fail_rejects():
    cov = EvidenceCoverageReport(
        requirements=[EvidenceCoverageRequirement(topic="unesco", minimum_direct_sources=2, found_direct=0, status="not_met")],
        status="fail",
    )
    decision = final_artifact_gate(
        _passing_conformance(), _passing_review(), cov,
        [], ClaimRegistry(), [],
    )
    assert decision.decision == "reject"

def test_rendered_section_leakage_caught():
    sections = [ArtifactSection(
        section_path="slide_5/body", section_type="slide_body",
        text="prior SDAIA project PRJ-001 confirmed",
    )]
    decision = final_artifact_gate(
        _passing_conformance(), _passing_review(), _passing_coverage(),
        [], ClaimRegistry(), sections,
    )
    assert decision.decision == "reject"
    assert any(f.code == "RENDERED_LEAKAGE" for f in decision.failures)
```

**Step 2:** Run → FAIL
**Step 3:** Add GateFailure, ArtifactGateDecision, EvidenceCoverageRequirement, EvidenceCoverageReport, final_artifact_gate to `src/services/artifact_gates.py`
**Step 4:** Run → PASS
**Step 5:** Commit: `git commit -m "feat(gates): add final artifact gate with severity-graded failures and rendered-section scanning"`

---

### Task 0.7: Create Engine 2 contract models

**Files:**
- Create: `src/models/engine2_contract.py`
- Test: `tests/models/test_engine2_contract.py`

**Step 1: Write failing tests**

```python
# tests/models/test_engine2_contract.py
from src.models.engine2_contract import (
    Engine2ProofRequest, Engine2ProofResponse, default_engine2_response,
)

def test_default_response_is_unverified():
    req = Engine2ProofRequest(
        claim_id="BIDDER-001", claim_text="SDAIA project",
        requested_proof_type="prior_project",
    )
    resp = default_engine2_response(req)
    assert resp.verified is False
    assert resp.verification_status == "internal_unverified"
    assert resp.client_name_disclosure_allowed is False
    assert resp.partner_name_disclosure_allowed is False

def test_request_carries_permission_requirements():
    req = Engine2ProofRequest(
        claim_id="BIDDER-002", claim_text="UNESCO partnership",
        requested_proof_type="partner_permission",
        requires_partner_naming_permission=True,
        anonymized_allowed=True,
    )
    assert req.requires_partner_naming_permission is True
```

**Step 2:** Run → FAIL
**Step 3:** Create `src/models/engine2_contract.py` with models from design doc Section 5.2
**Step 4:** Run → PASS
**Step 5:** Commit: `git commit -m "feat(models): add Engine 2 contract interface — request/response/default resolver"`

---

### Task 0.8: Freeze regression fixtures

**Files:**
- Create: `tests/fixtures/sb-ar-1776112115/` (copy from output)
- Create: `tests/fixtures/sb-ar-1777280086/` (copy from output)

**Step 1: Copy artifacts**

```bash
mkdir -p tests/fixtures/sb-ar-1776112115
cp output/sb-ar-1776112115/source_book.docx tests/fixtures/sb-ar-1776112115/
cp output/sb-ar-1776112115/conformance_report.json tests/fixtures/sb-ar-1776112115/
cp output/sb-ar-1776112115/evidence_ledger.json tests/fixtures/sb-ar-1776112115/
cp output/sb-ar-1776112115/slide_blueprint_from_source_book.json tests/fixtures/sb-ar-1776112115/

mkdir -p tests/fixtures/sb-ar-1777280086
cp output/sb-ar-1777280086/source_book.docx tests/fixtures/sb-ar-1777280086/
cp output/sb-ar-1777280086/conformance_report.json tests/fixtures/sb-ar-1777280086/
cp output/sb-ar-1777280086/evidence_ledger.json tests/fixtures/sb-ar-1777280086/
cp output/sb-ar-1777280086/slide_blueprint_from_source_book.json tests/fixtures/sb-ar-1777280086/
cp output/sb-ar-1777280086/external_evidence_pack.json tests/fixtures/sb-ar-1777280086/
```

**Step 2: Create fixture loader**

```python
# tests/fixtures/fixture_loader.py
from pathlib import Path
import json

_FIXTURE_DIR = Path(__file__).parent

def load_conformance_report(session_id: str) -> dict:
    return json.loads((_FIXTURE_DIR / session_id / "conformance_report.json").read_text(encoding="utf-8"))

def load_evidence_ledger(session_id: str) -> dict:
    return json.loads((_FIXTURE_DIR / session_id / "evidence_ledger.json").read_text(encoding="utf-8"))

def load_slide_blueprints(session_id: str) -> list:
    return json.loads((_FIXTURE_DIR / session_id / "slide_blueprint_from_source_book.json").read_text(encoding="utf-8"))

def load_docx_text(session_id: str) -> str:
    from docx import Document
    d = Document(str(_FIXTURE_DIR / session_id / "source_book.docx"))
    parts = []
    for p in d.paragraphs:
        parts.append(p.text)
    for t in d.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    parts.append(p.text)
    return "\n".join(parts)
```

**Step 3:** Commit: `git commit -m "test(fixtures): freeze sb-ar-1776112115 and sb-ar-1777280086 as regression fixtures"`

---

### Task 0.9: Write old-failure-detection tests

Tests that prove the old bugs EXIST in the frozen fixtures:

**Files:**
- Create: `tests/regression/test_old_failures_detected.py`

```python
# tests/regression/test_old_failures_detected.py
"""Prove the old bugs exist in frozen fixtures.
These tests should PASS — they detect known bad behavior."""
import re
import pytest
from tests.fixtures.fixture_loader import (
    load_conformance_report, load_evidence_ledger,
    load_slide_blueprints, load_docx_text,
)

def test_ncnp_has_9_conformance_failures():
    cr = load_conformance_report("sb-ar-1776112115")
    assert cr["hard_requirements_failed"] == 9

def test_ncnp_evidence_ledger_marks_rfp_facts_as_gaps():
    ledger = load_evidence_ledger("sb-ar-1776112115")
    gap_entries = [e for e in ledger["entries"] if e["verifiability_status"] == "gap"]
    rfp_source_gaps = [e for e in gap_entries if "HR-L1" in e.get("source_reference", "") or "CR-" in e.get("source_reference", "")]
    assert len(rfp_source_gaps) >= 5, "RFP facts incorrectly marked as gaps"

def test_unesco_has_prj_leakage_in_docx():
    text = load_docx_text("sb-ar-1777280086")
    assert re.search(r"\bPRJ-\d+\b", text), "PRJ ID should be present in old fixture"

def test_unesco_routing_has_digital_transformation():
    # Check from the result JSON
    import json
    from pathlib import Path
    result = json.loads(Path("source_book_only_ar_result.json").read_text(encoding="utf-8"))
    if result.get("session_id") == "sb-ar-1777280086":
        routing = result.get("routing_report", {}).get("classification", {})
        assert routing.get("domain") == "digital_transformation"

def test_unesco_conformance_stuck_at_10():
    cr = load_conformance_report("sb-ar-1777280086")
    assert cr["hard_requirements_failed"] == 10
```

**Step:** Run → PASS (these detect known bad behavior)
**Commit:** `git commit -m "test(regression): prove old failures exist in frozen fixtures"`

---

## ── CHECKPOINT: Slice 0 Complete ──

After Slice 0: all foundation models, gates, scanner, registry, fixtures, and old-failure-detection tests are in place. No pipeline behavior changed yet.

Run: `pytest tests/models/ tests/services/test_artifact_gates.py tests/services/test_forbidden_scanner.py tests/services/test_final_gate.py tests/regression/ -v`

Expected: ALL PASS.

---

## Slice 1: `rfp_fact` — RFP Facts Never Engine 2 Gaps

### Task 1.1: Create skeleton domain packs

**Files:**
- Create: `src/packs/ai_governance_ethics.json`
- Create: `src/packs/unesco_unesco_ram.json`
- Create: `src/packs/international_research_collaboration.json`
- Create: `src/packs/government_capacity_building.json`
- Create: `src/packs/knowledge_transfer.json`
- Create: `src/packs/research_program_evaluation.json`
- Test: `tests/services/test_skeleton_packs.py`

**Step 1:** Create the 6 JSON files with exact keyword sets from approved Q3 answer (including tiered strong/medium/weak keywords, forbidden_assumptions, and search query seeds).

**Step 2: Write tests**

```python
# tests/services/test_skeleton_packs.py
import json
from pathlib import Path
import pytest

PACKS_DIR = Path("src/packs")

@pytest.mark.parametrize("pack_id", [
    "ai_governance_ethics", "unesco_unesco_ram",
    "international_research_collaboration", "government_capacity_building",
    "knowledge_transfer", "research_program_evaluation",
])
def test_skeleton_pack_structure(pack_id):
    path = PACKS_DIR / f"{pack_id}.json"
    assert path.exists(), f"Pack file missing: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["pack_id"] == pack_id
    assert data["status"] == "skeleton"
    assert data["requires_enrichment"] is True
    assert len(data.get("classification_keywords", {}).get("domain", {}).get(pack_id, [])) >= 5
    assert len(data.get("forbidden_assumptions", [])) >= 2
    assert len(data.get("regulatory_references", [])) == 0  # skeleton: no fake content

def test_skeleton_pack_has_search_seeds():
    data = json.loads((PACKS_DIR / "unesco_unesco_ram.json").read_text(encoding="utf-8"))
    queries = data.get("recommended_search_queries", [])
    assert len(queries) >= 3
    assert any("UNESCO" in q or "RAM" in q for q in queries)
```

**Step 3:** Run → PASS
**Step 4:** Commit: `git commit -m "feat(packs): add 6 skeleton domain packs with strong keywords + search seeds"`

---

### Task 1.2: Multi-label routing classifier

**Files:**
- Modify: `src/models/routing.py:24-50` (RFPClassification → add primary_domains, secondary_domains)
- Modify: `src/services/routing.py:232-420` (classify_rfp → weighted scoring, multi-label, demotion)
- Modify: `src/services/routing.py:424-458` (select_packs → multi-domain selection)
- Test: `tests/services/test_routing_multilabel.py`

**Step 1: Write failing tests**

```python
# tests/services/test_routing_multilabel.py
import pytest
from src.models.state import DeckForgeState
from src.models.rfp import RFPContext
from src.models.common import BilingualText
from src.services.routing import classify_rfp, select_packs

def _unesco_ai_state():
    state = DeckForgeState()
    state.rfp_context = RFPContext(
        rfp_name=BilingualText(
            ar="الخدمات الاحترافية في أبحاث الذكاء الاصطناعي وأخلاقياته مع اليونسكو ومنهجية تقييم الجاهزية RAM",
            en="",
        ),
        issuing_entity=BilingualText(
            ar="الهيئة السعودية للبيانات والذكاء الاصطناعي - سدايا",
            en="SDAIA",
        ),
    )
    return state

def test_unesco_routes_to_specific_domains():
    classification = classify_rfp(_unesco_ai_state())
    assert "ai_governance_ethics" in classification.primary_domains
    assert "unesco_unesco_ram" in classification.primary_domains
    assert "digital_transformation" not in classification.primary_domains

def test_digital_transformation_demoted_to_secondary():
    classification = classify_rfp(_unesco_ai_state())
    if "digital_transformation" in classification.secondary_domains:
        assert "digital_transformation" not in classification.primary_domains

def test_pack_selection_includes_domain_packs():
    classification = classify_rfp(_unesco_ai_state())
    selected, fallbacks = select_packs(classification)
    assert "ai_governance_ethics" in selected or "ai_governance_ethics" not in classification.primary_domains
    assert "saudi_public_sector" in selected

def test_saudi_jurisdiction_from_issuing_entity():
    classification = classify_rfp(_unesco_ai_state())
    assert classification.jurisdiction == "saudi_arabia"
```

**Step 2:** Run → FAIL
**Step 3:** Update `src/models/routing.py` (add primary_domains, secondary_domains). Update `src/services/routing.py` (weighted scoring with strong/medium/weak tiers, demotion logic, issuing-entity tiebreak, multi-domain pack selection).
**Step 4:** Run → PASS
**Step 5:** Run existing routing tests: `pytest tests/services/test_routing.py -v` → no regressions
**Step 6:** Commit: `git commit -m "feat(routing): multi-label weighted domain classification with primary/secondary split and skeleton pack selection"`

---

### Task 1.3: Build structured ComplianceIndex from hard requirements

**Files:**
- Modify: `src/services/hard_requirement_extractor.py` (add compliance_index builder)
- Modify: `src/pipeline/graph.py` (wire ComplianceIndex into state)
- Test: `tests/services/test_compliance_index_builder.py`

**Step 1: Write failing tests**

```python
# tests/services/test_compliance_index_builder.py
from src.models.claim_provenance import ComplianceIndex, ComplianceIndexEntry
from src.services.hard_requirement_extractor import build_compliance_index
from src.models.conformance import HardRequirement

_ARABIC_ALIASES = {
    "commercial_registration": ["السجل التجاري", "سجل تجاري"],
    "zakat": ["الزكاة", "شهادة الزكاة"],
    "chamber": ["الغرفة التجارية", "اشتراك الغرفة"],
    "saudization": ["السعودة", "شهادة السعودة"],
}

def test_compliance_index_built_from_hard_requirements():
    hrs = [
        HardRequirement(requirement_id="HR-L1-002", category="compliance",
                        subject="Commercial registration", value_text="Valid commercial registration",
                        validation_scope="source_book", severity="critical"),
    ]
    source_book_text = "السجل التجاري ساري المفعول"
    index = build_compliance_index(hrs, source_book_text)
    assert len(index.entries) >= 1
    entry = index.entries[0]
    assert entry.requirement_id == "HR-L1-002"
    assert entry.content_conformance_pass is True

def test_missing_compliance_item():
    hrs = [
        HardRequirement(requirement_id="HR-L1-099", category="compliance",
                        subject="Unknown item", value_text="Some unknown requirement",
                        validation_scope="source_book", severity="critical"),
    ]
    index = build_compliance_index(hrs, "no match here")
    entry = next(e for e in index.entries if e.requirement_id == "HR-L1-099")
    assert entry.response_status == "missing"
    assert entry.content_conformance_pass is False
```

**Step 2:** Run → FAIL
**Step 3:** Add `build_compliance_index()` to hard_requirement_extractor. Uses Arabic alias dictionary for matching. Sets `response_status` based on whether the requirement text (or aliases) appear in the source book structured data.
**Step 4:** Run → PASS
**Step 5:** Commit: `git commit -m "feat(compliance): build structured ComplianceIndex from hard requirements with Arabic alias matching"`

---

### Task 1.4: Rewrite conformance validator to use ComplianceIndex

**Files:**
- Modify: `src/agents/source_book/conformance_validator.py` (new _pass1 reads ComplianceIndex first)
- Test: `tests/agents/test_conformance_structured.py`

**Step 1: Write failing tests against the frozen NCNP fixture**

```python
# tests/agents/test_conformance_structured.py
"""These tests prove the NEW validator fixes the false negatives from the old one."""
import pytest

def test_ncnp_compliance_rows_now_pass():
    """HR-L1-009..014 (compliance certificates) should pass via ComplianceIndex,
    not fail via English keyword scanning."""
    # This test runs the new validator against the NCNP fixture
    # and asserts the 6 compliance false negatives are gone.
    from tests.fixtures.fixture_loader import load_docx_text
    text = load_docx_text("sb-ar-1776112115")

    # Verify the Arabic terms ARE present (fixture invariant)
    assert "السجل التجاري" in text
    assert "الزكاة" in text
    assert "السعودة" in text

    # Build ComplianceIndex from the text
    from src.services.hard_requirement_extractor import build_compliance_index
    from tests.fixtures.fixture_loader import load_conformance_report
    cr = load_conformance_report("sb-ar-1776112115")

    # The old report had these as failures — they should now pass
    previously_failed = {"HR-L1-009", "HR-L1-010", "HR-L1-011",
                         "HR-L1-012", "HR-L1-013", "HR-L1-014"}
    # (actual test implementation will build HRs and run build_compliance_index)
```

**Step 2-5:** Implement, verify, commit.

**Step 6:** Commit: `git commit -m "fix(conformance): ComplianceIndex-first validation — close 6 compliance false negatives on NCNP fixture"`

---

### Task 1.5: RFP fact extraction into ClaimRegistry

**Files:**
- Modify: `src/pipeline/graph.py` (context_node registers rfp_fact claims)
- Test: `tests/pipeline/test_rfp_fact_registration.py`

Extract dates, bid bond, language rules, compliance requirements, deliverable definitions, and evaluation criteria from RFPContext into ClaimRegistry as `rfp_fact` claims with `verified_from_rfp` status. These must NEVER appear in the Engine 2 shopping list.

**Test:**

```python
def test_rfp_facts_not_in_engine2_shopping_list():
    from src.models.engine2_contract import build_engine2_shopping_list
    # Build a registry with both rfp_facts and bidder_claims
    registry = ClaimRegistry()
    registry.register(ClaimProvenance(
        claim_id="RFP-FACT-001", text="مدة العقد 12 شهراً",
        claim_kind="rfp_fact", source_kind="rfp_document",
        verification_status="verified_from_rfp",
    ))
    registry.register(ClaimProvenance(
        claim_id="BIDDER-001", text="SG prior project",
        claim_kind="internal_company_claim", source_kind="internal_backend",
        verification_status="internal_unverified",
        requested_external_contexts=["source_book", "slide_blueprint"],
    ))
    shopping = build_engine2_shopping_list(registry)
    ids = {r.claim_id for r in shopping}
    assert "RFP-FACT-001" not in ids
    assert "BIDDER-001" in ids
    # Verify requested_external_contexts comes from the claim field, not usage_allowed
    bidder_req = next(r for r in shopping if r.claim_id == "BIDDER-001")
    assert bidder_req.requested_external_contexts == ["source_book", "slide_blueprint"]
```

**Commit:** `git commit -m "feat(pipeline): register RFP facts in ClaimRegistry — never sent to Engine 2"`

---

## ── CHECKPOINT: Slice 1 Complete ──

**Acceptance criteria:**
- RFP dates, bid bond, Arabic-language rule, compliance requirements are `verified_from_rfp`, not Engine 2 gaps
- Validator no longer flags present compliance rows as missing (ComplianceIndex-first)
- Routing produces multi-label domains, UNESCO AI ethics RFPs no longer route as `digital_transformation`

**Report:** Full ID-level checkpoint per the reporting format in design doc §5.4.

---

## Slice 2: `internal_company_claim` — Block PRJ/CLI Leakage

### Task 2.1: Engine 2 shopping list builder

**Files:**
- Add `build_engine2_shopping_list()` to `src/models/engine2_contract.py`
- Test: `tests/models/test_engine2_shopping_list.py`

Uses claim properties (not ID prefixes) to filter. Asserts no non-bidder claims leak in.

### Task 2.2: Wire forbidden scanner into conformance validator

**Files:**
- Modify: `src/agents/source_book/conformance_validator.py` (add forbidden scan as Pass 5)
- Test: `tests/agents/test_forbidden_leakage_integration.py`

### Task 2.3: Wire proof-point gating into slide blueprint writer

**Files:**
- Modify: `src/agents/source_book/writer.py` (stage 2a: resolve each proof_point via registry, block if `can_use_as_proof_point()` fails)
- Test: `tests/agents/test_slide_proof_gating.py`

### Task 2.4: Regression test — PRJ-001 blocked on UNESCO fixture

```python
def test_prj_blocked_in_new_pipeline():
    # Run new pipeline logic against UNESCO fixture
    # Assert PRJ-001 not in any client_facing section
    # Assert PRJ-001 only in internal_gap_appendix
```

**Commit after each task.**

---

## ── CHECKPOINT: Slice 2 Complete ──

**Acceptance:** PRJ-001, CLI-002, CLI-003 impossible in client-facing content without `internal_verified` + permissioned.

---

## Slice 3: `external_methodology` — Analogies Cannot Carry Core Proof

### Task 3.1: Evidence relevance classifier

Classify each external source as `direct_topic`, `adjacent_domain`, or `analogical`.

### Task 3.2: Evidence coverage gate

Build `EvidenceCoverageReport` with per-topic direct/adjacent/analogical counts. Only `found_direct >= minimum_direct_sources` passes.

### Task 3.3: Writer integration — analogical sources flagged in source book

### Task 3.4: Regression test — UNESCO fixture evidence coverage

---

## Slice 4: `proposal_option` — Numeric Commitments Not Facts

### Task 4.1: Numeric commitment detector

Scan client-facing sections (not internal notes) for unregistered numeric ranges. Normalize Arabic-Indic digits and range separators.

### Task 4.2: Gate rule — unregistered commitments reject

### Task 4.3: Regression test — "5-8 countries" blocked unless approved

---

## Slice 5: `generated_inference` — Portal, Deliverables, Conflicts

### Task 5.1: Portal inference guard

`PortalExtraction` model, `PORTAL_BRANDS` vs `TEMPLATE_OR_AUTHORITY_BRANDS`, region-aware extraction.

### Task 5.2: Formal deliverable classifier

`DeliverableClassification` model, D-N normalization to workstream IDs when origin is not formal.

### Task 5.3: Source hierarchy conflict resolver

Field-specific `FIELD_SOURCE_HIERARCHY`, `SourceConflict` model, conflict notes registered as `generated_inference`.

### Task 5.4: Regression test — portal not from logo, training not D-3

---

## ── FINAL CHECKPOINT ──

After all 5 slices:

1. Run full regression suite: `pytest tests/ -v`
2. Run both frozen fixtures through the new pipeline
3. Report exact checkpoint format from design doc §5.4
4. Only then: re-run on `data_run` (NCNP) and `data_unesco_ai` (UNESCO)

---

## Sub-skills referenced

- @superpowers:test-driven-development — every task is failing-test-first
- @superpowers:systematic-debugging — if any fixture test fails unexpectedly
- @superpowers:verification-before-completion — run full suite before claiming any slice complete
- @superpowers:executing-plans — REQUIRED at the top of this plan
- @superpowers:finishing-a-development-branch — after final checkpoint

## Prior plan assets retained

- Frozen fixtures: `tests/fixtures/sb-ar-1776112115/`, `tests/fixtures/sb-ar-1777280086/`
- ID-level checkpoint reporting format
- Acceptance gate discipline (no "fixed" without all gates passing)
- STOP-on-regression rule for NEW IDs

## Prior plan implementation superseded

- Bilingual keyword maps as primary validator strategy
- Negation-context regex as primary safeguard
- Validator-only conformance patches
- Prompt-only instructions to prevent leakage
- Document-specific fixes tied to one RFP
