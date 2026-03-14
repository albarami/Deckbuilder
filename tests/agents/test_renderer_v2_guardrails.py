"""Phase 15 — Static Guardrails on ALL v2-Path Modules.

AST-level and source-level verification that every module in the
renderer_v2 code path obeys the zero-shape-creation guardrail and the
zero-legacy-imports guardrail.

Modules scanned (exhaustive list):
  - renderer_v2.py
  - placeholder_injectors.py
  - shell_sanitizer.py
  - content_fitter.py
  - composition_scorer.py
  - scorer_profiles.py

Any new module added to the v2 code path must be added to
``V2_PATH_MODULES`` and tested here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


# ── Module list ───────────────────────────────────────────────────────

_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "services"

V2_PATH_MODULES: list[str] = [
    "renderer_v2.py",
    "placeholder_injectors.py",
    "shell_sanitizer.py",
    "content_fitter.py",
    "composition_scorer.py",
    "scorer_profiles.py",
]

# Modules that must NEVER be imported by v2-path code
FORBIDDEN_IMPORT_SOURCES: set[str] = {
    "src.services.renderer",
    "src.services.formatting",
    "src.services.design_tokens",
    "src.utils.formatting",
}

# Forbidden method calls (shape creation)
FORBIDDEN_CALLS: list[str] = [
    ".add_shape(",
    ".add_textbox(",
    ".add_table(",
    ".add_picture(",
]


def _read_source(module_name: str) -> str:
    """Read a v2-path module source file."""
    path = _SRC / module_name
    assert path.exists(), f"v2-path module not found: {path}"
    return path.read_text(encoding="utf-8")


# ── Zero-Shape-Creation Guardrail (all 6 modules) ────────────────────


class TestZeroShapeCreationAllModules:
    """Every v2-path module must contain zero shape-creation calls."""

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_no_add_shape(self, module_name: str):
        source = _read_source(module_name)
        assert ".add_shape(" not in source, (
            f"{module_name} contains forbidden .add_shape() call"
        )

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_no_add_textbox(self, module_name: str):
        source = _read_source(module_name)
        assert ".add_textbox(" not in source, (
            f"{module_name} contains forbidden .add_textbox() call"
        )

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_no_add_table(self, module_name: str):
        source = _read_source(module_name)
        assert ".add_table(" not in source, (
            f"{module_name} contains forbidden .add_table() call"
        )

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_no_add_picture(self, module_name: str):
        source = _read_source(module_name)
        assert ".add_picture(" not in source, (
            f"{module_name} contains forbidden .add_picture() call"
        )


class TestZeroShapeCreationAST:
    """AST-based verification: walk every v2-path module and verify no
    attribute call to add_shape / add_textbox / add_table / add_picture."""

    _FORBIDDEN_ATTR_CALLS = {
        "add_shape",
        "add_textbox",
        "add_table",
        "add_picture",
    }

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_ast_no_forbidden_calls(self, module_name: str):
        source = _read_source(module_name)
        tree = ast.parse(source, filename=module_name)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Check attribute calls: something.add_shape(...)
                if isinstance(func, ast.Attribute):
                    assert func.attr not in self._FORBIDDEN_ATTR_CALLS, (
                        f"{module_name} line {node.lineno}: "
                        f"AST detected forbidden call to .{func.attr}()"
                    )


# ── Zero-Legacy-Imports Guardrail (all 6 modules) ────────────────────


class TestZeroLegacyImportsAllModules:
    """No v2-path module may import from renderer.py, formatting.py,
    or design_tokens."""

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_no_import_from_renderer(self, module_name: str):
        source = _read_source(module_name)
        assert "from src.services.renderer " not in source, (
            f"{module_name} imports from legacy renderer.py"
        )
        assert "import src.services.renderer" not in source, (
            f"{module_name} imports legacy renderer module"
        )

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_no_import_from_formatting(self, module_name: str):
        source = _read_source(module_name)
        assert "from src.services.formatting" not in source, (
            f"{module_name} imports from formatting.py"
        )
        assert "import src.services.formatting" not in source, (
            f"{module_name} imports formatting module"
        )

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_no_design_tokens_import(self, module_name: str):
        source = _read_source(module_name)
        tree = ast.parse(source, filename=module_name)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "design_tokens" not in node.module, (
                    f"{module_name} imports from design_tokens: {node.module}"
                )


class TestImportIsolationAST:
    """AST walk on every v2-path module: verify all imports are from
    approved sources only."""

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_no_forbidden_import_sources(self, module_name: str):
        source = _read_source(module_name)
        tree = ast.parse(source, filename=module_name)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for forbidden in FORBIDDEN_IMPORT_SOURCES:
                    assert not node.module.startswith(forbidden), (
                        f"{module_name} line {node.lineno}: "
                        f"imports from forbidden source: {node.module}"
                    )


# ── No raw-display-name resolution in v2-path code ───────────────────


class TestNoRawDisplayNameResolution:
    """Verify v2-path modules never use raw layout display names for
    runtime resolution.  Display names like 'Methodology -4- Overview of
    Phases' should only appear in audit/metadata comments, never in code
    logic.

    The indicator: no string literal in source matches known raw display
    name patterns that would be used for matching/routing.
    """

    # Known raw display name patterns that must NOT appear in code logic
    _RAW_DISPLAY_PATTERNS = [
        "Methodology -4-",
        "Methodology -3-",
        "Methdology -4-",  # note: typo in original template
        "two team members",
        "Services - Cases",
        "Services - Detailed Case",
    ]

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_no_raw_display_names(self, module_name: str):
        source = _read_source(module_name)
        for pattern in self._RAW_DISPLAY_PATTERNS:
            assert pattern not in source, (
                f"{module_name} contains raw display name: '{pattern}'. "
                f"All layout resolution must use semantic layout IDs."
            )


# ── design_tokens string absence (not just imports) ──────────────────


class TestNoDesignTokensString:
    """Verify the string 'design_tokens' does not appear anywhere in
    v2-path module source (not even in comments or docstrings).

    Exception: composition_scorer.py and scorer_profiles.py MAY reference
    'design_tokens' in explanatory comments, but NOT in code logic.
    """

    _STRICT_MODULES = [
        "renderer_v2.py",
        "placeholder_injectors.py",
        "shell_sanitizer.py",
        "content_fitter.py",
    ]

    @pytest.mark.parametrize("module_name", _STRICT_MODULES)
    def test_no_design_tokens_string(self, module_name: str):
        source = _read_source(module_name)
        assert "design_tokens" not in source, (
            f"{module_name} contains 'design_tokens' string"
        )


# ── Module list completeness ─────────────────────────────────────────


class TestModuleListCompleteness:
    """All declared v2-path modules must exist on disk."""

    @pytest.mark.parametrize("module_name", V2_PATH_MODULES)
    def test_module_exists(self, module_name: str):
        path = _SRC / module_name
        assert path.exists(), f"Declared v2-path module missing: {path}"

    def test_module_count(self):
        """We expect exactly 6 v2-path modules."""
        assert len(V2_PATH_MODULES) == 6


# ── Frozen data classes in v2-path modules ────────────────────────────


class TestFrozenDataClasses:
    """Key data classes in v2-path modules must be frozen (immutable).
    Verify via AST that @dataclass(frozen=True) is used."""

    _EXPECTED_FROZEN: dict[str, list[str]] = {
        "composition_scorer.py": ["ShapeInfo", "Violation", "SlideScore", "CompositionResult"],
        "scorer_profiles.py": ["ProfileConfig"],
    }

    @pytest.mark.parametrize(
        "module_name,class_name",
        [
            (mod, cls)
            for mod, classes in _EXPECTED_FROZEN.items()
            for cls in classes
        ],
    )
    def test_class_is_frozen(self, module_name: str, class_name: str):
        source = _read_source(module_name)
        tree = ast.parse(source, filename=module_name)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Check decorators for @dataclass(frozen=True)
                found_frozen = False
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call):
                        for kw in dec.keywords:
                            if kw.arg == "frozen" and isinstance(kw.value, ast.Constant):
                                if kw.value.value is True:
                                    found_frozen = True
                assert found_frozen, (
                    f"{module_name}::{class_name} must use @dataclass(frozen=True)"
                )
                return

        pytest.fail(f"Class {class_name} not found in {module_name}")
