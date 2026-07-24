# When to use standpoint (TRIGGERS)

`standpoint` turns one comparison table — options in rows, criteria in columns, numbers
in the cells — into a labelled 2D **positioning map** (a quadrant / perceptual /
competitive-landscape map), a short written analysis, and a YAML of every coordinate.
This page is the exhaustive list of what should, and should not, reach for it — for a
human skimming, and for an agent deciding whether to invoke the
[skill](skills/standpoint/SKILL.md).

## Use it when

**The user wants to position options against each other.**
- "Plot these tools / products / vendors / frameworks / languages / cars / models on a
  map." · "Where does *X* stand versus the others?" · "Map the competitive landscape."
- "Make a positioning map / perceptual map / quadrant / 2×2 / competitive map / magic-
  quadrant-style chart from this."
- "Compare these options across these criteria and chart the result."

**The user already has (or is describing) an options × criteria table.**
- A CSV or Markdown table whose first column is names and the rest are numeric ratings.
- A scorecard / rating grid / feature-comparison matrix they want turned into a picture.
- "Reduce these criteria to two readable axes." · "PCA / perceptual map of this ratings
  table." (the *labelled* map, not feature engineering — see below).

**The user names the tool or its symbols.**
- Commands: `standpoint`, `standpoint-click`, `standpoint-gui`, `standpoint-mcp`,
  `python -m standpoint`.
- Library: `positioning`, `analyze`, `axis_poles`, `assign_roles`, `gradient_colors`,
  `to_vega`, `export_all`, `parse_table`, the `Positioning` / `PCAResult` objects.
- Install / run: "install standpoint", "run the standpoint GUI / API / MCP server".

**The user wants a specific standpoint feature.**
- Axis names in plain words, in the table's own language (English / French / Spanish).
- A reference option placed top-right; lower-is-better columns (`Price (↓)`, `--lower`).
- Export to PNG / SVG / Vega-Lite JSON / Markdown / YAML, transparent or white.

## Skip it when

- **Ordinary plotting of one or two variables** — a bar / line / scatter / pie of a
  series or a time axis. That is plain charting, not a positioning map; reach for a
  figures / Vega skill instead.
- **PCA for dimensionality reduction inside an ML pipeline** — use scikit-learn
  directly. standpoint is for the *labelled competitive map*, not feature engineering
  or model input.
- **A single-criterion ranking** — if the answer is "sort by one column", no 2D map is
  needed.
- **Building, cleaning, or gathering the table** — standpoint maps a table that already
  exists; it does not collect the data, scrape it, or fit a predictor.

## Interfaces (same engine, six ways)

| Reach for | When |
|---|---|
| **Library** `import standpoint as sp` | inside Python, or to get the `Positioning` object |
| **CLI** `standpoint` / `standpoint-click` | one-shot from a file, or scripting |
| **GUI** `standpoint-gui` (`/gui`) | a human editing tables interactively in the browser |
| **HTTP API** `POST /api/position` | another program calling over HTTP |
| **MCP** `standpoint-mcp` (`/mcp`) | an MCP-aware agent/host calling `position` as a tool |
| **Docker** `docker run … standpoint` | serving the API + MCP in a container |

See the [README](README.md) for install and usage, and the
[skill](skills/standpoint/SKILL.md) for the agent-facing instructions.
