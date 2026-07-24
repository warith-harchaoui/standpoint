"""Smoke tests for the browser GUI backend (`dev-gui` investigation).

These run only when the ``gui`` extra (FastAPI + a test client) is installed, so the
default suite is unaffected. They exercise the three endpoints end to end with the
deterministic (no-model) path, mirroring how the core library is tested.
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
    assert "Standpoint" in r.text and "vega-embed" in r.text


def test_root_redirects_to_gui() -> None:
    """`GET /` redirects to the GUI page."""
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"].endswith("/gui")


def test_example_endpoint_returns_csv() -> None:
    """`GET /api/example` returns a non-empty CSV starter table."""
    r = client.get("/api/example")
    assert r.status_code == 200
    assert r.text.splitlines()[0].startswith("Language,")


def test_position_roundtrip_deterministic() -> None:
    """`POST /api/position` returns a full, drawable result on a valid table."""
    table = "Language,Speed,Safety,Jobs\nPython,2,2,5\nRust,5,5,3\nGo,4,4,4\nJava,4,4,5"
    r = client.post("/api/position", json={"table": table, "reference": "0", "use_llm": False})
    assert r.status_code == 200
    data = r.json()
    assert data["reference"] == "Python"
    assert data["roles"]["Python"] == "best"
    assert data["vega"]["layer"]  # a real Vega-Lite spec the browser can render
    assert data["markdown"].startswith("# Python")
    assert "meta:" in data["yaml"]


def test_position_response_has_full_frontend_contract() -> None:
    """The response carries everything the browser needs to draw and colorize."""
    table = "Language,Speed,Safety,Jobs\nPython,2,2,5\nRust,5,5,3\nGo,4,4,4\nJava,4,4,5"
    data = client.post("/api/position", json={"table": table, "use_llm": False}).json()
    assert {"vega", "markdown", "yaml", "axes", "poles", "reference", "roles"} <= set(data)
    assert set(data["axes"]) == {"x", "y"}
    assert len(data["poles"]) == 4
    # the four highlighted roles the analysis colorizer tints by name
    assert {"best", "worst", "top", "right"} <= set(data["roles"].values())
    # spec ships transparent; the UI sets the background per the toggle
    assert data["vega"]["background"] is None
    assert "Leaderboard" not in data["markdown"]


def test_position_rejects_degenerate_table() -> None:
    """A table with too few options yields a clean 400, not a 500."""
    r = client.post("/api/position", json={"table": "A,B\nonly,1", "use_llm": False})
    assert r.status_code == 400
    assert "detail" in r.json()


def test_position_rejects_empty_table() -> None:
    """An empty table body is rejected with 400."""
    r = client.post("/api/position", json={"table": "   ", "use_llm": False})
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
