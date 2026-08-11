"""Render the training-loss figure as the bounded score Q, not raw nats.

Pure hand-authored SVG -- no matplotlib, no Vega, no chart-rendering runtime of
any kind, mirroring `standpoint/__init__.py`'s own `to_svg()` (Standpoint dropped
Vega entirely for exactly this reason; this figure follows the same house rule
rather than reaching for a plotting library out of convenience).

`extract_loss_curve.py` already computes Q(theta) := 1 - CE(theta)/ln(K) per row
-- see that script's docstring for why ("What Likelihood Means",
harchaoui.org/warith/LIKELIHOOD-en.pdf, Section 5). This draws the raw (noisy,
every-10-iteration) training curve at low opacity, a 100-iteration centered
moving average of it on top (the trend it's easy to lose in the noise otherwise),
and the sparse (every half epoch) validation-loss line, with two reference lines
the paper's own bounds name directly -- Q = 1 (oracle) and Q = 0 (uniform-
guessing floor) -- plus vertical epoch-boundary markers and a legend. Colors are
the Okabe-Ito colorblind-safe "academic" palette
(harchaoui.org/warith/colors/academic), fetched and hardcoded here since it's a
small fixed set of hex values, not a runtime dependency.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

CSV_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/training_loss.csv")
OUT_SVG = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/training_loss.svg")
VOCAB_SIZE = 49280
TRAIN_EXAMPLES = 2763  # from the current run's own "N train / M val examples" log line
TOTAL_ITERS = 8289  # scripts/03_train_lora.py: EPOCHS * len(train)
MA_WINDOW_ITERS = 100  # centered moving average window on the training curve
STEPS_PER_REPORT = 10  # extract_loss_curve.py: training rows are 10 iterations apart

# harchaoui.org/warith/colors/academic -- Okabe-Ito, colorblind-safe.
RED = "#D55E00"
ORANGE = "#E69F00"
GREEN = "#009E73"
BLUE = "#0072B2"
PURPLE = "#CC79A7"
GRAY = "#808080"
INK = "#000000"
MUTED = "#595959"

FONT = "Roboto, 'Roboto Serif', 'Roboto Mono', system-ui, sans-serif"


def load_rows() -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    train, val = [], []
    with CSV_PATH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pt = (int(r["iteration"]), float(r["q"]))
            (train if r["split"] == "train" else val).append(pt)
    return train, val


def centered_moving_average(points: list[tuple[int, float]], window_iters: int) -> list[tuple[int, float]]:
    """Centered moving average over `points`' q values, window in iteration units.

    Rows are `STEPS_PER_REPORT` iterations apart, so a `window_iters`-wide window
    spans `window_iters // STEPS_PER_REPORT` rows on each side of center. Edges use
    a shrinking (not padded) window, same as pandas' `rolling(center=True,
    min_periods=1)`, so the smoothed line still covers the full x-range instead of
    losing `window_iters/2` at each end.
    """
    half = max(1, window_iters // STEPS_PER_REPORT // 2)
    qs = [q for _, q in points]
    out = []
    for i, (it, _) in enumerate(points):
        lo, hi = max(0, i - half), min(len(qs), i + half + 1)
        out.append((it, sum(qs[lo:hi]) / (hi - lo)))
    return out


def epoch_boundaries() -> list[int]:
    """Iteration numbers where a full pass over the train split completes."""
    boundaries = []
    k = 1
    while k * TRAIN_EXAMPLES <= TOTAL_ITERS:
        boundaries.append(k * TRAIN_EXAMPLES)
        k += 1
    return boundaries


def main() -> None:
    train, val = load_rows()
    if not train:
        print(f"No rows in {CSV_PATH}; run extract_loss_curve.py first.", file=sys.stderr)
        sys.exit(1)

    # -- layout: data space (iteration, q) -> pixel space ------------------ #
    PAD_L, PAD_R, PAD_T, PAD_B = 74, 24, 72, 46
    PLOT_W, PLOT_H = 660, 360
    CANVAS_W, CANVAS_H = PLOT_W + PAD_L + PAD_R, PLOT_H + PAD_T + PAD_B

    x_min, x_max = 0, TOTAL_ITERS
    y_min, y_max = -0.08, 1.12  # extra headroom above 1.0 so the oracle label clears the top

    def x_px(it: float) -> float:
        return PAD_L + (it - x_min) / (x_max - x_min) * PLOT_W

    def y_px(q: float) -> float:
        return PAD_T + (1 - (q - y_min) / (y_max - y_min)) * PLOT_H

    train_pts = " ".join(f"{x_px(it):.1f},{y_px(q):.1f}" for it, q in train)
    train_ma = centered_moving_average(train, MA_WINDOW_ITERS)
    train_ma_pts = " ".join(f"{x_px(it):.1f},{y_px(q):.1f}" for it, q in train_ma)

    last_it = train[-1][0]
    last_val = f", last val Q={val[-1][1]:.3f}" if val else ""

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
        f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" role="img" '
        f'aria-labelledby="loss-title loss-desc" font-family="{FONT}">',
        '<title id="loss-title">SmolVLM2-500M LoRA distillation — bounded likelihood score</title>',
        f'<desc id="loss-desc">Training and validation curves of Q(θ) = 1 minus cross-entropy '
        f"over log of {VOCAB_SIZE}, from iteration {train[0][0]} to {last_it} of {TOTAL_ITERS}, "
        "with oracle, worst-case, and epoch-boundary reference lines.</desc>",
        f'<rect x="0" y="0" width="{CANVAS_W}" height="{CANVAS_H}" fill="#FFFFFF"/>',
        f'<text x="{PAD_L}" y="24" font-size="16" font-weight="700" fill="{INK}">'
        f"SmolVLM2-500M LoRA distillation — bounded likelihood score</text>",
        f'<text x="{PAD_L}" y="42" font-size="11" fill="{MUTED}">'
        f"Q(θ) = 1 − CE(θ)/ln(K), K = {VOCAB_SIZE} (vocab) — "
        f"iter {last_it}/{TOTAL_ITERS}{last_val} — higher is better</text>",
    ]

    # -- plot border (bottom + left axis only, matching the house no-spine rule) -- #
    parts.append(
        f'<line x1="{x_px(x_min):.1f}" y1="{y_px(y_min):.1f}" x2="{x_px(x_max):.1f}" '
        f'y2="{y_px(y_min):.1f}" stroke="{INK}" stroke-width="1"/>'
    )
    parts.append(
        f'<line x1="{x_px(x_min):.1f}" y1="{y_px(y_min):.1f}" x2="{x_px(x_min):.1f}" '
        f'y2="{y_px(1.0):.1f}" stroke="{INK}" stroke-width="1"/>'
    )

    # -- y ticks (0, 0.25, ..., 1) ------------------------------------------ #
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        ty = y_px(tick)
        parts.append(
            f'<text x="{PAD_L - 8:.1f}" y="{ty + 4:.1f}" font-size="10" fill="{MUTED}" '
            f'text-anchor="end">{tick:.2f}</text>'
        )
    # -- x ticks -------------------------------------------------------------#
    for tick in range(0, TOTAL_ITERS + 1, 1000):
        tx = x_px(tick)
        parts.append(
            f'<text x="{tx:.1f}" y="{y_px(y_min) + 18:.1f}" font-size="10" fill="{MUTED}" '
            f'text-anchor="middle">{tick}</text>'
        )
    parts.append(
        f'<text x="{PAD_L + PLOT_W / 2:.1f}" y="{CANVAS_H - 6:.1f}" font-size="11" '
        f'fill="{INK}" text-anchor="middle">Iteration</text>'
    )
    parts.append(
        f'<text x="16" y="{PAD_T + PLOT_H / 2:.1f}" font-size="11" fill="{INK}" '
        f'text-anchor="middle" transform="rotate(-90 16 {PAD_T + PLOT_H / 2:.1f})">'
        "Q(θ) — bounded likelihood score (higher is better)</text>"
    )

    # -- epoch-boundary vlines (label along the TOP so they don't collide with the
    #    x-axis tick labels or the oracle/worst-case text sitting near the data).
    #    Left-anchored (end of text at the line, not start): the last epoch boundary
    #    coincides with TOTAL_ITERS by construction (EPOCHS * len(train)), i.e. sits
    #    exactly at the plot's right edge, so a right-growing label there always ran
    #    off-canvas (caught by the Ralph Eyeball Loop: rendered as "epocl", visibly
    #    clipped). Growing left instead has room for every boundary, including that
    #    last one, with no adjacent-label collision risk since boundaries are a full
    #    TRAIN_EXAMPLES apart. --------------------------------------------------- #
    for k, it in enumerate(epoch_boundaries(), start=1):
        ex = x_px(it)
        parts.append(
            f'<line x1="{ex:.1f}" y1="{y_px(y_min):.1f}" x2="{ex:.1f}" y2="{y_px(y_max):.1f}" '
            f'stroke="{GRAY}" stroke-width="1" stroke-dasharray="2,3"/>'
        )
        parts.append(
            f'<text x="{ex - 3:.1f}" y="{PAD_T - 4:.1f}" font-size="9" fill="{GRAY}" '
            f'text-anchor="end">epoch {k}</text>'
        )

    # -- oracle (Q=1) and worst-case (Q=0) reference hlines, labelled INSIDE the
    #    plot's left margin only (not spanning the full width) to stay clear of
    #    the data curves, which occupy the right two-thirds of the plot -------- #
    parts.append(
        f'<line x1="{x_px(x_min):.1f}" y1="{y_px(1.0):.1f}" x2="{x_px(x_max):.1f}" '
        f'y2="{y_px(1.0):.1f}" stroke="{PURPLE}" stroke-width="1.5" stroke-dasharray="4,4"/>'
    )
    parts.append(
        f'<text x="{x_px(x_min) + 4:.1f}" y="{y_px(1.0) - 5:.1f}" font-size="10" fill="{PURPLE}">'
        "oracle (Q=1, perfectly confident &amp; correct)</text>"
    )
    parts.append(
        f'<line x1="{x_px(x_min):.1f}" y1="{y_px(0.0):.1f}" x2="{x_px(x_max):.1f}" '
        f'y2="{y_px(0.0):.1f}" stroke="{RED}" stroke-width="1.5" stroke-dasharray="4,4"/>'
    )
    parts.append(
        f'<text x="{x_px(x_min) + 4:.1f}" y="{y_px(0.0) + 14:.1f}" font-size="10" fill="{RED}">'
        "worst case (Q=0, uniform guessing over the vocabulary)</text>"
    )

    # -- the data itself, drawn after the reference lines so it sits above them.
    #    Raw training curve at low opacity (the noise is real signal too, just not
    #    the trend), the 100-iteration centered moving average bold on top. ------- #
    parts.append(
        f'<polyline points="{train_pts}" fill="none" stroke="{GREEN}" stroke-width="1" '
        f'opacity="0.35"/>'
    )
    parts.append(
        f'<polyline points="{train_ma_pts}" fill="none" stroke="{GREEN}" stroke-width="2.5"/>'
    )
    if val:
        val_pts = " ".join(f"{x_px(it):.1f},{y_px(q):.1f}" for it, q in val)
        parts.append(
            f'<polyline points="{val_pts}" fill="none" stroke="{BLUE}" stroke-width="2.5"/>'
        )
        for it, q in val:
            parts.append(f'<circle cx="{x_px(it):.1f}" cy="{y_px(q):.1f}" r="3.5" fill="{BLUE}"/>')

    # -- legend: a boxed panel in the bottom-right of the plot area, the one
    #    region the data (which climbs toward Q~1) and the epoch/oracle labels
    #    (top and top-left) don't reach ---------------------------------------- #
    leg_w, leg_h = 190, 72
    leg_x = x_px(x_max) - leg_w - 8
    leg_y = y_px(0.02) - leg_h
    parts.append(
        f'<rect x="{leg_x:.1f}" y="{leg_y:.1f}" width="{leg_w}" height="{leg_h}" '
        f'fill="#FFFFFF" stroke="{GRAY}" stroke-width="0.75" rx="6"/>'
    )
    parts.append(
        f'<line x1="{leg_x + 12:.1f}" y1="{leg_y + 16:.1f}" x2="{leg_x + 34:.1f}" '
        f'y2="{leg_y + 16:.1f}" stroke="{GREEN}" stroke-width="1" opacity="0.35"/>'
    )
    parts.append(
        f'<text x="{leg_x + 40:.1f}" y="{leg_y + 19:.1f}" font-size="10" fill="{INK}">'
        "training, raw (every 10 iters)</text>"
    )
    parts.append(
        f'<line x1="{leg_x + 12:.1f}" y1="{leg_y + 34:.1f}" x2="{leg_x + 34:.1f}" '
        f'y2="{leg_y + 34:.1f}" stroke="{GREEN}" stroke-width="2.5"/>'
    )
    parts.append(
        f'<text x="{leg_x + 40:.1f}" y="{leg_y + 37:.1f}" font-size="10" fill="{INK}">'
        f"training, {MA_WINDOW_ITERS}-iter moving avg</text>"
    )
    parts.append(
        f'<line x1="{leg_x + 12:.1f}" y1="{leg_y + 52:.1f}" x2="{leg_x + 34:.1f}" '
        f'y2="{leg_y + 52:.1f}" stroke="{BLUE}" stroke-width="2.5"/>'
    )
    parts.append(f'<circle cx="{leg_x + 23:.1f}" cy="{leg_y + 52:.1f}" r="3.5" fill="{BLUE}"/>')
    parts.append(
        f'<text x="{leg_x + 40:.1f}" y="{leg_y + 55:.1f}" font-size="10" fill="{INK}">'
        "validation (every half epoch)</text>"
    )

    parts.append("</svg>")

    OUT_SVG.parent.mkdir(parents=True, exist_ok=True)
    OUT_SVG.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT_SVG}")


if __name__ == "__main__":
    main()
