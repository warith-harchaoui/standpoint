#!/usr/bin/env python3
"""Run standpoint on one table: write the figure + data, print where they went.

A thin, deterministic wrapper the skill can call instead of re-writing the glue. It
reads a table (a path argument, or ``-`` for stdin), runs ``standpoint.positioning()``,
and writes the deliverable to disk. The figure is a hand-authored, interactive
**SVG** (no Vega), plus the same figure as PNG, each on a transparent and a white
background, alongside the YAML. It then prints the list of files it wrote.

Axis naming comes from a local Ollama model (``--model``, default
``qwen2.5vl:7b``). Requires the ``standpoint`` package.

Built with click, like every other command line in the suite. ``main(argv)``
still returns an ``int`` rather than exiting, because the skill and
``tests/test_skill_script.py`` both drive it that way.

Examples
--------
    python positioning_summary.py table.csv --outdir out
    python positioning_summary.py table.csv --reference AWS --lower Price,Latency
    cat table.csv | python positioning_summary.py - --outdir out
"""

from __future__ import annotations

import sys

import click


def _read_table(source: str) -> str:
    """Return the raw table text: from stdin when `source` is ``-``, else from a file."""
    if source == "-":
        return sys.stdin.read()
    with open(source, encoding="utf-8") as fh:
        return fh.read()


# ``allow_dash`` is what keeps ``-`` meaning stdin: click would otherwise reject
# it as a missing path. The skill pipes tables in, so losing that would break it.
@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("table", type=click.Path(exists=True, dir_okay=False, allow_dash=True))
@click.option(
    "-o",
    "--outdir",
    default="out",
    show_default=True,
    help="Directory for the figure + analysis + data.",
)
@click.option(
    "-r",
    "--reference",
    default="0",
    show_default=True,
    help="Option placed top-right: row index, or an exact name.",
)
@click.option(
    "--lower",
    default="",
    help="Comma-separated criteria where lower is better (e.g. Price,Latency).",
)
@click.option(
    "--model",
    default="qwen2.5vl:7b",
    show_default=True,
    help="Ollama model for axis naming.",
)
def cli(table: str, outdir: str, reference: str, lower: str, model: str) -> None:
    """Run standpoint on TABLE and write the figure, the analysis and the data."""
    # Imported here so ``--help`` works even without the package installed.
    import standpoint as sp

    # A numeric reference is a row index; anything else is an option name.
    ref: int | str = int(reference) if reference.lstrip("-").isdigit() else reference
    lower_list = [c.strip() for c in lower.split(",") if c.strip()]

    try:
        pos = sp.positioning(
            _read_table(table), reference=ref, lower_is_better=lower_list, model=model
        )
        # Write the deliverable: <name>.{svg,png,white.svg,white.png,yaml}.
        files = pos.export(outdir)
    except (ValueError, OSError) as exc:  # bad table / unknown reference / missing file
        raise click.ClickException(str(exc)) from exc

    click.echo("Files written:")
    for path in files:
        click.echo(f"  {path}")


def main(argv: list[str] | None = None) -> int:
    """Run the command and return its exit code.

    Returns an ``int`` instead of exiting, which is the contract the skill and
    ``tests/test_skill_script.py`` rely on. ``standalone_mode=False`` is what
    stops click from calling :func:`sys.exit` itself, so the code can be handed
    back to the caller.

    Parameters
    ----------
    argv : list of str, optional
        Argument vector; defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        ``0`` on success, ``1`` on a bad table / reference / path, ``2`` on a
        usage error.
    """
    try:
        cli.main(args=argv if argv is not None else sys.argv[1:], standalone_mode=False)
    except click.ClickException as exc:
        # Keep the original wording ("error: ...") so anything reading stderr
        # for it — the skill's own prose included — still matches.
        click.echo(f"error: {exc.format_message()}", err=True)
        return exc.exit_code if isinstance(exc, click.UsageError) else 1
    except click.exceptions.Exit as exc:  # --help and --version land here
        return int(exc.exit_code)
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
