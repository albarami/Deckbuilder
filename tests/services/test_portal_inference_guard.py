"""Portal inference guard — Slice 5.1.

Verifies that the portal extractor refuses to infer a portal name from
logos, headers, footers, watermarks, or template-authority brands. A
portal name is set to "explicit_submission_clause" only when the brand
appears in body / table / submission-clause regions.

Acceptance #5: Portal name cannot be inferred from logo/header/footer/
template authority brands.
"""
from __future__ import annotations

from src.services.portal_inference_guard import (
    PORTAL_BRANDS,
    TEMPLATE_OR_AUTHORITY_BRANDS,
    ExtractedTextSpan,
    PortalExtraction,
    extract_portal,
)


def _span(text: str, region: str = "body") -> ExtractedTextSpan:
    return ExtractedTextSpan(
        text=text,
        page=1,
        region_type=region,  # type: ignore[arg-type]
    )


# ── Default / generic ─────────────────────────────────────────────────


def test_no_brand_yields_default_unknown_portal() -> None:
    portal = extract_portal([_span("Generic prose with no portal mention.")])
    assert portal.portal_name == "البوابة الإلكترونية المعتمدة"
    assert portal.portal_confidence == "unknown_named_portal"
    assert portal.inferred_from_logo is False


# ── Acceptance #5 — never infer portal from logo/header/footer ─────────


def test_etimad_in_logo_does_not_become_explicit() -> None:
    """Even a real portal brand (Etimad) in a LOGO region must not be
    promoted to explicit_submission_clause confidence."""
    portal = extract_portal([_span("Etimad", region="logo")])
    assert portal.portal_confidence != "explicit_submission_clause"
    assert portal.inferred_from_logo is True


def test_etimad_in_header_does_not_become_explicit() -> None:
    portal = extract_portal([_span("منصة اعتماد", region="header")])
    assert portal.portal_confidence != "explicit_submission_clause"


def test_etimad_in_footer_does_not_become_explicit() -> None:
    portal = extract_portal([_span("Etimad", region="footer")])
    assert portal.portal_confidence != "explicit_submission_clause"


def test_template_brand_in_logo_never_becomes_portal() -> None:
    """EXPRO is a template / authority brand — its presence in a LOGO
    must NOT cause the extractor to call it a portal."""
    portal = extract_portal([_span("EXPRO", region="logo")])
    assert portal.portal_confidence != "explicit_submission_clause"
    assert portal.portal_name != "EXPRO"
    assert portal.portal_name != "اكسبرو"


def test_template_brand_in_body_never_becomes_portal() -> None:
    """Even in a BODY region, a template-authority brand must not be
    promoted to a portal — the extractor recognises template brands as
    a separate class."""
    portal = extract_portal([_span(
        "The procurement is published under the EXPRO framework.",
        region="body",
    )])
    assert portal.portal_confidence != "explicit_submission_clause"
    assert "EXPRO" not in portal.portal_name


def test_nupco_in_header_not_portal() -> None:
    portal = extract_portal([_span("NUPCO", region="header")])
    assert portal.portal_confidence != "explicit_submission_clause"


# ── Acceptance #5 — portal IS allowed when explicit in body / table ───


def test_etimad_explicit_in_submission_clause_body() -> None:
    portal = extract_portal([_span(
        "Submit your offer through منصة اعتماد by 2026-05-15.",
        region="body",
    )])
    assert portal.portal_confidence == "explicit_submission_clause"
    assert "اعتماد" in portal.portal_name or portal.portal_name == "Etimad"


def test_etimad_in_table_treated_as_explicit() -> None:
    portal = extract_portal([_span(
        "Submission portal | Etimad",
        region="table",
    )])
    assert portal.portal_confidence == "explicit_submission_clause"


# ── Inferred from logo flag is honest ─────────────────────────────────


def test_inferred_from_logo_true_when_only_logo_match() -> None:
    portal = extract_portal([_span("Etimad", region="logo")])
    assert portal.inferred_from_logo is True


def test_inferred_from_logo_false_when_body_match_present() -> None:
    portal = extract_portal([
        _span("Etimad", region="logo"),
        _span("Submit through Etimad portal.", region="body"),
    ])
    assert portal.inferred_from_logo is False


# ── Brand sets are well-formed ───────────────────────────────────────


def test_portal_brands_include_etimad() -> None:
    assert "Etimad" in PORTAL_BRANDS or "etimad" in {b.lower() for b in PORTAL_BRANDS}
    assert "اعتماد" in PORTAL_BRANDS


def test_template_brands_include_expro() -> None:
    assert "EXPRO" in TEMPLATE_OR_AUTHORITY_BRANDS


def test_brand_sets_are_disjoint() -> None:
    """A brand cannot be both a portal and a template — that would
    defeat the guard."""
    overlap = {b.lower() for b in PORTAL_BRANDS} & {
        b.lower() for b in TEMPLATE_OR_AUTHORITY_BRANDS
    }
    assert overlap == set()


# ── PortalExtraction shape ─────────────────────────────────────────────


def test_portal_extraction_default_construction() -> None:
    p = PortalExtraction()
    assert p.portal_name == "البوابة الإلكترونية المعتمدة"
    assert p.portal_confidence == "unknown_named_portal"
    assert p.source_clause == ""
    assert p.inferred_from_logo is False
