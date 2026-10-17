---
name: standpoint
description: >-
  Turn one comparison table — options in rows, criteria in columns, numbers in
  the cells — into a labelled 2D positioning map (quadrant / perceptual /
  competitive-landscape chart) plus a YAML of every coordinate, so the
  placement is auditable rather than hand-drawn. Use when the user says "plot
  these tools / products / vendors / frameworks on a map", "where does X stand
  versus the others", "map the competitive landscape", "make a positioning map
  / perceptual map / quadrant / 2×2 / magic-quadrant-style chart", "compare
  these options across these criteria and chart it", hands over a CSV or
  Markdown table whose first column is names and the rest numeric ratings, or
  names `standpoint`, `standpoint-click`, `standpoint-gui`, `standpoint-mcp`,
  `import standpoint`. Do NOT use for a bar / line / scatter chart of raw data,
  a single-criterion ranking, or a diagram with no numbers behind it. The
  exhaustive trigger catalogue is in `references/triggers.md`.
license: BSD-3-Clause
metadata:
  author: Warith Harchaoui
  package: standpoint
  suite: ai-helpers
  homepage: https://deraison.ai/ai-helpers
---

# standpoint — comparison table → positioning map

`standpoint` reads one table (options in rows, criteria in columns, numbers in the
cells) and writes a two-fold deliverable: a labelled 2D map (hand-authored,
interactive SVG + PNG, no Vega) and a YAML with every coordinate and coefficient.
One command does it, entirely on the machine, with no chart-rendering runtime. The
maths is ordinary correlation PCA — the value it adds is the work you would
otherwise do by hand: orienting the map around a reference, naming the axes in
plain words, and colouring and labelling the points.

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

Axis names use a local [Ollama](https://ollama.com) model
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

pos = sp.positioning("table.csv")  # a path, a raw string, or a DataFrame
pos.export("out")  # writes out/<name>.{png,svg,white.png,white.svg,yaml}
pos.axes  # {'x': 'Cost ↔ Scalability', 'y': 'Simplicity ↔ Power'}
pos.role_of  # {'AWS': 'best', 'DigitalOcean': 'worst', ...}
```

## Which interface to reach for

- **Library** (`import standpoint as sp`) — inside Python, or to get the `Positioning`
  object (`.coords`, `.loadings`, `.axes`, `.to_svg()`, `.export()`).
- **CLI** — `standpoint` (argparse) or the twin `standpoint-click`; same flags. Best
  for a one-shot from a file, or scripting.
- **GUI** — `standpoint-gui` → http://localhost:8000/gui: edit a table in the browser,
  upload/download CSV or XLSX, and generate the quadrant live. Best when a human
  wants to try tables interactively.
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

One command does the common case — write the figure + YAML and print where they
went:

```bash
python scripts/positioning_summary.py table.csv --outdir out
```

See `references/interfaces.md` for the full library / CLI / API / MCP / Docker surface,
`references/input-and-output.md` for the table rules and the exact files written,
and `references/triggers.md` for the exhaustive, auditable trigger catalogue.

## Gotchas worth remembering

- It is a **2D projection**: the axes carry a stated fraction of the information, so
  read the map as a summary, not the whole truth.
- The model only **names** things (axes); the geometry is deterministic, so
  the map is the same run to run whatever model you pick.
- Everything is **local**: the table never leaves the machine; the only network touch
  is Ollama pulling its model the first time.

The exhaustive list of what should (and should not) invoke this tool lives in
[TRIGGERS.md](https://github.com/warith-harchaoui/standpoint/blob/main/TRIGGERS.md).
