# Standpoint

[🇫🇷](https://github.com/warith-harchaoui/standpoint/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/standpoint/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/standpoint/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/standpoint/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/standpoint/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/local--first-Ollama%20%2B%20SVG-brightgreen.svg)](#local-first)

`Standpoint` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![Standpoint logo](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/assets/logo.png)](https://harchaoui.org/warith/ai-helpers/#standingpoint)

Know where each option actually stands.

Standpoint reads a comparison table (options as rows, criteria as columns, numbers
in the cells) and produces a 2D positioning map, a short written analysis, and a
YAML file with all the coordinates and coefficients. One command does it.

The method is ordinary Principal Component Analysis (PCA), which people have used for
perceptual maps for a long time. What Standpoint adds is the work you would otherwise do by hand: it orients
the map around a reference option, names the axes in plain words (in the language
of your columns), colours and labels the points, and writes everything out.

## Local-first

Everything runs on your machine: parsing, PCA, orientation, colouring, and rendering
the figure as hand-authored SVG, rasterised to PNG by
[`resvg`](https://github.com/RazrFalcon/resvg) — no Vega, no chart-rendering runtime.
Your table is never uploaded, and there is no telemetry, no account, and nothing to
sign up for.

The one thing that reaches out is the axis naming and the written analysis, which ask a
local vision-LLM running on `localhost`. Standpoint does not hard-code a model: it ships
a committed brief (`standpoint/llm.brief.yaml`) describing the job, and
[best-engine-ai-helper](https://pypi.org/project/best-engine-ai-helper/) resolves the
best local model for *your* machine on first use, caching the pick to a gitignored
`standpoint/llm.engine.yaml`. The weights are fetched once, then everything works offline.

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/standingpoint-doc/)

[🗺️ Landscape](https://github.com/warith-harchaoui/standpoint/blob/main/LANDSCAPE.md)

[📋 Examples](https://github.com/warith-harchaoui/standpoint/blob/main/EXAMPLES.md)

Input: a table of options and their ratings.

| Language | Performance | Ease of Learning | Ecosystem | Concurrency | Type Safety | Job Market | Tooling |
|---|---|---|---|---|---|---|---|
| Python | 2 | 5 | 5 | 2 | 2 | 5 | 4 |
| Rust | 5 | 2 | 3 | 5 | 5 | 3 | 4 |
| Go | 4 | 4 | 4 | 5 | 4 | 4 | 4 |
| JavaScript | 3 | 4 | 5 | 3 | 2 | 5 | 3 |
| … | | | | | | | |

Output: a positioning map,

![Programming languages positioning map](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/programming_languages.png)

plus a Markdown analysis (what the axes mean, where the reference wins, which options
stand out, with the loadings and a ranking) and a YAML file with every option's
coordinates, role, colour, and original values.

## Features

- **One command, three-fold deliverable**: a hand-authored, interactive figure
  (PNG + SVG, no Vega), a Markdown interpretation, and a YAML of coordinates +
  coefficients.
- **Readable axes**: PCA keeps the axes as weighted sums of your columns; a local
  model names the four poles as positive qualities, guarded against acronyms,
  negatives, and antonym pairs.
- **Multilingual**: axis names, the written analysis, and the figure title come out
  in the table's own language (English, French, or Spanish), auto-detected from the
  column names, so a French table reads *Voitures dans le quadrant*.
- **Reference-oriented**: the option you care about is rotated to the top-right; an
  all-max reference is placed just past the best competitor rather than as an outlier.
- **Four highlighted options**: the leader, the weakest overall, and the two
  challengers that reach furthest toward the top and right poles.
- **Polarity aware**: mark a lower-is-better column with `(↓)` (or `--lower`) and
  Standpoint names the benefit (*Affordable*, *Portable*), never the drawback.
- **Vision self-check**: `--check` asks a local vision model whether the figure reads
  correctly (leader top-right, labels legible, legend visible).

**One engine, six access surfaces.** The same `positioning()` pipeline is reachable as:

- **Library**: `import standpoint as sp`.
- **CLI ×2**: `standpoint` (argparse, always installed) and `standpoint-click`
  (click twin) with identical flags.
- **GUI**: `standpoint-gui` → a single-page browser app at `/gui` (`[gui]` extra).
- **HTTP API**: a FastAPI app (`POST /api/position`), same `[gui]` extra.
- **MCP**: `standpoint-mcp` publishes the API as MCP tools at `/mcp` (`[mcp]` extra).

It also ships as a **Claude / OpenCode skill**; see
[skills/standpoint/SKILL.md](https://github.com/warith-harchaoui/standpoint/blob/main/skills/standpoint/SKILL.md)
and the exhaustive
[TRIGGERS.md](https://github.com/warith-harchaoui/standpoint/blob/main/TRIGGERS.md).

## Installation

**Prerequisites:** **Python 3.10–3.13** and **git**, cross-platform:

- 🍎 **macOS** ([Homebrew](https://brew.sh)): `brew install python git`
- 🐧 **Ubuntu/Debian**: `sudo apt update && sudo apt install -y python3 python3-pip git`
- 🪟 **Windows** (PowerShell): `winget install Python.Python.3.12 Git.Git`

For axis names and the written analysis, install [Ollama](https://ollama.com) and start
it. You do **not** pick a model: on first use best-engine-ai-helper resolves the best
local vision-LLM for your machine from `standpoint/llm.brief.yaml` and pulls it once.

- 🍎 **macOS**: `brew install ollama`, then `ollama serve &`
- 🐧 **Ubuntu/Debian**: `curl -fsSL https://ollama.com/install.sh | sh`, then `ollama serve &`
- 🪟 **Windows**: install from [ollama.com/download](https://ollama.com/download), then launch it

**Use a virtual environment.** Installing into the system Python is the #1 cause of
"it installed but the command isn't found" or a version conflict with another project:

- 🍎 **macOS** / 🐧 **Ubuntu/Debian**:
  ```bash
  python3 -m venv .venv && source .venv/bin/activate
  python -m pip install --upgrade pip   # an old pip is the #1 cause of install failures
  ```
- 🪟 **Windows** (PowerShell):
  ```powershell
  python -m venv .venv; .venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  ```

New to Python environments? See [🥸 Tech tips](https://harchaoui.org/warith/4ml/#install).

### From PyPI (recommended)

```bash
pip install standpoint             # library + the two CLIs
pip install "standpoint[gui]"      # + the browser GUI and HTTP API
pip install "standpoint[mcp]"      # + the MCP server (over the API)
```

### From source

```bash
git clone https://github.com/warith-harchaoui/standpoint.git
cd standpoint
pip install -e .          # or: pip install -r requirements.txt
```

Or install a specific released version straight from GitHub (the import name is
`standpoint`; see [Releases](https://github.com/warith-harchaoui/standpoint/releases)
for the latest tag):

```bash
pip install standpoint
```

### Verify the install

```bash
python -c "import standpoint; print(standpoint.__version__)"   # prints the version
standpoint --help                                               # confirms the CLI is on PATH
```

### Troubleshooting

- 🍎🐧 **`command not found: standpoint`**: the virtual environment isn't activated,
  re-run `source .venv/bin/activate`; or the install failed silently, re-run
  `pip install standpoint` and read the last few lines of its output.
- 🪟 **`standpoint` is not recognized...`**: same cause on Windows, re-run
  `.venv\Scripts\Activate.ps1`, then confirm with `Get-Command standpoint`.
- 🍎🐧🪟 **`ModuleNotFoundError: No module named 'standpoint'`**: you're running a
  different Python than the one you installed into; compare `which python3` /
  `which pip` (macOS/Ubuntu) or `Get-Command python`, `Get-Command pip` (Windows),
  then reinstall with `python -m pip install standpoint` to force the match.
- 🍎🐧 **GUI: "The local Ollama server is not reachable"**: start it with
  `ollama serve` (some installs already run it as a background service), then confirm
  with `curl http://localhost:11434`.
- 🪟 **GUI: "The local Ollama server is not reachable"**: launch the Ollama app from
  the Start menu, then confirm with `Invoke-WebRequest http://localhost:11434`.
- 🍎🐧🪟 **GUI: "The model '...' is not installed"**: `ollama pull <tag>` for the tag in
  the error (the one resolved in `standpoint/llm.engine.yaml`, or whichever `--model` you
  passed); delete that engine file to re-resolve after a hardware change.
- 🍎🐧 **`Address already in use` on `standpoint-gui`**: port 8000 is taken, find the
  process with `lsof -i :8000`, or just run
  `uvicorn standpoint.api:app --port 8001` on a free port instead.
- 🪟 **`Address already in use` on `standpoint-gui`**: find the process with
  `netstat -ano | findstr :8000`, or run
  `uvicorn standpoint.api:app --port 8001` on a free port instead.
- 🍎🐧🪟 **Old Python (< 3.10)**: check with `python3 --version` (or `python --version`
  on Windows); Standpoint requires 3.10+. Install a newer Python with the prerequisite
  commands above rather than patching around the version check.

## Usage

```bash
standpoint examples/programming_languages.csv --outdir out
# without installing: python3 -m standpoint examples/programming_languages.csv --outdir out
```

Two equivalent CLIs are installed: `standpoint` (argparse) and `standpoint-click`.

As a library:

```python
import standpoint as sp

pos = sp.positioning("examples/programming_languages.csv")
pos.export("out")                 # writes out/python.{png,svg,white.png,white.svg,md,yaml}
print(pos.axes)
# {'x': 'Concurrency ↔ Ecosystem', 'y': 'Safety ↔ Learning'}
```

Pick a different local model for the axis names and the analysis:

```bash
standpoint my_table.csv --model qwen3:8b
```

More in [EXAMPLES.md](https://github.com/warith-harchaoui/standpoint/blob/main/EXAMPLES.md).

## As a service: GUI, API, MCP, Docker

```bash
pip install "standpoint[gui]"
standpoint-gui                     # browser app → http://localhost:8000/gui
```

![The Standpoint GUI: edit a table, generate the quadrant and analysis](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/assets/gui-preview.png)

The GUI's backend is a FastAPI app: `POST /api/position` returns the SVG,
the Markdown analysis, and the YAML. Serve it with the MCP endpoint mounted so an
agent can call `position` as a tool:

```bash
pip install "standpoint[mcp]"
standpoint-mcp                     # API + MCP at /mcp (GUI still at /gui)
```

Or run it all in a container (installs from `requirements.txt`, serves API + MCP):

```bash
docker build -t standpoint .
docker run --rm -p 8000:8000 standpoint
```

For local library work, a thin conda env wraps the same `requirements.txt`:

```bash
conda env create -f environment.yaml && conda activate env-for-standpoint && pip install -e .
```

## Input format

A CSV or Markdown table. The first column holds the option names; the rest are
numeric criteria on any scale. Higher means better. Empty cells are filled with
the column's minimum, so a missing rating never helps an option.

| Language | Performance | Ease of Learning | Ecosystem | Type Safety | Job Market |
|---|---|---|---|---|---|
| Python | 2 | 5 | 5 | 2 | 5 |
| Rust | 5 | 2 | 3 | 5 | 3 |
| Go | 4 | 4 | 4 | 4 | 4 |

The first row is the reference and goes to the top right. Change it with
`--reference "<name>"`. Mark a lower-is-better column with `(↓)`, e.g.
`Price (↓)`, or list it in `--lower`.

## How it works

1. Standardize each criterion to mean 0 and standard deviation 1. PCA is sensitive
   to scale, so this puts every criterion on equal footing.
2. Run PCA and keep two components. The axes stay as weighted sums of the original
   columns, so you can read them.
3. Rotate the map so the reference sits top right. If the reference scores top
   marks on everything, it is placed just past the best competitor on each axis
   rather than far off on its own.
4. Label it. The four highlighted options (leader, weakest, and the two challengers
   furthest toward the top and right poles) come straight from the map geometry.
   Each option takes its own colour from its position. A local model reads the
   loadings and names the four axis ends, as positive qualities, in your columns'
   language (English, French, or Spanish).

The figure keeps to a dotted cross for the axes, the pole words at the ends, labels
only where they fit, and a legend for the rest.

![Electric cars, French input gives a French title and French axis names](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/voitures_electriques.png)

## Notes

- Axis names come from a local model. A guard keeps them positive, distinct, and
  free of acronyms; a larger `--model` helps, and `--check` asks the vision model
  whether the figure reads correctly.
- Higher is better by default. For a column where lower is better, mark its header
  with `(↓)` (`Price (↓)`, `Latency (↓)`) or pass `--lower Price,Latency`. Standpoint
  negates it and names the pole for the benefit ("Affordable", "Portable"), never
  the drawback.
- Every figure is written twice: a **transparent** `.png` / `.svg` that drops onto any
  page, and a **white-background** `.white.png` / `.white.svg` for dark surfaces where
  the near-black labels would otherwise vanish on transparency.
- It is a 2D projection. The axes carry a stated fraction of the variance, so read
  it as a summary rather than the whole picture.

## Examples

Tracked in `examples/`, input CSV and generated figures:

| Table | Language | Leader |
|---|---|---|
| `programming_languages.csv` | en | Python |
| `cloud_providers.csv` | en | AWS |
| `laptops.csv` | en | MacBook Air (uses `Price (↓)` / `Weight (↓)`) |
| `voitures_electriques.csv` | fr | Tesla Model 3 |

## Development

```bash
pip install -r requirements-dev.txt   # or: pip install -e ".[dev]"
python3 -m pytest tests/ -q           # deterministic tests; model-backed ones auto-skip
python3 -m ruff check standpoint tests
python3 -m ruff format --check standpoint tests
```

The coding standard for this repository is [CODING.md](https://github.com/warith-harchaoui/standpoint/blob/main/CODING.md);
the contribution and versioning policy is in [CONTRIBUTING.md](https://github.com/warith-harchaoui/standpoint/blob/main/CONTRIBUTING.md).

## Author

[Warith Harchaoui](https://www.linkedin.com/in/warith-harchaoui)

## Credits

PCA perceptual maps are standard (`factoextra` and `FactoMineR` in R, `prince` and
`pca` in Python); using a model to read the components is a newer idea. Colours
come from the ["Good Colors"](https://harchaoui.org/warith/colors/) palette.
Figures are hand-authored SVG, rasterised to PNG by
[`resvg`](https://github.com/RazrFalcon/resvg).

## License

BSD 3-Clause, the same license as scikit-learn. See
[`LICENSE`](https://github.com/warith-harchaoui/standpoint/blob/main/LICENSE).
