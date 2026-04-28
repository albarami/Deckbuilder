"""Skeleton domain packs — structure and search-seed tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PACKS_DIR = Path("src/packs")

SKELETON_PACK_IDS = [
    "ai_governance_ethics",
    "unesco_unesco_ram",
    "international_research_collaboration",
    "government_capacity_building",
    "knowledge_transfer",
    "research_program_evaluation",
]


@pytest.mark.parametrize("pack_id", SKELETON_PACK_IDS)
def test_skeleton_pack_structure(pack_id: str) -> None:
    path = PACKS_DIR / f"{pack_id}.json"
    assert path.exists(), f"Pack file missing: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["pack_id"] == pack_id
    assert data["status"] == "skeleton"
    assert data["requires_enrichment"] is True
    assert (
        len(data.get("classification_keywords", {}).get("domain", {}).get(pack_id, []))
        >= 5
    )
    assert len(data.get("forbidden_assumptions", [])) >= 2
    # Skeleton packs must not invent regulatory content
    assert len(data.get("regulatory_references", [])) == 0


def test_skeleton_pack_has_search_seeds() -> None:
    data = json.loads(
        (PACKS_DIR / "unesco_unesco_ram.json").read_text(encoding="utf-8")
    )
    queries = data.get("recommended_search_queries", [])
    assert len(queries) >= 3
    assert any("UNESCO" in q or "RAM" in q for q in queries)
