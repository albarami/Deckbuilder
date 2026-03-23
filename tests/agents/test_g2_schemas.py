"""Tests for G2 filler output schemas — structured, validated, no paragraphs.

Tests cover:
1. Schema validation (bullet counts, word limits, essay transitions)
2. Per-section schema compliance
3. Paragraph rejection (anti-paragraph enforcement)
4. Placeholder mapping from schema to injection_data
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.agents.section_fillers.g2_schemas import (
    BulletList,
    Bullets_2_3,
    Bullets_2_4,
    Bullets_3_4,
    Bullets_3_5,
    Bullets_4_6,
    EscalationBlock,
    FourBoxSlide,
    GovernanceOutput,
    GovernanceStructureSlide,
    GovernanceTier,
    HeadingDescriptionContentSlide,
    IntroMessageOutput,
    IntroMessageSlide,
    MethodologyDetailSlide,
    MethodologyFocusedSlide,
    MethodologyOutput,
    MethodologyOverviewSlide,
    MilestoneColumn,
    MilestonesSlide,
    PhaseContent,
    QAReportingSlide,
    QualityGate,
    ReportingBlock,
    SlideOutput,
    TimelineOutput,
    TimelineOverviewSlide,
    TimelinePhaseBlock,
    TocOutput,
    TocRow,
    TocSlide,
    TwoColumnSlide,
    UnderstandingOutput,
    contains_unapproved_english,
)

# ── Bullet list constraint tests ─────────────────────────────────────────


class TestBulletConstraints:
    """Bullet list types enforce item count and content rules."""

    def test_bullets_2_3_accepts_2(self):
        b = Bullets_2_3(items=["Point A", "Point B"])
        assert len(b.items) == 2

    def test_bullets_2_3_accepts_3(self):
        b = Bullets_2_3(items=["A", "B", "C"])
        assert len(b.items) == 3

    def test_bullets_2_3_rejects_4(self):
        with pytest.raises(ValidationError, match="at most 3"):
            Bullets_2_3(items=["A", "B", "C", "D"])

    def test_bullets_2_3_rejects_1(self):
        with pytest.raises(ValidationError, match="at least 2"):
            Bullets_2_3(items=["A"])

    def test_bullets_3_4_rejects_2(self):
        with pytest.raises(ValidationError, match="at least 3"):
            Bullets_3_4(items=["A", "B"])

    def test_bullets_3_5_accepts_5(self):
        b = Bullets_3_5(items=["A", "B", "C", "D", "E"])
        assert len(b.items) == 5

    def test_bullets_4_6_rejects_3(self):
        with pytest.raises(ValidationError, match="at least 4"):
            Bullets_4_6(items=["A", "B", "C"])

    def test_bullets_4_6_accepts_6(self):
        b = Bullets_4_6(items=["A", "B", "C", "D", "E", "F"])
        assert len(b.items) == 6

    def test_word_count_over_25_rejected(self):
        """Anti-paragraph: bullets >25 words are rejected."""
        long_bullet = " ".join(["word"] * 26)
        with pytest.raises(ValidationError, match="exceeds 25 words"):
            Bullets_2_3(items=[long_bullet, "ok"])

    def test_word_count_exactly_25_accepted(self):
        bullet_25 = " ".join(["word"] * 25)
        b = Bullets_2_3(items=[bullet_25, "ok"])
        assert len(b.items) == 2

    def test_essay_transition_furthermore_rejected(self):
        """Anti-essay: 'Furthermore' opener is rejected."""
        with pytest.raises(ValidationError, match="Essay transition"):
            Bullets_2_3(items=["Furthermore this is wrong", "ok"])

    def test_essay_transition_moreover_rejected(self):
        with pytest.raises(ValidationError, match="Essay transition"):
            Bullets_3_4(items=["Moreover we should note", "ok", "ok"])

    def test_essay_transition_in_addition_rejected(self):
        with pytest.raises(ValidationError, match="Essay transition"):
            Bullets_2_4(items=["In addition to this", "ok"])

    def test_essay_transition_additionally_rejected(self):
        with pytest.raises(ValidationError, match="Essay transition"):
            BulletList(items=["Additionally we need", "ok"])

    def test_essay_transition_it_is_worth_noting_rejected(self):
        with pytest.raises(ValidationError, match="Essay transition"):
            Bullets_2_3(items=["It is worth noting that", "ok"])

    def test_clean_bullets_accepted(self):
        """Bullets starting with action verbs pass."""
        b = Bullets_3_4(items=[
            "Deploy cloud infrastructure within 4 weeks",
            "Establish governance framework for PMO",
            "Conduct stakeholder alignment workshops",
        ])
        assert len(b.items) == 3


# ── Title constraints ────────────────────────────────────────────────────


class TestTitleConstraints:
    """SlideOutput title enforcement."""

    def test_title_10_words_accepted(self):
        s = SlideOutput(title="One Two Three Four Five Six Seven Eight Nine Ten")
        assert len(s.title.split()) == 10

    def test_title_over_15_words_truncated(self):
        """SlideOutput truncates titles over 15 words instead of crashing."""
        s = SlideOutput(
            title="One Two Three Four Five Six Seven Eight Nine Ten "
                  "Eleven Twelve Thirteen Fourteen Fifteen Sixteen",
        )
        assert len(s.title.split()) == 15

    def test_intro_title_12_words_accepted(self):
        """IntroMessageSlide allows up to 12 words."""
        slide = IntroMessageSlide(
            title="IT Infrastructure Modernization for Kingdom of Saudi Arabia Government",
            client_name="Ministry of ICT",
            scope_line="End-to-end IT modernization",
            attr_duration="16 weeks",
            attr_sector="Government / ICT",
            attr_geography="KSA - Riyadh",
            attr_service_line="Digital Transformation",
        )
        assert len(slide.title.split()) <= 12

    def test_intro_title_13_words_rejected(self):
        with pytest.raises(ValidationError, match="exceeds 12 words"):
            IntroMessageSlide(
                title="One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen",
                client_name="Client",
                scope_line="Scope",
                attr_duration="16 weeks",
                attr_sector="Gov",
                attr_geography="KSA",
                attr_service_line="Advisory",
            )


# ── IntroMessage schema ──────────────────────────────────────────────────


class TestIntroMessageSchema:
    """IntroMessageOutput structured validation."""

    def _make_valid_intro(self) -> IntroMessageOutput:
        return IntroMessageOutput(
            section_id="section_00",
            language="en",
            slide=IntroMessageSlide(
                title="IT Infrastructure Modernization Program",
                client_name="Ministry of Communications and IT",
                scope_line="End-to-end IT infrastructure modernization advisory",
                attr_duration="16 weeks",
                attr_sector="Government / ICT",
                attr_geography="KSA - Riyadh",
                attr_service_line="Digital Transformation",
            ),
        )

    def test_valid_intro_accepted(self):
        output = self._make_valid_intro()
        assert output.slide.client_name == "Ministry of Communications and IT"

    def test_scope_line_over_15_words_rejected(self):
        with pytest.raises(ValidationError, match="exceeds 15 words"):
            IntroMessageSlide(
                title="Test Title",
                client_name="Client",
                scope_line=" ".join(["word"] * 16),
                attr_duration="16 weeks",
                attr_sector="Gov",
                attr_geography="KSA",
                attr_service_line="Advisory",
            )

    def test_client_name_over_60_chars_rejected(self):
        with pytest.raises(ValidationError):
            IntroMessageSlide(
                title="Test",
                client_name="A" * 61,
                scope_line="Scope",
                attr_duration="16 weeks",
                attr_sector="Gov",
                attr_geography="KSA",
                attr_service_line="Advisory",
            )

    def test_all_fields_required(self):
        """Missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            IntroMessageSlide(
                title="Test",
                client_name="Client",
                # scope_line missing
                attr_duration="16 weeks",
                attr_sector="Gov",
                attr_geography="KSA",
                attr_service_line="Advisory",
            )


