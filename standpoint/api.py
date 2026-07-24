"""FastAPI backend for the Standpoint browser GUI (investigation, `dev-gui` branch).

This is the thin server behind the single-page GUI: it turns an edited table into a
positioning result the browser can render. The heavy lifting stays in the library —
`positioning()` runs the PCA, orientation, colouring, LLM pole naming, and analysis;
this module only exposes it over HTTP and serves the static page.

Endpoints
---------
GET  /             redirect to the GUI.
GET  /gui          the single-page editor + viewer (see `webgui.GUI_HTML`).
GET  /api/example  a starter table (CSV text) to populate the grid.
POST /api/position from an edited table, return the Vega-Lite spec + Markdown + YAML.

Run it with ``standpoint-gui`` (installed by the ``gui`` extra) or
``uvicorn standpoint.api:app``. It is intentionally *not* imported by the core
package, so the library and CLIs carry no web dependency.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from pydantic import BaseModel

from standpoint import DEFAULT_MODEL, analysis_markdown, parse_table, positioning
from standpoint.webgui import GUI_HTML

# Excel MIME type for the .xlsx download response.
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

app = FastAPI(title="Standpoint GUI", version="0.1.0")

# The grid is seeded from the tracked example so the GUI always mirrors it; this
# small built-in table is the fallback when the file isn't on disk (installed package).
_EXAMPLE_CSV = Path(__file__).resolve().parents[1] / "examples" / "programming_languages.csv"
_STARTER_TABLE = (
    "Programming Language,Performance,Ease of Learning,Ecosystem,Concurrency,Type Safety,Job Market,Tooling\n"
    "Python,2,5,5,2,2,5,4\n"
    "Rust,5,2,3,5,5,3,4\n"
    "Go,4,4,4,5,4,4,4\n"
    "JavaScript,3,4,5,3,2,5,3\n"
    "Java,4,3,5,4,4,5,4\n"
)


class PositionRequest(BaseModel):
    """Body of ``POST /api/position`` — one edited table plus a few options.

    Attributes
    ----------
    table : str
        The edited comparison table as CSV text (first column = option names).
    reference : str
        Row index (as a string) or exact option name to place top-right.
    lower : str
        Comma-separated criteria where lower is better (e.g. ``"Price,Weight"``).
    model : str
        Ollama model used to name the axes and write the analysis.
    """

    table: str
    reference: str = "0"
    lower: str = ""
    model: str = DEFAULT_MODEL


class PositionResponse(BaseModel):
    """What the browser needs to draw the quadrant and show the write-up."""

    vega: dict
    markdown: str
    yaml: str
    axes: dict[str, str]
    poles: list[str]
    reference: str
    roles: dict[str, str]


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    """Redirect the site root to the GUI page."""
    return RedirectResponse(url="/gui")


@app.get("/gui", response_class=HTMLResponse, include_in_schema=False)
def gui() -> str:
    """Serve the single-page table editor + quadrant viewer."""
    return GUI_HTML


@app.get("/api/example", response_class=PlainTextResponse)
def example() -> str:
    """Return a starter table (CSV text) to populate an empty grid.

    Prefer the tracked `examples/programming_languages.csv` so the GUI stays in sync
    with it; fall back to the small built-in table when the file isn't present.
    """
    try:
        return _EXAMPLE_CSV.read_text(encoding="utf-8")
    except OSError:
        return _STARTER_TABLE


def _df_to_csv(df: pd.DataFrame) -> str:
    """Serialize a parsed table back to clean CSV for the grid (ints stay ints)."""
    # `%g` drops the ".0" that read_excel / parse_table introduce, and blanks stay
    # blank, so the grid shows "2" and "" rather than "2.0" and "nan".
    return df.to_csv(float_format="%g")


@app.post("/api/upload", response_class=PlainTextResponse)
async def upload(file: UploadFile = File(...)) -> str:
    """Load an uploaded **CSV or XLSX** table and return it as CSV for the grid.

    Parameters
    ----------
    file : UploadFile
        The uploaded file; ``.xlsx`` / ``.xls`` are read with pandas (openpyxl),
        anything else is treated as CSV or Markdown via `parse_table`.

    Returns
    -------
    str
        The table as CSV text, ready to populate the editor grid.

    Raises
    ------
    HTTPException
        400 if the file can't be read as a table.
    """
    content = await file.read()
    name = (file.filename or "").lower()
    try:
        if name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content), index_col=0)
        else:
            df = parse_table(content.decode("utf-8", errors="replace"))
    except Exception as exc:  # unreadable spreadsheet / not a table
        raise HTTPException(status_code=400, detail=f"Could not read the file: {exc}") from exc
    return _df_to_csv(df)


class TableText(BaseModel):
    """A table as CSV text — the body of the XLSX download request."""

    table: str


@app.post("/api/download/xlsx")
def download_xlsx(req: TableText) -> Response:
    """Convert the edited table (CSV text) to an ``.xlsx`` file for download.

    Parameters
    ----------
    req : TableText
        The current grid serialized to CSV.

    Returns
    -------
    Response
        The workbook bytes with an ``attachment`` disposition so the browser saves
        ``standpoint.xlsx``.

    Raises
    ------
    HTTPException
        400 if the CSV can't be parsed into a table.
    """
    try:
        df = parse_table(req.table)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse the table: {exc}") from exc
    buf = io.BytesIO()
    df.to_excel(buf)  # index = option names; openpyxl writes the .xlsx
    return Response(
        content=buf.getvalue(),
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": "attachment; filename=standpoint.xlsx"},
    )


@app.post("/api/position", response_model=PositionResponse)
def position(req: PositionRequest) -> PositionResponse:
    """Run the full positioning on an edited table and return everything to draw it.

    Parameters
    ----------
    req : PositionRequest
        The edited table and options from the browser.

    Returns
    -------
    PositionResponse
        The Vega-Lite spec (rendered client-side by vega-embed), the Markdown
        interpretation, the YAML dump, and the axis names / poles / roles.

    Raises
    ------
    HTTPException
        400 if the table is empty or degenerate, or the reference is unknown —
        the library's ``ValueError`` message is passed straight through to the UI.
    """
    if not req.table.strip():
        raise HTTPException(status_code=400, detail="The table is empty.")
    # A numeric reference arrives as a string ("0"); pass ints through as ints so
    # `positioning` treats it as a row index rather than an option name.
    ref: int | str = int(req.reference) if req.reference.lstrip("-").isdigit() else req.reference
    lower = [c.strip() for c in req.lower.split(",") if c.strip()]
    try:
        pos = positioning(
            req.table,
            reference=ref,
            lower_is_better=lower,
            model=req.model,
        )
    except ValueError as exc:  # bad table / unknown reference -> a clean 400 for the UI
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # The Markdown narrative is a separate call so a slow model doesn't block the
    # spec; here we compute it inline since the whole request is already synchronous.
    markdown = analysis_markdown(pos.result, pos.roles, pos.poles, model=req.model)
    return PositionResponse(
        vega=pos.to_vega(),
        markdown=markdown,
        yaml=pos.to_yaml(),
        axes=pos.axes,
        poles=pos.poles,
        reference=pos.result.reference,
        roles=pos.role_of,
    )


def main_gui() -> None:
    """Console entry point (``standpoint-gui``): serve the GUI on localhost:8000."""
    import uvicorn

    # Local-first: bind to loopback only, so the table never leaves the machine.
    print("Standpoint GUI -> http://localhost:8000/gui  (Ctrl-C to stop)")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main_gui()
