"""Tests for Phase G Quality Gate — hard rules, scored metrics, fail-close.

Tests organized by:
  1. Hard rejection rules (R2-R10) — ENFORCEABLE_NOW
  2. Pending-extension findings (P1-P3)
  3. Scored metrics (S1-S4)
  4. Integration test — fail-close via render_v2 path
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agents.section_fillers.g2_schemas import (
    Bullets_2_4,
    Bullets_3_5,
    MethodologyDetailSlide,
    MethodologyFocusedSlide,
    MethodologyOutput,
    MethodologyOverviewSlide,
    PhaseContent,
)
from src.services.placeholder_injectors import InjectionResult
from src.services.quality_gate import (
    REQUIRED_SECTIONS,
    QualityGateResult,
    _check_r2_prose_detection,
    _check_r3_methodology_structure,
    _check_r4_methodology_phase_count,
    _check_r5_section_presence,
    _check_r7_empty_renderable_slides,
    _check_r8_placeholder_markers,
    _check_r9_internal_notes,
    _check_r10_arabic_purity,
    _collect_pending_findings,
    _score_s1_methodology_structure,
    _score_s2_section_completeness,
    _score_s3_content_density,
    _score_s4_arabic_integrity,
    run_quality_gate,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _make_record(
    layout: str = "content_heading_desc",
    section_id: str = "section_01",
    injection_data: dict | None = None,
    entry_type: str = "b_variable",
) -> dict:
    return {
        "semantic_layout_id": layout,
        "section_id": section_id,
        "injection_data": injection_data,
        "entry_type": entry_type,
    }


def _make_phases(
    count: int = 4,
    duplicate_titles: bool = False,
) -> list[PhaseContent]:
    """Build a list of PhaseContent for testing."""
    return [
        PhaseContent(
            phase_number=i + 1,
            phase_title="Same Title" if duplicate_titles
            else f"Phase {i + 1}",
            phase_activities=Bullets_3_5(items=[
                f"Activity {i + 1}.1",
                f"Activity {i + 1}.2",
                f"Activity {i + 1}.3",
            ]),
        )
        for i in range(count)
    ]


def _make_methodology_output(
    phase_count: int = 4,
    with_overflow: bool = False,
    duplicate_focused: bool = False,
    empty_detail_zone: bool = False,
    duplicate_overview: bool = False,
) -> MethodologyOutput:
    """Build a valid MethodologyOutput for testing."""
    # Grid phases are capped at 4; overflow uses phase 5 detail
    grid_count = min(phase_count, 4)
    phases = _make_phases(
        count=grid_count,
        duplicate_titles=duplicate_overview,
    )

    overview = MethodologyOverviewSlide(
        title="Methodology Overview",
        subtitle="Our Approach",
        phases=phases,
    )

    focused = [
        MethodologyFocusedSlide(
            title=f"Phase {i + 1} Focus" if not duplicate_focused
            else "Same Focus",
            focused_phase_number=i + 1,
            phases=phases,
        )
        for i in range(grid_count)
    ]

    detail = [
        MethodologyDetailSlide(
            phase_number=i + 1,
            title=f"Phase {i + 1} Detail",
            activities=Bullets_3_5(items=[
                f"Detail act {i + 1}.1", f"Detail act {i + 1}.2",
                f"Detail act {i + 1}.3",
            ] if not (empty_detail_zone and i == 0) else [
                "a", "b", "c",
            ]),
            deliverables=Bullets_3_5(items=[
                f"Deliv {i + 1}.1", f"Deliv {i + 1}.2",
                f"Deliv {i + 1}.3",
            ]),
            frameworks=Bullets_2_4(items=[
                f"Tool {i + 1}.1", f"Tool {i + 1}.2",
            ] if not (empty_detail_zone and i == 0) else [
                "x", "y",
            ]),
        )
        for i in range(grid_count)
    ]

    overflow = None
    if with_overflow and grid_count == 4:
        overflow = MethodologyDetailSlide(
            phase_number=5,
            title="Phase 5 Detail",
            activities=Bullets_3_5(items=[
                "Overflow act 1", "Overflow act 2", "Overflow act 3",
            ]),
            deliverables=Bullets_3_5(items=[
                "Overflow del 1", "Overflow del 2", "Overflow del 3",
            ]),
            frameworks=Bullets_2_4(items=[
                "Overflow fw 1", "Overflow fw 2",
            ]),
        )

    return MethodologyOutput(
        section_id="section_03",
        language="en",
        overview=overview,
        focused_slides=focused,
        detail_slides=detail,
        phase_5_overflow=overflow,
    )


def _all_sections_records() -> list[dict]:
    """Generate records covering all required sections."""
    records = []
    for section_id in sorted(REQUIRED_SECTIONS):
        records.append(_make_record(
            section_id=section_id,
            injection_data={"title": f"Title for {section_id}"},
        ))
    return records


# ── R2: Prose detection ────────────────────────────────────────────────


class TestR2ProseDetection:
    def test_structured_bullets_pass(self):
        """5 bullets each <=25 words should pass."""
        record = _make_record(injection_data={
            "body": "First bullet point\nSecond bullet\nThird point\n"
                    "Fourth item\nFifth item",
        })
        assert _check_r2_prose_detection([record]) == []

    def test_prose_paragraph_fails(self):
        """30 words without linebreak should fail."""
        long_prose = " ".join(["word"] * 30)
        record = _make_record(injection_data={"body": long_prose})
        failures = _check_r2_prose_detection([record])
        assert len(failures) == 1
        assert "R2" in failures[0]
        assert "30 consecutive words" in failures[0]

    def test_exactly_25_words_passes(self):
        """Exactly 25 words without linebreak should pass."""
        text = " ".join(["word"] * 25)
        record = _make_record(injection_data={"body": text})
        assert _check_r2_prose_detection([record]) == []

    def test_extension_layout_skipped(self):
        """REQUIRES_EXTENSION layouts are not checked."""
        long_prose = " ".join(["word"] * 30)
        record = _make_record(
            layout="layout_heading_and_4_boxes_of_content",
            injection_data={"body": long_prose},
        )
        assert _check_r2_prose_detection([record]) == []


# ── R3: Methodology phase structure ────────────────────────────────────


class TestR3MethodologyStructure:
    def test_valid_4_phase_passes(self):
        meth = _make_methodology_output(phase_count=4)
        failures = _check_r3_methodology_structure(
            {"section_03": meth}, [],
        )
        assert failures == []

    def test_duplicate_focused_titles_fails(self):
        meth = _make_methodology_output(
            phase_count=4, duplicate_focused=True,
        )
        failures = _check_r3_methodology_structure(
            {"section_03": meth}, [],
        )
        assert any("duplicate titles" in f for f in failures)

    def test_duplicate_overview_titles_fails(self):
        meth = _make_methodology_output(
            phase_count=4, duplicate_overview=True,
        )
        failures = _check_r3_methodology_structure(
            {"section_03": meth}, [],
        )
        assert any("duplicate phase titles" in f for f in failures)

    def test_missing_methodology_output_fails(self):
        failures = _check_r3_methodology_structure({}, [])
        assert any("No MethodologyOutput" in f for f in failures)


# ── R4: Methodology phase count ────────────────────────────────────────


class TestR4MethodologyPhaseCount:
    def test_valid_3_phase_passes(self):
        meth = _make_methodology_output(phase_count=3)
        assert _check_r4_methodology_phase_count(
            {"section_03": meth}, [],
        ) == []

    def test_valid_4_phase_passes(self):
        meth = _make_methodology_output(phase_count=4)
        assert _check_r4_methodology_phase_count(
            {"section_03": meth}, [],
        ) == []

    def test_valid_5_phase_passes(self):
        meth = _make_methodology_output(
            phase_count=4, with_overflow=True,
        )
        assert _check_r4_methodology_phase_count(
            {"section_03": meth}, [],
        ) == []


# ── R5: Section presence ──────────────────────────────────────────────


class TestR5SectionPresence:
    def test_all_sections_present_passes(self):
        records = _all_sections_records()
        assert _check_r5_section_presence(records) == []

    def test_missing_governance_fails(self):
        records = [
            r for r in _all_sections_records()
            if r["section_id"] != "section_06"
        ]
        failures = _check_r5_section_presence(records)
        assert any("section_06" in f for f in failures)

    def test_missing_case_studies_fails(self):
        records = [
            r for r in _all_sections_records()
            if r["section_id"] != "section_07"
        ]
        failures = _check_r5_section_presence(records)
        assert any("section_07" in f for f in failures)


# ── R7: Empty renderable slide detection ──────────────────────────────


class TestR7EmptyRenderableSlides:
    def test_all_populated_passes(self):
        records = [
            _make_record(injection_data={"title": "T"})
            for _ in range(10)
        ]
        inj = [
            InjectionResult(
                semantic_layout_id="content_heading_desc",
                injected=(MagicMock(),),
            )
            for _ in range(10)
        ]
        assert _check_r7_empty_renderable_slides(records, inj) == []

    def test_15_percent_empty_fails(self):
        """15% empty exceeds 10% threshold."""
        records = [
            _make_record(injection_data={"title": "T"})
            for _ in range(20)
        ]
        inj = []
        for i in range(20):
            if i < 3:  # 3/20 = 15%
                inj.append(InjectionResult(
                    semantic_layout_id="content_heading_desc",
                    injected=(),
                ))
            else:
                inj.append(InjectionResult(
                    semantic_layout_id="content_heading_desc",
                    injected=(MagicMock(),),
                ))
        failures = _check_r7_empty_renderable_slides(records, inj)
        assert len(failures) == 1
        assert "R7" in failures[0]

    def test_8_percent_empty_passes(self):
        """8% empty is below 10% threshold."""
        records = [
            _make_record(injection_data={"title": "T"})
            for _ in range(25)
        ]
        inj = []
        for i in range(25):
            if i < 2:  # 2/25 = 8%
                inj.append(InjectionResult(
                    semantic_layout_id="content_heading_desc",
                    injected=(),
                ))
            else:
                inj.append(InjectionResult(
                    semantic_layout_id="content_heading_desc",
                    injected=(MagicMock(),),
                ))
        assert _check_r7_empty_renderable_slides(records, inj) == []


# ── R8: Placeholder marker detection ──────────────────────────────────


class TestR8PlaceholderMarkers:
    def test_clean_text_passes(self):
        record = _make_record(injection_data={"body": "Clean content"})
        assert _check_r8_placeholder_markers([record]) == []

    def test_tbd_marker_fails(self):
        record = _make_record(injection_data={"body": "Status: [TBD]"})
        failures = _check_r8_placeholder_markers([record])
        assert len(failures) == 1
        assert "R8" in failures[0]

    def test_tbc_marker_fails(self):
        record = _make_record(injection_data={"body": "Value: [TBC]"})
        assert len(_check_r8_placeholder_markers([record])) == 1

    def test_todo_marker_fails(self):
        record = _make_record(injection_data={"body": "TODO fix this"})
        assert len(_check_r8_placeholder_markers([record])) == 1

    def test_fixme_marker_fails(self):
        record = _make_record(injection_data={"body": "FIXME broken"})
        assert len(_check_r8_placeholder_markers([record])) == 1

    def test_double_brace_fails(self):
        record = _make_record(
            injection_data={"body": "Hello {{client_name}}"},
        )
        assert len(_check_r8_placeholder_markers([record])) == 1

    def test_gap_marker_fails(self):
        record = _make_record(injection_data={"body": "See GAP-001"})
        assert len(_check_r8_placeholder_markers([record])) == 1

    def test_insert_marker_fails(self):
        record = _make_record(
            injection_data={"body": "[INSERT client name here]"},
        )
        assert len(_check_r8_placeholder_markers([record])) == 1


# ── R9: Internal note detection ───────────────────────────────────────


class TestR9InternalNotes:
    def test_clean_text_passes(self):
        record = _make_record(injection_data={"body": "Clean content"})
        assert _check_r9_internal_notes([record]) == []

    def test_internal_note_fails(self):
        record = _make_record(
            injection_data={"body": "[INTERNAL: remove before send]"},
        )
        failures = _check_r9_internal_notes([record])
        assert len(failures) == 1
        assert "R9" in failures[0]

    def test_note_marker_fails(self):
        record = _make_record(
            injection_data={"body": "[NOTE: check with team]"},
        )
        assert len(_check_r9_internal_notes([record])) == 1

    def test_draft_marker_fails(self):
        record = _make_record(
            injection_data={"body": "[DRAFT version 2]"},
        )
        assert len(_check_r9_internal_notes([record])) == 1


# ── R10: Arabic purity ────────────────────────────────────────────────


class TestR10ArabicPurity:
    def test_english_mode_skipped(self):
        record = _make_record(injection_data={"body": "English text"})
        assert _check_r10_arabic_purity([record], "en") == []

    def test_approved_term_passes(self):
        record = _make_record(
            injection_data={"body": "TOGAF framework"},
        )
        # In AR mode, "framework" is unapproved but "TOGAF" is approved
        failures = _check_r10_arabic_purity([record], "ar")
        assert any("framework" in f for f in failures)

    def test_unapproved_english_fails(self):
        record = _make_record(
            injection_data={"body": "implementation strategy"},
        )
        failures = _check_r10_arabic_purity([record], "ar")
        assert len(failures) >= 1
        assert "R10" in failures[0]

    def test_all_approved_passes(self):
        record = _make_record(
            injection_data={"body": "SAP ERP KPI"},
        )
        assert _check_r10_arabic_purity([record], "ar") == []

    def test_extension_layout_skipped(self):
        """REQUIRES_EXTENSION layouts are not checked in AR mode."""
        record = _make_record(
            layout="layout_heading_and_4_boxes_of_content",
            injection_data={"body": "implementation"},
        )
        assert _check_r10_arabic_purity([record], "ar") == []


# ── Pending-extension findings ─────────────────────────────────────────


class TestPendingFindings:
    def test_understanding_extension_layout_recorded(self):
        record = _make_record(
            layout="layout_heading_and_two_content_with_tiltes",
            section_id="section_01",
        )
        findings = _collect_pending_findings([record])
        assert len(findings) == 1
        assert "P1" in findings[0]

    def test_timeline_extension_layout_recorded(self):
        record = _make_record(
            layout="layout_heading_and_4_boxes_of_content",
            section_id="section_04",
        )
        findings = _collect_pending_findings([record])
        assert len(findings) == 1
        assert "P2" in findings[0]

    def test_governance_extension_layout_recorded(self):
        record = _make_record(
            layout="layout_heading_and_two_content_with_tiltes",
            section_id="section_06",
        )
        findings = _collect_pending_findings([record])
        assert len(findings) == 1
        assert "P3" in findings[0]

    def test_renderable_layout_not_recorded(self):
        record = _make_record(
            layout="content_heading_desc",
            section_id="section_01",
        )
        assert _collect_pending_findings([record]) == []


# ── Scored metrics ─────────────────────────────────────────────────────


class TestS1MethodologyScore:
    def test_valid_4_phase_scores_high(self):
        meth = _make_methodology_output(phase_count=4)
        score = _score_s1_methodology_structure({"section_03": meth})
        assert score >= 80.0

    def test_no_methodology_scores_zero(self):
        assert _score_s1_methodology_structure({}) == 0.0


class TestS2SectionCompleteness:
    def test_all_sections_scores_100(self):
        records = _all_sections_records()
        score = _score_s2_section_completeness(records)
        assert score == 100.0

    def test_missing_sections_scores_lower(self):
        records = [
            r for r in _all_sections_records()
            if r["section_id"] != "section_03"  # -18 points
        ]
        score = _score_s2_section_completeness(records)
        assert score == 82.0


class TestS3ContentDensity:
    def test_clean_content_scores_high(self):
        records = [
            _make_record(injection_data={
                "title": "Understanding the Challenge",
                "body": "Point one\nPoint two\nPoint three",
            })
            for _ in range(5)
        ]
        score = _score_s3_content_density(records)
        assert score >= 80.0

    def test_prose_content_scores_lower(self):
        long_prose = " ".join(["word"] * 30)
        records = [
            _make_record(injection_data={"body": long_prose})
            for _ in range(5)
        ]
        score = _score_s3_content_density(records)
        assert score < 80.0


class TestS4ArabicIntegrity:
    def test_english_mode_returns_none(self):
        assert _score_s4_arabic_integrity([], "en") is None

    def test_clean_arabic_scores_100(self):
        records = [
            _make_record(injection_data={"body": "SAP ERP"})
        ]
        score = _score_s4_arabic_integrity(records, "ar")
        assert score == 100.0

    def test_english_contamination_scores_lower(self):
        records = [
            _make_record(injection_data={
                "body": "implementation strategy roadmap",
            })
        ]
        score = _score_s4_arabic_integrity(records, "ar")
        assert score is not None
        assert score < 100.0


# ── run_quality_gate integration ───────────────────────────────────────


class TestRunQualityGate:
    def test_clean_deck_passes(self):
        """A deck with all sections, clean content, and valid methodology."""
        records = _all_sections_records()
        meth = _make_methodology_output(phase_count=4)
        result = run_quality_gate(
            records=records,
            filler_outputs={"section_03": meth},
        )
        assert result.passed
        assert result.hard_failures == []

    def test_prose_causes_rejection(self):
        """Prose in a renderable zone causes hard failure."""
        records = _all_sections_records()
        records[0]["injection_data"]["body"] = " ".join(["word"] * 30)
        meth = _make_methodology_output(phase_count=4)
        result = run_quality_gate(
            records=records,
            filler_outputs={"section_03": meth},
        )
        assert not result.passed
        assert any("R2" in f for f in result.hard_failures)

    def test_placeholder_marker_causes_rejection(self):
        """[TBD] in slide causes hard failure."""
        records = _all_sections_records()
        records[0]["injection_data"]["body"] = "Status [TBD]"
        meth = _make_methodology_output(phase_count=4)
        result = run_quality_gate(
            records=records,
            filler_outputs={"section_03": meth},
        )
        assert not result.passed
        assert any("R8" in f for f in result.hard_failures)

    def test_scores_computed_even_on_failure(self):
        """Scores are always computed, even when deck is rejected."""
        records = _all_sections_records()
        records[0]["injection_data"]["body"] = " ".join(["word"] * 30)
        meth = _make_methodology_output(phase_count=4)
        result = run_quality_gate(
            records=records,
            filler_outputs={"section_03": meth},
        )
        assert not result.passed
        # Scores still computed
        assert result.methodology_structure_score > 0
        assert result.section_completeness_score > 0

    def test_pending_findings_do_not_block(self):
        """Extension layout findings are recorded but don't cause failure."""
        records = _all_sections_records()
        # Add an extension layout slide
        records.append(_make_record(
            layout="layout_heading_and_4_boxes_of_content",
            section_id="section_01",
        ))
        meth = _make_methodology_output(phase_count=4)
        result = run_quality_gate(
            records=records,
            filler_outputs={"section_03": meth},
        )
        assert result.passed
        assert len(result.pending_findings) >= 1
        assert any("P1" in f for f in result.pending_findings)