# ── Introduction filler injection mapping ────────────────────────────────


class TestIntroInjectionMapping:
    """Introduction filler produces correct injection_data."""

    def test_injection_data_maps_all_fields(self):
        from src.agents.section_fillers.introduction import (
            build_intro_injection,
        )

        slide = IntroMessageSlide(
            title="IT Modernization Program",
            client_name="Ministry of ICT",
            scope_line="End-to-end IT modernization advisory",
            attr_duration="16 weeks",
            attr_sector="Government / ICT",
            attr_geography="KSA - Riyadh",
            attr_service_line="Digital Advisory",
        )
        data = build_intro_injection(slide)

        assert data["title"] == "IT Modernization Program"
        body = data["body_contents"]
        assert body[1] == "Ministry of ICT"
        assert body[13] == "End-to-end IT modernization advisory"
        assert body[14] == "16 weeks"
        assert body[15] == "Government / ICT"
        assert body[16] == "KSA - Riyadh"
        assert body[17] == "Digital Advisory"

    def test_injection_data_has_7_fields(self):
        """7 placeholder slots: title + 6 body_contents."""
        from src.agents.section_fillers.introduction import (
            build_intro_injection,
        )

        slide = IntroMessageSlide(
            title="Title",
            client_name="Client",
            scope_line="Scope line here",
            attr_duration="16 weeks",
            attr_sector="Gov",
            attr_geography="KSA",
            attr_service_line="Advisory",
        )
        data = build_intro_injection(slide)
        assert "title" in data
        assert len(data["body_contents"]) == 6


# ── Methodology schema ───────────────────────────────────────────────────


def _make_phase(n: int) -> PhaseContent:
    return PhaseContent(
        phase_number=n,
        phase_title=f"Phase {n} Title",
        phase_activities=Bullets_3_5(items=[
            f"Activity {n}.1 for this phase",
            f"Activity {n}.2 for this phase",
            f"Activity {n}.3 for this phase",
        ]),
    )


def _make_detail(n: int) -> MethodologyDetailSlide:
    return MethodologyDetailSlide(
        title=f"Phase {n} Deep Dive",
        phase_number=n,
        activities=Bullets_3_5(items=[
            f"Work item {n}.1",
            f"Work item {n}.2",
            f"Work item {n}.3",
        ]),
        deliverables=Bullets_3_5(items=[
            f"Deliverable {n}.1",
            f"Deliverable {n}.2",
            f"Deliverable {n}.3",
        ]),
        frameworks=Bullets_2_4(items=["TOGAF 10", "PMBOK Guide"]),
    )


