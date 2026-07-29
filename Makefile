# Convenience wrappers around the local gate. The source of truth for the full
# gate is scripts/check.sh (mirrored from CONTRIBUTING.md); `make check` runs it.
# Individual targets exist for the tighter loop while developing.
.PHONY: check lint format test install help

help:  ## Show the available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

check:  ## Run the full local gate (lint + format check + tests)
	scripts/check.sh

lint:  ## Lint everything, skill scripts included
	ruff check standpoint tests skills

format:  ## Apply ruff formatting to the package and tests
	ruff format standpoint tests

test:  ## Run the test suite (heavy surfaces self-skip if their dep is absent)
	pytest tests/ -q

install:  ## Install the library plus the dev / GUI / API / MCP surfaces
	pip install -e ".[dev,mcp]"
