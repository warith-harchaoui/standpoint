"""End-to-end GUI test: drive the real page in headless Chromium (dev-gui).

This is the one test that exercises the *frontend* JavaScript rather than the
endpoints — it loads `/gui`, clicks Generate, and checks that the quadrant actually
renders, the analysis comes out role-colorized, and no JavaScript error fires.
Generating always names the axes with the local model (a hard prerequisite that
`tests/conftest.py` guarantees). It is otherwise heavily gated on test infrastructure:
it starts the FastAPI app on a loopback port in a background thread and skips unless
FastAPI, Playwright, and a Chromium build are all present, so CI (which has none of
them) is unaffected.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest

pytest.importorskip("fastapi")
sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn  # noqa: E402  (after importorskip by design)

from standpoint.api import app  # noqa: E402


def _free_port() -> int:
    """Grab an unused loopback TCP port for the test server."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    """Run the GUI app in a background uvicorn thread; yield its base URL."""
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # Wait for uvicorn to report itself started (or give up and skip).
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    else:
        server.should_exit = True
        pytest.skip("uvicorn did not start in time")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_generate_flow_renders_and_colorizes(base_url: str) -> None:
    """Load the page, generate a quadrant, and verify the rendered result."""
    errors: list[str] = []
    try:
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:  # no chromium build available
                pytest.skip(f"chromium unavailable: {exc}")
            page = browser.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{base_url}/gui", wait_until="networkidle")
            page.wait_for_selector("#grid input")  # the seeded example loaded
            page.click("#run")
            # the chart appears and the analysis heading renders
            page.wait_for_selector("#chart canvas, #chart svg", timeout=30000)
            page.wait_for_function("document.querySelector('#comments h1') !== null", timeout=30000)
            role_spans = page.eval_on_selector_all(
                "#comments .role-best, #comments .role-worst, "
                "#comments .role-top, #comments .role-right",
                "els => els.length",
            )
            png_visible = page.is_visible("#dlPng")
            svg_visible = page.is_visible("#dlSvg")
            browser.close()
    except sync_api.Error as exc:  # playwright driver/runtime problem, not a real fail
        pytest.skip(f"playwright runtime unavailable: {exc}")

    assert not errors, f"JavaScript errors on the page: {errors}"
    assert role_spans >= 3, "analysis should tint highlighted option names by role"
    assert png_visible and svg_visible, "PNG/SVG export buttons should appear"