def _make_focused(n: int, phases: list[PhaseContent]) -> MethodologyFocusedSlide:
    return MethodologyFocusedSlide(
        title=f"Focus Phase {n}",
        focused_phase_number=n,
        phases=phases,
    )


class TestMethodologySchema:
    """MethodologyOutput phase count and overflow rules."""

    def test_valid_4_phase_no_overflow(self):
        phases = [_make_phase(i) for i in range(1, 5)]
        output = MethodologyOutput(
            section_id="section_03",
            language="en",
            overview=MethodologyOverviewSlide(
                title="Our Approach",
                subtitle="Agile Transformation",
                phases=phases,
            ),
            focused_slides=[_make_focused(i, phases) for i in range(1, 5)],
            detail_slides=[_make_detail(i) for i in range(1, 5)],
        )
        assert output.phase_5_overflow is None

    def test_valid_3_phase(self):
        phases = [_make_phase(i) for i in range(1, 4)]
        output = MethodologyOutput(
            section_id="section_03",
            language="en",
            overview=MethodologyOverviewSlide(
                title="Our Approach",
                subtitle="Three Phase Method",
                phases=phases,
            ),
            focused_slides=[_make_focused(i, phases) for i in range(1, 4)],
            detail_slides=[_make_detail(i) for i in range(1, 4)],
        )
        assert len(output.overview.phases) == 3

    def test_valid_5_phase_with_overflow(self):
        phases = [_make_phase(i) for i in range(1, 5)]
        output = MethodologyOutput(
            section_id="section_03",
            language="en",
            overview=MethodologyOverviewSlide(
                title="Our Approach",
                subtitle="Five Phase Method",
                phases=phases,
            ),
            focused_slides=[_make_focused(i, phases) for i in range(1, 5)],
            detail_slides=[_make_detail(i) for i in range(1, 5)],
            phase_5_overflow=_make_detail(5),
        )
        assert output.phase_5_overflow is not None
        assert output.phase_5_overflow.phase_number == 5

    def test_3_phase_with_overflow_rejected(self):
        """3-phase engagement must NOT have overflow."""
        phases = [_make_phase(i) for i in range(1, 4)]
        with pytest.raises(ValidationError, match="must NOT have phase_5_overflow"):
            MethodologyOutput(
                section_id="section_03",
                language="en",
                overview=MethodologyOverviewSlide(
                    title="Our Approach",
                    subtitle="Method",
                    phases=phases,
                ),
                focused_slides=[_make_focused(i, phases) for i in range(1, 4)],
                detail_slides=[_make_detail(i) for i in range(1, 4)],
                phase_5_overflow=_make_detail(5),
            )

    def test_overflow_wrong_phase_number_rejected(self):
        """Overflow must be phase 5, not phase 3."""
        phases = [_make_phase(i) for i in range(1, 5)]
        with pytest.raises(ValidationError, match="phase_5_overflow must be phase 5"):
            MethodologyOutput(
                section_id="section_03",
                language="en",
                overview=MethodologyOverviewSlide(
                    title="Our Approach",
                    subtitle="Method",
                    phases=phases,
                ),
                focused_slides=[_make_focused(i, phases) for i in range(1, 5)],
                detail_slides=[_make_detail(i) for i in range(1, 5)],
                phase_5_overflow=_make_detail(3),
            )

    def test_focused_count_mismatch_rejected(self):
        """Focused slide count must match grid phase count.

        Note: min_length=3 on focused_slides fires before model_validator,
        so with only 1 focused slide, the field-level constraint triggers.
        """
        phases = [_make_phase(i) for i in range(1, 5)]
        with pytest.raises(ValidationError):
            MethodologyOutput(
                section_id="section_03",
                language="en",
                overview=MethodologyOverviewSlide(
                    title="Approach",
                    subtitle="Method",
                    phases=phases,
                ),
                focused_slides=[_make_focused(1, phases)],  # only 1
                detail_slides=[_make_detail(i) for i in range(1, 5)],
            )

    def test_duplicate_focused_phases_rejected(self):
        """Each focused slide must highlight a different phase."""
        phases = [_make_phase(i) for i in range(1, 5)]
        with pytest.raises(ValidationError, match="Duplicate focused"):
            MethodologyOutput(
                section_id="section_03",
                language="en",
                overview=MethodologyOverviewSlide(
                    title="Approach",
                    subtitle="Method",
                    phases=phases,
                ),
                focused_slides=[
                    _make_focused(1, phases),
                    _make_focused(1, phases),  # duplicate
                    _make_focused(2, phases),
                    _make_focused(3, phases),
                ],
                detail_slides=[_make_detail(i) for i in range(1, 5)],
            )

    def test_phase_title_over_5_words_truncated(self):
        """PhaseContent truncates phase_title to 5 words instead of crashing."""
        pc = PhaseContent(
            phase_number=1,
            phase_title="This Phase Title Is Way Too Long",
            phase_activities=Bullets_3_5(items=["a", "b", "c"]),
        )
        assert len(pc.phase_title.split()) == 5

    def test_paragraph_in_activity_rejected(self):
        """Anti-paragraph: activity bullet >25 words is rejected."""
        long_activity = " ".join(["conduct"] + ["detailed"] * 25)
        with pytest.raises(ValidationError, match="exceeds 25 words"):
            PhaseContent(
                phase_number=1,
                phase_title="Discovery",
                phase_activities=Bullets_3_5(items=[
                    long_activity, "ok", "ok",
                ]),
            )

    def test_overview_duplicate_phase_numbers_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate phase numbers"):
            MethodologyOverviewSlide(
                title="Approach",
                subtitle="Method",
                phases=[_make_phase(1), _make_phase(1), _make_phase(2)],
            )

    def test_overview_phase_5_in_grid_rejected(self):
        with pytest.raises(ValidationError, match="phases 1-4"):
            MethodologyOverviewSlide(
                title="Approach",
                subtitle="Method",
                phases=[_make_phase(1), _make_phase(2), _make_phase(5)],
            )


