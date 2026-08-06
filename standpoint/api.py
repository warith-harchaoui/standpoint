"""FastAPI backend for the Standpoint browser GUI.

This is the thin server behind the single-page GUI: it turns an edited table into a
positioning result the browser can render. The heavy lifting stays in the library:
`positioning()` runs the PCA, orientation, colouring, LLM pole naming, and analysis;
this module only exposes it over HTTP and serves the static page.

Endpoints
---------
GET  /             redirect to the GUI.
GET  /gui          the single-page editor + viewer (see `webgui.GUI_HTML`).
GET  /api/example  a starter table (CSV text) to populate the grid.
POST /api/position from an edited table, return the SVG + Markdown + YAML.

Run it with ``standpoint-gui`` (installed by the ``gui`` extra) or
``uvicorn standpoint.api:app``. It is intentionally *not* imported by the core
package, so the library and CLIs carry no web dependency.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from standpoint import (
    SUPPORTED_LANGS,
    __version__,
    analysis_markdown,
    i18n,
    parse_table,
    positioning,
    suggest_ratings,
)
from standpoint.webgui import GUI_HTML

# Excel MIME type for the .xlsx download response.
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Keep the OpenAPI version in step with the package (single source of truth).
app = FastAPI(title="Standpoint GUI", version=__version__)

# Static assets (the app icon set + web manifest) live next to this module so they
# ship as package data and resolve identically whether run from the repo or an
# installed wheel. Mounting them lets the page reference stable `/static/...` URLs.
_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    """Serve the multi-size favicon browsers request from the site root by default."""
    return FileResponse(_STATIC_DIR / "favicon.ico", media_type="image/x-icon")


@app.get("/site.webmanifest", include_in_schema=False)
def webmanifest() -> FileResponse:
    """Serve the PWA manifest (name, theme colours, install icons)."""
    return FileResponse(_STATIC_DIR / "site.webmanifest", media_type="application/manifest+json")


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
    """Body of ``POST /api/position``: one edited table plus a few options.

    Attributes
    ----------
    table : str
        The edited comparison table as CSV text (first column = option names).
    reference : str
        Row index (as a string) or exact option name to place top-right.
    lower : str
        Comma-separated criteria where lower is better (e.g. ``"Price,Weight"``).
    model : str
        Force a specific local model tag; ``""`` uses the one resolved in the engine.
    """

    table: str
    reference: str = "0"
    lower: str = ""
    model: str = ""  # "" = the model resolved in llm.engine.yaml; a tag forces an override
    lang: str = ""  # "" = detect from the table; "en"/"fr"/"es" force the output language


class PositionResponse(BaseModel):
    """What the browser needs to draw the quadrant and show the write-up."""

    svg: str
    markdown: str
    yaml: str
    axes: dict[str, str]
    poles: list[str]
    reference: str
    roles: dict[str, str]
    slug: str  # filename stem for exports, from the table's plural noun (e.g. "programming-languages")


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
    """A table as CSV text: the body of the XLSX download request."""

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


def _slugify(text: str) -> str:
    """Turn a display name into a filename stem: lowercase, words joined by hyphens.

    Used to name exports after the table's subject, so the "Programming Language"
    example downloads as ``programming-languages.png`` rather than a generic stem.
    """
    import re
    import unicodedata

    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "standpoint"


def _model_error(exc: Exception, model: str) -> HTTPException:
    """Map a local-model failure to a clean 503 with an actionable hint.

    The library talks to the local backend through best-engine-ai-helper, which
    raises ``RuntimeError`` when the server is unreachable or the model errors; a
    first run otherwise surfaces as an opaque 500. Here it becomes a message the UI
    can show verbatim, naming the offending model tag when one was forced.
    """
    tag = f" '{model}'" if model else ""
    return HTTPException(
        status_code=503,
        detail=(
            f"The local model{tag} is unavailable ({exc}). Start your local LLM "
            "backend (e.g. `ollama serve`) and make sure the model resolved in "
            "standpoint/llm.engine.yaml is installed; regenerate the engine with "
            "`best-engine-ai-helper resolve` if the machine changed."
        ),
    )


@app.get("/api/i18n")
def i18n_strings(lang: str = "en") -> dict:
    """Return the GUI's localized strings for `lang` (falls back to English).

    The single-page app fetches this to render every label, button, and message in
    the language chosen by the header toggle, so the UI text lives in `i18n.yaml`
    next to the LLM prompts rather than being hard-coded in the HTML.
    """
    strings = i18n(lang).get("gui") or i18n("en")["gui"]
    return {"lang": lang if lang in SUPPORTED_LANGS else "en", "strings": strings}


class AutofillRequest(BaseModel):
    """Body of ``POST /api/autofill``: the names to score, plus model and language.

    Attributes
    ----------
    noun : str
        The first-column word (what a row is, e.g. "Programming Language").
    options : list[str]
        Option (row) names to rate.
    criteria : list[str]
        Criterion (column) names to rate each option on.
    model : str
        Force a specific local model tag; ``""`` uses the one resolved in the engine.
    lang : str
        Force the prompt language; "" detects it from the names.
    """

    noun: str = "Option"
    options: list[str]
    criteria: list[str]
    model: str = ""
    lang: str = ""


@app.post("/api/autofill")
def autofill(req: AutofillRequest) -> dict:
    """ "Flemme" (lazy) auto-fill: score every option on every criterion via the model.

    The user typed only the row and column names (common for a freshly uploaded CSV
    that carries headers but no values); this asks the local model to fill the whole
    ratings matrix from its own knowledge, offline.

    Returns
    -------
    dict
        ``{"ratings": {option: {criterion: int}}}`` for the front-end to load into
        the grid.

    Raises
    ------
    HTTPException
        400 if no option / criterion was named; 503 if the model is unavailable.
    """
    lang = req.lang if req.lang in SUPPORTED_LANGS else None
    try:
        ratings = suggest_ratings(
            req.noun, req.options, req.criteria, model=req.model or None, lang=lang
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ConnectionError, RuntimeError) as exc:
        raise _model_error(exc, req.model) from exc
    return {"ratings": ratings}


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
        The self-contained, interactive SVG (dropped straight into the page), the
        Markdown interpretation, the YAML dump, and the axis names / poles / roles.

    Raises
    ------
    HTTPException
        400 if the table is empty or degenerate, or the reference is unknown;
        the library's ``ValueError`` message is passed straight through to the UI.
    """
    if not req.table.strip():
        raise HTTPException(status_code=400, detail="The table is empty.")
    # A numeric reference arrives as a string ("0"); pass ints through as ints so
    # `positioning` treats it as a row index rather than an option name.
    ref: int | str = int(req.reference) if req.reference.lstrip("-").isdigit() else req.reference
    lower = [c.strip() for c in req.lower.split(",") if c.strip()]
    # "" means detect from the table; a toggle value forces the whole deliverable
    # (poles, title, narrative) into that language.
    lang = req.lang if req.lang in SUPPORTED_LANGS else None
    try:
        pos = positioning(
            req.table,
            reference=ref,
            lower_is_better=lower,
            model=req.model or None,
            lang=lang,
        )
        # The Markdown narrative is a separate call so a slow model doesn't block the
        # spec; here we compute it inline since the whole request is already synchronous.
        markdown = analysis_markdown(
            pos.result, pos.roles, pos.poles, model=req.model or None, lang=lang
        )
    except ValueError as exc:  # bad table / unknown reference -> a clean 400 for the UI
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ConnectionError, RuntimeError) as exc:  # model unavailable -> actionable 503
        raise _model_error(exc, req.model) from exc
    # One payload with everything the page draws from: the SVG for the chart, the
    # Markdown write-up, the YAML dump for download, and the axis names / poles /
    # per-option roles the front-end uses to colour the analysis. Bundling them
    # means the browser draws the whole result from a single round-trip.
    return PositionResponse(
        svg=pos.to_svg(),  # dropped straight into the page's #chart div
        markdown=markdown,  # the written interpretation
        yaml=pos.to_yaml(),  # coordinates + coefficients, offered as a download
        axes=pos.axes,  # {'x': ..., 'y': ...} axis titles
        poles=pos.poles,  # the four pole labels
        reference=pos.result.reference,  # resolved name of the top-right anchor
        roles=pos.role_of,  # option -> role, drives the name tinting
        slug=_slugify(pos.noun_plural),  # export filename stem from the table's plural noun
    )


def main_gui() -> None:
    """Console entry point (``standpoint-gui``): serve the GUI on localhost:8000."""
    import uvicorn

    # Local-first: bind to loopback only, so the table never leaves the machine.
    print("Standpoint GUI -> http://localhost:8000/gui  (Ctrl-C to stop)")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main_gui()
