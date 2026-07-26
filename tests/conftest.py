"""Shared test setup for Standpoint.

Standpoint always names the axes and writes the analysis with the local model
(`standpoint.DEFAULT_MODEL`); there is no model-free path. Tests that exercise that
path are marked ``@pytest.mark.needs_model``. For them the model is a hard prerequisite:
the autouse guard below pulls it once if missing.

When Ollama is unreachable the guard behaves differently by environment. On a developer
machine it fails loudly, because a missing model is a prerequisite to install, not a
reason to skip. In CI (where no Ollama runs) it skips the model-backed tests instead, so
CI stays the light, deterministic gate the workflow documents. The many model-free tests
(parsing, geometry, roles, colours, i18n, Vega structure) always run, in CI and locally.
"""

from __future__ import annotations

import os

import pytest

import standpoint as sp

# Session cache: has DEFAULT_MODEL been confirmed present? Avoids re-probing Ollama for
# every model-backed test once the first one has ensured it.
_MODEL_READY: bool = False


def pytest_configure(config: pytest.Config) -> None:
    """Register the marker that flags a test as calling the local model."""
    config.addinivalue_line(
        "markers", "needs_model: test calls the local Ollama model (DEFAULT_MODEL)"
    )


def _ensure_model() -> None:
    """Pull ``DEFAULT_MODEL`` if it is not installed. Raise if Ollama is unreachable."""
    import ollama

    models = ollama.list().get("models", [])
    names = [getattr(m, "model", None) or m.get("model", "") for m in models]
    if sp.DEFAULT_MODEL not in names:
        ollama.pull(sp.DEFAULT_MODEL)  # one-time download; raises if Ollama is down


@pytest.fixture(autouse=True)
def _guard_model(request: pytest.FixtureRequest) -> None:
    """Guarantee the local model for ``needs_model`` tests; leave the rest untouched.

    A missing Ollama is treated as a prerequisite to install locally (the fixture
    re-raises) but as an expected absence in CI (the test is skipped), which keeps the
    model-free suite green on the hosted runner.
    """
    global _MODEL_READY
    if "needs_model" not in request.keywords or _MODEL_READY:
        return
    try:
        _ensure_model()
        _MODEL_READY = True
    except Exception as exc:  # Ollama down or the pull failed
        if os.environ.get("CI"):
            pytest.skip(f"local Ollama model unavailable in CI: {exc}")
        raise