# ── Methodology injection mapping ────────────────────────────────────────


class TestMethodologyInjectionMapping:
    """Methodology filler injection_data builders produce correct output."""

    def test_overview_injection_maps_phase_titles(self):
        from src.agents.section_fillers.methodology import (
            build_overview_injection,
        )

        phases = [_make_phase(i) for i in range(1, 5)]
        overview = MethodologyOverviewSlide(
            title="Our Approach",
            subtitle="Agile Delivery",
            phases=phases,
            cross_cutting_themes=["Change Management", "Data Governance"],
        )
        data = build_overview_injection(overview, 4)
        body = data["body_contents"]

        # Phase titles at correct indices
        assert body[41] == "Phase 1 Title"  # phase_1_title
        assert body[33] == "Phase 2 Title"  # phase_2_title
        assert body[37] == "Phase 3 Title"  # phase_3_title
        assert body[42] == "Phase 4 Title"  # phase_4_title
        # Subtitle
        assert body[13] == "Agile Delivery"
        # Cross-cutting themes
        assert body[44] == "Change Management"
        assert body[45] == "Data Governance"

    def test_overview_injection_activities_are_joined_bullets(self):
        """Activities are newline-joined from typed Bullets_3_5, not prose."""
        from src.agents.section_fillers.methodology import (
            build_overview_injection,
        )

        phases = [_make_phase(i) for i in range(1, 5)]
        overview = MethodologyOverviewSlide(
            title="Approach",
            subtitle="Method",
            phases=phases,
        )
        data = build_overview_injection(overview, 4)
        body = data["body_contents"]

        # phase_1_content at idx 23 should be newline-joined
        content = body[23]
        assert "\n" in content
        assert "Activity 1.1" in content

    def test_detail_injection_maps_3_zones(self):
        from src.agents.section_fillers.methodology import (
            build_detail_injection,
        )

        detail = _make_detail(2)
        data = build_detail_injection(detail)

        assert data["title"] == "Phase 2 Deep Dive"
        body = data["body_contents"]
        assert 42 in body  # activities
        assert 43 in body  # deliverables
        assert 44 in body  # frameworks
        # All are newline-joined bullet strings
        assert "\n" in body[42]
        assert "Work item 2.1" in body[42]
        assert "Deliverable 2.1" in body[43]
        assert "TOGAF 10" in body[44]

    def test_detail_injection_no_paragraphs(self):
        """Detail zones contain newline-joined bullets, not paragraphs."""
        from src.agents.section_fillers.methodology import (
            build_detail_injection,
        )

        detail = _make_detail(1)
        data = build_detail_injection(detail)
        body = data["body_contents"]

        # No zone should contain ". " followed by a capital letter (prose)
        for idx, text in body.items():
            # Should be newline-separated bullets
            lines = text.split("\n")
            assert len(lines) >= 2, f"idx {idx} has <2 lines: {text!r}"

    def test_focused_injection_has_title_and_body(self):
        from src.agents.section_fillers.methodology import (
            build_focused_injection,
        )

        phases = [_make_phase(i) for i in range(1, 5)]
        focused = MethodologyFocusedSlide(
            title="Phase 2 Focus",
            focused_phase_number=2,
            phases=phases,
        )
        data = build_focused_injection(focused, 4)

        assert data["title"] == "Phase 2 Focus"
        body = data["body_contents"]
        assert 41 in body  # phase_1_title
        assert 23 in body  # phase_1_content


# ── Understanding schema ─────────────────────────────────────────────────


