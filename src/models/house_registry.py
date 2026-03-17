"""Phase 4 — House Asset Registry.

Built exclusively from catalog_lock_en.json / catalog_lock_ar.json.
Uses typed AssetLocation objects from template_manager.  Fail-closed
if any required semantic asset ID or semantic layout ID is missing
from the catalog lock.

Never hardcodes slide indices or display names.  All runtime resolution
is by semantic ID only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from src.services.template_manager import AssetLocation, ShellDef

log = logging.getLogger(__name__)


# ── Exceptions ────────────────────────────────────────────────────────────


class RegistryLoadError(RuntimeError):
    """Raised when catalog lock is missing required data."""


class SemanticIDMissing(KeyError):
    """Raised when a semantic ID lookup fails (fail-closed)."""


# ── Registry dataclass ───────────────────────────────────────────────────


@dataclass(frozen=True)
class HouseAssetRegistry:
    """Immutable registry of all house assets loaded from catalog lock.

    Every field is populated from the catalog lock JSON.  No slide indices
    or display names are hardcoded in this module.  Any semantic ID
    (asset or layout) missing from the catalog lock at load time causes
    a ``RegistryLoadError``.
    """

    house_slides_a1: dict[str, AssetLocation]
    house_slides_a2: dict[str, ShellDef]
    section_dividers: dict[int, ShellDef]
    case_study_pool: dict[str, list[AssetLocation]]
    team_bio_pool: list[AssetLocation]
    service_dividers: list[AssetLocation]
    methodology_layouts: dict[str, str]   # semantic layout ID -> semantic layout ID (identity; proves presence)
    template_hash: str

    # ── Fail-closed lookups ───────────────────────────────────────────

    def get_a1(self, semantic_id: str) -> AssetLocation:
        """Resolve an A1 immutable house slide by semantic asset ID."""
        if semantic_id not in self.house_slides_a1:
            raise SemanticIDMissing(
                f"A1 semantic ID '{semantic_id}' not in registry"
            )
        return self.house_slides_a1[semantic_id]

    def get_a2(self, semantic_id: str) -> ShellDef:
        """Resolve an A2 shell by semantic asset ID."""
        if semantic_id not in self.house_slides_a2:
            raise SemanticIDMissing(
                f"A2 semantic ID '{semantic_id}' not in registry"
            )
        return self.house_slides_a2[semantic_id]

    def get_divider(self, number: int) -> ShellDef:
        """Resolve a section divider by number (1-6)."""
        if number not in self.section_dividers:
            raise SemanticIDMissing(
                f"Section divider {number} not in registry"
            )
        return self.section_dividers[number]

    def get_methodology_layout(self, semantic_layout_id: str) -> str:
        """Verify a methodology layout exists. Returns the same ID."""
        if semantic_layout_id not in self.methodology_layouts:
            raise SemanticIDMissing(
                f"Methodology layout '{semantic_layout_id}' not in registry"
            )
        return self.methodology_layouts[semantic_layout_id]

    @property
    def a1_ids(self) -> list[str]:
        """All A1 semantic asset IDs."""
        return sorted(self.house_slides_a1.keys())

    @property
    def a2_ids(self) -> list[str]:
        """All A2 semantic asset IDs."""
        return sorted(self.house_slides_a2.keys())

    @property
    def divider_numbers(self) -> list[int]:
        """All section divider numbers."""
        return sorted(self.section_dividers.keys())


# ── Loader ────────────────────────────────────────────────────────────────


def _parse_asset_location(entry: dict) -> AssetLocation:
    """Parse a catalog lock entry into an AssetLocation."""
    return AssetLocation(
        slide_idx=entry["slide_idx"],
        semantic_layout_id=entry["semantic_layout_id"],
        display_name=entry.get("display_name", ""),
        shape_count=entry.get("shape_count", 0),
        media_count=entry.get("media_count", 0),
    )


def _parse_shell_def(entry: dict) -> ShellDef:
    """Parse a catalog lock entry into a ShellDef."""
    return ShellDef(
        slide_idx=entry["slide_idx"],
        semantic_layout_id=entry["semantic_layout_id"],
        display_name=entry.get("display_name", ""),
        allowlist=entry.get("allowlist", {}),
    )


def load_registry(catalog_lock_path: Path) -> HouseAssetRegistry:
    """Load a HouseAssetRegistry from a catalog lock JSON file.

    Parameters
    ----------
    catalog_lock_path : Path
        Path to catalog_lock_en.json or catalog_lock_ar.json.

    Returns
    -------
    HouseAssetRegistry
        Fully populated, immutable registry.

    Raises
    ------
    RegistryLoadError
        If the catalog lock is missing, incomplete, or structurally invalid.
    """
    if not catalog_lock_path.exists():
        raise RegistryLoadError(
            f"Catalog lock not found: {catalog_lock_path}"
        )

    with open(catalog_lock_path, encoding="utf-8") as f:
        lock = json.load(f)

    # ── Validate required top-level keys ──────────────────────────────
    required_keys = {
        "template_hash", "a1_immutable", "a2_shells",
        "section_dividers", "case_study_pool", "team_bio_pool",
        "service_divider_pool", "layouts",
    }
    missing = required_keys - set(lock.keys())
    if missing:
        raise RegistryLoadError(
            f"Catalog lock missing required keys: {sorted(missing)}"
        )

    # ── A1 immutable house slides ─────────────────────────────────────
    house_a1: dict[str, AssetLocation] = {}
    for sem_id, entry in lock["a1_immutable"].items():
        house_a1[sem_id] = _parse_asset_location(entry)

    # ── A2 shells ─────────────────────────────────────────────────────
    house_a2: dict[str, ShellDef] = {}
    for sem_id, entry in lock["a2_shells"].items():
        house_a2[sem_id] = _parse_shell_def(entry)

    # ── Section dividers ──────────────────────────────────────────────
    dividers: dict[int, ShellDef] = {}
    for num_str, entry in lock["section_dividers"].items():
        dividers[int(num_str)] = _parse_shell_def(entry)

    # ── Case study pool ───────────────────────────────────────────────
    cs_pool: dict[str, list[AssetLocation]] = {}
    raw_pool = lock["case_study_pool"]
    if isinstance(raw_pool, dict):
        for category, entries in raw_pool.items():
            cs_pool[category] = [_parse_asset_location(e) for e in entries]
    else:
        raise RegistryLoadError(
            "case_study_pool must be a dict keyed by category"
        )

    # ── Team bio pool ─────────────────────────────────────────────────
    team_pool: list[AssetLocation] = [
        _parse_asset_location(e) for e in lock["team_bio_pool"]
    ]

    # ── Service dividers ──────────────────────────────────────────────
    svc_dividers: list[AssetLocation] = [
        _parse_asset_location(e) for e in lock["service_divider_pool"]
    ]

    # ── Methodology layouts (prove they exist in catalog lock) ────────
    methodology_ids = {
        "methodology_overview_4", "methodology_overview_3",
        "methodology_focused_4", "methodology_focused_3",
        "methodology_detail",
    }
    all_layouts = set(lock.get("layouts", {}).keys())
    meth_layouts: dict[str, str] = {}
    for mid in methodology_ids:
        if mid not in all_layouts:
            raise RegistryLoadError(
                f"Required methodology layout '{mid}' missing from catalog lock"
            )
        meth_layouts[mid] = mid

    # ── Template hash ─────────────────────────────────────────────────
    template_hash = lock["template_hash"]

    registry = HouseAssetRegistry(
        house_slides_a1=house_a1,
        house_slides_a2=house_a2,
        section_dividers=dividers,
        case_study_pool=cs_pool,
        team_bio_pool=team_pool,
        service_dividers=svc_dividers,
        methodology_layouts=meth_layouts,
        template_hash=template_hash,
    )

    log.info(
        "Registry loaded: %d A1, %d A2, %d dividers, %d case studies, "
        "%d team bios, %d service dividers, %d methodology layouts",
        len(house_a1), len(house_a2), len(dividers),
        sum(len(v) for v in cs_pool.values()),
        len(team_pool), len(svc_dividers), len(meth_layouts),
    )

    return registry
