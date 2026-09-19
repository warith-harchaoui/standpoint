"""Render the landing page's static example figures from the real engine.

The lead-magnet landing (webapp/gate/landing.php) shows non-editable previews
of the four example datasets. Rather than drawing separate marketing images,
this script drives the ACTUAL built app headlessly (Playwright over a local
server on ``dist/``, Pyodide engine, CDN embeddings for the pole names) and
saves each generated map as ``dist/static/examples/<id>.<lang>.svg`` — so the
public previews are pixel-honest about what the gated app produces.

Run after ``python webapp/build.py`` (needs network for the CDNs)::

    python webapp/render_examples.py

The landing page hides any preview whose file is missing, so a build without
this step ships a working page with an empty gallery, not broken images.
"""

from __future__ import annotations

import http.server
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

WEBAPP = Path(__file__).resolve().parent
DIST = WEBAPP / "dist"
OUT = DIST / "static" / "examples"
PORT = 8794

# Dataset id -> the first grid cell's value per language, the deterministic
# signal that THIS example finished loading (mirrors the tracked CSV headers).
EXAMPLES: dict[str, dict[str, str]] = {
    "programming_languages": {"en": "Programming Language", "fr": "Langage de programmation"},
    "laptops": {"en": "Laptop", "fr": "Ordinateur portable"},
    "cloud_providers": {"en": "Provider", "fr": "Fournisseur"},
    "voitures_electriques": {"en": "Electric Car", "fr": "Voiture"},
}


def serve() -> http.server.ThreadingHTTPServer:
    """Serve dist/ quietly on localhost; returns the running server."""

    class Quiet(http.server.SimpleHTTPRequestHandler):
        """SimpleHTTPRequestHandler without per-request stderr noise."""

        def log_message(self, *args: object) -> None:
            """Silence request logging (the render progress is the signal)."""

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", PORT), partial(Quiet, directory=str(DIST))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def render_one(page: Page, example_id: str, first_cell: str) -> str:
    """Load one example, generate its map, and return the SVG markup."""
    page.click(f'[data-example="{example_id}"]')
    page.wait_for_function(
        "value => document.querySelector('#grid input.cell-name').value === value",
        arg=first_cell,
    )
    page.click("#run")
    page.wait_for_selector("#chart svg", timeout=300_000)
    page.wait_for_function("document.getElementById('busy').classList.contains('hidden')")
    svg = page.eval_on_selector("#chart svg", "el => el.outerHTML")
    if "<svg" not in svg:
        raise SystemExit(f"no SVG produced for {example_id}")
    return svg


def main() -> None:
    """Render every (dataset, language) pair into dist/static/examples/."""
    OUT.mkdir(parents=True, exist_ok=True)
    server = serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{PORT}/index.html")
            page.wait_for_function("document.querySelectorAll('#grid tr').length > 5")
            # One browser session for all renders: the Pyodide boot (the slow
            # part) is paid once, each subsequent run reuses the live engine.
            for lang in ("en", "fr"):
                if page.evaluate("document.documentElement.lang") != lang:
                    page.click("#langToggle")
                    page.wait_for_function(
                        "lang => document.documentElement.lang === lang", arg=lang
                    )
                for example_id, cells in EXAMPLES.items():
                    svg = render_one(page, example_id, cells[lang])
                    out = OUT / f"{example_id}.{lang}.svg"
                    out.write_text(svg, encoding="utf-8")
                    print(f"{out.relative_to(DIST)} ({len(svg) / 1e3:.0f} kB)")
            browser.close()
    finally:
        server.shutdown()
    print("static example figures rendered")


if __name__ == "__main__":
    main()
