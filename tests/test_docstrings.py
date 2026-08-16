"""Guard the docstring-coverage half of CODING.md Rule 0/1.

Ruff's `select` list has no pydocstyle (`D`) rules, so nothing in the lint gate
actually stops a function or class from shipping without a docstring -- the
project has had 100% coverage on every `standpoint/*.py` file so far, but only by
discipline. This walks each module's AST directly (no import, no side effects,
no model) and fails with the exact missing names if that ever regresses. It
checks presence only, not full Numpy-style formatting (Parameters/Returns
sections etc.) -- ruff's pydocstyle rules are noisy against this codebase's
existing style without per-file tuning that isn't worth it just to catch the
one failure mode (a bare `def foo():` with no docstring at all) this guards.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_STANDPOINT_DIR = Path(__file__).resolve().parents[1] / "standpoint"
_MODULE_PATHS = sorted(_STANDPOINT_DIR.glob("*.py"))


def _undocumented(path: Path) -> list[str]:
    """Return `"ClassDef/FunctionDef/AsyncFunctionDef:name:lineno"` for each
    definition in `path` with no docstring as its first statement.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        first = node.body[0] if node.body else None
        has_docstring = (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )
        if not has_docstring:
            missing.append(f"{type(node).__name__}:{node.name}:{node.lineno}")
    return missing


@pytest.mark.parametrize("path", _MODULE_PATHS, ids=lambda p: p.name)
def test_every_function_and_class_has_a_docstring(path: Path) -> None:
    """Every `def`/`class` in `standpoint/*.py`, public or private, must have one."""
    missing = _undocumented(path)
    assert not missing, f"{path.name} is missing docstrings on: {missing}"
