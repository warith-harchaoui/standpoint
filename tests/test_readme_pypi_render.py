"""Guard the PyPI project page against links that only resolve on GitHub.

`pyproject.toml` ships `readme = "README.md"`, so README.md *is* the PyPI
project page. PyPI renders it standalone at `https://pypi.org/project/...`,
with no repository around it: a relative target like `[GUI.md](GUI.md)` or
`<img src="assets/logo.png">` resolves against the repository on GitHub but
404s on PyPI. The fix is to write the full `https://github.com/...` (or
`raw.githubusercontent.com`) URL, which renders correctly in *both* places.

LISEZMOI.md is held to the same rule: it is the French twin of the page and is
linked from it, so a reader arriving from PyPI is in the same position.

Same-page anchors (`](#local-first)`) are exempt -- they resolve inside the
rendered document itself, wherever it is rendered.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Repo root = the directory that holds pyproject.toml (tests/ is one level down).
_ROOT = Path(__file__).resolve().parent.parent

# The two documents rendered outside the repository: the PyPI page and its
# French twin, which the page links to.
_RENDERED = ("README.md", "LISEZMOI.md")

# A Markdown inline link or image target: `](target)`. Captures the target so the
# assertion can name it. Reference-style definitions (`[id]: target`) are matched
# by _MD_REFERENCE below.
_MD_INLINE = re.compile(r"!?\]\(\s*([^)\s]+)")

# A reference-style link definition at the start of a line: `[id]: target`.
_MD_REFERENCE = re.compile(r"(?m)^\s*\[[^\]]+\]:\s*(\S+)")

# An HTML `src=` / `href=` attribute (both files use raw <img>/<a> tags for the
# centred logo and the badges).
_HTML_ATTR = re.compile(r"(?:src|href)\s*=\s*[\"']([^\"']+)[\"']")

# Targets that resolve wherever the document is rendered: absolute URLs, protocol
# -relative URLs, same-page anchors, and mailto:.
_PORTABLE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.IGNORECASE)


def _targets(text: str) -> list[str]:
    """Every link/image target in a Markdown document, inline, reference and HTML."""
    return [
        *(m.group(1) for m in _MD_INLINE.finditer(text)),
        *(m.group(1) for m in _MD_REFERENCE.finditer(text)),
        *(m.group(1) for m in _HTML_ATTR.finditer(text)),
    ]


@pytest.mark.parametrize("filename", _RENDERED)
def test_rendered_doc_has_no_repo_relative_targets(filename: str) -> None:
    """No link or image in a PyPI-rendered doc may depend on the repository around it.

    PyPI serves README.md with no repo context, so a relative target silently
    becomes a broken link (or a missing image) on the project page. Fails with
    the exact offending targets so the fix is mechanical: prefix each with
    `https://github.com/warith-harchaoui/standpoint/blob/main/` for files, or
    `https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/` for
    images.
    """
    path = _ROOT / filename
    offenders = sorted(
        {t for t in _targets(path.read_text(encoding="utf-8")) if not _PORTABLE.match(t)}
    )
    assert not offenders, (
        f"{filename} has {len(offenders)} repo-relative target(s) that break on the "
        f"PyPI project page: {offenders}; write the full https:// URL instead, which "
        f"renders correctly on GitHub and on PyPI."
    )
