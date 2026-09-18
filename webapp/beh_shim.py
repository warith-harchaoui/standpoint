"""Browser stand-in for ``best_engine_ai_helper`` (the local-LLM helper).

The standpoint engine funnels every model call through one entry point,
``llm.chat(prompt, engine=..., kind=..., json_schema=..., ...)``. In the static
(Pyodide) build there is no local Ollama backend behind that entry point, so
this shim implements it with a *memoized replay* contract instead:

- a cache maps ``key = sha256(prompt + canonical(schema))`` to a parsed answer;
- a cache hit returns the stored answer, exactly like a model reply would;
- a cache miss raises :class:`PendingLLM` carrying the prompt and schema.

The JavaScript driver (``backend-pyodide.js``) catches the pending call —
surfaced by ``glue.py`` as a ``{"pending": ...}`` payload — generates an answer
(an in-browser WebLLM model, or the schema's neutral defaults when no model is
available), seeds the cache with :func:`seed`, and re-runs the whole call.
Runs are cheap (small tables, deterministic geometry) and a Generate makes at
most a handful of model calls, so the replay converges in a few iterations
while the engine's code path stays byte-for-byte the one the server runs.

``PendingLLM`` subclasses ``BaseException`` on purpose: ``noun_forms`` wraps
its model call in ``except Exception`` (falling back to a naive plural), which
would otherwise swallow the pending signal and the replay could never serve a
real answer for it.

This file is written into Pyodide's ``site-packages`` as
``best_engine_ai_helper.py`` at boot, shadowing nothing (the real package is
never installed in the browser).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# key -> parsed answer, seeded from JavaScript between replay rounds.
_CACHE: dict[str, Any] = {}


class PendingLLM(BaseException):
    """A model call the browser has not answered yet (replay-memoization miss).

    Parameters
    ----------
    key : str
        Cache key for this exact call (prompt + schema), used to seed the answer.
    prompt : str
        The full prompt the engine built for the model.
    schema : dict
        The JSON schema the answer must satisfy.
    """

    def __init__(self, key: str, prompt: str, schema: dict) -> None:
        super().__init__(f"pending LLM call {key[:12]}")
        self.key = key
        self.prompt = prompt
        self.schema = schema

    def payload(self) -> dict:
        """The JSON-safe dict the JavaScript driver needs to answer this call."""
        return {"key": self.key, "prompt": self.prompt, "schema": self.schema}


def _key(prompt: str, schema: dict) -> str:
    """Deterministic cache key for one (prompt, schema) pair."""
    canon = prompt + "\x00" + json.dumps(schema, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def seed(key: str, answer: Any) -> None:
    """Store the browser-generated answer for `key`; the next replay round hits it."""
    _CACHE[key] = answer


def ensure(pkg_dir: object = None) -> dict:
    """Engine descriptor stand-in (the real helper resolves hardware + models here).

    The engine dict is only threaded through to ``llm.chat`` by standpoint, and
    this shim's ``chat`` ignores it, so a minimal marker dict is enough.
    """
    return {"backend": "browser", "resolved": "in-browser (WebLLM / fallback)"}


class _Llm:
    """The ``best_engine_ai_helper.llm`` namespace: just the ``chat`` entry point."""

    @staticmethod
    def chat(
        prompt: str,
        engine: dict | None = None,
        kind: str = "vlm",
        json_schema: dict | None = None,
        temperature: float = 0,
        model: str | None = None,
        **_ignored: Any,
    ) -> Any:
        """Return the memoized answer for this call, or raise :class:`PendingLLM`.

        Mirrors the real helper's signature; `engine` / `kind` / `temperature` /
        `model` do not participate in the cache key because the static build runs
        a single in-browser model with deterministic settings.
        """
        schema = json_schema or {}
        key = _key(str(prompt), schema)
        if key in _CACHE:
            return _CACHE[key]
        raise PendingLLM(key, str(prompt), schema)


# `from best_engine_ai_helper import llm` then `llm.chat(...)` — an instance
# attribute satisfies both the import and the call site.
llm = _Llm()