class TestUnderstandingSchema:
    """UnderstandingOutput multi-zone slide validation."""

    def _make_valid_understanding(self) -> UnderstandingOutput:
        return UnderstandingOutput(
            section_id="section_01",
            language="en",
            slide_1_strategic_context=TwoColumnSlide(
                title="Strategic Context",
                left_subtitle="Regulatory Drivers",
                left_evidence=Bullets_3_4(items=[
                    "NTP 2025 mandates digital-first services",
                    "MoICT regulatory framework requires audit",
                    "Vision 2030 program alignment deadline Q4",
                ]),
                right_subtitle="Operational Challenges",
                right_evidence=Bullets_3_4(items=[
                    "Legacy infrastructure at 78% capacity",
                    "3 critical systems past end-of-life",
                    "Annual downtime cost exceeds SAR 4.2M",
                ]),
            ),
            slide_2_core_challenges=FourBoxSlide(
                title="Core Challenges",
                box_1=Bullets_2_3(items=[
                    "Fragmented IT landscape across 12 entities",
                    "No unified service catalog or CMDB",
                ]),
                box_2=Bullets_2_3(items=[
                    "Skills gap in cloud and cybersecurity",
                    "Attrition rate 23% in IT division",
                ]),
                box_3=Bullets_2_3(items=[
                    "Budget constraints limiting modernization",
                    "Procurement cycle averaging 14 months",
                ]),
                box_4=Bullets_2_3(items=[
                    "No enterprise architecture governance",
                    "Shadow IT estimated at 35% of spend",
                ]),
            ),
            slide_3_success_definition=HeadingDescriptionContentSlide(
                title="Defining Success",
                description="Measurable outcomes aligned with NTP targets",
                outcomes=Bullets_4_6(items=[
                    "Reduce system downtime by 60% within 12 months",
                    "Consolidate from 47 to 12 core platforms",
                    "Achieve ISO 27001 certification for all entities",
                    "Deploy unified service portal by Q3 2026",
                ]),
            ),
        )

    def test_valid_understanding_accepted(self):
        output = self._make_valid_understanding()
        assert output.slide_1_strategic_context.left_subtitle == "Regulatory Drivers"

    def test_description_over_30_words_rejected(self):
        with pytest.raises(ValidationError, match="exceeds 30 words"):
            HeadingDescriptionContentSlide(
                title="Success",
                description=" ".join(["word"] * 31),
                outcomes=Bullets_4_6(items=["a", "b", "c", "d"]),
            )

    def test_left_evidence_under_3_rejected(self):
        with pytest.raises(ValidationError, match="at least 3"):
            TwoColumnSlide(
                title="Context",
                left_subtitle="Left",
                left_evidence=Bullets_3_4(items=["only one", "only two"]),
                right_subtitle="Right",
                right_evidence=Bullets_3_4(items=["a", "b", "c"]),
            )

    def test_paragraph_in_evidence_rejected(self):
        """Anti-paragraph: evidence bullet >25 words is rejected."""
        long = " ".join(["analysis"] * 26)
        with pytest.raises(ValidationError, match="exceeds 25 words"):
            TwoColumnSlide(
                title="Context",
                left_subtitle="Left",
                left_evidence=Bullets_3_4(items=[long, "ok", "ok"]),
                right_subtitle="Right",
                right_evidence=Bullets_3_4(items=["a", "b", "c"]),
            )


# ── Understanding injection mapping ──────────────────────────────────────


class TestUnderstandingInjectionMapping:
    """Understanding filler injection_data builders produce correct output."""

    def test_slide_1_two_column_injection(self):
        from src.agents.section_fillers.understanding import (
            build_slide_1_injection,
        )

        slide = TwoColumnSlide(
            title="Strategic Context",
            left_subtitle="Regulatory Drivers",
            left_evidence=Bullets_3_4(items=[
                "NTP 2025 mandates digital-first",
                "MoICT framework requires audit",
                "Vision 2030 alignment deadline Q4",
            ]),
            right_subtitle="Operational Challenges",
            right_evidence=Bullets_3_4(items=[
                "Legacy infrastructure at 78% capacity",
                "3 critical systems past end-of-life",
                "Annual downtime cost exceeds SAR 4.2M",
            ]),
        )
        data = build_slide_1_injection(slide)

        assert data["title"] == "Strategic Context"
        body = data["body_contents"]
        assert body[1] == "Regulatory Drivers"
        assert body[3] == "Operational Challenges"
        # OBJECT placeholders — newline-joined bullets
        assert "\n" in body[2]
        assert "NTP 2025" in body[2]
        assert "\n" in body[4]
        assert "Legacy infrastructure" in body[4]

    def test_slide_2_four_box_injection(self):
        from src.agents.section_fillers.understanding import (
            build_slide_2_injection,
        )

        slide = FourBoxSlide(
            title="Core Challenges",
            box_1=Bullets_2_3(items=["Fragmented IT landscape", "No unified CMDB"]),
            box_2=Bullets_2_3(items=["Skills gap in cloud", "23% attrition rate"]),
            box_3=Bullets_2_3(items=["Budget constraints", "14-month procurement"]),
            box_4=Bullets_2_3(items=["No EA governance", "35% shadow IT spend"]),
        )
        data = build_slide_2_injection(slide)

        assert data["title"] == "Core Challenges"
        body = data["body_contents"]
        assert body[1] == "Fragmented IT landscape\nNo unified CMDB"
        assert body[2] == "Skills gap in cloud\n23% attrition rate"
        assert body[13] == "Budget constraints\n14-month procurement"
        assert body[14] == "No EA governance\n35% shadow IT spend"

    def test_slide_3_success_definition_injection(self):
        from src.agents.section_fillers.understanding import (
            build_slide_3_injection,
        )

        slide = HeadingDescriptionContentSlide(
            title="Defining Success",
            description="Measurable outcomes aligned with NTP targets",
            outcomes=Bullets_4_6(items=[
                "Reduce downtime by 60% within 12 months",
                "Consolidate from 47 to 12 platforms",
                "Achieve ISO 27001 certification",
                "Deploy unified portal by Q3 2026",
            ]),
        )
        data = build_slide_3_injection(slide)

        assert data["title"] == "Defining Success"
        assert data["body"] == "Measurable outcomes aligned with NTP targets"
        obj = data["object_contents"]
        assert 1 in obj  # OBJECT at idx 1
        assert "\n" in obj[1]
        assert "Reduce downtime" in obj[1]

    def test_slide_3_no_paragraphs_in_outcomes(self):
        """Outcomes are newline-joined bullets, not paragraphs."""
        from src.agents.section_fillers.understanding import (
            build_slide_3_injection,
        )

        slide = HeadingDescriptionContentSlide(
            title="Success",
            description="Measurable outcomes for client",
            outcomes=Bullets_4_6(items=[
                "Outcome one here",
                "Outcome two here",
                "Outcome three here",
                "Outcome four here",
            ]),
        )
        data = build_slide_3_injection(slide)
        text = data["object_contents"][1]
        lines = text.split("\n")
        assert len(lines) == 4


