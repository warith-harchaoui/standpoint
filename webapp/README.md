# webapp/ — the static build of the Standpoint GUI

The same single-page GUI the server serves at `/gui`, composed into a folder
any static host can serve: the engine runs in the visitor's browser (Pyodide /
WebAssembly), axes are named by default by a small in-page embedding model
(transformers.js MiniLM + curated vocabularies), and one click on "Laziness"
has an in-browser LLM (WebLLM, lazy ~1 GB download, then cached) fill the
empty cells. Full architecture, diagram and limitations:
[GUI.md § Static build](../GUI.md).

## Build and deploy

```bash
python webapp/build.py            # writes webapp/dist/ (~4 MB)
# upload the CONTENTS of webapp/dist/ to the target web folder, e.g.:
#   sftp> put -r webapp/dist/* /path/to/htdocs/standpoint/
```

The bundle is relocatable (relative URLs only), so it works at any mount point,
e.g. `https://deraison.ai/standpoint`. The Pyodide runtime and the numeric
wheels load from the jsDelivr CDN on first visit (~15–20 MB, browser-cached);
everything else ships in the folder.

### Hosts that forbid `.json`

Some shared hosts refuse to serve the `.json` extension at all. deraison.ai
started doing so on 2026-09-25: **every** `*.json` URL answers `403`, including
one that points at no file. The page then reads an HTML error body where it
expected JSON, and the visitor sees

    Unexpected token '<', "<!DOCTYPE "... is not valid JSON

`--json-txt` is the workaround. It ships each JSON payload as
`<name>.json.txt` (the bytes are untouched; `Response.json()` ignores the
content type) and injects `json-txt.js`, which rewrites *same-origin* `.json`
reads to that twin. Patching `fetch` rather than the call sites is deliberate:
transformers.js composes `config.json`, `tokenizer.json` and friends itself, so
there is no call site to edit. Cross-origin reads are left alone — the CDN
serving Pyodide and the embedding model has no such rule.

```bash
python webapp/build.py --no-gate --json-txt    # what deraison.ai needs today
```

Drop the flag once the host serves `.json` again; the payload is otherwise
identical. Verified against a deliberately `.json`-hostile local server with
`.private/ralph-loop/verify_hostile.py` (full journey plus Laziness, zero 403s
reaching the page).

## Files

| File                 | Role                                                                        |
| -------------------- | --------------------------------------------------------------------------- |
| `build.py`           | Composes `dist/` from `standpoint.webgui.GUI_HTML` + these files            |
| `backend-pyodide.js` | The `window.backend` transport: Pyodide boot, replay driver, embedding namer, delegation panel |
| `glue.py`            | Endpoint logic mirrored from `standpoint.api` (+ `pole_context`), in Pyodide |
| `beh_shim.py`        | Memoized-replay stand-in for `best-engine-ai-helper`                        |
| `vocab/<lang>.json`  | Candidate pole names (positive qualities; confusable entries glossed)       |
| `json-txt.js`        | Emitted by `--json-txt`: rewrites same-origin `.json` reads to `.json.txt` |
| `seo/head-seo.html`  | Deployment head block: canonical, Open Graph/Twitter card, JSON-LD          |
| `seo/icons/`         | Favicon/PWA set generated from `assets/logo.png` (sprezzature-publish)      |
| `seo/make_og_card.py`| Regenerates `seo/og-card.png` (the 1200×630 Open Graph card)                |

The build also emits `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`
and `humans.txt` into `dist/` (sprezzature-publish `site_indexes.py`), plus the
curated Markdown corpus those indexes cite. Note for the deployer: crawlers
only honor a `robots.txt` served at the DOMAIN root, so reference
`https://deraison.ai/standpoint/sitemap.xml` from deraison.ai's own
`/robots.txt` (a `Sitemap:` line) for full effect.

`dist/` is generated (and gitignored); rebuild it after any change to the GUI,
the locales, or the library.
