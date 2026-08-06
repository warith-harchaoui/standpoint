#!/usr/bin/env python3
"""Run standpoint on one table: write the figure + analysis, print where they went.

A thin, deterministic wrapper the skill can call instead of re-writing the glue. It
reads a table (a path argument, or ``-`` for stdin), runs ``standpoint.positioning()``,
and writes the deliverable to disk. The figure is a hand-authored, interactive
**SVG** (no Vega), plus the same figure as PNG, each on a transparent and a white
background, alongside the Markdown analysis and the YAML. It then prints the
analysis and the list of files it wrote.

Axis naming and the narrative come from a local Ollama model (``--model``, default
``qwen2.5vl:7b``). Requires the ``standpoint`` package.

Examples
--------
    python positioning_summary.py table.csv --outdir out
    python positioning_summary.py table.csv --reference AWS --lower Price,Latency
    cat table.csv | python positioning_summary.py - --outdir out
"""

from __future__ import annotations

import argparse
import sys


def _read_table(source: str) -> str:
    """Return the raw table text: from stdin when `source` is ``-``, else from a file."""
    if source == "-":
        return sys.stdin.read()
    with open(source, encoding="utf-8") as fh:
        return fh.read()


def main(argv: list[str] | None = None) -> int:
    """Parse args, run the positioning, write the files, print the analysis. Exit code."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("table", help="path to a CSV/Markdown table, or '-' for stdin")
    ap.add_argument(
        "-o",
        "--outdir",
        default="out",
        help="directory for the figure + analysis + data (default: out)",
    )
    ap.add_argument(
        "-r",
        "--reference",
        default="0",
        help="option placed top-right: row index (default 0) or exact name",
    )
    ap.add_argument(
        "--lower",
        default="",
        help="comma-separated criteria where lower is better (e.g. Price,Latency)",
    )
    ap.add_argument(
        "--model",
        default="qwen2.5vl:7b",
        help="Ollama model for axis naming and the narrative (default qwen2.5vl:7b)",
    )
    a = ap.parse_args(argv)

    # Imported here so `--help` works even without the package installed.
    import standpoint as sp

    # A numeric reference is a row index; anything else is an option name.
    ref: int | str = int(a.reference) if a.reference.lstrip("-").isdigit() else a.reference
    lower = [c.strip() for c in a.lower.split(",") if c.strip()]

    try:
        pos = sp.positioning(
            _read_table(a.table), reference=ref, lower_is_better=lower, model=a.model
        )
        # Write the deliverable: <name>.{svg,png,white.svg,white.png,md,yaml}.
        files = pos.export(a.outdir, model=a.model)
    except (ValueError, OSError) as exc:  # bad table / unknown reference / missing file
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # The analysis for the reader, then the paths; the .svg is the figure.
    print(pos.to_markdown(model=a.model))
    print("\nFiles written:")
    for path in files:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
