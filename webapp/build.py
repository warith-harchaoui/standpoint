"""Compose the static, SFTP-uploadable Standpoint web app into ``webapp/dist/``.

The static build is the same single-page GUI the FastAPI server serves at
``/gui`` — literally the same HTML string (``standpoint.webgui.GUI_HTML``) —
with two build-time twists:

1. ``backend-pyodide.js`` is injected *before* the page's main script, so the
   page's ``window.backend`` override kicks in and every data operation runs on
   an in-browser Python engine (Pyodide) instead of a server. Uploading the
   resulting ``dist/`` folder to any static host (e.g. SFTP to
   https://deraison.ai/standpoint) yields a fully working app: no process to
   run, nothing to maintain server-side.
2. Absolute server URLs (``/static/...``, ``/favicon.ico``,
   ``/site.webmanifest``) become bundle-relative so the app works from any
   mount point.

What lands in ``dist/``:

- ``index.html``          the composed page
- ``backend-pyodide.js``  the Pyodide transport + memoized-replay LLM driver
- ``py/beh_shim.py``      browser stand-in for best_engine_ai_helper (see file)
- ``py/glue.py``          the endpoint logic, mirrored from standpoint.api
- ``py/manifest.json``    vendored wheel list, in install order
- ``wheels/*.whl``        standpoint + pure-Python deps absent from Pyodide
                          (langdetect, et_xmlfile, openpyxl)
- ``i18n/<lang>.json``    the GUI string tables, exported so localization
                          needs no Python at page load
- ``vocab/<lang>.json``   candidate pole names for the embedding-based axis
                          naming (transformers.js MiniLM, loaded lazily)
- ``example.csv``         the starter table (tracked example, same as the API)
- ``static/*``            icons + webmanifest (paths rewritten to relative)

Run from the repo root with the project env active::

    python webapp/build.py          # writes webapp/dist/
    python webapp/build.py --clean  # rebuild from scratch

The Pyodide runtime itself is loaded from the jsDelivr CDN at page load (see
``backend-pyodide.js``): only the wheels built here ship in the folder.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Repo layout anchors: this file lives in <repo>/webapp/.
WEBAPP = Path(__file__).resolve().parent
REPO = WEBAPP.parent
DIST = WEBAPP / "dist"

# Pure-Python deps to vendor as wheels, in INSTALL ORDER (dependencies first:
# micropip installs each with deps=False, so order is the dependency resolution).
# Version pins mirror pyproject.toml lower bounds; bump deliberately, not by drift.
VENDORED = ["langdetect==1.0.9", "et_xmlfile", "openpyxl"]


def _run(cmd: list[str]) -> None:
    """Run a subprocess loudly; a non-zero exit aborts the build."""
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def build_wheels() -> list[str]:
    """Build the vendored wheels (standpoint + pure-Python deps) into dist/wheels.

    Returns
    -------
    list[str]
        Wheel filenames in install order (dependencies before dependents),
        ready for ``py/manifest.json``.
    """
    wheels_dir = DIST / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)
    # --no-deps everywhere: the browser install is deps=False by design (the
    # numeric stack comes from the Pyodide distribution, the LLM helper is
    # shimmed), so the build must not drag in wheels nobody installs.
    for spec in VENDORED:
        _run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheels_dir), spec])
    _run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheels_dir), str(REPO)])

    names = {p.name for p in wheels_dir.glob("*.whl")}

    def pick(prefix: str) -> str:
        """The one wheel whose filename starts with `prefix` (fail loudly otherwise)."""
        found = sorted(n for n in names if n.startswith(prefix))
        if len(found) != 1:
            raise SystemExit(f"expected exactly one {prefix}* wheel, found {found}")
        return found[0]

    # Explicit install order: langdetect and the openpyxl chain first, then
    # standpoint itself (its import pulls all of them plus the shimmed helper).
    return [pick("langdetect"), pick("et_xmlfile"), pick("openpyxl"), pick("standpoint")]


def export_i18n() -> None:
    """Dump each language's GUI string table to dist/i18n/<lang>.json.

    Exported at build time so the page localizes instantly from a static fetch,
    without waiting for the Python engine to boot.
    """
    import standpoint as sp

    out = DIST / "i18n"
    out.mkdir(parents=True, exist_ok=True)
    for lang in sorted(sp.SUPPORTED_LANGS):
        strings = sp.i18n(lang).get("gui") or sp.i18n("en")["gui"]
        (out / f"{lang}.json").write_text(
            json.dumps(strings, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"i18n/{lang}.json ({len(strings)} strings)")


def compose_index() -> None:
    """Write dist/index.html: GUI_HTML + the Pyodide backend + relative URLs."""
    from standpoint.webgui import GUI_HTML

    html = GUI_HTML
    # Bundle-relative asset URLs, so the app works mounted under /standpoint/.
    html = html.replace('href="/favicon.ico"', 'href="./static/favicon.ico"')
    html = html.replace('href="/site.webmanifest"', 'href="./static/site.webmanifest"')
    html = html.replace('"/static/', '"./static/')
    # Inject the backend override BEFORE the page's main script: the page keeps
    # `window.backend` when one is already defined (see webgui.py's backend layer).
    anchor = "<script>\n// --- tiny state"
    if html.count(anchor) != 1:
        raise SystemExit("GUI_HTML anchor not found: webgui.py layout changed, update build.py")
    html = html.replace(anchor, '<script src="./backend-pyodide.js"></script>\n' + anchor)
    (DIST / "index.html").write_text(html, encoding="utf-8")
    print("index.html composed")


def copy_assets(wheel_names: list[str]) -> None:
    """Copy the transport, glue, icons, starter table; write the wheel manifest."""
    (DIST / "py").mkdir(parents=True, exist_ok=True)
    shutil.copy2(WEBAPP / "backend-pyodide.js", DIST / "backend-pyodide.js")
    shutil.copy2(WEBAPP / "beh_shim.py", DIST / "py" / "beh_shim.py")
    shutil.copy2(WEBAPP / "glue.py", DIST / "py" / "glue.py")
    (DIST / "py" / "manifest.json").write_text(json.dumps({"wheels": wheel_names}, indent=1))

    # Icons + manifest: same files the server mounts at /static, with the
    # manifest's absolute URLs rewritten for a sub-path static deployment.
    static_src = REPO / "standpoint" / "static"
    static_dst = DIST / "static"
    if static_dst.exists():
        shutil.rmtree(static_dst)
    shutil.copytree(static_src, static_dst)
    manifest = json.loads((static_dst / "site.webmanifest").read_text(encoding="utf-8"))
    manifest["start_url"] = "./"
    manifest["scope"] = "./"
    for icon in manifest.get("icons", []):
        icon["src"] = icon["src"].replace("/static/", "./")
    (static_dst / "site.webmanifest").write_text(json.dumps(manifest, indent=2))

    # The same starter table the API serves, so the two builds boot identically.
    shutil.copy2(REPO / "examples" / "programming_languages.csv", DIST / "example.csv")

    # The candidate pole-name vocabularies the embedding-based axis naming
    # scores against (one list of positive qualities per GUI language).
    vocab_dst = DIST / "vocab"
    if vocab_dst.exists():
        shutil.rmtree(vocab_dst)
    shutil.copytree(WEBAPP / "vocab", vocab_dst)
    print("assets copied")


def main() -> None:
    """Build dist/ end to end; ``--clean`` wipes a previous build first."""
    parser = argparse.ArgumentParser(description="Build the static Standpoint web app.")
    parser.add_argument("--clean", action="store_true", help="remove dist/ before building")
    args = parser.parse_args()

    if args.clean and DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)

    wheels = build_wheels()
    export_i18n()
    compose_index()
    copy_assets(wheels)
    total = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"\ndist/ ready ({total / 1e6:.1f} MB before the CDN-served Pyodide runtime).")
    print("Upload the CONTENTS of webapp/dist/ to the web folder (e.g. /standpoint).")


if __name__ == "__main__":
    main()
