"""Click entry point (console command ``standpoint-click``).

A friendlier CLI that mirrors the argparse one; both share `standpoint.run`.
"""

from __future__ import annotations

import click

from standpoint import DEFAULT_MODEL, run


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
    "--model", default=DEFAULT_MODEL, show_default=True, help="Ollama model for axis naming."
)
@click.option("--check", is_flag=True, help="Vision-model sanity-check of the figure.")
def main_click(
    table: str,
    reference: str,
    outdir: str,
    stem: str | None,
    top: str | None,
    right: str | None,
    lower: str,
    model: str,
    check: bool,
) -> None:
    """Turn a comparison TABLE (CSV or Markdown) into a positioning map."""
    run(table, reference, outdir, stem, top, right, lower, model, check)


if __name__ == "__main__":
    main_click()
