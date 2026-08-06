---
name: standpoint
description: >-
  Turn a comparison table (options as rows, criteria as columns, numeric ratings on any
  scale) into a labelled 2D positioning map — a quadrant / perceptual / competitive-
  landscape map — plus a short written analysis and a YAML of every coordinate, all on
  the local machine with `standpoint`. Under the hood it is correlation PCA: the two
  axes stay readable weighted sums of the criteria and are named in plain words by a
  local Ollama model (in the table's own language, English / French / Spanish), the
  reference option is rotated to the top-right, and every option is coloured and
  labelled. Reachable as a Python library (`import standpoint as sp`), two CLIs
  (`standpoint`, `standpoint-click`), a browser GUI (`standpoint-gui`), a FastAPI HTTP
  API, and an MCP server (`standpoint-mcp`).

  TRIGGER — any of: the user wants to *place / position / map* several options against
  each other from a ratings table ("plot these tools / products / vendors / languages /
  cars / frameworks on a map", "make a positioning map / perceptual map / quadrant /
  2x2 / competitive landscape", "where does X stand versus the others", "compare these
  options across these criteria and chart it", "turn this comparison table into a map");
  the user has a table of *options × criteria* with numeric scores and wants a 2D
  picture of it; the user asks for a PCA / perceptual map of a scorecard or ratings
  table; the user names a command (`standpoint`, `standpoint-click`, `standpoint-gui`,
  `standpoint-mcp`) or a library symbol (`positioning`, `analyze`, `axis_poles`,
  `assign_roles`, `to_svg`, `export_all`, `parse_table`); the user points at a CSV /
  Markdown table whose first column is option names and the rest numeric criteria and
  wants it turned into a figure + written analysis; the user wants to run the standpoint
  GUI, HTTP API, or MCP server.

  SKIP when: the user wants an ordinary chart of one or two variables (bar / line /
  scatter / pie of a series or a time axis) — that is plain plotting, not a positioning
  map (reach for a figures skill instead); PCA purely for dimensionality
  reduction inside an ML pipeline (use scikit-learn directly — standpoint is for the
  *labelled competitive map*, not feature engineering); a single-criterion ranking that
  is really just a sort; or building / cleaning / gathering the table itself rather than
  mapping it. standpoint maps an existing options × criteria table; it does not collect
  the data or fit a predictor.
---

# standpoint — comparison table → positioning map

`standpoint` reads one table (options in rows, criteria in columns, numbers in the
cells) and writes a three-fold deliverable: a labelled 2D map (hand-authored,
interactive SVG + PNG, no Vega), a short written analysis (Markdown), and a YAML with
every coordinate and coefficient. One command does it, entirely on the machine, with
no chart-rendering runtime. The maths is ordinary
correlation PCA — the value it adds is the work you would otherwise do by hand:
orienting the map around a reference, naming the axes in plain words, colouring and
labelling the points, and writing it up.

## First: is it installed?

```bash
standpoint --help                 # the argparse CLI (always installed with the package)
python -c "import standpoint"     # library import check
```

If it is missing, install it (Python 3.10–3.13):

```bash
pip install standpoint                 # library + the two CLIs
pip install "standpoint[gui]"          # + browser GUI and HTTP API
pip install "standpoint[mcp]"          # + MCP server (over the API)
```

Axis names and the written analysis use a local [Ollama](https://ollama.com) model
(default `qwen2.5vl:7b`); pick another with `--model` / `model=`. The map geometry is
computed without the model, so it is the same every run.

## The fast path

CLI, from a CSV or Markdown table:

```bash
standpoint table.csv --outdir out
standpoint table.csv --model qwen3:8b         # a different local model
standpoint table.csv --reference "AWS"        # which option sits top-right
standpoint table.csv --lower Price,Latency    # criteria where lower is better
```

Library, one call:

```python
import standpoint as sp

pos = sp.positioning("table.csv")             # a path, a raw string, or a DataFrame
pos.export("out")                             # writes out/<name>.{png,svg,white.png,white.svg,md,yaml}
pos.axes        # {'x': 'Cost ↔ Scalability', 'y': 'Simplicity ↔ Power'}
pos.role_of     # {'AWS': 'best', 'DigitalOcean': 'worst', ...}
```

## Which interface to reach for

- **Library** (`import standpoint as sp`) — inside Python, or to get the `Positioning`
  object (`.coords`, `.loadings`, `.axes`, `.to_svg()`, `.to_markdown()`, `.export()`).
- **CLI** — `standpoint` (argparse) or the twin `standpoint-click`; same flags. Best
  for a one-shot from a file, or scripting.
- **GUI** — `standpoint-gui` → http://localhost:8000/gui: edit a table in the browser,
  upload/download CSV or XLSX, generate the quadrant live, read the colour-coded
  analysis. Best when a human wants to try tables interactively.
- **HTTP API / MCP** — `standpoint-mcp` serves the FastAPI app (`POST /api/position`)
  *and* the MCP endpoint at `/mcp`, so an agent can call `position` as a tool. Best for
  another program or an MCP-aware host.

## Input format (the one thing to get right)

The first column holds the option names; every other column is a numeric criterion on
any scale. **Higher means better** by default. A blank cell is filled with that
column's minimum (a missing rating never flatters an option). The first row is the
reference and lands top-right (change it with `--reference "<name>"`). For a criterion
where lower is better, mark the header `Price (↓)` or pass `--lower Price,Latency`.

```
Language,Performance,Ease of Learning,Ecosystem,Type Safety,Job Market
Python,2,5,5,2,5
Rust,5,2,3,5,3
Go,4,4,4,4,4
```

One command does the common case — write the figure + analysis and print where they
went:

```bash
python scripts/positioning_summary.py table.csv --outdir out
```

See `references/interfaces.md` for the full library / CLI / API / MCP / Docker surface,
and `references/input-and-output.md` for the table rules and the exact files written.

## Gotchas worth remembering

- It is a **2D projection**: the axes carry a stated fraction of the information, so
  read the map as a summary, not the whole truth.
- The model only **names** things (axes, analysis); the geometry is deterministic, so
  the map is the same run to run whatever model you pick.
- Everything is **local**: the table never leaves the machine; the only network touch
  is Ollama pulling its model the first time.

The exhaustive list of what should (and should not) invoke this tool lives in
[TRIGGERS.md](https://github.com/warith-harchaoui/standpoint/blob/main/TRIGGERS.md).
