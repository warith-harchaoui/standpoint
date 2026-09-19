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

The lead-magnet gate (``webapp/gate/``, PHP) is exercised end-to-end by
Playwright out-of-repo; here CI guards its deterministic contracts: the
generic-domain blocklist actually separates generic from professional
addresses, the ``.htaccess`` and ``serve.php`` protect the SAME app surface
(the two lists drifting apart is exactly the bug that would leak the app),
and every PHP source parses (when a ``php`` binary is available).
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_WEBAPP = Path(__file__).resolve().parents[1] / "webapp"
_GATE = _WEBAPP / "gate"


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


def test_gate_blocklist_separates_generic_from_professional() -> None:
    """The vendored domain list refuses the big generic providers, not companies."""
    domains = set((_GATE / "free_domains.txt").read_text().split())
    assert len(domains) > 5000, "blocklist suspiciously small; vendoring broke"
    for generic in (
        "gmail.com",
        "yahoo.com",
        "yahoo.fr",
        "hotmail.com",
        "outlook.com",
        "icloud.com",
        "protonmail.com",
        "orange.fr",
        "wanadoo.fr",
        "free.fr",
        "laposte.net",
        "mailinator.com",  # disposable providers are refused too
    ):
        assert generic in domains, f"{generic} missing from the blocklist"
    for professional in ("deraison.ai", "anthropic.com", "airbus.com"):
        assert professional not in domains, f"{professional} wrongly blocklisted"


def test_gate_htaccess_and_serve_protect_the_same_app_surface() -> None:
    """The Apache rewrites and serve.php's own matcher must never drift apart.

    .htaccess decides WHICH URLs go through the gate; serve.php re-matches the
    path before serving. A surface listed in one but not the other either
    leaks an app file to anonymous visitors or 404s it for signed-in ones.
    """
    htaccess = (_GATE / "htaccess.dist").read_text()
    serve = (_GATE / "serve.php").read_text()
    for surface in ("index\\.html", "backend-pyodide\\.js", "py|wheels|i18n|vocab|examples"):
        assert surface in htaccess, f".htaccess no longer routes {surface} through the gate"
        assert surface in serve, f"serve.php no longer matches {surface}"
    # The two other denial layers: runtime data, and the library file.
    assert "private" in htaccess
    assert "gate/auth\\.php" in htaccess


def test_gate_php_sources_parse() -> None:
    """Every PHP file passes `php -l` (skipped where no php binary exists, e.g. CI)."""
    php = shutil.which("php")
    if php is None:
        pytest.skip("no php binary on this machine")
    for source in sorted(_GATE.glob("*.php")):
        result = subprocess.run(
            [php, "-l", str(source)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, f"{source.name}: {result.stdout}{result.stderr}"


def test_gate_landing_keeps_consent_honeypot_and_seo_anchor() -> None:
    """The landing template ships its legal + anti-bot + SEO integration points."""
    landing = (_GATE / "landing.php").read_text()
    assert landing.count("<!--SEO_HEAD-->") == 1, "build.py's SEO head anchor is gone"
    assert 'name="consent"' in landing, "GDPR consent checkbox removed"
    assert 'name="website"' in landing, "bot honeypot field removed"
    assert "gate/access.php" in landing, "form no longer posts to the gate"
