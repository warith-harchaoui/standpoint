# standpoint skill — exhaustive trigger catalogue

Auditable superset of the phrasings that should fire this skill. The
`description:` in `SKILL.md` is what a host model actually sees and is capped at
1024 characters; this file carries the full list. Keep the two in sync — and
keep this file in sync with the repo-root `TRIGGERS.md`, the user-facing
catalogue it mirrors.

`standpoint` turns one comparison table (options in rows, criteria in columns,
numbers in the cells) into a labelled 2D **positioning map** (a quadrant /
perceptual / competitive-landscape map) and a YAML of every coordinate.

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
  table." (the *labelled* map, not feature engineering; see below).

**The user names the tool or its symbols.**
- Commands: `standpoint`, `standpoint-gui`, `standpoint-mcp`,
  `python -m standpoint`.
- Library: `positioning`, `analyze`, `axis_poles`, `assign_roles`, `gradient_colors`,
  `to_svg`, `export_all`, `parse_table`, the `Positioning` / `PCAResult` objects.
- Install / run: "install standpoint", "run the standpoint GUI / API / MCP server".

**The user wants a specific standpoint feature.**
- Axis names in plain words, in the table's own language (English / French / Spanish).
- A reference option placed top-right; lower-is-better columns (`Price (↓)`, `--lower`).
- Export to PNG / interactive SVG / Markdown / YAML, transparent or white, no Vega.

## Skip it when

- **Ordinary plotting of one or two variables**: a bar / line / scatter / pie of a
  series or a time axis. That is plain charting, not a positioning map; reach for a
  figures skill instead.
- **PCA for dimensionality reduction inside an ML pipeline**: use scikit-learn
  directly. standpoint is for the *labelled competitive map*, not feature engineering
  or model input.
- **A single-criterion ranking**: if the answer is "sort by one column", no 2D map is
  needed.
- **Building, cleaning, or gathering the table**: standpoint maps a table that already
  exists; it does not collect the data, scrape it, or fit a predictor.

## One engine, six access surfaces

| Reach for | When |
|---|---|
| **Library** `import standpoint as sp` | inside Python, or to get the `Positioning` object |
| **CLI** `standpoint` | one-shot from a file, or scripting |
| **GUI** `standpoint-gui` (`/gui`) | a human editing tables interactively in the browser |
| **HTTP API** `POST /api/position` | another program calling over HTTP |
| **MCP** `standpoint-mcp` (`/mcp`) | an MCP-aware agent/host calling `position` as a tool |
| **Skill** `skills/standpoint/` | a Claude / OpenCode agent driving the tool from a chat |

Any of the server surfaces also runs in a container: `docker run … standpoint`
serves the API with the MCP endpoint mounted.

See the repo's `README.md` for install and usage, `references/interfaces.md`
for the surfaces in detail, and `references/input-and-output.md` for the table
and export contracts.
