"""AI-powered slide visual design generator using Gemini 3 Pro Image.

Generates beautiful slide background images for each layout type using
Google's Gemini 3 Pro Image model (Nano Banana Pro) via OpenRouter.
The backgrounds contain visual design elements (color blocks, gradients,
shapes, icons) but NO text \u2014 text is overlaid by python-pptx as editable
elements.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from io import BytesIO

import httpx
from PIL import Image

from src.models.enums import LayoutType
from src.models.slides import SlideObject

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_ID = "google/gemini-3-pro-image-preview"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_CONCURRENT = 3
IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080

BRAND_CONFIG = {
    "primary_navy": "#0E2841",
    "accent_teal": "#156082",
    "accent_blue": "#0F9ED5",
    "accent_orange": "#E97132",
    "dark_teal": "#467886",
    "company_name": "Strategic Gears Consulting",
}

DARK_LAYOUTS = {
    LayoutType.TITLE,
    LayoutType.CLOSING,
    LayoutType.STAT_CALLOUT,
    LayoutType.SECTION,
}

_BASE_PROMPT = (
    "Generate a professional consulting presentation slide BACKGROUND IMAGE. "
    "This is ONLY the visual design \u2014 color blocks, shapes, gradients, "
    "decorative elements. Do NOT include any actual text, words, letters, or "
    "numbers in the image. The image will have editable text overlaid on top "
    "later. Aspect ratio: exactly 16:9 (1920x1080 pixels). Brand colors: "
    "navy #0E2841, teal #156082, blue #0F9ED5, orange accent #E97132. Style: "
    "modern executive consulting firm (McKinsey/BCG quality). Clean, minimal, "
    "professional. "
)

LAYOUT_PROMPTS: dict[LayoutType, str] = {
    LayoutType.TITLE: (
        "COVER SLIDE background. Dark navy (#0E2841) gradient from left to "
        "right. Subtle geometric pattern or abstract architectural lines at "
        "15% opacity. Large empty area in center-left for white title text. "
        "Bottom-right area reserved for date and entity name. A thin teal "
        "(#156082) horizontal accent line across the upper third. Elegant, "
        "executive, premium feel. No logos, no text."
    ),
    LayoutType.AGENDA: (
        "AGENDA slide background. White (#FFFFFF) background. Navy (#0E2841) "
        "solid bar across the top, 120px height. On the left side, small teal "
        "(#156082) numbered circles arranged vertically with thin horizontal "
        "lines extending to the right from each circle. Clean structured layout "
        "suggesting a numbered list. Subtle light gray (#F8F8F8) alternating "
        "row bands."
    ),
    LayoutType.CONTENT_1COL: (
        "SINGLE COLUMN CONTENT slide background. White (#FFFFFF) background. "
        "Navy (#0E2841) solid bar across the top, 100px height for the title. "
        "Thin teal (#156082) accent line directly below the navy bar. Large "
        "clean white content area. Subtle light gray (#F2F2F2) footer strip "
        "at the very bottom, 40px height. A small teal square decorative "
        "element in the bottom-right corner."
    ),
    LayoutType.CONTENT_2COL: (
        "TWO COLUMN CONTENT slide background. White (#FFFFFF) background. "
        "Navy (#0E2841) solid bar across the top, 100px height. Thin teal "
        "(#156082) accent line below the header. A subtle thin vertical teal "
        "(#156082) line dividing the content area into two columns. Left and "
        "right areas clearly delineated with equal width. Small decorative "
        "teal squares in the bottom corners."
    ),
    LayoutType.DATA_CHART: (
        "DATA/CHART slide background. White (#FFFFFF) background. Navy "
        "(#0E2841) solid bar across the top, 100px height. Thin teal (#156082) "
        "accent line below the header. Large clean white content area for "
        "chart placement. Very subtle grid pattern at 3% opacity in the "
        "content area."
    ),
    LayoutType.STAT_CALLOUT: (
        "STAT CALLOUT slide background. Dark navy (#0E2841) full background. "
        "A large teal (#156082) rounded rectangle in the center \u2014 approximately "
        "500x300px \u2014 for a big number/statistic to be overlaid. Subtle radiating "
        "lines or geometric patterns from the center. Three smaller rounded "
        "rectangles below for supporting metrics. Premium, infographic feel. "
        "Dark and bold."
    ),
    LayoutType.FRAMEWORK: (
        "METHODOLOGY/FRAMEWORK slide background. White (#FFFFFF) background. "
        "Navy (#0E2841) header bar at top. Four connected rounded rectangles "
        "arranged horizontally across the center \u2014 colored in a gradient: first "
        "navy (#0E2841), second teal (#156082), third blue (#0F9ED5), fourth "
        "lighter blue (#4DB8D9). Directional arrows connecting each rectangle "
        "from left to right. Process flow / methodology diagram style. No text."
    ),
    LayoutType.COMPARISON: (
        "COMPARISON slide background. White (#FFFFFF) background. Navy "
        "(#0E2841) header bar at top. Two distinct panels side by side \u2014 left "
        "panel has a very subtle teal (#156082) tint at 5% opacity, right "
        "panel has a very subtle blue (#0F9ED5) tint at 5% opacity. A thin "
        "navy vertical divider between panels. Each panel has a small colored "
        "header tab at the top."
    ),
    LayoutType.TEAM: (
        "TEAM GRID slide background. White (#FFFFFF) background. Navy "
        "(#0E2841) header bar at top. Thin teal accent line below. A 2-row x "
        "3-column grid of subtle rounded rectangles \u2014 each approximately "
        "280x180px \u2014 with very light teal (#E8F4F8) fill. Small teal (#156082) "
        "circle in the top-left of each card for a role icon placeholder. "
        "Clean, modern team card layout."
    ),
    LayoutType.COMPLIANCE_MATRIX: (
        "COMPLIANCE TABLE slide background. White (#FFFFFF) background. Navy "
        "(#0E2841) header bar at top. A clean table grid: 4 columns, 7 rows. "
        "Top row is solid navy (#0E2841) for column headers. Alternating white "
        "and light gray (#F2F2F2) rows below. Thin light gray (#D0D0D0) "
        "borders between cells."
    ),
    LayoutType.TIMELINE: (
        "PROJECT TIMELINE slide background. White (#FFFFFF) background. Navy "
        "(#0E2841) header bar at top. A horizontal timeline arrow running "
        "across the center, colored in a gradient from navy (#0E2841) to teal "
        "(#156082). 6-7 circular milestone markers evenly spaced along the "
        "arrow in teal. Space above each milestone for labels, below for "
        "descriptions."
    ),
    LayoutType.CLOSING: (
        "CLOSING SLIDE background. Same style as a premium cover. Dark navy "
        "(#0E2841) gradient background. Subtle geometric pattern at 15% "
        "opacity. A thin teal (#156082) horizontal line across the upper "
        "third. Large empty area in center for closing message. Bottom area "
        "for contact details. Elegant, executive."
    ),
    LayoutType.SECTION: (
        "SECTION DIVIDER slide background. Solid navy (#0E2841) background. "
        "A large teal (#156082) diagonal stripe or angular shape from "
        "bottom-left to center-right. Large empty area in the center for "
        "section title in white text. Bold, clean, signaling a transition "
        "to a new section."
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_dark_layout(layout_type: LayoutType) -> bool:
    """Return True if this layout uses a dark background requiring white text."""
    return layout_type in DARK_LAYOUTS


async def generate_slide_background(
    slide: SlideObject,
    slide_number: int,
    total_slides: int,
) -> bytes:
    """Generate a beautiful slide background image using Gemini 3 Pro.

    Returns PNG bytes (1920x1080) for use as slide background.
    """
    prompt = _build_design_prompt(slide.layout_type, slide, slide_number, total_slides)
    image_bytes = await _call_gemini_image(prompt)
    return image_bytes


async def generate_all_backgrounds(
    slides: list[SlideObject],
) -> list[bytes | None]:
    """Generate backgrounds for all slides with concurrency limit.

    Returns list of PNG bytes (or None if generation failed for a slide).
    Processes max MAX_CONCURRENT slides concurrently to respect rate limits.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    total = len(slides)
    total_cost = 0.0

    async def _generate_one(i: int, slide: SlideObject) -> bytes | None:
        async with semaphore:
            try:
                logger.info(
                    "Generating background %d/%d (%s)...",
                    i + 1, total, slide.layout_type,
                )
                start = time.time()
                result = await generate_slide_background(slide, i + 1, total)
                elapsed = time.time() - start
                logger.info(
                    "  Slide %d done in %.1fs (%d KB)",
                    i + 1, elapsed, len(result) // 1024,
                )
                return result
            except Exception as e:
                logger.warning(
                    "Background generation failed for slide %d: %s",
                    i + 1, e,
                )
                return None

    tasks = [_generate_one(i, s) for i, s in enumerate(slides)]
    results = await asyncio.gather(*tasks)

    generated = sum(1 for r in results if r is not None)
    logger.info("Generated %d/%d backgrounds", generated, total)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_design_prompt(
    layout_type: LayoutType,
    slide: SlideObject,
    slide_number: int,
    total_slides: int,
) -> str:
    """Build a layout-specific image generation prompt."""
    specific = LAYOUT_PROMPTS.get(
        layout_type,
        LAYOUT_PROMPTS[LayoutType.CONTENT_1COL],
    )
    return _BASE_PROMPT + specific


async def _call_gemini_image(prompt: str) -> bytes:
    """Call Gemini 3 Pro Image via OpenRouter to generate an image.

    Returns PNG image bytes (1920x1080).
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": prompt}],
            },
        )

    # Check for errors
    if response.status_code != 200:
        raise RuntimeError(
            f"Gemini API error {response.status_code}: "
            f"{response.text[:300]}"
        )

    data = response.json()

    # Extract image from response
    msg = data["choices"][0]["message"]
    images = msg.get("images", [])
    if not images:
        raise RuntimeError("No image returned in Gemini response")

    # Parse base64 data URL
    url = images[0]["image_url"]["url"]
    _, b64data = url.split(",", 1)
    raw_bytes = base64.b64decode(b64data)

    # Ensure correct size
    img = Image.open(BytesIO(raw_bytes))
    if img.size != (IMAGE_WIDTH, IMAGE_HEIGHT):
        img = img.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
