"""Smoke tests for the browser GUI backend (`dev-gui` investigation).

These run only when the ``gui`` extra (FastAPI + a test client) is installed, so the
default suite is unaffected. They exercise the endpoints end to end; the positive-path
round-trips call the real local model, which `tests/conftest.py` guarantees is
present, mirroring how the core library is tested.

Grouped as functional scenarios rather than one test per assertion: several checks
against the same request (e.g. one `GET /gui` fetch, one `/api/position` round-trip)
share that single call instead of re-fetching for each fact being verified.
"""

from __future__ import annotations

import pytest

# The GUI backend is optional; skip the whole module without the `gui` extra.
pytest.importorskip("fastapi")
starlette_testclient = pytest.importorskip("starlette.testclient")

from standpoint.api import app  # noqa: E402  (after importorskip by design)

client = starlette_testclient.TestClient(app)


def test_gui_page_served_and_wired() -> None:
    """`GET /gui` returns the single-page app, correctly wired end to end.

    One fetch, several regression checks against it: the page loads with no
    leftover chart-rendering runtime, the transparency checker carries its own
    light background (else dark mode swallows near-black labels behind it -- see
    `.dark .bg-white`), a freshly added row/column cell starts genuinely blank (so
    Autofill and the server's own min-impute both still treat it as missing), and
    the favicon/apple-touch-icon/manifest/header logo are all linked.
    """
    html = client.get("/gui").text
    assert "Standpoint" in html and 'id="chart"' in html
    assert "vega" not in html.lower()  # no chart-rendering runtime left to load
    assert "#chart.checker { background-color:#fff;" in html
    assert 'values: headers.map(() => "")' in html  # addRow
    assert 'r.values.push("")' in html  # addCol
    assert 'rel="manifest"' in html
    assert 'rel="apple-touch-icon"' in html
    assert "/static/logo-header.png" in html  # the header brand mark


def test_root_redirects_to_gui() -> None:
    """`GET /` redirects to the GUI page."""
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"].endswith("/gui")


def test_example_endpoint_returns_csv() -> None:
    """`GET /api/example` returns a non-empty CSV starter table."""
    r = client.get("/api/example")
    assert r.status_code == 200
    header = r.text.splitlines()[0]
    assert "," in header and "Performance" in header  # a real criteria table


@pytest.mark.needs_model
def test_position_roundtrip_has_full_frontend_contract() -> None:
    """`POST /api/position` returns everything the browser needs to draw and colorize."""
    table = "Language,Speed,Safety,Jobs\nPython,2,3,5\nRust,5,4,3\nGo,4,3,4\nJava,4,5,5"
    r = client.post("/api/position", json={"table": table, "reference": "0"})
    assert r.status_code == 200
    data = r.json()
    assert {"svg", "markdown", "yaml", "axes", "poles", "reference", "roles"} <= set(data)
    assert data["reference"] == "Python"
    assert data["roles"]["Python"] == "best"
    assert set(data["axes"]) == {"x", "y"}
    assert len(data["poles"]) == 4
    # the four highlighted roles the analysis colorizer tints by name
    assert {"best", "worst", "top", "right"} <= set(data["roles"].values())
    assert data["svg"].startswith("<svg")  # a real SVG the browser drops straight in
    assert "<rect" not in data["svg"]  # ships transparent; the UI paints white per toggle
    assert data["markdown"].startswith("# Python")
    assert "Leaderboard" not in data["markdown"]
    assert "meta:" in data["yaml"]


def test_position_rejects_bad_tables() -> None:
    """A table too small or blank yields a clean 400, not a 500, either way."""
    r = client.post("/api/position", json={"table": "A,B\nonly,1"})  # too few options
    assert r.status_code == 400
    assert "detail" in r.json()
    r = client.post("/api/position", json={"table": "   "})  # blank
    assert r.status_code == 400


def test_upload_normalizes_csv_and_xlsx_to_grid() -> None:
    """`POST /api/upload` accepts a CSV or an `.xlsx` file and returns clean CSV."""
    csv = b"Language,Speed,Safety\nPython,2,2\nRust,5,5\n"
    r = client.post("/api/upload", files={"file": ("table.csv", csv, "text/csv")})
    assert r.status_code == 200
    assert r.text.splitlines()[0] == "Language,Speed,Safety"
    assert "Python,2,2" in r.text  # ints stay ints (no "2.0")

    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    import io

    buf = io.BytesIO()
    df = pd.DataFrame({"Speed": [2, 5], "Safety": [2, 5]}, index=["Python", "Rust"])
    df.index.name = "Language"
    df.to_excel(buf)
    r = client.post(
        "/api/upload",
        files={"file": ("table.xlsx", buf.getvalue(), "application/vnd.ms-excel")},
    )
    assert r.status_code == 200
    assert r.text.splitlines()[0] == "Language,Speed,Safety"


