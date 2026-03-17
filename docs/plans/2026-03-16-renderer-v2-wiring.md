# Renderer V2 Pipeline Wiring — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire renderer_v2 (template-anchored, manifest-driven) as the default renderer in the live pipeline, replacing the legacy renderer that produces plain-text slides.

**Architecture:** The 5-turn iterative builder produces `WrittenSlides` (list of `SlideObject`). A new manifest builder converts these to a `ProposalManifest` (ordered list of `ManifestEntry` with semantic layout IDs, entry types, and injection data). The pipeline's `render_node` dispatches to `renderer_v2.render_v2()` which uses the `.potx` template and catalog lock to produce branded PPTX output.

**Tech Stack:** Python 3.12, python-pptx, LangGraph, Pydantic, pytest

---

## Root Cause Summary

The pipeline defaults to `RendererMode.LEGACY` which calls `renderer.py` — producing plain text on generic layouts. The `renderer_v2.py` (template-anchored, manifest-driven) exists and passes all 17 acceptance gates but is never called because:

1. `DeckForgeState.renderer_mode` defaults to `LEGACY`
2. No manifest builder exists to convert `WrittenSlides` → `ProposalManifest`
3. `_build_initial_state()` in `pipeline_runtime.py` never sets `renderer_mode`
4. `design_tokens.py` and `density_scorer.py` source files were never committed

---

### Task 1: Recover design_tokens.py from bytecode

**Files:**
- Create: `src/services/design_tokens.py`
- Reference: `src/services/__pycache__/design_tokens.cpython-312.pyc` (bytecode to recover from)

**Step 1: Reconstruct design_tokens.py from bytecode constants**

Use the bytecode dump (constants, class names, field names) to reconstruct the module. The .pyc reveals:
- `_Palette` frozen dataclass: NAVY, TEAL, ORANGE, GREEN, BLUE, DARK_TEAL, WHITE, LIGHT_GRAY, MID_GRAY, DARK_TEXT, STATUS_GREEN/AMBER/RED, STATUS_GREEN/AMBER/RED_BG
- `_Typography` frozen dataclass: HEADING_FONT="Aptos Display", BODY_FONT="Aptos", sizes (TITLE_BAR_PT, KEY_MESSAGE_PT, BODY_PT, BODY_SUB_PT, STAT_BIG_PT, etc.)
- `Region` dataclass: left, top, width, height (floats)
- `_ContentLayout` frozen dataclass: margin_left, margin_right, title_top, title_height, content_width, body_top, body_height, footer_top, footer_height
- `_TableTokens` frozen dataclass: dimensions and proportions for tables
- `_FlowTokens` frozen dataclass: process flow step-box rendering dimensions
- `_Spacing` frozen dataclass: paragraph spacing in points
- `_OverflowThresholds` frozen dataclass: content limits for overflow detection
- `_StatChipTokens` frozen dataclass: stat chip rendering dimensions

