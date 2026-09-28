# webapp/ — the static build of the Standpoint GUI

The same single-page GUI the server serves at `/gui`, composed into a folder
any static host can serve: the engine runs in the visitor's browser (Pyodide /
WebAssembly), and ONE model answers every language job — pole naming, noun
forms, the "Laziness" ratings fill. It is this project's own distilled student
(`distillation/`), downloaded once at page load (visible progress badge, then
browser-cached) and run through transformers.js over WebGPU; a build-time
`--llm-server` gateway, when configured and reachable, answers the same calls
faster. Full architecture, diagram and limitations:
[GUI.md § Static build](../GUI.md).

## Build and deploy

```bash
python webapp/build.py            # writes ~/web/deraison/standpoint/
# that folder IS the SFTP payload; upload its CONTENTS to the web folder:
#   sftp> put -r ~/web/deraison/standpoint/* /path/to/htdocs/standpoint/
```

The default output is the `standpoint/` sub-folder of the local deraison.ai
mirror, so what you build is already sitting where it gets uploaded from. That
one folder is all this project owns: everything else under `~/web/deraison/`
belongs to the site, and `build.py` refuses an `--out` pointing at the mirror
itself, at an ancestor of it, or at any other folder inside it — and refuses to
`--clean` a folder that is not a previous build of this app. Build somewhere
else with `--out`, anywhere outside that mirror.

The bundle is relocatable (relative URLs only), so it works at any mount point,
e.g. `https://deraison.ai/standpoint`. The Pyodide runtime and the numeric
wheels load from the jsDelivr CDN on first visit (~15–20 MB, browser-cached);
everything else ships in the folder.

### Hosts that forbid whole families of extensions

Some shared hosts refuse to serve "sensitive" extensions at all. deraison.ai
started doing so on 2026-09-25: **every** URL ending in one of

    .bak .db .env .ini .json .lock .log .md .old .py .sh .sql .sqlite
    .toml .yaml .yml

answers `403`, including one that points at no file — which is how the rule
gives itself away, and how the list above was measured (by requesting names
that do not exist). It is domain-wide and sits above `/standpoint/`. The page
then reads an HTML error body where it expected data or code, and the visitor
sees either

    Unexpected token '<', "<!DOCTYPE "... is not valid JSON

or, once the JSON is dealt with, a Python `SyntaxError` on
`<p>You don't have permission to access this resource.</p>` — Pyodide having
been handed the 403 page as `glue.py`'s source.

`--ext-txt` is the workaround. It ships each affected file as
`<name><ext>.txt` (the bytes are untouched; `Response.json()` and `.text()`
ignore the content type) and injects `ext-txt.js`, which rewrites
*same-origin* reads to that twin. Patching `fetch` rather than the call sites
is deliberate: transformers.js composes `config.json`, `tokenizer.json` and
friends itself, so there is no call site to edit. Cross-origin reads are left
alone — the CDN serving Pyodide and transformers.js has no such rule. The
generated SEO indexes are rewritten too, but only where they cite this
deployment, so the GitHub links they also carry survive.

```bash
python webapp/build.py --no-gate --ext-txt    # what deraison.ai needs today
```

Drop the flag once the host serves these extensions again; the payload is
otherwise identical. Verified with `.private/ralph-loop/hostile_server.py`,
which serves the built folder under exactly that rule, plus `verify_hostile.py` (full
journey and Laziness, asserting that no 403 reaches the page).

## Files

| File                 | Role                                                                        |
| -------------------- | --------------------------------------------------------------------------- |
| `build.py`           | Composes `dist/` from `standpoint.webgui.GUI_HTML` + these files            |
| `backend-pyodide.js` | The `window.backend` transport: Pyodide boot, replay driver, the one answering model (server / in-page student) |
| `glue.py`            | Endpoint logic mirrored from `standpoint.api`, in Pyodide                   |
| `beh_shim.py`        | Memoized-replay stand-in for `best-engine-ai-helper`                        |
| `ext-txt.js`         | Emitted by `--ext-txt`: rewrites same-origin reads of host-blocked extensions to their `.txt` twins |
| `seo/head-seo.html`  | Deployment head block: canonical, Open Graph/Twitter card, JSON-LD          |
| `seo/icons/`         | Favicon/PWA set generated from `assets/logo.png` (sprezzature-publish)      |
| `seo/make_og_card.py`| Regenerates `seo/og-card.png` (the 1200×630 Open Graph card)                |

The build also emits `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`
and `humans.txt` into `dist/` (sprezzature-publish `site_indexes.py`), plus the
curated Markdown corpus those indexes cite. Note for the deployer: crawlers
only honor a `robots.txt` served at the DOMAIN root, so reference
`https://deraison.ai/standpoint/sitemap.xml` from deraison.ai's own
`/robots.txt` (a `Sitemap:` line) for full effect.

The build folder is generated and lives outside the repo; rebuild it after any
change to the GUI, the locales, or the library.
