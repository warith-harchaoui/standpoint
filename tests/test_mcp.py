"""Smoke test for the MCP surface (`standpoint.mcp`).

Gated on the ``mcp`` extra (FastAPI + fastapi-mcp). Importing `standpoint.mcp` mounts
an MCP endpoint onto the FastAPI app; we check the endpoint is wired and that the HTTP
API keeps serving alongside it. Skips cleanly when the extra isn't installed, so the
default suite is unaffected.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("fastapi_mcp")
starlette_testclient = pytest.importorskip("starlette.testclient")

from standpoint import mcp as mcp_module  # noqa: E402  (import mounts MCP on the app)


def test_mcp_endpoint_is_mounted() -> None:
    """Importing the module publishes an `/mcp` endpoint named 'standpoint'."""
    paths = {r.path for r in mcp_module.app.routes}
    assert any("/mcp" in p for p in paths), paths
    assert mcp_module.mcp.name == "standpoint"


@pytest.mark.needs_model
def test_api_still_served_next_to_mcp() -> None:
    """The FastAPI routes still work once the MCP endpoint is mounted."""
    client = starlette_testclient.TestClient(mcp_module.app)
    assert client.get("/gui").status_code == 200
    table = "Language,Speed,Safety,Jobs\nPython,2,3,5\nRust,5,4,3\nGo,4,3,4\nJava,4,5,5"
    r = client.post("/api/position", json={"table": table})
    assert r.status_code == 200
    assert "vega" in r.json() and r.json()["reference"] == "Python"