Values come from the existing `formatting.py` constants (NAVY=#0E2841, TEAL=#156082, etc.) and template measurements.

**Step 2: Verify the reconstructed module imports cleanly**

Run: `cd C:\Projects\Deckbuilder\.claude\worktrees\nostalgic-nash && python -c "from src.services.design_tokens import Palette, Typography, ContentLayout; print(Palette.NAVY)"`
Expected: `RGBColor(0x0E, 0x28, 0x41)` or similar

**Step 3: Commit**
```bash
git add src/services/design_tokens.py
git commit -m "fix: recover design_tokens.py source from bytecode"
```

---

### Task 2: Recover density_scorer.py from bytecode

**Files:**
- Create: `src/services/density_scorer.py`
- Reference: `src/services/__pycache__/density_scorer.cpython-312.pyc`

**Step 1: Reconstruct density_scorer.py from bytecode constants**

Use the bytecode dump to reconstruct the density scoring module.

**Step 2: Verify imports**

Run: `python -c "from src.services.density_scorer import DensityScorer; print('OK')"`
Expected: `OK`

**Step 3: Commit**
```bash
git add src/services/density_scorer.py
git commit -m "fix: recover density_scorer.py source from bytecode"
```

---

### Task 3: Build manifest bridge — WrittenSlides → ProposalManifest

This is the critical missing piece. The 5-turn builder outputs `WrittenSlides` (list of `SlideObject`), but renderer_v2 expects a `ProposalManifest` (list of `ManifestEntry`).

**Files:**
- Create: `src/services/manifest_builder.py`
- Test: `tests/services/test_manifest_builder.py`

**Step 1: Write the failing test**

```python
def test_build_manifest_from_written_slides():
    """WrittenSlides should be converted to a valid ProposalManifest."""
    from src.services.manifest_builder import build_manifest_from_slides
    # Create minimal WrittenSlides fixture with various layout types
    # Assert: result is a ProposalManifest
    # Assert: entry count matches slide count + house slides
    # Assert: each entry has semantic_layout_id, section_id, entry_type
    # Assert: validate_manifest(result) returns empty error list
```

**Step 2: Implement manifest_builder.py**

The manifest builder must:
1. Accept `WrittenSlides`, RFP context (geography, sector, mode), and catalog lock path
2. Create the ordered entry list:
   - Cover section: proposal_cover (a2_shell), intro_message (a2_shell), toc_agenda (a2_shell)
   - Section dividers: a2_shell entries for each section break
   - Content slides: b_variable entries mapping SlideObject.layout_type → semantic_layout_id
   - Case studies: pool_clone entries selected from catalog lock
   - Team bios: pool_clone entries selected from catalog lock
   - Company profile: a1_clone entries based on inclusion policy depth
   - Closing: a1_clone entries (know_more, contact)
3. Map SlideObject fields to injection_data:
   - title → injection_data["title"]
   - body_content.text_elements → injection_data["body"] (joined)
   - key_message → injection_data["bold_body_lead"]
4. Map LayoutType → semantic_layout_id:
   - CONTENT_1COL → "content_heading_desc"
   - CONTENT_2COL → "content_heading_content"
   - FRAMEWORK → "content_heading_desc"
   - COMPARISON → "content_heading_content"
   - STAT_CALLOUT → "content_heading_desc"
   - TEAM → "team_two_members" (pool_clone)
   - TIMELINE → "content_heading_content"
   - COMPLIANCE_MATRIX → "content_heading_desc"
   - SECTION → section_divider_XX (a2_shell)
5. Apply HouseInclusionPolicy for standard proposal mode

Reference: `scripts/phase19_acceptance.py:_build_manifest()` — the working implementation

**Step 3: Run test to verify it passes**

Run: `pytest tests/services/test_manifest_builder.py -v`
Expected: PASS

**Step 4: Commit**
```bash
git add src/services/manifest_builder.py tests/services/test_manifest_builder.py
git commit -m "feat: add manifest builder — WrittenSlides to ProposalManifest bridge"
```

---

### Task 4: Wire renderer_v2 as default in pipeline

**Files:**
- Modify: `src/models/state.py` — change default renderer_mode to TEMPLATE_V2
- Modify: `src/pipeline/graph.py` — add manifest building step before render
- Modify: `backend/services/pipeline_runtime.py` — set renderer_mode in initial state

**Step 1: Change default renderer_mode**

In `src/models/state.py`, change:
```python
renderer_mode: RendererMode = RendererMode.LEGACY
```
to:
```python
renderer_mode: RendererMode = RendererMode.TEMPLATE_V2
```

**Step 2: Add manifest building to render_node**

In `src/pipeline/graph.py`, modify `_render_template_v2()` to build the manifest from `WrittenSlides` if `state.proposal_manifest` is None:

```python
async def _render_template_v2(state: DeckForgeState) -> dict[str, Any]:
    manifest = state.proposal_manifest
    if manifest is None:
        # Auto-build manifest from WrittenSlides
        from src.services.manifest_builder import build_manifest_from_slides
        slides = state.final_slides or (state.written_slides.slides if state.written_slides else [])
        if not slides:
            return {"current_stage": PipelineStage.ERROR, ...}
        manifest = build_manifest_from_slides(
            slides=slides,
            rfp_context=state.rfp_context,
            catalog_lock_path=...,
            language=state.output_language,
        )
    # ... rest of existing render_v2 logic
```

**Step 3: Set renderer_mode in backend initial state**

In `backend/services/pipeline_runtime.py`, modify `_build_initial_state()`:
```python
return DeckForgeState(
    ...
    renderer_mode=RendererMode.TEMPLATE_V2,  # Use v2 by default
)
```

**Step 4: Verify pipeline compiles**

Run: `python -c "from src.pipeline.graph import build_graph; g = build_graph(); print('OK')"`
Expected: `OK`

**Step 5: Commit**
```bash
git add src/models/state.py src/pipeline/graph.py backend/services/pipeline_runtime.py
git commit -m "feat: wire renderer_v2 as default pipeline renderer"
```

---

### Task 5: End-to-end verification

**Step 1: Run the Phase 19 acceptance script to verify v2 still works**

```bash
cd C:\Projects\Deckbuilder\.claude\worktrees\nostalgic-nash
python scripts/phase19_acceptance.py
```
Expected: 17/17 PASS, 40 slides EN, 40 slides AR

**Step 2: Run pytest to verify no regressions**

```bash
pytest tests/ -x -q --timeout=30
```
Expected: All existing tests pass

**Step 3: Export PNGs of key slides**

Use the PPTX skill's conversion pipeline:
```bash
python scripts/office/soffice.py --headless --convert-to pdf output/phase19_acceptance/en_v2_proposal.pptx
pdftoppm -jpeg -r 150 output/phase19_acceptance/en_v2_proposal.pdf slide
```

Show at least 8 slides demonstrating:
- Cover slide with branding
- Section divider with navy background
- Content slide with proper typography
- Case study with client logo
- Team bio with Euclid Flex Bold
- Methodology overview
- Deliverables table
- Company profile

**Step 4: Show Gate 5 summary evidence**

Terminal output showing: lint status, density status, submission readiness, blocker count.

---

## Execution Order

1. Task 1 + Task 2 (parallel — file recovery)
2. Task 3 (manifest builder)
3. Task 4 (pipeline wiring)
4. Task 5 (verification)

## Success Criteria

- [ ] `design_tokens.py` and `density_scorer.py` exist as proper `.py` source files
- [ ] `manifest_builder.py` converts WrittenSlides → ProposalManifest
- [ ] Pipeline defaults to `RendererMode.TEMPLATE_V2`
- [ ] Phase 19 acceptance still produces 17/17 PASS
- [ ] All existing tests pass
- [ ] PNG exports show professional branded slides (not plain text)
