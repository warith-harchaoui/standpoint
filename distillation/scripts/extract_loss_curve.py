"""Parse mlx_vlm.lora's training log into a CSV for the loss-curve figure.

Reconstructs approximate wall-clock elapsed time per reported training iteration
from each report row's own `It/sec` (the rate over the last `--steps-per-report`
steps), since the log itself has no timestamps. `Val loss` rows (from
`run_lora_with_val.py`'s real validation, on the `--steps-per-eval` cadence) carry
no `It/sec` of their own, so they're stamped with the elapsed time of the most
recent training row instead -- close enough for a loss-curve x-axis, off by at
most one report interval.

Also emits the bounded score from "What Likelihood Means" (harchaoui.org/warith/
LIKELIHOOD-en.pdf), Section 5: for a K-way next-token classifier trained on
cross-entropy, Q(theta) := 1 - CE(theta)/ln(K) reads 1 for a perfectly confident,
correct model, 0 for one no better than uniform guessing over the vocabulary, and
negative for one actively worse than that -- the raw nats loss has no such fixed
scale to compare against run to run. K = the model's vocab_size (config.json).
"""

from __future__ import annotations

import csv
import math
import re
import sys
from pathlib import Path

LOG_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/train_lora.log")
OUT_PATH = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/training_loss.csv")
STEPS_PER_REPORT = 10
VOCAB_SIZE = 49280  # checkpoints/smolvlm2-500m-mlx-bf16/config.json: vocab_size
LN_VOCAB_SIZE = math.log(VOCAB_SIZE)  # Q's worst-case floor: CE == ln(K), Q == 0

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
TRAIN_RE = re.compile(
    r"Iter (\d+): Train loss ([0-9.]+|nan), Learning Rate [0-9.e+-]+, It/sec ([0-9.]+)"
)
VAL_RE = re.compile(r"Iter (\d+): Val loss ([0-9.]+|nan), Val took")


def main() -> None:
    text = ANSI_RE.sub("", LOG_PATH.read_text(errors="replace"))

    # Merge train/val log lines in file order so elapsed-time carries forward
    # correctly regardless of which kind of row comes next.
    tagged = [(m.start(), "train", m) for m in TRAIN_RE.finditer(text)]
    tagged += [(m.start(), "val", m) for m in VAL_RE.finditer(text)]
    tagged.sort(key=lambda t: t[0])

    rows = []
    elapsed_min = 0.0
    for _, kind, m in tagged:
        it, loss = int(m.group(1)), m.group(2)
        if loss == "nan":
            continue  # the diverged float16 run's rows; excluded from the figure
        loss_f = float(loss)
        if kind == "train":
            it_per_sec = float(m.group(3))
            elapsed_min += (STEPS_PER_REPORT / it_per_sec) / 60.0 if it_per_sec > 0 else 0.0
        q = 1.0 - loss_f / LN_VOCAB_SIZE
        rows.append((it, kind, loss_f, round(elapsed_min, 2), round(q, 4)))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iteration", "split", "loss", "elapsed_min", "q"])
        w.writerows(rows)
    n_train = sum(1 for r in rows if r[1] == "train")
    n_val = sum(1 for r in rows if r[1] == "val")
    print(f"{len(rows)} rows ({n_train} train, {n_val} val) -> {OUT_PATH}")
    if rows:
        print(f"iter {rows[0][0]}..{rows[-1][0]}, ~{rows[-1][3]:.0f} min elapsed so far")


if __name__ == "__main__":
    main()
