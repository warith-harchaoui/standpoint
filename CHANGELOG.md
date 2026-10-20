# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.12.0] - 2026-10-20

### Changed

- **`locales/i18n.yaml` turned round into the suite's canonical shape, and
  `i18n()` now reads it through `os_helper.Locales`.** The file put the
  locale first (`en:` / `fr:` / `es:` at the top level) and declared no
  `meta`, so the loader shared by the rest of the suite refused it outright.
  It is now keyed by semantic name first and locale second, with its
  metadata declared (CODING.md 21.3).

  **`i18n(lang)` keeps its signature and its return value**: callers want a
  whole language at once, never a single key, so the function transposes the
  one section back into the per-language view they expect. No call site
  moved.

  These templates drive what a local model writes, in three languages, so
  the transposition was done by program rather than by hand and **verified
  to reproduce every language bundle object-for-object against the previous
  file** — not "looks right", identical. Four tests now hold that: the file
  loads under the shared loader, the shared validator finds nothing, all
  three languages carry the same keys, and an unknown language still falls
  back to English.

- **`os-helper` is a declared dependency.** standpoint was the only member of
  the suite that imported it nowhere, receiving it transitively through
  best-engine-ai-helper. The code now imports it by name, so it is declared
  by name.

- **`best-engine-ai-helper` is capped at `<2`, with the floor at 1.6.1.** It
  read `>=1.0` with no ceiling, so a future major would have resolved in
  silently. The floor is 1.6.1 because every earlier wheel shipped an empty
  model catalogue (see that package's 1.6.1 entry), which is not a version
  this one can be asked to work against.

## [0.11.1] - 2026-10-20

### Fixed

- **`assign_roles`' explanation of the four roles did not render at all.**
  The block laid the role name and its meaning in two aligned columns, which
  docutils reads as an ordinary paragraph; the continuation lines, indented to
  keep the columns, then became an "Unexpected indentation" error and Sphinx
  dropped the whole block. The one place that says what *best*, *worst*, *top*
  and *right* actually mean was missing from the documentation site while
  being present in the source — the worst version of a docs bug, because
  nothing in the repository looks wrong. Written as the definition list it
  always was, it renders.

## [0.11.0] - 2026-10-19

### Added

- **The written analysis, which this package had promised and never produced.**

  The module docstring has said `export_all` "writes PNG + SVG + a Markdown
  analysis + a YAML" for a long time, and the committed LLM brief says the
  model "writes a short positioning analysis in the language of the table's
  columns". Neither was true. There were four prompts — `axis_prompt`,
  `noun_prompt`, `vlm_assess_prompt`, `ratings_prompt` — and **no analysis
  prompt at all**. The deliverable was two faces, the docstring claimed three,
  and anything downstream looking for the Markdown found nothing and could not
  tell a missing analysis from a failed run.

  The gap surfaced as a `StopIteration` in the suite's landscape generator,
  which means `make landscape` was broken for every helper rather than for one.

  `analysis_markdown()` writes the third face, `analysis_prose()` is the model
  call behind it, and both are public. `Positioning` gains `to_markdown()`.

- **The document owns every number in it; the model owns only the reading.**

  The variance each axis preserves, the cumulative total, and the list of
  imputed cells are computed in Python and written by `analysis_markdown`. The
  prompt explicitly forbids the model from stating a percentage, a coordinate
  or a rating. A model asked to narrate its own figures will occasionally round
  one differently and contradict the file it sits in, and a positioning map
  that disagrees with itself is worse than one that says less — "auditable" is
  the property this package exists for.

  The `## Axes` section is machine-readable on purpose: each line reads
  `**Horizontal: A ↔ B** — ~NN% of the variance`, so a consumer can lift the
  pole names without a model and without parsing prose.

- **An unreachable model degrades the prose, never the document.** The figure
  and the YAML are the load-bearing halves and neither needs a model, so the
  analysis section says the model was unavailable rather than silently going
  missing. A section that is absent is indistinguishable from a map with
  nothing to say about itself.

### Fixed

- **The model was being asked to do signed arithmetic, and got it wrong.**

  The first version of the prompt passed each option as `name (+2.47, +2.08)`
  and named the four poles, leaving the convention — a positive first
  coordinate means the right-hand side — unstated. The model duly inverted the
  horizontal axis: it described the reference, which is *pinned to the
  top-right corner by construction*, as a left-hand option, and filed two
  left-hand options as right-hand ones. The vertical axis, where "up is more"
  is the stronger prior, came out correct, which is exactly what makes this
  kind of error easy to miss.

  Naming the pole instead was not enough either: told `Amazon Lex: Adaptable +
  Resourceful`, the model still had to know which side `Adaptable` was on, and
  it guessed wrong, grouping three left-hand options under "lower right".

  Sides and quadrants are now computed in Python and handed over as words, with
  the direction first — `right-top (Modular + Insightful)` — and no coordinate
  pairs reach the prompt at all. Verified against the coordinates: every
  spatial claim in the generated prose is correct, including which options share
  a quadrant and which do not.

  A prompt rule was added for the remaining failure this exposed: the model had
  written a closing sentence about two options "converging in the upper right"
  having correctly placed one of them in the upper *left* three sentences
  earlier. It may no longer claim two options sit together unless the computed
  quadrant list gives them the same label.

- **The analysis checks itself.** `check_analysis()` compares every spatial
  claim in the generated prose against the computed coordinates, with no model
  and no reasoning about meaning: find the direction words, find the option
  names, compare against the sign. Contradictions are logged as warnings rather
  than edited out, because silently fixing the prose would make the warning
  unfalsifiable. It found two real errors in generated output that reading the
  paragraph alone did not.

  Attribution is by position rather than by sentence. One sentence routinely
  carries two claims about two groups — "LiveKit shares the upper region, while
  Amazon Lex and Vapi are grouped in the lower right" — and applying every
  direction word in a sentence to every name in it reported nine problems where
  two were real. A warning channel that cries wolf is no better than the
  silence it replaced.

  And both word orders are read. "Vapi sits on the right" names the option
  before the direction; "in the bottom-right corner are Vapi and Rasa" names it
  after. A first version only looked backwards, and duly reported a run clean
  whose prose had filed a left-hand option in the bottom-right corner — found
  by reading the coordinates against the paragraph by hand, which is the work
  this function exists to remove.

- **The four corners are handed over with their membership.** Per-option
  quadrants were still not enough: the model wrote "the options in the
  bottom-right corner" and listed one that was in the bottom-left. Naming a
  group is now copying a computed list rather than assembling one. That is the
  third application of the same remedy in this one function — compute the
  thing and hand it over, instead of handing over its inputs and hoping — and
  after it, every corner claim in the generated prose is correct, by the
  checker and by hand.

- **`temperature=0`**, like every other call in this package. Reproducibility is
  a stated property here, and a sampled analysis would quietly have made the
  Markdown face the one file that changes between identical runs.

- Stale "two-fold deliverable" wording in the module docstring, the CLI output
  and the `--outdir` help.


## [0.10.0] - 2026-10-19

### Added

- **Every run now declares what it had to invent.**

  A blank cell is filled with its column's minimum. That default is unchanged
  and still right — a missing rating should not flatter an option — but nothing
  said it had happened, and the consequence is larger than one cell.

  Measured on a five-option table with a single blank `Safety` value: the
  affected option moved from `(1.15, 1.06)` to `(0.83, -1.41)`. That is 2.47
  units vertically, most of the map's height, and across the horizontal axis —
  in a quadrant chart, a different quadrant and therefore a different
  conclusion. **Every other option moved as well**, because criteria are
  z-scored before the projection, so an invented value shifts its column's mean
  and spread and perturbs the whole space. A gap in one row silently relocates
  rows that were complete.

  Meanwhile the YAML reported `Safety: 2.0` for that option, indistinguishable
  from a measurement, and the written analysis explained the resulting position
  as though it had been earned. For a tool whose stated purpose is a placement
  that is *auditable rather than hand-drawn*, that was the gap worth closing.

  Three disclosures, for three different readers:

  - **a warning on stderr**, before the map is drawn, for whoever runs the
    command and will never open the YAML. It names the cells and states that
    every coordinate is affected, not only the options with gaps;
  - **`meta.imputed_cells`** — every filled `(option, criterion)` pair;
  - **`imputed_attributes`** on each option, so one row is readable on its own.

  A complete table reports nothing, which keeps the signal meaningful.

### Unchanged, deliberately

- **The imputation strategy.** Column-minimum is defensible and is what every
  existing map was built on; swapping it would silently move all of them. The
  strategy was never the problem.
- **Tables with gaps are still accepted.** An unknown cell is a normal artefact
  of a comparison table. Refusing it would push people to invent a number by
  hand, which is worse: the tool's fill is at least consistent, and now stated.

## [0.9.0] - 2026-09-28

This release supersedes the `v0.8.6` tag, which was cut while these entries were
still under `[Unreleased]` and was never published to PyPI; 0.8.5 was the last
release on PyPI. Everything below therefore ships for the first time here.

### Changed

- **The static build writes straight into the folder it is uploaded from.**
  `webapp/build.py` now lands in `~/web/deraison/standpoint/` — the local
  mirror of `https://deraison.ai/standpoint` — instead of `web/` at the repo
  root, so the deploy is one SFTP put of one folder with nothing to copy in
  between. That sub-folder is all this project owns: `resolve_out()` refuses an
  `--out` pointing at the mirror itself, at an ancestor of it, or at any other
  folder inside it, and refuses to `--clean` anything that is not a previous
  build of this app (recognised by `index.html` + `backend-pyodide.js`), so a
  mistyped path can no longer `rmtree` a live site.

- **The static web app runs on ONE model — the distilled student answers
  everything.** The split brain (a MiniLM embedder + curated vocabularies
  naming the axes, neutral fallbacks for noun forms, the student only behind
  "Laziness") is gone: every engine model call — pole naming, noun forms, the
  ratings fill — now surfaces through the memoized-replay shim with the
  engine's own prompt and schema, and the same in-page student answers it
  (`webapp/backend-pyodide.js`); the optional `--llm-server` gateway, when
  reachable, answers the same calls first. "Laziness" goes through the
  engine's own `suggest_ratings` (glue) instead of a client-side prompt
  rebuild. The embedding machinery (`webapp/vocab/`, `glue.pole_context`, the
  MiniLM download) is deleted. The model now downloads **up front at page
  load** with a visible progress badge saying it happens once, instead of
  ambushing the first click.
- **The browser student shrank from 637 MB to 324 MB, same tasks, no
  retraining.** `07_prune_vocab.py` rebuilds the checkpoint around the
  vocabulary the three tasks can reach (151,936 → 43,190 tokens:
  corpus-closed + the 40k most frequent BPE merges + the byte alphabet, with
  BPE derivation closure so corpus tokenization is provably — and verifiedly —
  bit-identical), and `08_export_pruned.py` closes 05's blind spot by
  quantising the embedding `Gather` table to int8 with per-row scales (plain
  Gather/Cast/Mul ops, browser-runtime-safe). Gate: `06_evaluate_onnx.py`
  scores the exact deployed artifact on the held-out split, before and after.

- **`--check` no longer asks a vision model; it reads the geometry.** The new
  `assess_layout()` returns the same verdict keys `vlm_assess()` does
  (`leader_top_right`, `readable`, `axis_labels_visible`, `notes`, localized)
  but computes them from the coordinates and pole labels the caller already
  holds. Measuring the teacher settled it: across the 1480 `vlm_assess`
  examples recorded in this project's distillation corpus, `readable` came back
  `true` 1480 times and `axis_labels_visible` came back `true` 1480 times,
  while `leader_top_right` is the sign of a coordinate. The check is now exact,
  instant, offline, and needs no model to be reachable. `vlm_assess()` stays in
  the public API for anyone who wants a model's opinion; nothing calls it by
  default any more.

- **Baseline reworded everywhere**: "Know where each option actually stands."
  becomes "Where do you stand?" ("Sachez où vous en êtes" / "¿Dónde te
  sitúas?") — GUI hero, i18n tables, README/LISEZMOI, package docstring. The
  hero also gains the whole user guide in two lines (fill the table / pick the
  row to promote / Generate), and the footer is reduced to the license plus an
  author link to deraison.ai.

### Added

- **A full-screen "Patience…" veil while the app works.** The header activity
  ring was easy to miss; now every operation it tracks — the engine boot and
  the one-off model download included — also lays a translucent light-grey
  veil over the page, dark-grey word centred, and swallows stray clicks until
  the answer is there. It is up from the first paint on a cold start, with the
  download progress badge still readable above it. One word, not two: the
  spelling is identical in French and in English, and the veil can be on
  screen before the localized string table has landed.

- **A seventh access surface: the static web app (`webapp/`).** `python
  webapp/build.py` composes the exact GUI page into a folder any static host
  can serve (plain SFTP upload, no server process): the engine (numpy /
  pandas / scikit-learn / the unchanged `standpoint` wheel) runs in the
  visitor's browser via Pyodide, XLSX import/export runs on a vendored
  `openpyxl`, and figures stay the same hand-authored SVG. LLM calls go
  through a memoized-replay shim of `best-engine-ai-helper`
  (`webapp/beh_shim.py`): **axis naming runs by default** on a small
  multilingual embedding model (transformers.js MiniLM, lazily loaded,
  browser-cached) matched against a curated vocabulary of positive qualities
  (`webapp/vocab/<lang>.json`, confusable entries glossed), and **"Laziness"
  auto-fill is one direct in-browser LLM call** (WebLLM over WebGPU,
  Qwen2.5-1.5B, ~1 GB downloaded on first click then cached) answering the
  engine's own localized `ratings_prompt` with schema-constrained JSON — it
  fills only the still-empty cells, tells you when there is nothing to fill,
  and tells you when the browser lacks WebGPU. Offline or on any failure,
  schema-shaped neutral answers push the engine onto its built-in fallbacks
  so Generate always completes. Verified headless (Playwright), with
  embedding/WebLLM seams for determinism plus a real-model spot check on an
  English and a French table.
- **`webgui.py`: an injectable `backend` layer.** The page's six data
  operations (`example`, `i18n`, `upload`, `downloadXlsx`, `autofill`,
  `position`) now route through one `window.backend`-overridable object whose
  default implementation is the previous FastAPI transport, byte-for-byte
  behaviour-equivalent for the server GUI; this is what lets the static build
  reuse the page unmodified.
- **`i18n.yaml`: `gui.naming_*` and `gui.delegate_*` keys** (en/fr/es), the
  strings for the static build's axis-naming badge and delegation panel; the
  server GUI never shows them.
- **SEO/GEO for the static deployment (sprezzature-publish).** The build now
  injects a deployment head block into `dist/index.html` (canonical URL, Open
  Graph + Twitter card pointing at a generated 1200×630 `og-card.png`,
  Schema.org `WebApplication` JSON-LD crediting Warith Harchaoui /
  deraison.ai), overlays a full favicon/PWA icon set generated from
  `assets/logo.png`, and emits `robots.txt`, `sitemap.xml`, `llms.txt`,
  `llms-full.txt` and `humans.txt` plus the raw Markdown corpus they cite
  (README/LISEZMOI/GUI/EXAMPLES/EXEMPLES served as-is for generative
  engines). `webapp/build.py --base-url` overrides the default
  https://deraison.ai/standpoint target.

### Removed

- **The `narrative` feature: the LLM-written "Interpretation" paragraph and the
  whole Markdown deliverable it lived in.** `export()`/`export_all()` now write
  a **two-fold** deliverable (figures + YAML) instead of three-fold; `<name>.md`
  is no longer written. `analysis_markdown()`/`Positioning.to_markdown()` are
  gone, along with the `analysis:`/`narrative_prompt` blocks in
  `standpoint/locales/i18n.yaml` and the GUI's "Basic Analysis" panel
  (`webgui.py`: the panel, its role-tinting CSS/JS, and the `marked` CDN
  dependency). `POST /api/position` no longer returns a `markdown` field.
  `assets/landscape.csv`/`paysage.csv` drop the "Written Analysis" criterion
  and are re-run through the tool (see `LANDSCAPE.md`/`PAYSAGE.md`); this also
  consolidates two pairs of now-identically-rated competitors (`factoextra +
  FactoMineR` into `prince`, `Power BI` into `Tableau`) rather than inventing a
  fake differentiator to keep them apart.

## [0.8.5] - 2026-08-25

### Fixed

- **`render_figures()`/`export_all()` wrote SVG/PNG/export files
  non-atomically** (plain `open(path, "w")`), so a crash or a concurrent
  reader (e.g. a dev-server auto-reloader watching the output directory)
  could observe or persist a truncated file. Both now write via a new
  `_atomic_write()` helper (temp file + `os.replace`).

### Added

- **Pre-push git hook** (`.githooks/pre-push`, `git config core.hooksPath
  .githooks`) delegating to the repo's own `scripts/check.sh`, so
  `ruff check`/`ruff format --check`/`pytest` failures are caught before
  reaching `origin/main` instead of only in CI. `scripts/check.sh` now
  invokes `python3 -m ruff`/`python3 -m pytest` explicitly (a stray
  Homebrew `pytest` on some machines shadows the project's own
  environment). Documented in `CONTRIBUTING.md`.

## [0.8.4] - 2026-08-17

### Documentation

- **PCA/ACP was named repeatedly in README.md, LISEZMOI.md, and the
  package's own module docstring, expanded once as an acronym, but never
  actually explained** — added a plain-language gloss at each file's first
  substantive use: PCA finds the few directions along which the rows
  differ the most, collapsing many criteria into a readable two-axis map.

### Fixed

- **`export_all()` never forwarded `attributes` to `to_svg()`**, so every
  actually-exported figure (the CLI/GUI deliverable) got the degraded
  role+coordinates hover tooltip instead of the intended per-criterion one —
  `Positioning.to_svg()` (a separate convenience method) already did this
  correctly, `export_all()` did not.
- **`run()`'s vision self-check printed the wrong verdict key**:
  `vlm_assess()`'s returned schema key is `axis_labels_visible`, but the
  printed summary looked up `legend_visible`, which never exists in the
  dict — always printing `None` instead of the model's actual verdict.
- **Test collection could wander into `distillation/checkpoints/llama.cpp/`'s
  vendored test suites** on a machine that has done the `distillation/`
  setup, failing at import time on unrelated deps (`appium`, `wget`). Scoped
  `[tool.pytest.ini_options] testpaths = ["tests"]` so every invocation is
  safe by construction.

### Added

- **`tests/test_docstrings.py`**: an AST-walker guard over every
  `standpoint/*.py` module — fails with the exact missing names if any
  function or class ever ships without a docstring. The project has had
  100% coverage so far, but only by discipline; nothing in the lint gate
  actually enforced it.

## [0.8.3] - 2026-08-15

### Fixed

- **CLI**: a library exception on either console-script entry point
  (`standpoint`, `standpoint-click`) propagated as a raw Python traceback
  instead of a clean error. `standpoint`'s argparse `main()` had no
  try/except around `run()`; click's own `main()` only special-cases
  `ClickException`/`Abort`. Both now print `Error: ...` to stderr and exit
  1. `standpoint-click`'s console-script entry point moves to a new
  `click_cli.main()` wrapper (was the bare `main_click` command).

## [0.8.2] - 2026-08-10

### Fixed

- **`requirements.txt` drifted from `pyproject.toml`.** It still listed `ollama` as a
  runtime dependency and was missing `best-engine-ai-helper`, left over from the
  [0.7.0](#070---2026-08-05) migration that made `best-engine-ai-helper` the hard runtime dependency
  and dropped the direct `ollama` import. `ollama` is only needed by
  `tests/conftest.py` for `@needs_model` tests, so it moves to the `dev` extra.

## [0.8.1] - 2026-08-10

### Added

- **French `EXEMPLES.md`**, matching the suite-wide `EXAMPLES.md`/`EXEMPLES.md`
  convention; `LISEZMOI.md` now links to it instead of the English file.
- **Test coverage for the packaged CLI entry points.** `test_main_argv_writes_deliverable`
  and `test_main_click_writes_deliverable` exercise `main`/`main_click`, the argv
  wiring behind the `standpoint` and `standpoint-click` console scripts; previously
  nothing in the suite called them directly, so a broken flag name would only have
  surfaced at install time.
- **`laptops.csv` example**, illustrating the inline `(↓)` notation for
  lower-is-better columns without the `--lower` flag.

### Fixed

- **`EXAMPLES.md`/`EXEMPLES.md` still described a `.vl.json` Vega spec** among the
  files each run writes; `to_svg()` has been hand-authored SVG (no Vega) since an
  earlier release. Both docs now list six output files instead of seven.

### Changed

- Docstrings added to `to_svg()`'s internal `x_px`/`y_px`/`pole_label` helpers.

### Fixed

- **`mcp` extra installs a broken MCP server.** `fastapi-mcp>=0.3,<1` calls the
  underlying MCP SDK's `Server(name, description)` positionally; `mcp` 2.0.0 dropped
  that second positional argument, so `standpoint-mcp` failed at import with
  `TypeError: Server.__init__() takes 2 positional arguments but 3 were given`. The
  `mcp` extra now pins `mcp<2`.
- **A label could be placed twice and stranded far from its dot.** A point extreme on
  one axis with a near-zero value on the other can win two diagonal corner slots at
  once (the `tl`/`bl` or `tr`/`br` projections nearly tie); `label_placements()`
  placed its label for each win, and the second pass dodged its own first label as if
  it belonged to a stranger. `corner_extremes()`'s output is now deduped by index
  before placement.
- **GUI: the transparency checkerboard turned unreadable in dark mode.** `#chart.checker`
  let its gradient's `transparent` stops fall through to the card behind it; dark
  mode recolors that card near-black, so half the checker squares went near-black too
  and swallowed the map's own near-black labels. The checker now carries its own
  explicit white background.
- **GUI: a cell added via "+ Option (row)" / "+ Criterion (column)" defeated Autofill.**
  Both prefilled new cells with `"3"` instead of leaving them blank; Autofill only
  fills cells that are still blank (so it never overwrites what the user typed), so a
  table built by hand with these buttons silently kept every such cell stuck at `"3"`
  instead of getting a real score from the model.
- **A non-dominant reference could land exactly on a competitor's coordinates.**
  `analyze()`'s reference-softening clamps a reference onto the Pareto frontier (max
  x, max y of the field); when a single competitor defines that frontier on both axes
  at once, the reference landed exactly on that competitor's point -- one dot for two
  options. `examples/cloud_providers.csv` already exhibited this: AWS and Microsoft
  Azure were tied at identical coordinates in the committed example. The softened
  position now nudges 5% further out whenever it would otherwise exactly match
  another point, so the reference stays "just past" the competitor, as documented,
  rather than tied with them.
- **The GUI's language toggle produced a half-translated title.** `noun_forms()`'s
  anti-hallucination guard compared the model's translation against the *original*
  word's prefix, which no real translation shares ("Language" -> "Langue"); it
  silently discarded every correct cross-language translation and kept the source
  word. The `noun_prompt` templates also read as "don't translate" rather than
  "translate" on a word that isn't already in the target language. Toggling the
  shipped English example to French read "Programming languages dans le quadrant".
  The guard now only applies within the word's own language; all three prompt
  templates lead with "translate this word... if it isn't already".

### Changed

- **GUI chrome now matches sprezzature's neutral gray, not Tailwind's blue-tinted
  "slate".** The page's headings, borders, and hint text used Tailwind's `slate-*`
  utilities in light mode while the hand-written dark-mode overrides already
  hardcoded true-neutral hex values (`#171717`, `#e5e5e5`, `#d4d4d4`, ...) — the two
  modes were quietly using different gray families. Every `slate-*` class is now
  `neutral-*`, which resolves to those same hexes: measuring
  sprezzature.ai/figures.html confirms its ink (`#171717`), card
  border (`#e5e5e5`) and outline-button border (`#d4d4d4`) are exactly Tailwind's
  `neutral-900/200/300`. The hero headline grows to the reference's measured 48px,
  section headings (`Table`, `Options`, `Quadrant`, `Basic Analysis`) go from
  20px/600 to the reference's 24px/700, cards move from `rounded-xl`/20-28px padding
  to `rounded-2xl`/24-32px padding with a solid (not translucent) border, and the
  outline-button padding is now pixel-exact (`.5rem 1rem`) to the reference's pill
  buttons. The DATA-only colour rule (map dots + role-tinted names stay the sole
  source of colour; chrome stays neutral) is unchanged.
- **No more Vega, anywhere.** `to_vega()` is replaced by `to_svg()`: the positioning
  map is now built as a hand-authored, self-contained, interactive SVG (native
  `<title>` tooltips, pure-CSS `:hover`/`:focus`, no JavaScript, no external
  chart-rendering runtime), rasterised to PNG via `resvg` instead of `vl_convert`.
  `vl-convert-python` is dropped as a dependency in favour of `resvg-py`.
  `export_all()` / `Positioning.export()` no longer write a `<name>.vl.json` spec
  file (six files instead of seven). The GUI (`standpoint/webgui.py`) no longer
  loads `vega` / `vega-lite` / `vega-embed` from a CDN: the server sends back the
  SVG directly, the page drops it straight into the DOM, pole renames edit the
  SVG's own `data-pole` text nodes in place (no spec to rebuild, no re-render), and
  PNG/SVG export rasterises the live SVG client-side through an offscreen canvas.
  `POST /api/position`'s `vega` response field is renamed `svg`.

## [0.7.0] - 2026-08-05

### Changed

- **Model selection now follows the AI-Helpers brief → engine contract.** The
  hard-coded `DEFAULT_MODEL` / `AI_HELPERS_LLM_MODEL` env override and the
  `standpoint-select-model` picker are gone. Standpoint ships a committed
  `standpoint/llm.brief.yaml` describing its one-model, three-in-one job
  (structured JSON axis poles, bilingual FR/EN prose, chart-image reading);
  [best-engine-ai-helper](https://pypi.org/project/best-engine-ai-helper/)
  resolves the best local vision-LLM for the machine on first use and caches the
  pick to a gitignored `standpoint/llm.engine.yaml`. Every LLM/VLM call now routes
  through `best_engine_ai_helper.llm.chat(engine=…, kind="vlm")`, which serves
  Ollama or vLLM per the resolved engine.
- `best-engine-ai-helper` is now a hard dependency; the direct `ollama` dependency
  and the optional `[engine]` extra were removed.
- **Label placement keeps clear of the pole margin.** `label_placements` gained
  `keepin_x`/`keepin_y` bounds so a candidate label position is rejected once it
  would stray into the outer band reserved for the pole words, instead of only
  avoiding other labels. The figure's view, margins and canvas were widened
  (`view_x`/`view_y` now `2.0x` the span, canvas `1200x900`+) and pole words are
  centred on their edge and point outward, so labels and pole phrases no longer
  collide in tight clusters.
- Refreshed a handful of example dataset values in `voitures_electriques.csv`.

### Added

- **Input validation rejects redundant rows/columns.** `validate_table` now
  raises a clear `ValueError` when two options have identical ratings (they
  would land on the same point) or two criteria are identical columns (they
  would double-count the same evidence and skew the axes), alongside the
  existing empty/constant-column checks.

## [0.6.0] - 2026-08-02

### Added

- **Editable axis poles in the GUI.** After a run, a compass-laid-out editor
  (top over left ✚ right over bottom) is filled with the model's four pole
  names; renaming any of them re-labels the map **live**, entirely client-side —
  no second model call — and the PNG / SVG exports pick up the new names for
  free. The server keeps the pristine spec and pole names, so a blank field
  falls back to the original label and duplicate labels never confuse the swap.
  Localized in English, French and Spanish (`poles_title`, `poles_hint`, and the
  four `aria_pole_*` labels).
- `tests/test_readme_install_pin.py` guards against a stale `git+…@vX` self-pin
  ever returning to any Markdown file.

### Changed

- **Positioning-figure geometry.** The four pole words now sit well outside the
  dot cloud (out near the axis ends) at a larger font, so they read as the map's
  headline instead of crowding the points, and the label de-clutter now uses the
  **actual** rendered canvas size instead of the old fixed default — so option
  labels sit next to their dots rather than being pushed too far vertically.
- **GUI look and feel**, matched to the [sprezzature](https://sprezzature.ai/figures.html)
  design system: a sticky, translucent, blurred nav bar (logo + wordmark, GitHub star
  and language/theme pills); a monospace "eyebrow" tag over a serif display headline;
  bordered cards with no shadow (in dark mode the card fill sits at page-black, the
  border alone separates it); one unified outlined-button style for every secondary
  action; and a minimal footer with a border-top divider. The data palette (map dots,
  role-tinted names) and the "chrome stays neutral" rule are unchanged; hover states use
  neutral grays, never the brand blue, which stays reserved for the map's right pole.

### Fixed

- README / LISEZMOI install commands no longer self-pin to a git tag (`@v0.4.2`);
  they use `pip install standpoint`, which always resolves to the latest
  published release.

## [0.5.0] - 2026-08-01

### Added

- **Bilingual GUI with the language driving the whole output.** A 🇫🇷 / 🇬🇧 toggle in
  the header re-localizes every label, button, and message, and forces the language of
  the model output too (pole names, figure title, and the written analysis, including
  its section headings). GUI strings and LLM prompts now live side by side in
  `standpoint/locales/i18n.yaml` (new `gui:` and `analysis:` blocks per language),
  served to the page by `GET /api/i18n`.
- **Dark theme.** A 🌞 / 🌛 toggle switches the page between light and dark; the choice
  persists in `localStorage`. The "Good Colors" data palette (map dots, role-tinted
  names) is deliberately left untouched, so a colour still always means "data".
- **"Laziness" auto-fill.** A button fills every empty cell from the local model's
  knowledge once the row and column names are set, so a headers-only CSV/XLSX upload
  becomes a full table in one click (`POST /api/autofill`, `suggest_ratings()`).
- **App icon set.** Favicon, Apple touch icon, Android/maskable icons, and a PWA
  manifest, all generated from `assets/logo.png` and served under `/static`.
- **Sprezzature look and feel.** Roboto typography, neutral palette with bordered
  cards, a responsive layout (down to phone widths), and a "⭐️ on GitHub" link.
- **"New Table" button** to start from an empty grid and build it up row by row and
  column by column (replaces "Reset to example"; the example still loads on first
  visit).
- **Richer hover tooltip.** Hovering a dot now lists every criterion with the option's
  value (the original numbers you typed), instead of the two abstract PC coordinates.
  `to_vega()` gains an `attributes` argument for the raw table.
- `lang` parameter on `positioning()` and `POST /api/position` to force the output
  language instead of detecting it from the table.

### Changed

- **Pole labels** are drawn further inside the map (at ~0.86 of the view rather than
  hard against the edge) and one size smaller, so a long label never bites the canvas
  edge or overflows the figure.
- GUI exports are named after the table's subject (e.g. `programming-languages.png`)
  rather than a generic stem; the plural slug is returned by `POST /api/position`.
- `POST /api/position` and `POST /api/autofill` now return an actionable `503` when the
  local Ollama server is unreachable or the model is not installed, instead of an
  opaque `500`.
- CI now installs the pure-Python `gui` extra and runs the model-free GUI/API tests
  (endpoints, i18n integrity, auto-fill validation, the 503 error paths); a failure
  blocks the merge. The Playwright, MCP, eval, and model-backed tests still self-skip.

## [0.4.2] - 2026-07-27

### Changed

- **Cleaner map (Ralph Eyeball Loop).** The positioning map no longer draws a colour
  legend when every dot is already labelled in place, which is the common case. The
  legend was pure redundancy there and it squeezed the plot; hiding it lets the map use
  the whole canvas. The legend still appears as a fallback when a crowded map forces a
  label to drop, so densely packed dots stay identifiable. All shipped example and
  landscape figures were regenerated.
- The `--check` vision self-check (`vlm_assess`) now reports `axis_labels_visible`
  (are the four italic pole labels legible) instead of `legend_visible`, since the
  legend is now conditional. The four pole labels are always drawn.

## [0.4.1] - 2026-07-27

### Removed

- The `--no-llm` flag and the `use_llm=` parameter are gone; the local Ollama model is
  always used (pick one with `--model` / `model=`). This removal landed in the engine
  earlier; the docs, the Docker example, and the skill helper are now aligned with it.

### Fixed

- `skills/standpoint/scripts/positioning_summary.py` crashed on every run because it
  still passed the removed `use_llm=` keyword to `positioning()`, `export()`, and
  `to_markdown()`. It now takes `--model` and calls the current API, with tests
  (`tests/test_skill_script.py`) guarding the argument wiring so the regression cannot
  return.
- Stale `--no-llm` / `use_llm=` references in README, LISEZMOI, EXAMPLES, the Dockerfile,
  `SKILL.md`, and `references/interfaces.md` (including a non-existent `use_llm` field in
  the documented `POST /api/position` body, corrected to `model`).
- CI was red: making the local model a hard prerequisite turned the `tests/conftest.py`
  guard into a fixture that errored the whole suite when Ollama was absent (as on the
  hosted runner). The guard now only gates tests marked `@pytest.mark.needs_model`, and
  for those it skips in CI while still failing loudly on a developer machine. The
  model-free suite (parsing, geometry, roles, colours, i18n, Vega structure) runs in CI
  again, so the badge reflects real state.

### Changed

- GUI: the header now carries the tagline and a short plain-language explanation of what
  the tool does and how to read the map (first-fold clarity), and the "Generate quadrant"
  button locks itself (with `aria-busy`) while a run is in flight, so a second click can
  no longer fire a concurrent request. The browser GUI is documented as a shipped access
  surface (it was still labelled a `dev-gui` "feasibility investigation").
- Writing standard: the generated deliverable no longer uses dash punctuation. The
  en/fr/es prompt templates were reworded (and no longer nudge the model to emit dashes),
  the Axes section of the analysis reads `Horizontal (X ↔ Y)`, and the front-door docs
  (README, LISEZMOI, PAYSAGE) were cleaned to match.
- The FastAPI app version now tracks `standpoint.__version__` instead of a hard-coded
  string; added the missing `__main__` module docstring and a `PCAResult` class docstring.

## [0.4.0] - 2026-07-24

### Added

- **MCP surface** (`standpoint.mcp`, `standpoint-mcp`, `[mcp]` extra): `fastapi-mcp`
  publishes the existing FastAPI endpoints as MCP tools at `/mcp`, so an MCP-aware host
  can call `position` (table → map + analysis) as a first-class tool. Smoke-tested.
- **Claude / OpenCode skill** under `skills/standpoint/`: a trigger-rich `SKILL.md`,
  `references/` (interfaces, input/output), and a `scripts/positioning_summary.py`
  helper (table → figure + analysis, printing the paths). Exhaustive `TRIGGERS.md` at
  the repo root, referenced from README/LISEZMOI.
- **Container + environments**: a `Dockerfile` (installs from `requirements.txt`, serves
  the API + MCP) with `.dockerignore`, a thin conda `environment.yaml` wrapping
  `requirements.txt`, and an expanded `requirements-dev.txt` that installs the server
  surfaces so the GUI/MCP tests run.

### Changed

- The six surfaces (library, two CLIs, GUI, HTTP API, MCP) all funnel into the same
  `positioning()` engine — no logic is duplicated across them.
- Prompt templates moved to `standpoint/locales/i18n.yaml` (still en/fr/es,
  auto-detected from the column names).

## [0.3.0] - 2026-07-24

### Added

- **Browser GUI** (optional `gui` extra: FastAPI + uvicorn + openpyxl), launched with
  `standpoint-gui`. A single self-contained HTML page (vanilla JS + Tailwind +
  vega-embed + marked, no build step): an editable table grid (add/remove rows &
  columns, per-column ⬆️/⬇️ polarity, reference picker), **CSV/XLSX upload &
  download**, a live-rendered quadrant with **PNG/SVG export** and a transparent /
  white toggle, and a colour-coded written analysis. Served by `standpoint.api`
  (`/gui`, `/api/example`, `/api/position`, `/api/upload`, `/api/download/xlsx`); the
  core library and CLIs gain no new runtime dependency. Covered by endpoint tests and
  a headless-Chromium end-to-end test, with a dedicated CI job for the backend.

### Changed

- **Analysis is more useful and readable.** The narrative prompt (en/fr/es) now asks
  for decision-useful takeaways rather than a restatement of the axes; wording uses
  "information" instead of "variance", percentages are approximate (`~90%`), each
  axis lists its criteria **by influence (names only, no raw weights)**, and the
  leaderboard coordinate dump plus the rotation jargon are gone.
- **Colour discipline.** The "Good Colors" palette is reserved for **data** — the map
  dots and the role-tinted option names in the analysis — while the GUI chrome stays
  neutral, so a colour always means data.

## [0.2.0] - 2026-07-24

### Added

- **Joined the [AI Helpers](https://deraison.ai/ai-helpers) suite** (Misc
  group): suite framing + logo in the README/LISEZMOI, a canonical Documentation
  section, and a self-referential positioning map wired into `LANDSCAPE.md` /
  `PAYSAGE.md` from the committed `assets/landscape.csv` / `paysage.csv` source.
- **First PyPI release** (`pip install standpoint`); README/LISEZMOI use absolute
  URLs so they render on the PyPI project page.

### Changed

- **Highlighted roles are now domain-agnostic.** The two extra highlights used to be
  chosen with a fixed keyword list carried over from an early voice-AI example, so on
  a generic table they degraded to an arbitrary pick. They are now read straight off
  the map geometry: the leader, the weakest overall, and the two challengers reaching
  furthest toward the **top** and **right** poles ("strongest toward `<pole>`"). The
  corresponding CLI overrides were renamed `--innovative`/`--trustworthy` →
  `--top`/`--right`, and `positioning(innovative=, trustworthy=)` → `top=`/`right=`.
- **The figure title is fully localized.** A French table now reads
  *Voitures dans le quadrant* (and Spanish *… en el cuadrante*) instead of keeping the
  English connector. Driven by a per-language `title_template` in `i18n.yaml`.

### Added

- **Two figure backgrounds per run.** Every render now writes a **transparent**
  `<name>.png` / `.svg` (default, drops onto any page) *and* a white-background
  `<name>.white.png` / `.white.svg` (for dark surfaces where the near-black labels
  would vanish on transparency). The `--check` vision self-assessment runs against a
  white-composited render (`png_on_white`) so transparency can't fool it.
- Bilingual documentation: reworked `README.md` and a French `LISEZMOI.md`, plus this
  `CHANGELOG.md`, a `CONTRIBUTING.md`, and the repository `CODING.md`.
- A competitive positioning map of the tool itself in `LANDSCAPE.md` / `PAYSAGE.md`,
  rendered by Standpoint (dogfooding).
- Continuous integration (`.github/workflows/ci.yml`): ruff lint + format check and a
  pytest matrix on Python 3.10–3.13.
- An optional DeepEval evaluation of pole-naming quality (`tests/test_eval.py`),
  auto-skipped when Ollama or the model is unavailable.
- Explicit ruff configuration in `pyproject.toml` (line length 100, target py310,
  a conservative lint set); the package is now `ruff check` and `ruff format` clean.

### Fixed

- Library diagnostics go through the `logging` module instead of a bare `print`.
- Numpydoc docstrings and full type annotations on every private and nested function.

## [0.1.0] - 2026-07-23

### Added

- Initial public release. From one comparison table (`options × criteria`, CSV or
  Markdown, numeric ratings on any scale), Standpoint produces a three-fold
  deliverable in one command:
  - a **figure** — a labelled 2D positioning map (PNG + SVG + Vega-Lite JSON), the
    reference option rotated to the top-right, de-cluttered labels, full legend;
  - a **Markdown** interpretation (axes, where the leader wins, standout options,
    loadings, ranking);
  - a **YAML** dump of every option's coordinates, role, colour, and original values,
    plus axis loadings and variance.
- Correlation PCA (z-score standardization) with the axes kept as readable weighted
  sums of the criteria.
- Local-LLM axis-pole naming (default `qwen2.5vl:7b`) in the table's own language
  (English, French, Spanish), with a guard enforcing positive, distinct, acronym-free
  labels; deterministic `--no-llm` fallback.
- Per-column polarity: lower-is-better criteria via a `(↓)` header marker or `--lower`.
- Optional `--check` vision self-assessment of the rendered figure.
- Two console commands (`standpoint`, `standpoint-click`) and a `positioning()`
  library API returning a `Positioning` object.

[Unreleased]: https://github.com/warith-harchaoui/standpoint/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.8.6...v0.9.0
[0.8.6]: https://github.com/warith-harchaoui/standpoint/compare/v0.8.5...v0.8.6
[0.8.5]: https://github.com/warith-harchaoui/standpoint/compare/v0.8.4...v0.8.5
[0.8.4]: https://github.com/warith-harchaoui/standpoint/compare/v0.8.3...v0.8.4
[0.8.3]: https://github.com/warith-harchaoui/standpoint/compare/v0.8.2...v0.8.3
[0.8.2]: https://github.com/warith-harchaoui/standpoint/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/warith-harchaoui/standpoint/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.4.2...v0.6.0
[0.4.2]: https://github.com/warith-harchaoui/standpoint/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/warith-harchaoui/standpoint/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/warith-harchaoui/standpoint/releases/tag/v0.1.0