def test_download_xlsx_returns_workbook() -> None:
    """`POST /api/download/xlsx` turns the CSV grid into a real .xlsx download."""
    pytest.importorskip("openpyxl")
    r = client.post(
        "/api/download/xlsx",
        json={"table": "Language,Speed,Safety\nPython,2,2\nRust,5,5"},
    )
    assert r.status_code == 200
    assert r.content[:4] == b"PK\x03\x04"  # xlsx is a zip
    assert "attachment" in r.headers.get("content-disposition", "")


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/favicon.ico", "image/x-icon"),
        ("/site.webmanifest", "application/manifest+json"),
        ("/static/apple-touch-icon.png", "image/png"),
        ("/static/android-chrome-192.png", "image/png"),
        ("/static/logo-header.png", "image/png"),
    ],
)
def test_app_icons_served(path: str, content_type: str) -> None:
    """The icon set generated from the logo is served for browsers and installers."""
    r = client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(content_type)


def test_position_reports_ollama_down_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """The local backend not running yields an actionable 503, not a raw 500."""

    def boom(*_a: object, **_k: object) -> None:
        raise ConnectionError("Failed to connect to the local backend.")

    monkeypatch.setattr("standpoint.api.positioning", boom)
    r = client.post("/api/position", json={"table": "L,A,B\nx,1,2\ny,2,1"})
    assert r.status_code == 503
    assert "ollama serve" in r.json()["detail"].lower()


def test_position_reports_missing_model_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model that isn't installed yields a 503 that names the offending tag.

    best-engine-ai-helper surfaces backend/model failures as ``RuntimeError``; the API
    maps it to an actionable 503 that echoes the forced model tag.
    """

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("model 'ghost:1b' not found")

    monkeypatch.setattr("standpoint.api.positioning", boom)
    r = client.post(
        "/api/position",
        json={"table": "L,A,B\nx,1,2\ny,2,1", "model": "ghost:1b"},
    )
    assert r.status_code == 503
    assert "ghost:1b" in r.json()["detail"]


def test_i18n_endpoint_localizes_gui() -> None:
    """`GET /api/i18n` returns the GUI strings for the requested language."""
    fr = client.get("/api/i18n", params={"lang": "fr"}).json()
    assert fr["lang"] == "fr"
    assert fr["strings"]["generate"] == "Générer le quadrant"
    assert "Paresse" in fr["strings"]["flemme"]
    # An unsupported language falls back to English rather than erroring.
    xx = client.get("/api/i18n", params={"lang": "xx"}).json()
    assert xx["lang"] == "en"
    assert xx["strings"]["generate"] == "Generate quadrant"


def test_autofill_requires_names() -> None:
    """`POST /api/autofill` rejects a call with no options / criteria (400, no model)."""
    r = client.post("/api/autofill", json={"options": [], "criteria": []})
    assert r.status_code == 400
    assert "detail" in r.json()


def test_autofill_reports_model_down_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """The local backend unreachable during auto-fill yields an actionable 503, not a 500."""

    def boom(*_a: object, **_k: object) -> None:
        raise ConnectionError("Failed to connect to the local backend.")

    monkeypatch.setattr("standpoint.api.suggest_ratings", boom)
    r = client.post("/api/autofill", json={"options": ["A", "B"], "criteria": ["X"]})
    assert r.status_code == 503
    assert "ollama serve" in r.json()["detail"].lower()


@pytest.mark.needs_model
def test_autofill_roundtrip_fills_matrix() -> None:
    """`POST /api/autofill` returns a full option×criterion matrix of 1..5 integers."""
    r = client.post(
        "/api/autofill",
        json={
            "noun": "Programming Language",
            "options": ["Python", "Rust"],
            "criteria": ["Performance", "Ease of Learning"],
            "lang": "en",
        },
    )
    assert r.status_code == 200
    ratings = r.json()["ratings"]
    assert set(ratings) == {"Python", "Rust"}
    for row in ratings.values():
        assert set(row) == {"Performance", "Ease of Learning"}
        assert all(isinstance(v, int) and 1 <= v <= 5 for v in row.values())


@pytest.mark.needs_model
def test_position_language_and_slug() -> None:
    """A forced language localizes the whole report, slug included."""
    table = "Programming Language,Performance,Ease of Learning\nPython,2,5\nRust,5,2\nGo,4,4"
    data = client.post("/api/position", json={"table": table, "lang": "fr"}).json()
    # The slug is the plural noun, slugified, translated to French like the rest of
    # the deliverable (noun_forms() translates a forced cross-language override; see
    # standpoint/__init__.py). "programming-languages" here would mean the noun stayed
    # English while the rest of the report went French -- the bug this guards against.
    assert data["slug"] == "langages-de-programmation"
    assert "## Interprétation" in data["markdown"]  # analysis headings follow the language
    assert "Approches mises en avant" in data["markdown"]
