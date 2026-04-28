"""Regression tests for Layer 1 deterministic hard-requirement extraction.

Tests verify that _layer1_extract correctly converts structured RFPContext
fields into HardRequirement objects without any LLM involvement.
"""

from __future__ import annotations

import pytest

from src.models.common import BilingualText
from src.models.conformance import HardRequirement
from src.models.enums import Language
from src.models.rfp import (
    ComplianceRequirement,
    Completeness,
    Deliverable,
    DeliverableSchedule,
    EvaluationCategory,
    EvaluationCriteria,
    ProjectTimeline,
    RFPContext,
    SubmissionFormat,
    TeamRequirement,
)

# The function is module-private; import directly for unit testing.
from src.services.hard_requirement_extractor import _layer1_extract as extract_layer1


# ── Helpers ──────────────────────────────────────────────────────────────


def _minimal_rfp(**overrides) -> RFPContext:
    """Build a minimal valid RFPContext, merging *overrides* on top."""
    defaults = dict(
        rfp_name=BilingualText(en="Test RFP"),
        issuing_entity=BilingualText(en="Test Entity"),
        mandate=BilingualText(en="Test mandate"),
        source_language=Language.EN,
        completeness=Completeness(),
    )
    defaults.update(overrides)
    return RFPContext(**defaults)


# ── Tests ────────────────────────────────────────────────────────────────


class TestLayer1ExtractsAwardMechanism:
    """Layer 1 must emit an HR for non-unknown award_mechanism."""

    def test_layer1_extracts_award_mechanism(self):
        rfp = _minimal_rfp(
            evaluation_criteria=EvaluationCriteria(
                award_mechanism="pass_fail_then_lowest_price",
            ),
        )

        hrs = extract_layer1(rfp)

        award_hrs = [h for h in hrs if h.category == "award_mechanism"]
        assert len(award_hrs) == 1
        hr = award_hrs[0]
        assert "pass_fail" in hr.value_text
        assert hr.confidence == "high"
        assert hr.extraction_method == "context_field"
        assert hr.severity == "critical"


class TestLayer1ExtractsContractDuration:
    """Layer 1 must emit an HR for project_timeline.total_duration_months."""

    def test_layer1_extracts_contract_duration(self):
        rfp = _minimal_rfp(
            project_timeline=ProjectTimeline(
                total_duration="12 months",
                total_duration_months=12,
            ),
        )

        hrs = extract_layer1(rfp)

        dur_hrs = [h for h in hrs if h.category == "contract_duration"]
        assert len(dur_hrs) == 1
        hr = dur_hrs[0]
        assert hr.value_number == 12.0
        assert hr.unit == "months"
        assert hr.severity == "critical"


class TestLayer1ExtractsMandatoryCompliance:
    """Layer 1 must emit one HR per mandatory ComplianceRequirement."""

    def test_layer1_extracts_mandatory_compliance(self):
        rfp = _minimal_rfp(
            compliance_requirements=[
                ComplianceRequirement(
                    id="COMP-001",
                    requirement=BilingualText(en="ISO 27001 certification required"),
                    mandatory=True,
                ),
                ComplianceRequirement(
                    id="COMP-002",
                    requirement=BilingualText(en="Local office presence required"),
                    mandatory=True,
                ),
                ComplianceRequirement(
                    id="COMP-003",
                    requirement=BilingualText(en="Valid trade license"),
                    mandatory=True,
                ),
                ComplianceRequirement(
                    id="COMP-OPT",
                    requirement=BilingualText(en="Optional preference"),
                    mandatory=False,
                ),
            ],
        )

        hrs = extract_layer1(rfp)

        comp_hrs = [h for h in hrs if h.category == "compliance"]
        assert len(comp_hrs) == 3  # only mandatory
        ids = {h.subject for h in comp_hrs}
        assert ids == {"COMP-001", "COMP-002", "COMP-003"}
        for h in comp_hrs:
            assert h.severity == "critical"


class TestLayer1ExtractsTeamRequirements:
    """Layer 1 must emit an HR per TeamRequirement with qualifications."""

    def test_layer1_extracts_team_requirements(self):
        rfp = _minimal_rfp(
            team_requirements=[
                TeamRequirement(
                    role_title=BilingualText(en="Project Manager"),
                    certifications=["PMP"],
                    min_years_experience=5,
                ),
            ],
        )

        hrs = extract_layer1(rfp)

        team_hrs = [h for h in hrs if h.category == "team_qualification"]
        assert len(team_hrs) == 1
        hr = team_hrs[0]
        assert hr.subject == "Project Manager"
        assert "PMP" in hr.value_text
        assert "5+ years" in hr.value_text
        assert hr.value_number == 5.0


class TestLayer1ExtractsMandatoryDeliverables:
    """Layer 1 must emit one HR per mandatory Deliverable."""

    def test_layer1_extracts_mandatory_deliverables(self):
        rfp = _minimal_rfp(
            deliverables=[
                Deliverable(
                    id="DEL-001",
                    description=BilingualText(en="Inception report"),
                    mandatory=True,
                ),
                Deliverable(
                    id="DEL-002",
                    description=BilingualText(en="Final methodology document"),
                    mandatory=True,
                ),
                Deliverable(
                    id="DEL-OPT",
                    description=BilingualText(en="Optional supplementary"),
                    mandatory=False,
                ),
            ],
        )

        hrs = extract_layer1(rfp)

        del_hrs = [h for h in hrs if h.category == "deliverable_required"]
        assert len(del_hrs) == 2  # only mandatory
        del_ids = {h.subject for h in del_hrs}
        assert del_ids == {"DEL-001", "DEL-002"}
        for h in del_hrs:
            assert h.severity == "critical"
            assert h.deliverable_ids == [h.subject]


class TestLayer1ExtractsPassingThreshold:
    """Layer 1 must emit an HR for technical_passing_threshold."""

    def test_layer1_extracts_passing_threshold(self):
        rfp = _minimal_rfp(
            evaluation_criteria=EvaluationCriteria(
                technical_passing_threshold=70.0,
            ),
        )

        hrs = extract_layer1(rfp)

        thresh_hrs = [h for h in hrs if h.category == "minimum_threshold"]
        assert len(thresh_hrs) == 1
        hr = thresh_hrs[0]
        assert hr.value_number == 70.0
        assert hr.unit == "percent"
        assert hr.severity == "critical"


class TestLayer1ExtractsSubmissionFormat:
    """Layer 1 must emit an HR when bank_guarantee_required=True."""

    def test_layer1_extracts_submission_format(self):
        rfp = _minimal_rfp(
            submission_format=SubmissionFormat(
                bank_guarantee_required=True,
            ),
        )

        hrs = extract_layer1(rfp)

        pkg_hrs = [h for h in hrs if h.category == "packaging"]
        assert len(pkg_hrs) >= 1
        bank_hrs = [h for h in pkg_hrs if h.subject == "bank_guarantee"]
        assert len(bank_hrs) == 1
        assert "bank guarantee" in bank_hrs[0].value_text.lower()


class TestLayer1EmptyRFP:
    """Layer 1 on a minimal RFP must produce zero HRs."""

    def test_layer1_empty_rfp_produces_no_hrs(self):
        rfp = _minimal_rfp()

        hrs = extract_layer1(rfp)

        assert hrs == []
