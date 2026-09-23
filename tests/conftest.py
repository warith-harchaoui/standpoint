"""Shared test setup for Standpoint.

Standpoint always names the axes and writes the analysis with the local model
resolved through the brief -> engine contract (`standpoint.engine()`); there is no
model-free path. Tests that exercise that path are marked ``@pytest.mark.needs_model``.
For them the model is a hard prerequisite: the autouse guard below pulls it once if
missing.

When the local backend is unreachable the guard behaves differently by environment. On
a developer machine it fails loudly, because a missing model is a prerequisite to
install, not a reason to skip. In CI (where no local model server runs) it skips the
model-backed tests instead, so CI stays the light, deterministic gate the workflow
documents. The many model-free tests (parsing, geometry, roles, colours, i18n, SVG
structure) always run, in CI and locally.
"""

from __future__ import annotations

import os

import best_engine_ai_helper as beh
import pytest

import standpoint as sp

# Session cache: has the resolved model been confirmed present? Avoids re-probing the
# backend for every model-backed test once the first one has ensured it.
_MODEL_READY: bool = False


def pytest_configure(config: pytest.Config) -> None:
    """Register the marker that flags a test as calling the local model."""
    config.addinivalue_line(
        "markers", "needs_model: test calls the local model resolved in llm.engine.yaml"
    )


def _ensure_model() -> None:
    """Pull the engine's resolved VLM if it is not installed. Raise if the backend is down."""
    import ollama

    model = beh.model_for(sp.engine(), "vlm")[2]  # (backend, base_url, model)
    models = ollama.list().get("models", [])
    names = [getattr(m, "model", None) or m.get("model", "") for m in models]
    if model not in names:
        ollama.pull(model)  # one-time download; raises if the backend is down


def _ensure_model_or_skip() -> None:
    """Shared gate: model confirmed present, or skip (CI) / re-raise (local).

    A missing Ollama is treated as a prerequisite to install locally (re-raise) but as
    an expected absence in CI (skip), which keeps the model-free suite green on the
    hosted runner.
    """
    global _MODEL_READY
    if _MODEL_READY:
        return
    try:
        _ensure_model()
        _MODEL_READY = True
    except Exception as exc:  # Ollama down or the pull failed
        if os.environ.get("CI"):
            pytest.skip(f"local Ollama model unavailable in CI: {exc}")
        raise


@pytest.fixture(autouse=True)
def _guard_model(request: pytest.FixtureRequest) -> None:
    """Guarantee the local model for ``needs_model`` tests; leave the rest untouched."""
    if "needs_model" in request.keywords:
        _ensure_model_or_skip()


@pytest.fixture(scope="module")
def model_guard() -> None:
    """Same gate for MODULE-scoped fixtures that call the model (e.g. ``poles``).

    Module fixtures are set up before the function-scoped autouse guard, so one that
    reaches the model must request this fixture itself or a down Ollama surfaces as a
    setup ERROR instead of the intended skip.
    """
    _ensure_model_or_skip()
