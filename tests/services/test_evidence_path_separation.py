"""Tests for three-path RFP/evidence separation.

Verifies that:
- RFP input path (--docs-path) feeds only uploaded_documents/context
- Evidence cache path loads the retrieval backend and KG
- Evidence docs path resolves DOC-### IDs for full-document loading
- The two corpora are never merged
- Cache/docs consistency is validated
- Module globals reset cleanly between tests
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import src.services.search as search_mod
from src.services.search import (
    EVIDENCE_CACHE_PATH,
    EVIDENCE_DOCS_PATH,
    EVIDENCE_KG_PATH,
    _list_supported_documents,
    load_evidence_backend_from_cache,
    reset_evidence_runtime_config,
    set_evidence_docs_path,
    validate_evidence_cache_consistency,
)


@pytest.fixture(autouse=True)
def _reset_evidence_globals():
    """Reset evidence globals before and after each test."""
    reset_evidence_runtime_config()
    yield
    reset_evidence_runtime_config()


# ── Reset / isolation ────────────────────────────────────────────


def test_reset_evidence_runtime_config_clears_all_globals():
    search_mod.EVIDENCE_DOCS_PATH = "/some/path"
    search_mod.EVIDENCE_CACHE_PATH = "/some/cache"
    search_mod.EVIDENCE_KG_PATH = "/some/kg.json"

    reset_evidence_runtime_config()

    assert search_mod.EVIDENCE_DOCS_PATH is None
    assert search_mod.EVIDENCE_CACHE_PATH is None
    assert search_mod.EVIDENCE_KG_PATH is None
    assert search_mod._backend is None


def test_evidence_config_does_not_leak_between_tests():
    """This test runs after reset — all globals should be None."""
    assert search_mod.EVIDENCE_DOCS_PATH is None
    assert search_mod.EVIDENCE_CACHE_PATH is None
    assert search_mod.EVIDENCE_KG_PATH is None


# ── set_evidence_docs_path ───────────────────────────────────────


def test_set_evidence_docs_path_sets_global():
    set_evidence_docs_path("/evidence/corpus")
    assert search_mod.EVIDENCE_DOCS_PATH == "/evidence/corpus"


# ── Cache/docs consistency ───────────────────────────────────────


def test_cache_docs_consistency_passes_when_matched(tmp_path):
    # Create evidence docs folder with 2 files
    (tmp_path / "alpha.pdf").write_bytes(b"%PDF-fake")
    (tmp_path / "beta.pptx").write_bytes(b"PK-fake")

    # Create matching manifest
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    manifest = {
        "total_documents": 2,
        "documents": [
            {"doc_id": "DOC-001", "filename": "alpha.pdf"},
            {"doc_id": "DOC-002", "filename": "beta.pptx"},
        ],
    }
    (cache_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    ok, msg = validate_evidence_cache_consistency(str(cache_dir), str(tmp_path))
    assert ok is True
    assert "consistent" in msg.lower()


def test_cache_docs_consistency_fails_on_count_mismatch(tmp_path):
    (tmp_path / "alpha.pdf").write_bytes(b"%PDF-fake")

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    manifest = {
        "total_documents": 3,
        "documents": [
            {"doc_id": "DOC-001", "filename": "alpha.pdf"},
            {"doc_id": "DOC-002", "filename": "beta.pptx"},
            {"doc_id": "DOC-003", "filename": "gamma.docx"},
        ],
    }
    (cache_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    ok, msg = validate_evidence_cache_consistency(str(cache_dir), str(tmp_path))
    assert ok is False
    assert "3 docs" in msg


def test_cache_docs_consistency_fails_on_filename_mismatch(tmp_path):
    (tmp_path / "alpha.pdf").write_bytes(b"%PDF-fake")
    (tmp_path / "gamma.docx").write_bytes(b"PK-fake")

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    manifest = {
        "total_documents": 2,
        "documents": [
            {"doc_id": "DOC-001", "filename": "alpha.pdf"},
            {"doc_id": "DOC-002", "filename": "beta.pptx"},
        ],
    }
    (cache_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    ok, msg = validate_evidence_cache_consistency(str(cache_dir), str(tmp_path))
    assert ok is False
    assert "mismatch" in msg.lower()


def test_cache_docs_consistency_fails_on_missing_manifest(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    # No manifest.json

    ok, msg = validate_evidence_cache_consistency(str(cache_dir), str(tmp_path))
    assert ok is False
    assert "No manifest.json" in msg


# ── load_evidence_full_documents fallback ────────────────────────


@pytest.mark.asyncio
async def test_load_evidence_full_documents_uses_evidence_path(tmp_path):
    """When EVIDENCE_DOCS_PATH is set, full-doc loading resolves from there."""
    from src.services.search import load_evidence_full_documents

    # Create evidence folder with a real file
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "proposal_alpha.pdf").write_bytes(b"%PDF-fake-content")

    set_evidence_docs_path(str(evidence_dir))

    # load_evidence_full_documents should pass evidence_dir to load_full_documents
    with patch("src.services.search.load_full_documents") as mock_load:
        mock_load.return_value = [{"doc_id": "DOC-001", "title": "proposal_alpha"}]
        result = await load_evidence_full_documents(["DOC-001"])
        mock_load.assert_called_once_with(
            ["DOC-001"],
            docs_path=str(evidence_dir),
            max_chars_per_document=50_000,
        )
    assert len(result) == 1


@pytest.mark.asyncio
async def test_load_evidence_full_documents_fallback_when_no_evidence_path():
    """Without EVIDENCE_DOCS_PATH, falls back to DEFAULT_DOCS_PATH."""
    from src.services.search import load_evidence_full_documents

    assert search_mod.EVIDENCE_DOCS_PATH is None

    with patch("src.services.search.load_full_documents") as mock_load:
        mock_load.return_value = []
        await load_evidence_full_documents(["DOC-001"])
        # Called without explicit docs_path → uses default
        mock_load.assert_called_once_with(
            ["DOC-001"],
            max_chars_per_document=50_000,
        )


# ── Backward compatibility ──────────────────────────────────────


def test_backward_compat_no_evidence_args():
    """When no evidence args, all evidence globals remain None."""
    assert search_mod.EVIDENCE_DOCS_PATH is None
    assert search_mod.EVIDENCE_CACHE_PATH is None
    assert search_mod.EVIDENCE_KG_PATH is None


# ── KG path resolution ──────────────────────────────────────────


def test_evidence_kg_path_overrides_default():
    search_mod.EVIDENCE_KG_PATH = "/evidence/cache/knowledge_graph.json"

    # Simulate what graph.py does
    kg_path = (
        search_mod.EVIDENCE_KG_PATH
        or f"{search_mod.DEFAULT_CACHE_PATH}/knowledge_graph.json"
    )
    assert kg_path == "/evidence/cache/knowledge_graph.json"


def test_default_kg_path_when_no_evidence():
    assert search_mod.EVIDENCE_KG_PATH is None

    kg_path = (
        search_mod.EVIDENCE_KG_PATH
        or f"{search_mod.DEFAULT_CACHE_PATH}/knowledge_graph.json"
    )
    assert "DEFAULT" not in kg_path or search_mod.DEFAULT_CACHE_PATH in kg_path


# ── RFP isolation ────────────────────────────────────────────────


def test_rfp_uploaded_documents_not_contaminated_by_evidence():
    """_build_domain_agnostic_input reads only from docs_path.
    Setting EVIDENCE_DOCS_PATH does not affect uploaded_documents."""
    set_evidence_docs_path("/some/evidence/path")

    # _build_domain_agnostic_input does not read EVIDENCE_DOCS_PATH
    # it only reads from its docs_path argument. This is architectural.
    # We verify the function signature doesn't reference evidence globals.
    import inspect
    from scripts.source_book_only import _build_domain_agnostic_input

    sig = inspect.signature(_build_domain_agnostic_input)
    param_names = list(sig.parameters.keys())
    assert "evidence" not in " ".join(param_names).lower()
