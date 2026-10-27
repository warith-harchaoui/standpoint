# Examples

[🇫🇷](https://github.com/warith-harchaoui/standpoint/blob/main/EXEMPLES.md) · [🇬🇧](https://github.com/warith-harchaoui/standpoint/blob/main/EXAMPLES.md)

Every snippet below was run against the tables tracked in
[`examples/`](https://github.com/warith-harchaoui/standpoint/tree/main/examples),
and every output block is what came back. Two kinds of number live in this file and
it is worth separating them up front: the **geometry** (variance, rotation,
loadings, coordinates, roles, file names) is deterministic — the same table gives
you the same figures — while the **pole words** come from whichever local model your
machine resolved, so yours will read differently. The runs here were made with a
small local `qwen2.5:3b`.

## Table of Contents

- [Setup](#setup)
- [1. One table, one map](#1-one-table-one-map)
- [2. Read the table before you plot it](#2-read-the-table-before-you-plot-it)
- [3. Lower is better](#3-lower-is-better)
- [4. Choosing the reference](#4-choosing-the-reference)
- [5. The six files a run writes](#5-the-six-files-a-run-writes)
- [6. Blank cells are reported, never hidden](#6-blank-cells-are-reported-never-hidden)
- [7. A French table gives a French map](#7-a-french-table-gives-a-french-map)
- [8. Auditing the model's prose](#8-auditing-the-models-prose)
- [9. Browser app, HTTP API, MCP tool](#9-browser-app-http-api-mcp-tool)
- [Command line](#command-line)
- [Troubleshooting](#troubleshooting)

## Setup

```bash
pip install --upgrade standpoint          # library + the `standpoint` command
pip install --upgrade "standpoint[gui]"   # adds the browser app and the HTTP API
pip install --upgrade "standpoint[mcp]"   # adds the MCP endpoint
```

Every Python snippet below assumes these two lines, and nothing else:

```python
import pandas as pd
import standpoint as sp
```

The commands are run from a checkout, so the `examples/` paths resolve:

```bash
git clone https://github.com/warith-harchaoui/standpoint
cd standpoint
```

**One external thing is needed, once.** Naming the axis poles and writing the
analysis both ask a local model over `localhost`. Standpoint hard-codes no model
tag: it ships a brief (`standpoint/llm.brief.yaml`) and
[best-engine-ai-helper](https://pypi.org/project/best-engine-ai-helper/) resolves
the best fit for your machine on first use, caching the pick to the gitignored
`standpoint/llm.engine.yaml`. Everything geometric — parsing, polarity, PCA,
orientation, colours, the SVG, the YAML, `--check` — needs no model at all, which is
why sections 2 to 6 run on a machine with nothing serving.

## 1. One table, one map

The whole package in one call. `positioning()` takes a path, a raw CSV/Markdown
string or a DataFrame, and hands back an object you can read or write out.

```python
pos = sp.positioning("examples/laptops.csv")
print(pos.axes)
print(pos.poles)
```

```
{'x': 'Affordable ↔ Craftsmanship', 'y': 'Efficiency ↔ Portability'}
['Affordable', 'Craftsmanship', 'Efficiency', 'Portability']
```

`poles` is always ordered `[left, right, bottom, top]`; `axes` is the same four
words paired into the two axis titles. One more call writes the deliverable:

```python
pos.export("out")
```

```
['out/macbook_air.png', 'out/macbook_air.svg', 'out/macbook_air.white.png',
 'out/macbook_air.white.svg', 'out/macbook_air.md', 'out/macbook_air.yaml']
```

The stem comes from the reference option (`MacBook Air` → `macbook_air`); pass
`stem="laptops"` to choose it yourself.

![Laptops positioning map](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/laptops.png)

## 2. Read the table before you plot it

`parse_table` is the front door for both formats. It reads a path or a raw string,
takes the first column as the option names, and turns every other cell into a
number:

```python
df = sp.parse_table("examples/programming_languages.csv")
print(df.shape, "|", df.index.name)
print(df.head(3).to_string())
```

```
(12, 7) | Programming Language
                      Performance  Ease of Learning  Ecosystem  Concurrency  Type Safety  Job Market  Tooling
Programming Language
Python                        2.0               5.0        5.0          2.0          2.0         5.0      4.0
Rust                          5.0               2.0        3.0          5.0          5.0         3.0      4.0
Go                            4.0               4.0        4.0          5.0          4.0         4.0      4.0
```

A Markdown table pasted straight out of a document works the same way — no file
needed:

```python
editors = sp.parse_table("""
| Editor | Speed | Plugins | Learning Curve (↓) |
| --- | --- | --- | --- |
| Neovim | 5 | 5 | 5 |
| VS Code | 3 | 5 | 2 |
| Emacs | 4 | 5 | 5 |
| Sublime | 5 | 3 | 2 |
""")
print(list(editors.columns))
```

```
['Speed', 'Plugins', 'Learning Curve (↓)']
```

`validate_table` is the gate the pipeline runs for you. It returns `None` when the
table can be positioned and raises a sentence you can show a user when it cannot:

```python
print(sp.validate_table(df))
try:
    sp.validate_table(pd.DataFrame({"x": [1.0, 2.0]}))
except ValueError as err:
    print("ValueError:", err)
```

```
None
ValueError: need at least 2 criteria (columns); got 1.
```

It also rejects a column with no numbers at all, a table where every criterion is
constant, two options with identical ratings (they would land on the same point)
and two identical criteria (they would count the same evidence twice).

## 3. Lower is better

Price and weight are criteria where a *low* number is the good news. Mark the
header with `(↓)` and Standpoint strips the marker, negates the column, and names
the pole after the benefit:

```python
laptops = sp.parse_table("examples/laptops.csv")
clean, lower = sp.resolve_polarity(laptops)
print(list(clean.columns))
print("lower is better:", sorted(lower))
```

```
['Price', 'Performance', 'Battery Life', 'Build Quality', 'Weight', 'Screen']
lower is better: ['Price', 'Weight']
```

If you cannot edit the headers, name the columns instead — the two routes are
equivalent and additive:

```python
sp.positioning("examples/laptops.csv", lower_is_better=["Price", "Weight"])
```

```bash
standpoint examples/laptops.csv --lower "Price,Weight" --outdir out
```

This is why section 1's map reads *Affordable*, never *Expensive*: the model is
shown `low Price` rather than `Price`, so it names what the laptops at that end are
good at.

## 4. Choosing the reference

The reference is the option placed top-right, and the whole map is rotated to put
it there. Everything else about the geometry is unchanged, which is the point: the
rotation is a change of viewpoint, not a change of data.

```python
res = sp.analyze(df, reference="Python")
print("reference:", res.reference)
print("rotation: %+.1f deg" % res.rotation_deg)
print("variance kept:", [round(float(v), 4) for v in res.explained_variance_ratio])
print(res.coords().round(2).head(4).to_string())
```

```
reference: Python
rotation: -127.9 deg
variance kept: [0.4936, 0.3042]
            axis-1  axis-2
Python        2.45    2.86
Rust         -1.21   -2.86
Go            0.65   -1.26
JavaScript    2.08    1.57
```

`assign_roles` then reads four options straight off that geometry — the leader, the
weakest overall, and the two challengers reaching furthest toward the top and right
poles. Everything else is a competitor:

```python
roles = sp.assign_roles(res)
print({name: role for name, role in zip(res.names, roles) if role != "competitor"})
print(sp.gradient_colors(res, roles)[:4])
```

```
{'Python': 'best', 'Rust': 'worst', 'Java': 'right', 'Ruby': 'top'}
['#FF3B30', '#A52A2A', '#75A857', '#9CB7FF']
```

Force a named option into a highlight with `top=` / `right=` (`--top` / `--right`
on the command line) when you want to talk about a specific challenger rather than
the geometric pick.

![Cloud providers positioning map](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/cloud_providers.png)

## 5. The six files a run writes

```python
pos = sp.positioning("examples/laptops.csv")
pos.export("out", stem="laptops")
```

| File | What it is |
|---|---|
| `laptops.png` | the figure on a **transparent** background, so it drops onto any page |
| `laptops.svg` | the same figure as hand-authored, interactive SVG (hover tooltips, no Vega) — editable and embeddable |
| `laptops.white.png` | the figure on **white**, for dark surfaces where the near-black labels would vanish on transparency |
| `laptops.white.svg` | the white-background SVG |
| `laptops.md` | the written analysis: the computed facts, then the model's reading |
| `laptops.yaml` | every coordinate, loading, role, colour and original value |

Each face is also reachable in memory, without touching the disk:

```python
print(len(pos.to_svg()), "bytes of SVG")
print("\n".join(pos.to_yaml().splitlines()[:6]))
```

```
6124 bytes of SVG
meta:
  reference: MacBook Air
  rotation_deg: -67.979
  explained_variance_ratio:
  - 0.5268
  - 0.3522
```

The YAML has three top-level keys — `meta`, `axes`, `approaches` — and the `axes`
block is the stable contract for anything downstream that wants the pole names
without re-running a model:

```yaml
axes:
  axis_1:
    name: Affordable ↔ Craftsmanship
    pole_left: Affordable
    pole_right: Craftsmanship
    loadings:
      Price: -0.3459
      Performance: 0.1943
      Battery Life: 0.5171
      Build Quality: 0.6472
      Weight: 0.2949
      Screen: 0.2633
```

And `--check` reads the written coordinates back to confirm the figure holds up. No
model is involved, so this works offline:

```python
print(sp.assess_layout(pos))
```

```
{'leader_top_right': True, 'readable': True, 'axis_labels_visible': True, 'notes': 'Layout checks passed.'}
```

## 6. Blank cells are reported, never hidden

An empty cell is filled with its column's minimum, so a gap never flatters an
option. That default is a judgement rather than a measurement, and because every
criterion is z-scored before the projection it moves *every* option's coordinates,
not only the one with the gap. So each run says what it had to invent.

```python
gaps = sp.parse_table("""
| Tool | Speed | Docs |
| --- | --- | --- |
| A | 5 | 4 |
| B | 3 |  |
| C | 4 | 2 |
""")
print(sp.imputed_cells(gaps))
print(sp.impute(gaps).to_string())
```

```
[('B', 'Docs')]
      Speed  Docs
Tool
A       5.0   4.0
B       3.0   2.0
C       4.0   2.0
```

The command line says it on stderr before the map exists:

```
warning: 1 empty cell(s) filled with the column minimum: Neovim/Docs. Every coordinate below is affected, not just these options -- see meta.imputed_cells in the YAML.
```

and the YAML keeps the record in two places — once globally, once per option, so a
single row is readable on its own:

```yaml
meta:
  imputed_cells:
  - option: Neovim
    criterion: Docs
```

```yaml
- name: Neovim
  coordinates:
    axis_1: 2.0037
    axis_2: 0.7785
  role: best
  color: '#FF3B30'
  attributes:
    Speed: 5.0
    Plugins: 5.0
    Docs: 3.0
  imputed_attributes:
  - Docs
```

A complete table prints nothing at all. The point is not to discourage gaps; it is
that a placement you cannot audit is not auditable.

## 7. A French table gives a French map

Nothing is configured. The language is detected from the column names, and it
drives the pole words, the noun, the figure title and the analysis:

```python
voitures = sp.parse_table("examples/voitures_electriques.csv")
print(sp.detect_language(list(voitures.columns)))

pos = sp.positioning("examples/voitures_electriques.csv")
print(pos.lang, "|", pos.title)
print(pos.axes)
print({n: r for n, r in pos.role_of.items() if r != "competitor"})
```

```
fr
fr | Voitures dans le quadrant
{'x': 'Économique ↔ Fiable', 'y': 'Sécurisé ↔ Système avancé'}
{'Tesla Model 3': 'best', 'BMW i4': 'right', 'MG4': 'top', 'Dacia Spring': 'worst'}
```

English, French and Spanish are supported (`sp.SUPPORTED_LANGS`). Pass `lang="fr"`
to force the output language when the column names are ambiguous or English but the
reader is not.

![Carte de positionnement des voitures électriques](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/voitures_electriques.png)

## 8. Auditing the model's prose

The `.md` face is split deliberately: the numbers in it (the variance each axis
keeps, the cumulative total, the imputed cells) are computed in Python, and the
model is forbidden from quoting a percentage, a coordinate or a rating. It
contributes interpretation only.

That still leaves it free to put an option in the wrong corner, so Standpoint
checks its own sentences against the coordinates. `check_analysis` needs no model —
it finds the direction words, finds the option names, and compares each claim
against the sign of that option's coordinate:

```python
pos = sp.positioning("examples/voitures_electriques.csv")
print(sp.check_analysis("Tesla Model 3 sits in the lower left of the map.", pos.result))
print(sp.check_analysis("Tesla Model 3 sits in the upper right of the map.", pos.result))
```

```
['written analysis places Tesla Model 3 on the bottom, but it sits top', 'written analysis places Tesla Model 3 on the left, but it sits right']
[]
```

Every run does this for you and prints the mismatches on stderr, which is how a
small model's over-grouping becomes visible instead of shipping. From a real run on
a four-row table:

```
written analysis: written analysis places Emacs on the right, but it sits left
written analysis: written analysis places VS Code on the bottom, but it sits top
written analysis: written analysis places VS Code on the right, but it sits left
```

Three warnings on one tiny table is the honest signal that the model is too small
for the prose. The figure and the YAML are unaffected: they never went near a
model.

## 9. Browser app, HTTP API, MCP tool

The same `positioning()` pipeline, three more doors. All three come from the
`[gui]` / `[mcp]` extras and all three bind to loopback by default, honouring
`STANDPOINT_HOST` / `STANDPOINT_PORT`.

```bash
standpoint-gui     # Standpoint GUI -> http://127.0.0.1:8000/gui  (Ctrl-C to stop)
standpoint-mcp     # Standpoint API + MCP -> http://127.0.0.1:8000  (MCP at /mcp)
```

`GET /api/example` serves the tracked tables, so the browser grid is seeded from
the same files as this page:

```bash
curl "http://127.0.0.1:8000/api/example?name=laptops"
```

```
Laptop,Price (↓),Performance,Battery Life,Build Quality,Weight (↓),Screen
MacBook Air,3,3,5,5,1,4
MacBook Pro,5,5,4,5,3,5
Dell XPS,4,4,3,4,2,5
```

`POST /api/position` is the whole engine in one round-trip. The body is the table
as CSV text plus the few options the command line also takes (`reference`, `lower`,
`model`, `lang`):

```bash
curl -s -X POST "http://127.0.0.1:8000/api/position" \
  -H 'Content-Type: application/json' \
  -d '{"table":"Editor,Speed,Plugins\nNeovim,5,5\nVS Code,3,5\nEmacs,4,4\n","reference":"Neovim"}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sorted(d)); print(d["axes"]); print(d["roles"]); print(d["slug"], len(d["svg"]), len(d["yaml"]))'
```

```
['axes', 'poles', 'reference', 'roles', 'slug', 'svg', 'yaml']
{'x': 'Innovative ↔ Efficient', 'y': 'Sustainable ↔ Optimized'}
{'Neovim': 'best', 'VS Code': 'worst', 'Emacs': 'right'}
editors 2488 1048
```

Omit `model` and the resolved engine is used; the run above forced
`"model": "qwen2.5:3b"` so the pole words match the rest of this page.

Bad input comes back as a status you can act on rather than a traceback: `400` with
the library's own message for an empty or degenerate table or an unknown reference,
`503` when the local model is not serving.

```bash
curl -s -X POST "http://127.0.0.1:8000/api/position" \
  -H 'Content-Type: application/json' -d '{"table":""}'
```

```
{"detail":"The table is empty."}
```

`standpoint-mcp` publishes those same routes as MCP tools at `/mcp` — one
`fastapi-mcp` wrapper over the existing app, so there is no second implementation
to drift. And `python webapp/build.py` composes the same page as a static bundle
that runs the engine in the visitor's browser via Pyodide, with no server process
at all; see
[GUI.md](https://github.com/warith-harchaoui/standpoint/blob/main/GUI.md).

## Command line

One command is installed, `standpoint`, built with click. `python3 -m standpoint`
is the same door without a console script on the PATH.

```bash
standpoint --help
```

```
Usage: standpoint [OPTIONS] TABLE

  Turn a comparison TABLE (CSV or Markdown) into a positioning map.

  Writes PNG + interactive SVG + a Markdown analysis + a YAML of every
  coordinate into the output directory, and prints the axis names, the four
  highlighted options and the loadings.

Options:
  -r, --reference TEXT  Option placed top-right: row index or exact name.
                        [default: 0]
  -o, --outdir TEXT     Output directory for the deliverable.  [default: out]
  --stem TEXT           Basename for outputs (default: from reference).
  --top TEXT            Exact name of the option to highlight as strongest
                        toward the top pole.
  --right TEXT          Exact name of the option to highlight as strongest
                        toward the right pole.
  --lower TEXT          Comma-separated criteria where lower is better.
  --model TEXT          Override the local model tag (default: the one
                        resolved in llm.engine.yaml).
  --check               Sanity-check the figure's layout from its geometry.
  -V, --version         Show the version and exit.
  -h, --help            Show this message and exit.
```

A full run, with the layout self-check on:

```bash
standpoint examples/laptops.csv --outdir out --check
```

```
Parsed 10 options x 6 criteria
Reference 'MacBook Air' rotated by -68.0 deg onto the top-right diagonal

PCA explained variance: axis-1(PC1)=52.7%  axis-2(PC2)=35.2%  (cumulative 87.9%)

Axis names: axis-1 = 'Affordable ↔ Craftsmanship'   axis-2 = 'Efficiency ↔ Portability'

Highlighted options:
  leader (reference)                : MacBook Air
  weakest overall                   : Lenovo Legion
  strongest toward 'Portability'    : Acer Swift
  strongest toward 'Craftsmanship'  : MacBook Pro

Canonical axes in the oriented frame (loadings):
               axis-1  axis-2
Price          -0.346   0.436
Performance     0.194  -0.515
Battery Life    0.517   0.391
Build Quality   0.647  -0.020
Weight          0.295   0.520
Screen          0.263  -0.349

Deliverable written:
  out/macbook_air.png
  out/macbook_air.svg
  out/macbook_air.white.png
  out/macbook_air.white.svg
  out/macbook_air.md
  out/macbook_air.yaml

Layout self-check:
  leader_top_right: True
  readable        : True
  axis_labels_visible: True
  notes           : Layout checks passed.
```

The flags that change the map:

```bash
standpoint examples/cloud_providers.csv --reference AWS --outdir out
standpoint examples/programming_languages.csv --reference Rust --stem rust --outdir out
standpoint examples/laptops.csv --lower "Price,Weight" --outdir out
standpoint examples/voitures_electriques.csv --model qwen3:8b --check --outdir out
standpoint examples/cloud_providers.csv --top Cloudflare --right "Google Cloud" --outdir out
```

The four tracked tables and who leads each:

| Table | Language | Leader (row 0) |
|---|---|---|
| `examples/programming_languages.csv` | en | Python |
| `examples/cloud_providers.csv` | en | AWS |
| `examples/laptops.csv` | en | MacBook Air — uses `Price (↓)` / `Weight (↓)` |
| `examples/voitures_electriques.csv` | fr | Tesla Model 3 |

![Programming languages positioning map](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/programming_languages.png)

## Troubleshooting

**`Ollama has no model '<tag>'`, or `503 The local model is unavailable`.** The axis
naming needs a local model serving on `localhost`. Start the backend
(`ollama serve`), then either pull the tag the resolver picked or re-resolve for
this machine:

```bash
best-engine-ai-helper resolve --brief standpoint/llm.brief.yaml --out standpoint/llm.engine.yaml
```

`standpoint --model qwen3:8b` overrides the tag for the axis naming of a single
run. Note that the figure, the YAML and `--check` need no model: if all you want is
the map, an outage costs you the pole words and the prose.

**`need at least 2 criteria (columns); got 1`.** A single-criterion comparison is a
sorted list, not a map. The same gate also rejects a column with no numbers, an
all-constant table, duplicate option rows, and duplicate criterion columns — each
with a sentence naming the offending row or column.

**`reference '<name>' not found`.** `--reference` takes either a row index (`0`,
the default) or an option name spelled exactly as it appears in the first column,
spaces and capitals included. Quote names that contain spaces:
`--reference "Google Cloud"`.

**The axis names are vague, repetitive, or English on a French table.** Pole naming
is the one step that depends on model quality. A bigger `--model` helps most; if the
language is wrong, the column names were too ambiguous to detect — pass
`lang="fr"` to `positioning()` to force it.

**The labels are invisible on a dark page.** You are looking at the transparent
`.png` / `.svg`. Use the `.white.png` / `.white.svg` written beside it.

**`Address already in use` on `standpoint-gui`.** Port 8000 is popular. Set
`STANDPOINT_PORT=8001`, or run `uvicorn standpoint.api:app --port 8001` yourself.
