"""Standpoint's command line (console command ``standpoint``).

One door, built with click: a positional table plus the flags that steer the map
-- which option leads, where the files land, which criteria are lower-is-better,
which local model names the axes. Nothing is computed here: `standpoint.run`
builds the positioning, prints the summary and writes the deliverable. This
module is argument parsing and error presentation only, which is why the library
(`standpoint/__init__.py`) imports no command-line framework at all.
"""

from __future__ import annotations

import sys

import click

from standpoint import __version__, run


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("table", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "-r",
    "--reference",
    default="0",
    show_default=True,
    help="Option placed top-right: row index or exact name.",
)
@click.option(
    "-o", "--outdir", default="out", show_default=True, help="Output directory for the deliverable."
)
@click.option("--stem", default=None, help="Basename for outputs (default: from reference).")
@click.option(
    "--top",
    default=None,
    help="Exact name of the option to highlight as strongest toward the top pole.",
)
@click.option(
    "--right",
    default=None,
    help="Exact name of the option to highlight as strongest toward the right pole.",
)
@click.option("--lower", default="", help="Comma-separated criteria where lower is better.")
@click.option(
    "--model",
    default=None,
    help="Override the local model tag (default: the one resolved in llm.engine.yaml).",
)
# Not "ask the vision model": `--check` reaches `assess_layout`, which reads the
# coordinates. Both doors used to advertise a vision model here, which stopped
# being true when the check moved to the geometry.
@click.option("--check", is_flag=True, help="Sanity-check the figure's layout from its geometry.")
# The version is passed explicitly instead of being read from the installed
# distribution metadata: in an editable checkout that metadata reports whatever
# was last pip-installed, so `-V` would cheerfully print a stale release.
@click.version_option(__version__, "-V", "--version", package_name="standpoint")
def cli(
    table: str,
    reference: str,
    outdir: str,
    stem: str | None,
    top: str | None,
    right: str | None,
    lower: str,
    model: str | None,
    check: bool,
) -> None:
    """Turn a comparison TABLE (CSV or Markdown) into a positioning map.

    Writes PNG + interactive SVG + a Markdown analysis + a YAML of every
    coordinate into the output directory, and prints the axis names, the four
    highlighted options and the loadings.

    \f

    Everything past the form feed is for readers of the source, not for users of
    the command: click renders a command's entire docstring in ``--help`` and
    stops at ``\\f``, so the Numpy-style block that CODING.md Rule 1 asks for
    would otherwise reach the terminal as one reflowed paragraph
    ("Parameters ---------- table : str ...").

    Parameters
    ----------
    table : str
        Path to the comparison table: options in rows, numeric criteria in
        columns, CSV or Markdown.
    reference : str
        The option that leads, placed top-right -- a row index (``"0"``) or an
        exact name. Deliberately left a string: `standpoint.run` owns the
        digits-or-name decision, so both this door and a library caller resolve
        it the same way.
    outdir : str
        Directory the deliverable is written to; created if missing.
    stem : str, optional
        Basename shared by the output files; derived from the reference option
        when omitted.
    top, right : str, optional
        Force a named option into the top-pole / right-pole highlight instead of
        the geometric pick.
    lower : str
        Comma-separated criteria where a lower value is better
        (``Price,Latency``), on top of any ``(↓)`` markers in the headers.
    model : str, optional
        Override the local model tag resolved in ``llm.engine.yaml``.
    check : bool
        Also print the layout self-check (leader top-right, labels legible).
    """
    run(table, reference, outdir, stem, top, right, lower, model, check)


def main() -> None:
    """Console entry point (``standpoint``).

    click's own ``main()`` only special-cases ``ClickException``/``Abort``
    (and a broken pipe); a plain library exception from ``standpoint.run``
    would otherwise propagate as a raw Python traceback instead of a clean
    CLI error. This wraps the whole invocation and translates that last
    case into a one-line stderr message + exit 1 — click's own control flow
    (usage errors, ``--help``, an explicit ``sys.exit`` in a subcommand)
    already raises ``SystemExit``, a ``BaseException`` this does not catch,
    so it passes through untouched.
    """
    try:
        cli()
    except Exception as err:  # noqa: BLE001 — last resort: see docstring
        click.echo(f"Error: {err}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
