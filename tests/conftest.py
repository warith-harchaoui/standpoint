"""Shared test setup for Standpoint.

Standpoint always names the axes and writes the analysis with the local model
(`standpoint.DEFAULT_MODEL`); there is no model-free path. The model is therefore a
hard prerequisite of the test suite, not an optional extra: the session-scoped,
autouse fixture below guarantees it is present, pulling it once if needed. If Ollama
itself is unreachable, the tests fail loudly — that is a missing prerequisite to
install, not a reason to skip.
"""

from __future__ import annotations

import pytest

import standpoint as sp


@pytest.fixture(scope="session", autouse=True)
def _ensure_local_model() -> None:
    """Guarantee `standpoint.DEFAULT_MODEL` is available in Ollama for the whole run.

    Pulls the model once if it is not already installed. A missing Ollama daemon (or a
    failed pull) surfaces as a hard error so the prerequisite gets installed rather
    than silently skipped.
    """
    import ollama

    models = ollama.list().get("models", [])
    names = [getattr(m, "model", None) or m.get("model", "") for m in models]
    if sp.DEFAULT_MODEL not in names:
        ollama.pull(sp.DEFAULT_MODEL)  # one-time download; raises if Ollama is down
