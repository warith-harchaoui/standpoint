# webapp/ — the static build of the Standpoint GUI

The same single-page GUI the server serves at `/gui`, composed into a folder
any static host can serve: the engine runs in the visitor's browser (Pyodide /
WebAssembly), axes are named by default by a small in-page embedding model
(transformers.js MiniLM + curated vocabularies), and "Laziness" auto-fill
delegates to the user's own AI via a copy-the-prompt panel. Full architecture,
diagram and limitations: [GUI.md § Static build](../GUI.md).

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

## Files

| File                 | Role                                                                        |
| -------------------- | --------------------------------------------------------------------------- |
| `build.py`           | Composes `dist/` from `standpoint.webgui.GUI_HTML` + these files            |
| `backend-pyodide.js` | The `window.backend` transport: Pyodide boot, replay driver, embedding namer, delegation panel |
| `glue.py`            | Endpoint logic mirrored from `standpoint.api` (+ `pole_context`), in Pyodide |
| `beh_shim.py`        | Memoized-replay stand-in for `best-engine-ai-helper`                        |
| `vocab/<lang>.json`  | Candidate pole names (positive qualities; confusable entries glossed)       |

`dist/` is generated (and gitignored); rebuild it after any change to the GUI,
the locales, or the library.
