"""Standpoint: Model Context Protocol (MCP) surface.

A thin adapter that exposes the FastAPI app from :mod:`standpoint.api` as MCP tools,
so any MCP-aware host (an agent runtime, an IDE integration, a custom shell) can call
``position`` (turn a comparison table into a labelled 2D positioning map plus a
written analysis) as a first-class tool. It uses `fastapi-mcp`
(https://github.com/tadata-org/fastapi_mcp): one wrapper publishes the whole existing
HTTP surface, so the routes are never duplicated.

Install the extra to pull in ``fastapi-mcp``::

    pip install "standpoint[mcp]"

Then run the server (HTTP API + MCP endpoint at ``/mcp``)::

    standpoint-mcp                 # console entry point
    python -m standpoint.mcp       # equivalent

Author
------
Warith Harchaoui, https://www.linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

try:
    from fastapi_mcp import FastApiMCP
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'The MCP surface needs the [mcp] extra: pip install "standpoint[mcp]"'
    ) from exc

# Reuse the exact same FastAPI app: MCP is a thin wrapper on top, no new routes.
from standpoint.api import app

# Publish the HTTP endpoints (position / example / upload / download) as MCP tools.
mcp = FastApiMCP(
    app,
    name="standpoint",
    description=(
        "Standpoint MCP tools: turn a comparison table (options x criteria) into a "
        "labelled 2D positioning map (a quadrant / perceptual map) plus a written "
        "analysis, entirely on the local machine."
    ),
)
# Newer fastapi-mcp splits mount() into transport-specific mount_http(); fall back to
# the legacy mount() so a range of fastapi-mcp versions keeps working.
if hasattr(mcp, "mount_http"):
    mcp.mount_http()
else:  # pragma: no cover - legacy fastapi-mcp
    mcp.mount()


def main(argv: list[str] | None = None) -> None:
    """Console entry point (``standpoint-mcp``): serve the API + MCP endpoint.

    Boots the FastAPI app (now serving both the ``/api/...`` routes and the ``/mcp``
    MCP endpoint) with uvicorn in a single worker. Local-first: binds to loopback by
    default (override with ``--host`` / ``--port`` or ``STANDPOINT_HOST`` /
    ``STANDPOINT_PORT``). A click command, so ``--help`` answers instead of
    starting the server.
    """
    import click

    @click.command(context_settings={"help_option_names": ["-h", "--help"]})
    @click.option("--host", envvar="STANDPOINT_HOST", default="127.0.0.1", show_default=True)
    @click.option("--port", envvar="STANDPOINT_PORT", default=8000, type=int, show_default=True)
    def serve(host: str, port: int) -> None:
        """Serve the Standpoint API and its MCP endpoint (/mcp)."""
        import uvicorn

        click.echo(f"Standpoint API + MCP -> http://{host}:{port}  (MCP at /mcp)")
        uvicorn.run(app, host=host, port=port, workers=1)

    serve.main(args=argv, prog_name="standpoint-mcp")


if __name__ == "__main__":  # pragma: no cover
    main()
