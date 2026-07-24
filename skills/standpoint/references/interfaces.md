# Interfaces — the same engine, six ways

All six surfaces run the same `positioning()` pipeline. Pick by who is calling.

## Library

```python
import standpoint as sp

pos = sp.positioning("table.csv", reference=0, lower_is_better=["Price"], use_llm=True)
pos.coords        # DataFrame: axis-1 / axis-2 per option
pos.loadings      # DataFrame: criterion weights per axis
pos.axes          # {'x': 'Cost ↔ Scalability', 'y': 'Simplicity ↔ Power'}
pos.role_of       # {'AWS': 'best', 'DigitalOcean': 'worst', 'Azure': 'top', ...}
pos.to_vega()     # a Vega-Lite spec (dict)
pos.to_markdown() # the written analysis
pos.to_yaml()     # coordinates + coefficients
pos.export("out") # writes every file (see input-and-output.md)
```

`positioning(data, ...)` accepts a path, a raw CSV/Markdown string, or a pandas
DataFrame. Lower-level building blocks are exported too: `parse_table`, `analyze`
(→ `PCAResult`), `assign_roles`, `axis_poles`, `gradient_colors`, `to_vega`,
`analysis_markdown`, `results_yaml`, `render_figures`, `export_all`.

## CLI (two twins, identical flags)

```bash
standpoint table.csv --outdir out            # argparse CLI (always installed)
standpoint-click table.csv --outdir out      # click twin ([gui] extra not required)

standpoint table.csv --no-llm                # skip the model (instant, deterministic)
standpoint table.csv --reference "AWS"       # option placed top-right
standpoint table.csv --lower Price,Latency   # lower-is-better criteria
standpoint table.csv --model qwen3:8b        # a different Ollama model
standpoint table.csv --check                 # ask a vision model to sanity-check the figure
standpoint table.csv --top Azure --right IBM # force the two challenger highlights
```

`python -m standpoint table.csv` works without installing a console script.

## GUI

```bash
pip install "standpoint[gui]"
standpoint-gui                     # → http://localhost:8000/gui
```

Edit a table in the browser (add/remove rows & columns, per-column ⬇️/⬆️ polarity,
reference picker), upload/download CSV or XLSX, generate the quadrant live, export it
PNG/SVG, and read the colour-coded analysis.

## HTTP API

The GUI's backend is a FastAPI app; the useful endpoint for programs is:

```
POST /api/position
  { "table": "<csv text>", "reference": "0", "lower": "Price", "use_llm": false }
→ { "vega": {...}, "markdown": "...", "yaml": "...", "axes": {...},
    "poles": [...], "reference": "...", "roles": {...} }
```

Also `GET /api/example`, `POST /api/upload` (CSV/XLSX file), `POST /api/download/xlsx`.

## MCP

```bash
pip install "standpoint[mcp]"
standpoint-mcp                     # serves the API + an MCP endpoint at /mcp
```

`fastapi-mcp` publishes the same endpoints as MCP tools, so an MCP-aware host can call
`position` (table → map + analysis) as a first-class tool.

## Docker

```bash
docker build -t standpoint .
docker run --rm -p 8000:8000 standpoint          # API + MCP (GUI at /gui, MCP at /mcp)
# LLM naming needs a reachable Ollama:
docker run --rm -p 8000:8000 -e OLLAMA_HOST=http://host.docker.internal:11434 standpoint
```

## Conda (local, for the library)

```bash
conda env create -f environment.yaml     # thin: python + pip + -r requirements.txt
conda activate env-for-standpoint
pip install -e .
```
