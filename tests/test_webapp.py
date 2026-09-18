"""Model-free tests for the static build's Python halves (webapp/).

The in-browser journeys (Pyodide boot, embedding naming, WebLLM auto-fill) are
exercised by Playwright out-of-repo; what belongs in CI is the deterministic
Python that ships to the browser:

- ``beh_shim.py`` — the memoized-replay stand-in for best-engine-ai-helper.
  Its whole contract is subtle enough to guard: a miss must raise
  :class:`PendingLLM`, which must NOT be an ``Exception`` (``noun_forms`` wraps
  its model call in ``except Exception`` and would silently swallow the pending
  signal), and a seeded key must replay to a hit.
- ``glue.py::pole_context`` — the deterministic per-pole criteria the
  embedding-based axis namer scores; it must mirror ``axis_poles``'s own
  selection rules (|weight| > 0.05, benefit-phrased lower-is-better).

Both modules are loaded from ``webapp/`` by path: they are shipped source, not
an installed package.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_WEBAPP = Path(__file__).resolve().parents[1] / "webapp"


def _load(name: str, path: Path) -> ModuleType:
    """Import a webapp source file by path under module name `name`."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def beh_shim() -> ModuleType:
    """The browser shim, imported fresh from webapp/beh_shim.py."""
    return _load("_test_beh_shim", _WEBAPP / "beh_shim.py")


def test_shim_miss_raises_pending_which_is_not_an_exception(beh_shim: ModuleType) -> None:
    """A cache miss raises PendingLLM, and PendingLLM must bypass `except Exception`.

    `noun_forms` wraps its model call in `except Exception` (naive-plural
    fallback); if PendingLLM were an Exception subclass, the replay signal
    would be swallowed there and the browser could never serve a real answer.
    """
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    with pytest.raises(beh_shim.PendingLLM) as excinfo:
        beh_shim.llm.chat("some prompt", engine={}, json_schema=schema)
    assert not isinstance(excinfo.value, Exception)
    payload = excinfo.value.payload()
    assert payload["prompt"] == "some prompt"
    assert payload["schema"] == schema
    assert payload["key"]  # non-empty deterministic key


def test_shim_seeded_answer_replays_as_a_hit(beh_shim: ModuleType) -> None:
    """seed(key, answer) then the SAME call returns the answer (replay converges)."""
    schema = {"type": "object", "properties": {"y": {"type": "integer"}}}
    with pytest.raises(beh_shim.PendingLLM) as excinfo:
        beh_shim.llm.chat("rate things", json_schema=schema)
    beh_shim.seed(excinfo.value.key, {"y": 4})
    assert beh_shim.llm.chat("rate things", json_schema=schema) == {"y": 4}
    # A different prompt is a different key: still pending, not a stale hit.
    with pytest.raises(beh_shim.PendingLLM):
        beh_shim.llm.chat("rate other things", json_schema=schema)


@pytest.fixture(scope="module")
def glue() -> ModuleType:
    """The endpoint glue, imported from webapp/glue.py against the real engine.

    glue imports `best_engine_ai_helper`; in the browser that resolves to the
    shim, here to the real installed helper — fine for `pole_context`, which is
    deterministic and never reaches `llm.chat`.
    """
    return _load("_test_glue", _WEBAPP / "glue.py")


def test_pole_context_mirrors_axis_poles_selection(glue: ModuleType) -> None:
    """pole_context returns benefit-phrased, strongest-first criteria per pole."""
    table = "Laptop,Performance,Battery,Price (↓)\nA,5,4,1\nB,1,2,5\nC,4,5,2\nD,2,1,4\n"
    ctx = glue.pole_context(table, reference="0", lang="en")
    assert ctx["lang"] == "en"
    assert set(ctx["poles"]) == {"left", "right", "bottom", "top"}
    all_crits = [c for crits in ctx["poles"].values() for c in crits]
    assert all_crits, "at least one pole must carry criteria"
    for crits in ctx["poles"].values():
        # Strongest-first ordering, and the axis_poles |w| > 0.05 cutoff.
        weights = [c["weight"] for c in crits]
        assert weights == sorted(weights, reverse=True)
        assert all(w > 0.05 for w in weights)
    # The lower-is-better column is presented as its benefit ("low Price"),
    # exactly like the prompt `axis_poles` builds for the server-side model.
    assert any(c["text"] == "low Price" for c in all_crits)
    assert not any(c["text"] == "Price" for c in all_crits)


def test_pole_context_rejects_an_empty_table(glue: ModuleType) -> None:
    """Same clean ValueError contract as the API endpoint."""
    with pytest.raises(ValueError):
        glue.pole_context("   ")