# ── Timeline schema ──────────────────────────────────────────────────────


def _make_timeline_block(n: int) -> TimelinePhaseBlock:
    return TimelinePhaseBlock(
        phase_number=n,
        phase_name=f"Phase {n}",
        week_range=f"Weeks {(n-1)*4+1}-{n*4}",
        key_activities=Bullets_2_3(items=[
            f"Activity {n}.1",
            f"Activity {n}.2",
        ]),
    )


class TestTimelineSchema:
    """TimelineOutput multi-zone validation."""

    def test_valid_timeline_accepted(self):
        output = TimelineOutput(
            section_id="section_04",
            language="en",
            slide_1_overview=TimelineOverviewSlide(
                title="Implementation Timeline",
                box_1=_make_timeline_block(1),
                box_2=_make_timeline_block(2),
                box_3=_make_timeline_block(3),
                box_4=_make_timeline_block(4),
            ),
            slide_2_milestones=MilestonesSlide(
                title="Milestones and Deliverables",
                left_column=MilestoneColumn(
                    subtitle="Phases 1-2",
                    deliverables=BulletList(items=[
                        "Current state assessment report",
                        "Target architecture blueprint",
                    ]),
                ),
                right_column=MilestoneColumn(
                    subtitle="Phases 3-5",
                    deliverables=BulletList(items=[
                        "Migration execution plan",
                        "Go-live readiness checklist",
                    ]),
                ),
            ),
        )
        assert output.slide_1_overview.box_1.phase_number == 1

    def test_duplicate_phase_numbers_rejected(self):
        with pytest.raises(ValidationError, match="distinct phase numbers"):
            TimelineOverviewSlide(
                title="Timeline",
                box_1=_make_timeline_block(1),
                box_2=_make_timeline_block(1),  # duplicate
                box_3=_make_timeline_block(3),
                box_4=_make_timeline_block(4),
            )

    def test_paragraph_in_activity_rejected(self):
        """Anti-paragraph: timeline activity >25 words rejected."""
        long = " ".join(["deploy"] * 26)
        with pytest.raises(ValidationError, match="exceeds 25 words"):
            TimelinePhaseBlock(
                phase_number=1,
                phase_name="Phase 1",
                week_range="Weeks 1-4",
                key_activities=Bullets_2_3(items=[long, "ok"]),
            )


# ── Timeline injection mapping ───────────────────────────────────────────


class TestTimelineInjectionMapping:
    """Timeline filler injection_data builders produce correct output."""

    def test_slide_1_timeline_overview_injection(self):
        from src.agents.section_fillers.timeline import (
            build_slide_1_injection,
        )

        slide = TimelineOverviewSlide(
            title="16-Week Delivery Timeline",
            box_1=_make_timeline_block(1),
            box_2=_make_timeline_block(2),
            box_3=_make_timeline_block(3),
            box_4=_make_timeline_block(4),
        )
        data = build_slide_1_injection(slide)

        assert data["title"] == "16-Week Delivery Timeline"
        body = data["body_contents"]
        # Box 1 at OBJECT idx 1 — formatted as "Phase 1 | Weeks 1-4\n..."
        assert "Phase 1 | Weeks 1-4" in body[1]
        assert "Activity 1.1" in body[1]
        # Box 4 at OBJECT idx 14
        assert "Phase 4 | Weeks 13-16" in body[14]

    def test_slide_1_no_paragraphs_in_boxes(self):
        """Timeline boxes contain structured header+bullets, not prose."""
        from src.agents.section_fillers.timeline import (
            build_slide_1_injection,
        )

        slide = TimelineOverviewSlide(
            title="Timeline",
            box_1=_make_timeline_block(1),
            box_2=_make_timeline_block(2),
            box_3=_make_timeline_block(3),
            box_4=_make_timeline_block(4),
        )
        data = build_slide_1_injection(slide)
        body = data["body_contents"]

        for idx in (1, 2, 13, 14):
            lines = body[idx].split("\n")
            assert len(lines) >= 3, f"idx {idx}: expected >=3 lines, got {len(lines)}"

    def test_slide_2_milestones_injection(self):
        from src.agents.section_fillers.timeline import (
            build_slide_2_injection,
        )

        slide = MilestonesSlide(
            title="Milestones and Deliverables",
            left_column=MilestoneColumn(
                subtitle="Phases 1-2",
                deliverables=BulletList(items=[
                    "Current state assessment report",
                    "Target architecture blueprint",
                ]),
            ),
            right_column=MilestoneColumn(
                subtitle="Phases 3-5",
                deliverables=BulletList(items=[
                    "Migration execution plan",
                    "Go-live readiness checklist",
                ]),
            ),
        )
        data = build_slide_2_injection(slide)

        assert data["title"] == "Milestones and Deliverables"
        body = data["body_contents"]
        assert body[1] == "Phases 1-2"  # left subtitle
        assert body[3] == "Phases 3-5"  # right subtitle
        assert "\n" in body[2]  # left deliverables joined
        assert "Current state assessment report" in body[2]
        assert "\n" in body[4]  # right deliverables joined


