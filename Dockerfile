# syntax=docker/dockerfile:1
#
# standpoint — container image serving the HTTP API + MCP endpoint (and the GUI).
#
# Build:
#   docker build -t standpoint .
#
# Run (API + MCP on 0.0.0.0:8000 — GUI at /gui, MCP at /mcp):
#   docker run --rm -p 8000:8000 standpoint
#
# One-shot CLI instead of the server (mount a folder for I/O):
#   docker run --rm -v "$PWD:/data" standpoint \
#       standpoint /data/table.csv --outdir /data/out --no-llm
#
# LLM axis-naming needs a reachable Ollama. Point the container at one on the host:
#   docker run --rm -p 8000:8000 \
#       -e OLLAMA_HOST=http://host.docker.internal:11434 standpoint

FROM python:3.12-slim AS base

# tini reaps orphaned children cleanly on SIGTERM. No compilers — everything installs
# from wheels (vl-convert ships its own renderer and fonts).
RUN apt-get update && apt-get install --no-install-recommends -y tini \
    && rm -rf /var/lib/apt/lists/*

# The app never needs root at runtime.
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

# Install the runtime contract first, so this heavy layer (numpy / pandas /
# scikit-learn / vl-convert) is cached until requirements.txt actually changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Then the package itself with the server surfaces (FastAPI + MCP). Deps already
# satisfied above; this layer just adds fastapi / uvicorn / fastapi-mcp and standpoint.
COPY pyproject.toml README.md LICENSE ./
COPY standpoint ./standpoint
RUN pip install --no-cache-dir ".[mcp]"

USER app
EXPOSE 8000
ENV PYTHONUNBUFFERED=1 \
    STANDPOINT_HOST=0.0.0.0 \
    STANDPOINT_PORT=8000

ENTRYPOINT ["/usr/bin/tini", "--"]
# Default: serve the FastAPI API + MCP endpoint. Override the CMD for one-shot CLI use.
CMD ["standpoint-mcp"]