# ── Fail-close integration via render_v2 ──────────────────────────────


class TestQualityGateFailCloseInRenderV2:
    """Proves that quality gate rejection prevents PPTX save in render_v2."""

    @patch("src.services.renderer_v2.load_registry")
    @patch("src.services.renderer_v2.build_contracts_from_catalog_lock")
    @patch("src.services.renderer_v2.load_a2_allowlists")
    @patch("src.services.renderer_v2.validate_manifest")
    @patch("src.services.renderer_v2.verify_zero_placeholders")
    @patch("src.services.renderer_v2._render_entry")
    @patch("src.services.renderer_v2.run_quality_gate")
    def test_quality_gate_rejection_prevents_save(
        self,
        mock_qg,
        mock_render_entry,
        mock_zero_ph,
        mock_validate,
        mock_allowlists,
        mock_contracts,
        mock_registry,
    ):
        """When quality gate returns passed=False, render_v2 adds error
        and returns without saving."""
        from pathlib import Path

        from src.models.proposal_manifest import (
            ContentSourcePolicy,
            ManifestEntry,
            ProposalManifest,
        )
        from src.services.renderer_v2 import (
            PlaceholderAuditResult,
            SlideRenderRecord,
            render_v2,
        )

        # Set up mocks
        reg = MagicMock()
        reg.template_hash = "hash123"
        mock_registry.return_value = reg

        mock_contracts.return_value = {}
        mock_allowlists.return_value = {}
        mock_validate.return_value = []

        # _render_entry returns a clean record (no error)
        clean_record = SlideRenderRecord(
            manifest_index=0,
            entry_type="b_variable",
            asset_id="test",
            semantic_layout_id="content_heading_desc",
            section_id="section_01",
        )
        mock_render_entry.return_value = clean_record

        # Zero-placeholder audit passes
        mock_zero_ph.return_value = PlaceholderAuditResult()

        # Quality gate returns REJECTED
        mock_qg.return_value = QualityGateResult(
            passed=False,
            hard_failures=["R8: Placeholder marker [TBD] found on slide 3"],
        )

        tm = MagicMock()
        tm.template_hash = "hash123"
        tm.add_slide_from_layout.return_value = MagicMock()
        tm.save.return_value = Path("/output.pptx")

        manifest = ProposalManifest(entries=[
            ManifestEntry(
                entry_type="b_variable",
                asset_id="test",
                semantic_layout_id="content_heading_desc",
                content_source_policy=ContentSourcePolicy.PROPOSAL_SPECIFIC,
                section_id="section_01",
                injection_data={"title": "Test [TBD]"},
            ),
        ])

        result = render_v2(
            manifest, tm,
            Path("/fake/catalog.json"),
            Path("/fake/output.pptx"),
        )

        # Verify: PPTX was NOT saved
        tm.save.assert_not_called()
        # Verify: render_errors populated with quality gate message
        assert any("Quality gate REJECTED" in e for e in result.render_errors)
        # Verify: quality gate result attached
        assert result.quality_gate is not None
        assert not result.quality_gate.passed