# ── Governance schema ────────────────────────────────────────────────────


class TestGovernanceSchema:
    """GovernanceOutput multi-zone validation."""

    def _make_valid_governance(self) -> GovernanceOutput:
        return GovernanceOutput(
            section_id="section_06",
            language="en",
            slide_1_structure=GovernanceStructureSlide(
                title="Project Governance Framework",
                tier_1=GovernanceTier(
                    tier_name="STEERING COMMITTEE",
                    members="CIO, Program Director, SG Partner",
                    cadence="Monthly",
                    responsibilities=Bullets_2_4(items=[
                        "Strategic direction and priority alignment",
                        "Budget approval and resource allocation",
                    ]),
                ),
                tier_2=GovernanceTier(
                    tier_name="PROJECT BOARD",
                    members="PMO Lead, Tech Lead, Client PM",
                    cadence="Bi-weekly",
                    responsibilities=Bullets_2_4(items=[
                        "Milestone tracking and risk mitigation",
                        "Cross-workstream dependency management",
                    ]),
                ),
                tier_3=GovernanceTier(
                    tier_name="WORKING TEAMS",
                    members="Stream leads, SMEs, Client analysts",
                    cadence="Weekly",
                    responsibilities=Bullets_2_4(items=[
                        "Sprint execution and deliverable production",
                        "Technical issue resolution and escalation",
                    ]),
                ),
                escalation=EscalationBlock(
                    triggers=Bullets_3_4(items=[
                        "Schedule variance exceeding 2 weeks",
                        "Budget overrun above 10% threshold",
                        "Critical dependency blocker unresolved 5 days",
                    ]),
                ),
            ),
            slide_2_qa_reporting=QAReportingSlide(
                title="QA and Reporting Framework",
                reporting_blocks=[
                    ReportingBlock(
                        cadence="Weekly",
                        report_name="Status Report",
                        audience="Project Board",
                        items=Bullets_2_3(items=[
                            "Sprint progress and blockers",
                            "Risk register updates",
                        ]),
                    ),
                    ReportingBlock(
                        cadence="Monthly",
                        report_name="Steering Dashboard",
                        audience="Steering Committee",
                        items=Bullets_2_3(items=[
                            "KPI dashboard with trend analysis",
                            "Budget utilization and forecast",
                        ]),
                    ),
                ],
                quality_gates=[
                    QualityGate(
                        gate_name="Phase Exit Gate",
                        criteria=Bullets_2_3(items=[
                            "All deliverables accepted by client PM",
                            "Zero critical defects outstanding",
                        ]),
                        sign_off_authority="Project Board",
                    ),
                    QualityGate(
                        gate_name="Go-Live Readiness Gate",
                        criteria=Bullets_2_3(items=[
                            "UAT completion with 95% pass rate",
                            "Rollback plan documented and tested",
                        ]),
                        sign_off_authority="Steering Committee",
                    ),
                ],
            ),
        )

    def test_valid_governance_accepted(self):
        output = self._make_valid_governance()
        assert output.slide_1_structure.tier_1.tier_name == "STEERING COMMITTEE"

    def test_cadence_required_nonempty(self):
        with pytest.raises(ValidationError):
            GovernanceTier(
                tier_name="TEST",
                members="Members",
                cadence="",  # min_length=1
                responsibilities=Bullets_2_4(items=["a", "b"]),
            )

    def test_paragraph_in_responsibility_rejected(self):
        """Anti-paragraph: responsibility >25 words rejected."""
        long = " ".join(["manage"] * 26)
        with pytest.raises(ValidationError, match="exceeds 25 words"):
            GovernanceTier(
                tier_name="TEST",
                members="Members",
                cadence="Weekly",
                responsibilities=Bullets_2_4(items=[long, "ok"]),
            )

    def test_escalation_under_3_triggers_rejected(self):
        with pytest.raises(ValidationError, match="at least 3"):
            EscalationBlock(
                triggers=Bullets_3_4(items=["only one", "only two"]),
            )


# ── Governance injection mapping ─────────────────────────────────────────


