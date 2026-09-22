"""Compose the static, SFTP-uploadable Standpoint web app into ``web/``.

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
- ``examples/*.csv``      the tracked example tables (one per example button)
- ``static/*``            icons + webmanifest (paths rewritten to relative),
                          incl. the sprezzature favicon/PWA set generated from
                          assets/logo.png and the Open Graph card (og-card.png)
- ``robots.txt`` / ``sitemap.xml`` / ``llms.txt`` / ``llms-full.txt`` /
  ``humans.txt``          SEO + GEO indexes (sprezzature-publish site_indexes)
- ``*.md``                the curated Markdown corpus (README, LISEZMOI, GUI,
                          EXAMPLES, EXEMPLES) the indexes cite, served raw
- ``index.php``           the PUBLIC landing page (lead-magnet gate): SEO head,
                          static example figures, professional-email form
- ``gate/*.php``, ``gate/free_domains.txt``, ``gate/track.js``, ``.htaccess``
                          the gate itself (see webapp/gate/auth.php): magic-link
                          auth, per-user activity logs, generic-domain blocklist;
                          the .htaccess routes every app file through the gate
- ``private/``            runtime data (secret, leads, logs), pre-created here
                          with its "Require all denied" .htaccess

The gate needs the host to run PHP (deraison.ai does, 8.1) and to honour
.htaccess rewrites; served without PHP the SAME dist/ degrades to the old
ungated static app (index.html still works directly), which is also how the
local python -m http.server smoke tests keep passing.

``index.html`` additionally carries the deployment head block (canonical URL,
Open Graph / Twitter card, Schema.org JSON-LD) from ``seo/head-seo.html``,
resolved against ``--base-url`` (default: https://deraison.ai/standpoint).

Run from the repo root with the project env active::

    python webapp/build.py --model distillation/checkpoints/llm-engine

writes ``web/`` at the repo root: the whole upload payload for
deraison.ai/standpoint, code and model together, nothing else to think about.
Upload its CONTENTS (including the dotfiles ``.htaccess``) to /standpoint.

    python webapp/build.py --clean  # rebuild from scratch

    # Open-access mirror (sev7n): no landing page, no PHP, no tracking.
    python webapp/build.py --no-gate --clean --out web-sev7n \\
        --base-url https://deraison.ai/standpoint

The Pyodide runtime itself is loaded from the jsDelivr CDN at page load (see
``backend-pyodide.js``): only the wheels built here ship in the folder.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Repo layout anchors: this file lives in <repo>/webapp/.
WEBAPP = Path(__file__).resolve().parent
REPO = WEBAPP.parent
DIST = REPO / "web"

# Where the bundle is deployed; drives the canonical URL, the OG image URL and
# every absolute URL in sitemap.xml / llms.txt (override with --base-url).
BASE_URL = "https://deraison.ai/standpoint"

# The sprezzature-publish scripts used for the SEO/GEO artifacts.
_SPREZZATURE = Path.home() / ".claude" / "skills" / "sprezzature-publish" / "scripts"

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
    # Start clean: a version bump would otherwise leave the previous standpoint
    # wheel behind and break the exactly-one pick below.
    if wheels_dir.exists():
        shutil.rmtree(wheels_dir)
    wheels_dir.mkdir(parents=True)
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
        strings = dict(sp.i18n(lang).get("gui") or sp.i18n("en")["gui"])
        # The static build's "Laziness" panel formats the engine's own ratings
        # prompt client-side (no Pyodide wait), so ship the template alongside
        # the GUI strings.
        strings["ratings_prompt"] = sp.i18n(lang)["ratings_prompt"]
        (out / f"{lang}.json").write_text(
            json.dumps(strings, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"i18n/{lang}.json ({len(strings)} strings)")


def compose_index(base_url: str, *, gated: bool = True, llm_server: dict | None = None) -> None:
    """Write dist/index.html: GUI_HTML + Pyodide backend + relative URLs + SEO head.

    Parameters
    ----------
    base_url
        Deployment URL, used for the canonical/OG/JSON-LD head block.
    gated
        Whether this build ships the lead-magnet gate. A gate-less build must
        not reference ``gate/track.js``: the file is not copied, so the tag
        would only buy a 404 in every visitor's console.
    llm_server
        Optional ``{url, model, key}`` for a shared OpenAI-compatible inference
        server. Injected as ``window.__standpointLLMServer``; the page decides
        at runtime whether it is actually reachable (an http endpoint cannot be
        called from an https page) and falls back to the in-page model. Absent
        by default, so the public builds stay purely in-browser.
    """
    from standpoint.webgui import GUI_HTML

    html = GUI_HTML
    # Bundle-relative asset URLs, so the app works mounted under /standpoint/.
    html = html.replace('href="/favicon.ico"', 'href="./static/favicon.ico"')
    html = html.replace('href="/site.webmanifest"', 'href="./static/site.webmanifest"')
    html = html.replace('"/static/', '"./static/')
    # The SEO/GEO head block (canonical, Open Graph / Twitter card, JSON-LD) is a
    # deployment concern, so it lives in the build, not in GUI_HTML: the localhost
    # server GUI must never claim the deraison.ai canonical.
    seo_head = (WEBAPP / "seo" / "head-seo.html").read_text(encoding="utf-8")
    seo_head = seo_head.replace("{BASE}", base_url.rstrip("/"))
    html = html.replace("</title>", "</title>\n" + seo_head, 1)
    # Inject the backend override BEFORE the page's main script: the page keeps
    # `window.backend` when one is already defined (see webgui.py's backend layer).
    anchor = "<script>\n// --- tiny state"
    if html.count(anchor) != 1:
        raise SystemExit("GUI_HTML anchor not found: webgui.py layout changed, update build.py")
    tracker = '<script src="./gate/track.js" defer></script>\n' if gated else ""
    # Injected BEFORE backend-pyodide.js, which reads it at module scope.
    server = (
        f"<script>window.__standpointLLMServer = {json.dumps(llm_server)};</script>\n"
        if llm_server
        else ""
    )
    html = html.replace(
        anchor,
        tracker + server + '<script src="./backend-pyodide.js"></script>\n' + anchor,
    )
    (DIST / "index.html").write_text(html, encoding="utf-8")
    print("index.html composed")


def copy_assets(wheel_names: list[str]) -> None:
    """Copy the transport, glue, icons, starter table; write the wheel manifest."""
    (DIST / "py").mkdir(parents=True, exist_ok=True)
    shutil.copy2(WEBAPP / "backend-pyodide.js", DIST / "backend-pyodide.js")
    shutil.copy2(WEBAPP / "beh_shim.py", DIST / "py" / "beh_shim.py")
    shutil.copy2(WEBAPP / "glue.py", DIST / "py" / "glue.py")
    (DIST / "py" / "manifest.json").write_text(json.dumps({"wheels": wheel_names}, indent=1))

    # Icons: start from the server's /static (logo, legacy names some caches may
    # still ask for), then overlay the fuller sprezzature set generated from
    # assets/logo.png (webapp/seo/icons: 16/32/48, apple-touch, 192/512 +
    # maskable PWA icons) and the Open Graph card.
    static_src = REPO / "standpoint" / "static"
    static_dst = DIST / "static"
    if static_dst.exists():
        shutil.rmtree(static_dst)
    shutil.copytree(static_src, static_dst)
    for icon_file in (WEBAPP / "seo" / "icons").iterdir():
        if icon_file.suffix in {".png", ".ico"}:
            shutil.copy2(icon_file, static_dst / icon_file.name)
    shutil.copy2(WEBAPP / "seo" / "og-card.png", static_dst / "og-card.png")

    # One merged manifest: the sprezzature icon set + the app's identity, with
    # URLs relative to the manifest's own location (dist/static/), so the PWA
    # opens the app root, not the static folder.
    manifest = json.loads(
        (WEBAPP / "seo" / "icons" / "site.webmanifest").read_text(encoding="utf-8")
    )
    manifest["description"] = (
        "Turn a comparison table into a labelled 2D positioning map, entirely in your browser."
    )
    manifest["start_url"] = "../"
    manifest["scope"] = "../"
    for icon in manifest.get("icons", []):
        icon["src"] = "./" + icon["src"].lstrip("/")
    (static_dst / "site.webmanifest").write_text(json.dumps(manifest, indent=2))

    # The same tracked example tables the API serves (one per example button),
    # so the two builds boot identically and offer identical datasets. The
    # language matrix is completed here: every dataset ships as <id>.en.csv AND
    # <id>.fr.csv (the base file fills any missing translation), so the page
    # can fetch the current language's variant directly, without 404 probing.
    examples_dst = DIST / "examples"
    examples_dst.mkdir(parents=True, exist_ok=True)
    for csv in (REPO / "examples").glob("*.csv"):
        shutil.copy2(csv, examples_dst / csv.name)
    base_ids = [p.stem for p in examples_dst.glob("*.csv") if "." not in p.stem]
    for base_id in base_ids:
        for lang in ("en", "fr"):
            variant = examples_dst / f"{base_id}.{lang}.csv"
            if not variant.exists():
                shutil.copy2(examples_dst / f"{base_id}.csv", variant)

    # The candidate pole-name vocabularies the embedding-based axis naming
    # scores against (one list of positive qualities per GUI language).
    vocab_dst = DIST / "vocab"
    if vocab_dst.exists():
        shutil.rmtree(vocab_dst)
    shutil.copytree(WEBAPP / "vocab", vocab_dst)
    print("assets copied")


def gate_assets(base_url: str) -> None:
    """Install the lead-magnet gate: landing page, PHP endpoints, .htaccess.

    The interactive app stays exactly as composed by :func:`compose_index`;
    the gate wraps it at the HTTP layer (see ``webapp/gate/auth.php`` for the
    architecture). The landing page reuses the same SEO head block as the app,
    so gating changes what visitors can DO, not what crawlers can read.
    """
    gate_src = WEBAPP / "gate"
    gate_dst = DIST / "gate"
    gate_dst.mkdir(parents=True, exist_ok=True)
    for name in (
        "auth.php",
        "access.php",
        "login.php",
        "serve.php",
        "track.php",
        "track.js",
        "free_domains.txt",
        # The healing template: auth.php restores the root .htaccess from this
        # copy when an SFTP sync drops or overwrites the dotfile (seen in prod).
        "htaccess.dist",
    ):
        shutil.copy2(gate_src / name, gate_dst / name)

    # The public landing (dist/index.php) carries the deployment SEO head.
    seo_head = (WEBAPP / "seo" / "head-seo.html").read_text(encoding="utf-8")
    seo_head = seo_head.replace("{BASE}", base_url.rstrip("/"))
    landing = (gate_src / "landing.php").read_text(encoding="utf-8")
    if landing.count("<!--SEO_HEAD-->") != 1:
        raise SystemExit("landing.php SEO_HEAD placeholder missing")
    (DIST / "index.php").write_text(landing.replace("<!--SEO_HEAD-->", seo_head), encoding="utf-8")

    shutil.copy2(gate_src / "htaccess.dist", DIST / ".htaccess")

    # Pre-create the runtime data directory already web-denied, so the deny
    # rule is in place from the very first upload (auth.php re-asserts it).
    # private/ ships with its deny rule and NOTHING else: a local dev run leaves
    # magic-link outboxes, a session secret and per-user logs in here, and none
    # of that belongs in an upload. The server makes its own.
    private = DIST / "private"
    if private.exists():
        shutil.rmtree(private)
    private.mkdir(parents=True)
    (private / ".htaccess").write_text("Require all denied\n", encoding="utf-8")
    print("gate installed (index.php, gate/, .htaccess, private/)")


def site_indexes(base_url: str) -> None:
    """Emit robots.txt, sitemap.xml, llms.txt, llms-full.txt and humans.txt into dist/.

    Runs sprezzature-publish's stdlib-only ``site_indexes.py`` over a staged
    corpus: the built ``index.html`` (for the sitemap) plus the repo's curated
    Markdown (README/LISEZMOI, GUI, EXAMPLES/EXEMPLES), which becomes the
    ``llms-full.txt`` full-text body that generative engines read.
    """
    script = _SPREZZATURE / "site_indexes.py"
    if not script.exists():
        print(f"note: {script} not found; skipping robots/sitemap/llms indexes")
        return
    corpus = ["README.md", "LISEZMOI.md", "GUI.md", "EXAMPLES.md", "EXEMPLES.md"]
    # The corpus ships in dist/ too, so every URL the sitemap and llms.txt cite
    # actually resolves — and generative engines get raw Markdown to read.
    for name in corpus:
        shutil.copy2(REPO / name, DIST / name)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copy2(DIST / "index.html", stage / "index.html")
        for name in corpus:
            shutil.copy2(REPO / name, stage / name)
        # humans.txt credits: the script reads AUTHORS when present.
        (stage / "AUTHORS").write_text("Warith Harchaoui — https://deraison.ai\n", encoding="utf-8")
        _run(
            [
                sys.executable,
                str(script),
                "--root",
                str(stage),
                "--base-url",
                base_url,
                "--out",
                str(stage),
                "--humans",
                "--name",
                "Standpoint",
                "--summary",
                "Standpoint turns a comparison table into a labelled 2D positioning "
                "map, entirely in the visitor's browser (WebAssembly). By Warith "
                "Harchaoui (https://deraison.ai). Free, BSD 3-Clause.",
            ]
        )
        for name in ("robots.txt", "sitemap.xml", "llms.txt", "llms-full.txt", "humans.txt"):
            if (stage / name).exists():
                shutil.copy2(stage / name, DIST / name)
                print(f"{name} written")


def main() -> None:
    """Build dist/ end to end; ``--clean`` wipes a previous build first."""
    global DIST  # every helper writes relative to this module-level anchor
    parser = argparse.ArgumentParser(description="Build the static Standpoint web app.")
    parser.add_argument("--clean", action="store_true", help="remove dist/ before building")
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="deployment URL for canonical/OG/sitemap (default: %(default)s)",
    )
    parser.add_argument(
        "--llm-server",
        default=None,
        metavar="URL",
        help="point the Laziness button at a shared OpenAI-compatible server "
        "(e.g. http://gpu1.example:8000) instead of the in-page model. The page "
        "still falls back to the in-page model whenever the server cannot be "
        "used -- including from an https page, which browsers forbid from "
        "calling an http endpoint",
    )
    parser.add_argument(
        "--llm-server-model",
        default=None,
        metavar="NAME",
        help="model id to ask that server for (required with --llm-server)",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="copy this folder in as dist/llm-engine/ (the distilled student the "
        "Laziness button downloads, produced by "
        "distillation/scripts/05_export_browser.py). ~640 MB, so it is opt-in: "
        "without it the bundle expects the folder to be uploaded separately",
    )
    parser.add_argument(
        "--no-gate",
        action="store_true",
        help="build the freely accessible app: no landing page, no PHP endpoints, "
        "no .htaccess, no activity tracking (for hosts without PHP, or for a "
        "mirror that is meant to be open)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DIST,
        help="output folder (default: %(default)s); use a separate one to keep "
        "the gated dist/ intact",
    )
    args = parser.parse_args()
    DIST = args.out.resolve()

    if args.clean and DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)

    wheels = build_wheels()
    export_i18n()
    llm_server = None
    if args.llm_server:
        if not args.llm_server_model:
            parser.error("--llm-server needs --llm-server-model")
        llm_server = {"url": args.llm_server, "model": args.llm_server_model}
        print(f"shared inference server wired in: {args.llm_server} ({args.llm_server_model})")
    compose_index(args.base_url, gated=not args.no_gate, llm_server=llm_server)
    copy_assets(wheels)
    if args.model:
        model_dst = DIST / "llm-engine"
        if model_dst.exists():
            shutil.rmtree(model_dst)
        shutil.copytree(args.model, model_dst)
        size = sum(f.stat().st_size for f in model_dst.rglob("*") if f.is_file())
        print(f"llm-engine/ copied ({size / 1e6:.0f} MB)")
    if args.no_gate:
        print("gate skipped (--no-gate): index.html is the entry point, open access")
    else:
        gate_assets(args.base_url)
    site_indexes(args.base_url)
    total = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"\n{DIST.name}/ ready ({total / 1e6:.1f} MB before the CDN-served Pyodide runtime).")
    print(f"Upload the CONTENTS of {DIST.name}/ to the web folder (e.g. /standpoint),")
    print("dotfiles included (.htaccess). Do NOT use a mirroring sync that deletes")
    print("remote files: private/ on the server holds the leads and the session secret.")


if __name__ == "__main__":
    main()
