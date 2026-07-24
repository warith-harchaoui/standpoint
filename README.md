# Standpoint

[🇫🇷](https://github.com/warith-harchaoui/standingpoint/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/standingpoint/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/standingpoint/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/standingpoint/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/standingpoint/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/local--first-Ollama%20%2B%20Vega--Lite-brightgreen.svg)](#local-first)

`Standpoint` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![Standpoint logo](https://raw.githubusercontent.com/warith-harchaoui/standingpoint/main/assets/logo.png)](https://harchaoui.org/warith/ai-helpers/#standingpoint)

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
the figure with [`vl-convert`](https://github.com/vega/vl-convert). Your table is never
uploaded, and there is no telemetry, no account, and nothing to sign up for.

The one thing that reaches out is the axis naming and the written analysis, which ask a
[Ollama](https://ollama.com) model running on `localhost`. Ollama fetches the model
weights the first time, then works offline. You can also leave the model out entirely:
with `--no-llm` you still get the whole map, and the axes are named after the strongest
column at each end.

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/standingpoint-doc/)

[🗺️ Landscape](https://github.com/warith-harchaoui/standingpoint/blob/main/LANDSCAPE.md)

[📋 Examples](https://github.com/warith-harchaoui/standingpoint/blob/main/EXAMPLES.md)

Input: a table of options and their ratings.

| Language | Performance | Ease of Learning | Ecosystem | Concurrency | Type Safety | Job Market | Tooling |
|---|---|---|---|---|---|---|---|
| Python | 2 | 5 | 5 | 2 | 2 | 5 | 4 |
| Rust | 5 | 2 | 3 | 5 | 5 | 3 | 4 |
| Go | 4 | 4 | 4 | 5 | 4 | 4 | 4 |
| JavaScript | 3 | 4 | 5 | 3 | 2 | 5 | 3 |
| … | | | | | | | |

Output: a positioning map,

![Programming languages positioning map](https://raw.githubusercontent.com/warith-harchaoui/standingpoint/main/examples/programming_languages.png)

plus a Markdown analysis (what the axes mean, where the reference wins, which options
stand out, with the loadings and a ranking) and a YAML file with every option's
coordinates, role, colour, and original values.

## Features

- **One command, three-fold deliverable**: a figure (PNG + SVG + Vega-Lite JSON), a
  Markdown interpretation, and a YAML of coordinates + coefficients.
- **Readable axes**: PCA keeps the axes as weighted sums of your columns; a local
  model names the four poles as positive qualities, guarded against acronyms,
  negatives, and antonym pairs.
- **Multilingual**: axis names, the written analysis, and the figure title come out
  in the table's own language (English, French, or Spanish), auto-detected from the
  column names — a French table reads *Voitures dans le quadrant*.
- **Reference-oriented**: the option you care about is rotated to the top-right; an
  all-max reference is placed just past the best competitor rather than as an outlier.
- **Four highlighted options**: the leader, the weakest overall, and the two
  challengers that reach furthest toward the top and right poles.
- **Polarity aware**: mark a lower-is-better column with `(↓)` (or `--lower`) and
  Standpoint names the benefit (*Affordable*, *Portable*), never the drawback.
- **Vision self-check**: `--check` asks a local vision model whether the figure reads
  correctly (leader top-right, labels legible, legend visible).

**One engine, six access surfaces** — the same `positioning()` pipeline is reachable as:

- **Library**: `import standpoint as sp`.
- **CLI ×2**: `standpoint` (argparse, always installed) and `standpoint-click`
  (click twin) with identical flags.
- **GUI**: `standpoint-gui` → a single-page browser app at `/gui` (`[gui]` extra).
- **HTTP API**: a FastAPI app (`POST /api/position`), same `[gui]` extra.
- **MCP**: `standpoint-mcp` publishes the API as MCP tools at `/mcp` (`[mcp]` extra).

It also ships as a **Claude / OpenCode skill** — see
[skills/standpoint/SKILL.md](https://github.com/warith-harchaoui/standingpoint/blob/main/skills/standpoint/SKILL.md)
and the exhaustive
[TRIGGERS.md](https://github.com/warith-harchaoui/standingpoint/blob/main/TRIGGERS.md).

## Installation

**Prerequisites** — **Python 3.10–3.13** and **git**, cross-platform:

- 🍎 **macOS** ([Homebrew](https://brew.sh)): `brew install python git`
- 🐧 **Ubuntu/Debian**: `sudo apt update && sudo apt install -y python3 python3-pip git`
- 🪟 **Windows** (PowerShell): `winget install Python.Python.3.12 Git.Git`

For axis names and the written analysis, install [Ollama](https://ollama.com) and pull
the default model once (optional — skip it and use `--no-llm`):

- 🍎 **macOS**: `brew install ollama` — then `ollama serve &` and `ollama pull qwen2.5vl:7b`
- 🐧 **Ubuntu/Debian**: `curl -fsSL https://ollama.com/install.sh | sh` — then `ollama pull qwen2.5vl:7b`
- 🪟 **Windows**: install from [ollama.com/download](https://ollama.com/download), then `ollama pull qwen2.5vl:7b`

We recommend a Python environment. If you're new to that, see [🥸 Tech tips](https://harchaoui.org/warith/4ml/#install).

### From PyPI (recommended)

```bash
pip install standpoint             # library + the two CLIs
pip install "standpoint[gui]"      # + the browser GUI and HTTP API
pip install "standpoint[mcp]"      # + the MCP server (over the API)
```

### From source

```bash
git clone https://github.com/warith-harchaoui/standingpoint.git
cd standingpoint
pip install -e .          # or: pip install -r requirements.txt
```

Or install straight from GitHub (the import name is `standpoint`):

```bash
pip install "git+https://github.com/warith-harchaoui/standingpoint.git@v0.4.0"
```

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
pos.export("out")                 # writes out/python.{png,svg,white.png,white.svg,vl.json,md,yaml}
print(pos.axes)
# {'x': 'Concurrency ↔ Ecosystem', 'y': 'Safety ↔ Learning'}
```

Skip the model for a fast, deterministic run (no Ollama needed):

```bash
standpoint my_table.csv --no-llm
standpoint my_table.csv --model qwen3:8b
```

More in [EXAMPLES.md](https://github.com/warith-harchaoui/standingpoint/blob/main/EXAMPLES.md).

## As a service — GUI, API, MCP, Docker

```bash
pip install "standpoint[gui]"
standpoint-gui                     # browser app → http://localhost:8000/gui
```

![The Standpoint GUI — edit a table, generate the quadrant and analysis](https://raw.githubusercontent.com/warith-harchaoui/standingpoint/main/assets/gui-preview.png)

The GUI's backend is a FastAPI app: `POST /api/position` returns the Vega-Lite spec,
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

![Electric cars, French input gives a French title and French axis names](https://raw.githubusercontent.com/warith-harchaoui/standingpoint/main/examples/voitures_electriques.png)

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

The coding standard for this repository is [CODING.md](https://github.com/warith-harchaoui/standingpoint/blob/main/CODING.md);
the contribution and versioning policy is in [CONTRIBUTING.md](https://github.com/warith-harchaoui/standingpoint/blob/main/CONTRIBUTING.md).

## Credits

PCA perceptual maps are standard (`factoextra` and `FactoMineR` in R, `prince` and
`pca` in Python); using a model to read the components is a newer idea. Colours
come from the ["Good Colors"](https://harchaoui.org/warith/colors/) palette.
Figures are rendered by [`vl-convert`](https://github.com/vega/vl-convert) over
[Vega-Lite](https://vega.github.io/vega-lite/).

## Author

[Warith Harchaoui](https://www.linkedin.com/in/warith-harchaoui)

## License

BSD 3-Clause, the same license as scikit-learn. See
[`LICENSE`](https://github.com/warith-harchaoui/standingpoint/blob/main/LICENSE).
