# TASK

## Current Task

- [x] Write an implementation-based technical document describing the actual built DeckForge system and the remaining work required to complete it.
- [x] Semantic Scholar integration: `x-api-key` auth, bulk search + recommendations, no silent keyless retry after authenticated failure; optional `SEMANTIC_SCHOLAR_API_KEY` in `.env`.
- [x] Implement template-locked blueprint contract with canonical section order, ownership-aware schema, and validator tests.

## Discovered During Work

- [ ] Align backend runtime renderer selection with the requested `renderer_mode` instead of forcing `RendererMode.TEMPLATE_V2`.
- [ ] Replace mock export payloads in `backend/routers/export.py` with real file streaming from generated artifacts.
- [ ] Decide whether slide thumbnails should remain synthetic previews or be replaced with actual rendered slide images.
- [ ] Fix Gate 2 source-review payload/UI mismatches so reviewer source selections are preserved and submitted.
- [ ] Connect frontend history/dashboard views to backend session history if cross-browser or multi-user persistence is required.
- [ ] Implement or integrate a production search backend in place of the `AzureAISearchBackend` stub when moving beyond local/dev search.
- [ ] Regenerate `SEMANTIC_SCHOLAR_API_KEY` at https://www.semanticscholar.org/product/api if you need authenticated rate limits; incorrect keys get 403 and DeckForge uses the public S2 API (no header) automatically.
- [ ] Resolve baseline `tests/agents/test_config.py::test_settings_defaults` mismatch (`local_docs_path` default expected `./test_docs`, current value `data test`) so full `pytest tests/ -x -q` is green in this environment.
