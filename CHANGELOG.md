# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.1] - 2026-08-10

### Added

- **French `EXEMPLES.md`**, matching the suite-wide `EXAMPLES.md`/`EXEMPLES.md`
  convention; `LISEZMOI.md` now links to it instead of the English file.
- **Test coverage for the packaged CLI entry points.** `test_main_argv_writes_deliverable`
  and `test_main_click_writes_deliverable` exercise `main`/`main_click`, the argv
  wiring behind the `standpoint` and `standpoint-click` console scripts — previously
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
  harchaoui.org/warith/sprezzature/figures.html confirms its ink (`#171717`), card
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
- **GUI look and feel**, matched to the [sprezzature](https://harchaoui.org/warith/sprezzature/figures.html)
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

- **Joined the [AI Helpers](https://harchaoui.org/warith/ai-helpers) suite** (Misc
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

[Unreleased]: https://github.com/warith-harchaoui/standpoint/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/warith-harchaoui/standpoint/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/warith-harchaoui/standpoint/releases/tag/v0.1.0
