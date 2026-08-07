"""Smoke tests for the browser GUI backend (`dev-gui` investigation).

These run only when the ``gui`` extra (FastAPI + a test client) is installed, so the
default suite is unaffected. They exercise the three endpoints end to end; the
positive-path round-trips call the real local model, which `tests/conftest.py`
guarantees is present, mirroring how the core library is tested.
"""

from __future__ import annotations

import pytest

# The GUI backend is optional; skip the whole module without the `gui` extra.
pytest.importorskip("fastapi")
starlette_testclient = pytest.importorskip("starlette.testclient")

from standpoint.api import app  # noqa: E402  (after importorskip by design)

client = starlette_testclient.TestClient(app)


def test_gui_page_served() -> None:
    """`GET /gui` returns the single-page HTML app."""
    r = client.get("/gui")
    assert r.status_code == 200
    assert "Standpoint" in r.text and 'id="chart"' in r.text
    assert "vega" not in r.text.lower()  # no chart-rendering runtime left to load


def test_checker_background_stays_light_in_dark_mode() -> None:
    """The transparency checkerboard must carry its own light background-color.

    Without one, its gradient's "transparent" stops fall through to whatever is
    behind #chart -- the card, which dark mode recolors to near-black via
    `.dark .bg-white` -- turning half the squares near-black and swallowing the
    map's own near-black labels.
    """
    css = client.get("/gui").text
    assert "#chart.checker { background-color:#fff;" in css


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
def test_position_roundtrip() -> None:
    """`POST /api/position` returns a full, drawable result on a valid table."""
    table = "Language,Speed,Safety,Jobs\nPython,2,3,5\nRust,5,4,3\nGo,4,3,4\nJava,4,5,5"
    r = client.post("/api/position", json={"table": table, "reference": "0"})
    assert r.status_code == 200
    data = r.json()
    assert data["reference"] == "Python"
    assert data["roles"]["Python"] == "best"
    assert data["svg"].startswith("<svg")  # a real SVG the browser drops straight in
    assert data["markdown"].startswith("# Python")
    assert "meta:" in data["yaml"]


@pytest.mark.needs_model
def test_position_response_has_full_frontend_contract() -> None:
    """The response carries everything the browser needs to draw and colorize."""
    table = "Language,Speed,Safety,Jobs\nPython,2,3,5\nRust,5,4,3\nGo,4,3,4\nJava,4,5,5"
    data = client.post("/api/position", json={"table": table}).json()
    assert {"svg", "markdown", "yaml", "axes", "poles", "reference", "roles"} <= set(data)
    assert set(data["axes"]) == {"x", "y"}
    assert len(data["poles"]) == 4
    # the four highlighted roles the analysis colorizer tints by name
    assert {"best", "worst", "top", "right"} <= set(data["roles"].values())
    # the SVG ships transparent; the UI paints a white rect per the toggle
    assert "<rect" not in data["svg"]
    assert "Leaderboard" not in data["markdown"]


def test_position_rejects_degenerate_table() -> None:
    """A table with too few options yields a clean 400, not a 500."""
    r = client.post("/api/position", json={"table": "A,B\nonly,1"})
    assert r.status_code == 400
    assert "detail" in r.json()


def test_position_rejects_empty_table() -> None:
    """An empty table body is rejected with 400."""
    r = client.post("/api/position", json={"table": "   "})
    assert r.status_code == 400


def test_upload_csv_normalizes_to_grid() -> None:
    """`POST /api/upload` accepts a CSV file and returns clean CSV for the grid."""
    csv = b"Language,Speed,Safety\nPython,2,2\nRust,5,5\n"
    r = client.post("/api/upload", files={"file": ("table.csv", csv, "text/csv")})
    assert r.status_code == 200
    assert r.text.splitlines()[0] == "Language,Speed,Safety"
    assert "Python,2,2" in r.text  # ints stay ints (no "2.0")


def test_upload_xlsx_roundtrips() -> None:
    """An uploaded `.xlsx` is read (via pandas/openpyxl) back into CSV."""
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


def test_gui_head_links_icons_and_manifest() -> None:
    """The page advertises the favicon, apple-touch icon, and web manifest."""
    html = client.get("/gui").text
    assert 'rel="manifest"' in html
    assert 'rel="apple-touch-icon"' in html
    assert "/static/logo-header.png" in html  # the header brand mark


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
    """A forced language localizes the whole report; the slug is the plural stem."""
    table = "Programming Language,Performance,Ease of Learning\nPython,2,5\nRust,5,2\nGo,4,4"
    data = client.post("/api/position", json={"table": table, "lang": "fr"}).json()
    assert data["slug"] == "programming-languages"  # plural noun, slugified
    assert "## Interprétation" in data["markdown"]  # analysis headings follow the language
    assert "Approches mises en avant" in data["markdown"]
