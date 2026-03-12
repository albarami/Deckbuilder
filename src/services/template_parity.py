"""Phase 2 — Template Parity Validator.

Consumes EN and AR catalog lock files and enforces structural parity
between the two language variants. Every check is fail-closed: a critical
mismatch raises ``ParityError`` and blocks rendering.

Designed to run as a pre-render gate — if EN and AR catalog locks
diverge on any semantic ID set, placeholder index set, pool structure,
or allowlist shape, the pipeline must not proceed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ── Exceptions ────────────────────────────────────────────────────────────


class ParityError(RuntimeError):
    """Raised when EN/AR catalog locks fail a critical parity check."""


# ── Result dataclass ──────────────────────────────────────────────────────


@dataclass
class ParityCheck:
    """Single parity comparison result."""

    name: str
    severity: str  # "critical" | "warning"
    match: bool
    en_value: Any = None
    ar_value: Any = None
    detail: str = ""


@dataclass
class ParityReport:
    """Aggregated parity audit result."""

    overall_pass: bool = True
    critical_failures: int = 0
    warnings: int = 0
    checks: list[ParityCheck] = field(default_factory=list)

    def add(self, check: ParityCheck) -> None:
        self.checks.append(check)
        if not check.match:
            if check.severity == "critical":
                self.critical_failures += 1
                self.overall_pass = False
            else:
                self.warnings += 1

    def to_dict(self) -> dict:
        return {
            "overall_pass": self.overall_pass,
            "critical_failures": self.critical_failures,
            "warnings": self.warnings,
            "checks": [
                {
                    "check": c.name,
                    "severity": c.severity,
                    "match": c.match,
                    "en": c.en_value,
                    "ar": c.ar_value,
                    **({"detail": c.detail} if c.detail else {}),
                }
                for c in self.checks
            ],
        }


# ── Core parity engine ───────────────────────────────────────────────────


def _load_lock(path: Path) -> dict:
    """Load and validate a catalog lock file."""
    if not path.exists():
        raise ParityError(f"Catalog lock not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    required = {
        "template_hash", "language", "a1_immutable", "a2_shells",
        "section_dividers", "layouts", "case_study_pool",
        "team_bio_pool", "service_divider_pool",
    }
    missing = required - set(data.keys())
    if missing:
        raise ParityError(
            f"Catalog lock {path.name} missing fields: {sorted(missing)}"
        )
    return data


def run_parity_check(
    en_lock_path: Path,
    ar_lock_path: Path,
    *,
    fail_on_critical: bool = True,
) -> ParityReport:
    """Run full EN/AR catalog lock parity audit.

    Parameters
    ----------
    en_lock_path : Path
        Path to the EN catalog lock JSON.
    ar_lock_path : Path
        Path to the AR catalog lock JSON.
    fail_on_critical : bool
        If True (default), raise ``ParityError`` on any critical failure.

    Returns
    -------
    ParityReport
        Detailed parity audit results.

    Raises
    ------
    ParityError
        If ``fail_on_critical`` is True and any critical check fails.
    """
    en = _load_lock(en_lock_path)
    ar = _load_lock(ar_lock_path)
    report = ParityReport()

    # ── 1. Language labels ────────────────────────────────────────────
    report.add(ParityCheck(
        name="language_labels",
        severity="critical",
        match=en["language"] == "en" and ar["language"] == "ar",
        en_value=en["language"],
        ar_value=ar["language"],
        detail="EN lock must be 'en', AR lock must be 'ar'",
    ))

    # ── 2. A1 immutable semantic ID set ───────────────────────────────
    en_a1 = sorted(en["a1_immutable"].keys())
    ar_a1 = sorted(ar["a1_immutable"].keys())
    report.add(ParityCheck(
        name="a1_immutable_ids",
        severity="critical",
        match=en_a1 == ar_a1,
        en_value=en_a1,
        ar_value=ar_a1,
    ))

    # ── 3. A2 shell semantic ID set ───────────────────────────────────
    en_a2 = sorted(en["a2_shells"].keys())
    ar_a2 = sorted(ar["a2_shells"].keys())
    report.add(ParityCheck(
        name="a2_shell_ids",
        severity="critical",
        match=en_a2 == ar_a2,
        en_value=en_a2,
        ar_value=ar_a2,
    ))

    # ── 4. A2 allowlist injection placeholder parity ──────────────────
    for shell_id in sorted(set(en_a2) & set(ar_a2)):
        en_al = en["a2_shells"][shell_id].get("allowlist", {})
        ar_al = ar["a2_shells"][shell_id].get("allowlist", {})
        en_ph = sorted(en_al.get("approved_injection_placeholders", {}).keys())
        ar_ph = sorted(ar_al.get("approved_injection_placeholders", {}).keys())
        report.add(ParityCheck(
            name=f"a2_placeholder_parity:{shell_id}",
            severity="critical",
            match=en_ph == ar_ph,
            en_value=en_ph,
            ar_value=ar_ph,
        ))

    # ── 5. Section divider number set ─────────────────────────────────
    en_div = sorted(en["section_dividers"].keys())
    ar_div = sorted(ar["section_dividers"].keys())
    report.add(ParityCheck(
        name="section_divider_numbers",
        severity="critical",
        match=en_div == ar_div,
        en_value=en_div,
        ar_value=ar_div,
    ))

    # ── 6. Layout semantic ID set ─────────────────────────────────────
    en_lay = sorted(en["layouts"].keys())
    ar_lay = sorted(ar["layouts"].keys())
    report.add(ParityCheck(
        name="layout_semantic_ids",
        severity="critical",
        match=en_lay == ar_lay,
        en_value=en_lay,
        ar_value=ar_lay,
    ))

    # ── 7. Per-layout placeholder index parity ────────────────────────
    common_layouts = sorted(set(en_lay) & set(ar_lay))
    for sem_id in common_layouts:
        en_ph_idx = sorted(en["layouts"][sem_id].get("placeholders", {}).keys())
        ar_ph_idx = sorted(ar["layouts"][sem_id].get("placeholders", {}).keys())
        if en_ph_idx != ar_ph_idx:
            report.add(ParityCheck(
                name=f"layout_placeholder_parity:{sem_id}",
                severity="critical",
                match=False,
                en_value=en_ph_idx,
                ar_value=ar_ph_idx,
            ))

    # ── 8. Case study pool category set ───────────────────────────────
    en_cs = sorted(en["case_study_pool"].keys())
    ar_cs = sorted(ar["case_study_pool"].keys())
    report.add(ParityCheck(
        name="case_study_categories",
        severity="critical",
        match=en_cs == ar_cs,
        en_value=en_cs,
        ar_value=ar_cs,
    ))

    # ── 9. Case study pool count per category ─────────────────────────
    for cat in sorted(set(en_cs) & set(ar_cs)):
        en_count = len(en["case_study_pool"][cat])
        ar_count = len(ar["case_study_pool"][cat])
        report.add(ParityCheck(
            name=f"case_study_count:{cat}",
            severity="warning",
            match=en_count == ar_count,
            en_value=en_count,
            ar_value=ar_count,
        ))

    # ── 10. Team bio pool count ───────────────────────────────────────
    en_team = len(en["team_bio_pool"])
    ar_team = len(ar["team_bio_pool"])
    report.add(ParityCheck(
        name="team_bio_pool_count",
        severity="warning",
        match=en_team == ar_team,
        en_value=en_team,
        ar_value=ar_team,
    ))

    # ── 11. Team bio pool family parity ───────────────────────────────
    en_fam = sorted(
        entry.get("team_family", "unknown")
        for entry in en["team_bio_pool"]
    )
    ar_fam = sorted(
        entry.get("team_family", "unknown")
        for entry in ar["team_bio_pool"]
    )
    report.add(ParityCheck(
        name="team_bio_families",
        severity="warning",
        match=en_fam == ar_fam,
        en_value=en_fam,
        ar_value=ar_fam,
    ))

    # ── 12. Service divider pool count ────────────────────────────────
    en_sd = len(en["service_divider_pool"])
    ar_sd = len(ar["service_divider_pool"])
    report.add(ParityCheck(
        name="service_divider_pool_count",
        severity="warning",
        match=en_sd == ar_sd,
        en_value=en_sd,
        ar_value=ar_sd,
    ))

    # ── 13. Service divider semantic ID set ───────────────────────────
    en_sd_ids = sorted(
        entry.get("semantic_id", "") for entry in en["service_divider_pool"]
    )
    ar_sd_ids = sorted(
        entry.get("semantic_id", "") for entry in ar["service_divider_pool"]
    )
    report.add(ParityCheck(
        name="service_divider_ids",
        severity="critical",
        match=en_sd_ids == ar_sd_ids,
        en_value=en_sd_ids,
        ar_value=ar_sd_ids,
    ))

    # ── Summary log ───────────────────────────────────────────────────
    total = len(report.checks)
    passed = sum(1 for c in report.checks if c.match)
    log.info(
        "Parity audit: %d/%d passed, %d critical failures, %d warnings",
        passed, total, report.critical_failures, report.warnings,
    )

    if fail_on_critical and not report.overall_pass:
        failed = [c.name for c in report.checks if not c.match and c.severity == "critical"]
        raise ParityError(
            f"EN/AR parity blocked: {report.critical_failures} critical "
            f"failure(s): {failed}"
        )

    return report
