# Contributing

Thanks for your interest. This file documents how the project is maintained and what
to expect. The full engineering standard lives in [CODING.md](CODING.md).

## Versioning

This project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).
Given a version `MAJOR.MINOR.PATCH`:

- **MAJOR** bumps when the public API changes in a way that breaks existing callers:
  a function removed, a signature changed incompatibly, an exception type changed, a
  return shape changed, or a default behaviour reversed.
- **MINOR** bumps when functionality is added in a backwards-compatible way: a new
  function, a new optional parameter, a new optional dependency.
- **PATCH** bumps for backwards-compatible fixes only: bug fixes, internal refactors,
  packaging fixes, or dependency-pin bumps that don't change observable behaviour.

The public surface is what `standpoint.__all__` exports, the two console commands
(`standpoint`, `standpoint-click`), and the shapes of the `Positioning` / `PCAResult`
objects. The single source of truth for the version is `standpoint.__version__`.

## Running the checks locally

CI is intentionally light: one Python, `ruff check`, and the deterministic core
tests. The full gate runs **locally before you push** (shift validation left, coding
standard Rule 18). Run it all:

```bash
pip install -e ".[dev,mcp]"                        # library + tests + GUI/API/MCP surfaces

# Lint + format (everything, skill scripts included):
python3 -m ruff check standpoint tests skills
python3 -m ruff format --check standpoint tests

# The whole test suite:
python3 -m pytest tests/ -q                        # core + GUI + MCP endpoints

# Optional, heavier surfaces (each self-skips if its dep is missing):
pip install ".[eval]"                              # DeepEval pole-naming eval (needs Ollama)
pip install playwright && playwright install chromium   # the headless-Chromium GUI e2e test
```

Notes:

- `ruff check` and `ruff format --check` must both exit 0; a lint or format violation
  is a blocker, like a failing test. (CI pins `ruff` so its result is reproducible;
  match it locally if a new ruff release disagrees.)
- The deterministic tests need no model. The two model-backed tests and the DeepEval
  evaluation run only when a local Ollama with the `qwen2.5vl` model is present, and
  skip cleanly otherwise. The GUI / MCP endpoint tests need the `[gui]` / `[mcp]`
  extras; the Playwright end-to-end test needs Chromium. All skip when absent, so CI
  (which installs none of them) stays green.

## Code expectations

Summarized from [CODING.md](CODING.md); read it before a non-trivial change:

- **Docstrings and typing on every function**, including private (`_name`) and nested
  ones, in numpydoc style with full annotations.
- **Comment the *why*.** Aim for roughly one comment line per three or four lines of
  code; explain trade-offs and non-obvious choices, not the syntax.
- **No bare `print` in library code**: use the module `logger`. The CLI in `run()`
  is the one place that prints on purpose.
- **Keep the diff focused.** Update tests and docs alongside behaviour changes; don't
  fold in unrelated rewrites.
- **No AI-assistant attribution.** Commits are authored by their human contributors;
  AI tools are not listed as authors or co-authors.

## Releasing

1. Update `CHANGELOG.md` (move the relevant `[Unreleased]` entries under the new
   version and date).
2. Bump `standpoint.__version__`.
3. Regenerate the example figures if behaviour that affects them changed
   (`python3 -m standpoint examples/<name>.csv --outdir examples --stem <name>`).
4. Ensure CI is green, tag `vMAJOR.MINOR.PATCH`, and publish the GitHub release.

## Author

[Warith Harchaoui](https://www.linkedin.com/in/warith-harchaoui)
