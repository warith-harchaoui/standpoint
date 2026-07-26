"""Regression tests for the skill helper `scripts/positioning_summary.py`.

The helper is a thin wrapper the Claude / OpenCode skill calls instead of re-writing
the glue. It once shipped a crash: it kept passing a `use_llm=` keyword that the core
engine had already dropped, so every invocation raised `TypeError`. Nothing tested it,
so the break went unnoticed. These tests close that gap.

They are fast and deterministic: `standpoint.positioning` is monkeypatched with a stub
that records how it was called, so the helper's argument wiring is checked without the
local model. The key assertions are that the helper calls the current API (`model=`)
and never the removed `use_llm=`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

# Load the helper by path: it lives under skills/, not on the package import path.
_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "standpoint"
    / "scripts"
    / "positioning_summary.py"
)


def _load_helper() -> ModuleType:
    """Import `positioning_summary.py` from its on-disk path as a module."""
    spec = importlib.util.spec_from_file_location("positioning_summary", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _StubPositioning:
    """Stand-in for a `Positioning` result that records the kwargs it was built with."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    def export(self, outdir: str, model: str = "") -> list[str]:
        """Record the export call and return one fake output path."""
        self.export_kwargs = {"outdir": outdir, "model": model}
        return [f"{outdir}/stub.md"]

    def to_markdown(self, model: str = "") -> str:
        """Record the markdown call and return a fixed string."""
        self.markdown_kwargs = {"model": model}
        return "# Stub\n"


def test_helper_calls_current_api_not_use_llm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The helper runs cleanly and forwards `model=` (never the removed `use_llm=`)."""
    import standpoint as sp

    calls: dict[str, object] = {}

    def fake_positioning(text: str, **kwargs: object) -> _StubPositioning:
        # Guard the exact regression: the removed keyword must never be passed.
        assert "use_llm" not in kwargs
        calls.update(kwargs)
        return _StubPositioning(**kwargs)

    monkeypatch.setattr(sp, "positioning", fake_positioning)

    table = tmp_path / "t.csv"
    table.write_text("Tool,Speed,Cost\nA,5,2\nB,2,5\nC,4,4\n", encoding="utf-8")

    helper = _load_helper()
    rc = helper.main([str(table), "--outdir", str(tmp_path / "out"), "--model", "some-model"])

    assert rc == 0
    assert calls["model"] == "some-model"  # --model reached the engine
    assert calls["reference"] == 0  # default numeric reference is an int (row index)
    out = capsys.readouterr().out
    assert "# Stub" in out and "Files written:" in out


def test_helper_reports_bad_table_without_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `ValueError` from the engine becomes a clean exit code 1, not a traceback."""
    import standpoint as sp

    def boom(text: str, **kwargs: object) -> None:
        raise ValueError("degenerate table")

    monkeypatch.setattr(sp, "positioning", boom)

    table = tmp_path / "bad.csv"
    table.write_text("A,B\nonly,1\n", encoding="utf-8")

    helper = _load_helper()
    rc = helper.main([str(table), "--outdir", str(tmp_path / "out")])

    assert rc == 1
    assert "error:" in capsys.readouterr().err