class TestGovernanceInjectionMapping:
    """Governance filler injection_data builders produce correct output."""

    def _make_structure_slide(self) -> GovernanceStructureSlide:
        return GovernanceStructureSlide(
            title="Project Governance Framework",
            tier_1=GovernanceTier(
                tier_name="STEERING COMMITTEE",
                members="CIO, Program Director, SG Partner",
                cadence="Monthly",
                responsibilities=Bullets_2_4(items=[
                    "Strategic direction and priority alignment",
                    "Budget approval and resource allocation",
                ]),
            ),
            tier_2=GovernanceTier(
                tier_name="PROJECT BOARD",
                members="PMO Lead, Tech Lead, Client PM",
                cadence="Bi-weekly",
                responsibilities=Bullets_2_4(items=[
                    "Milestone tracking and risk mitigation",
                    "Cross-workstream dependency management",
                ]),
            ),
            tier_3=GovernanceTier(
                tier_name="WORKING TEAMS",
                members="Stream leads, SMEs",
                cadence="Weekly",
                responsibilities=Bullets_2_4(items=[
                    "Sprint execution and deliverable production",
                    "Technical issue resolution",
                ]),
            ),
            escalation=EscalationBlock(
                triggers=Bullets_3_4(items=[
                    "Schedule variance exceeding 2 weeks",
                    "Budget overrun above 10% threshold",
                    "Critical dependency blocker unresolved 5 days",
                ]),
            ),
        )

    def test_slide_1_governance_structure_injection(self):
        from src.agents.section_fillers.governance import (
            build_slide_1_injection,
        )

        slide = self._make_structure_slide()
        data = build_slide_1_injection(slide)

        assert data["title"] == "Project Governance Framework"
        body = data["body_contents"]
        # Tier 1 at OBJECT idx 1
        assert "STEERING COMMITTEE | Monthly" in body[1]
        assert "CIO, Program Director" in body[1]
        assert "Strategic direction" in body[1]
        # Tier 3 at OBJECT idx 13
        assert "WORKING TEAMS | Weekly" in body[13]
        # Escalation at OBJECT idx 14
        assert "ESCALATION TRIGGERS" in body[14]
        assert "Schedule variance" in body[14]

    def test_slide_1_no_paragraphs_in_tiers(self):
        """Tier blocks contain structured header+bullets, not prose."""
        from src.agents.section_fillers.governance import (
            build_slide_1_injection,
        )

        slide = self._make_structure_slide()
        data = build_slide_1_injection(slide)
        body = data["body_contents"]

        for idx in (1, 2, 13, 14):
            lines = body[idx].split("\n")
            assert len(lines) >= 3, f"idx {idx}: expected >=3 lines"

    def test_slide_2_qa_reporting_injection(self):
        from src.agents.section_fillers.governance import (
            build_slide_2_injection,
        )

        slide = QAReportingSlide(
            title="QA and Reporting Framework",
            reporting_blocks=[
                ReportingBlock(
                    cadence="Weekly",
                    report_name="Status Report",
                    audience="Project Board",
                    items=Bullets_2_3(items=[
                        "Sprint progress and blockers",
                        "Risk register updates",
                    ]),
                ),
                ReportingBlock(
                    cadence="Monthly",
                    report_name="Steering Dashboard",
                    audience="Steering Committee",
                    items=Bullets_2_3(items=[
                        "KPI dashboard with trend analysis",
                        "Budget utilization and forecast",
                    ]),
                ),
            ],
            quality_gates=[
                QualityGate(
                    gate_name="Phase Exit Gate",
                    criteria=Bullets_2_3(items=[
                        "All deliverables accepted by client PM",
                        "Zero critical defects outstanding",
                    ]),
                    sign_off_authority="Project Board",
                ),
                QualityGate(
                    gate_name="Go-Live Readiness Gate",
                    criteria=Bullets_2_3(items=[
                        "UAT completion with 95% pass rate",
                        "Rollback plan documented and tested",
                    ]),
                    sign_off_authority="Steering Committee",
                ),
            ],
        )
        data = build_slide_2_injection(slide)

        assert data["title"] == "QA and Reporting Framework"
        body = data["body_contents"]
        assert body[1] == "Reporting Cadence"  # left subtitle
        assert body[3] == "Quality Gates"  # right subtitle
        # Left OBJECT — reporting blocks
        assert "Status Report | Weekly" in body[2]
        assert "Steering Dashboard | Monthly" in body[2]
        # Right OBJECT — quality gates
        assert "Phase Exit Gate" in body[4]
        assert "Sign-off: Project Board" in body[4]


# ── Arabic enforcement ───────────────────────────────────────────────────


class TestArabicEnforcement:
    """Arabic-specific content validation."""

    def test_approved_english_terms_pass(self):
        assert not contains_unapproved_english("SAP ERP KPI", "ar")

    def test_unapproved_english_detected(self):
        assert contains_unapproved_english("The strategic roadmap plan", "ar")

    def test_english_mode_always_passes(self):
        assert not contains_unapproved_english("Any English text here", "en")

    def test_single_letter_ignored(self):
        """Single letters are not flagged."""
        assert not contains_unapproved_english("A B C", "ar")


# ── ToC schema ───────────────────────────────────────────────────────────


class TestTocSchema:
    """TocOutput validation."""

    def test_valid_toc_accepted(self):
        output = TocOutput(
            section_id="section_toc",
            language="en",
            slide=TocSlide(
                title="Table of Contents",
                rows=[
                    TocRow(section_number=1, section_name="Understanding"),
                    TocRow(section_number=2, section_name="Why Strategic Gears"),
                    TocRow(section_number=3, section_name="Methodology"),
                ],
            ),
        )
        assert len(output.slide.rows) == 3

    def test_toc_under_3_rows_rejected(self):
        with pytest.raises(ValidationError, match="at least 3"):
            TocSlide(
                title="Contents",
                rows=[
                    TocRow(section_number=1, section_name="A"),
                    TocRow(section_number=2, section_name="B"),
                ],
            )

    def test_toc_section_number_zero_rejected(self):
        with pytest.raises(ValidationError):
            TocRow(section_number=0, section_name="Invalid")
