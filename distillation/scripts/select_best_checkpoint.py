"""Pick the checkpoint with the lowest validation loss, not just the last one.

`mlx_vlm.trainer.sft_trainer.train()` has no "keep the best checkpoint" logic of
its own -- it just periodically overwrites `adapters.safetensors` ("latest") and
writes a numbered snapshot (`checkpoints/distilled-adapter/0001381_adapters.
safetensors`, etc.) on the `--steps-per-save` cadence. If validation loss ticks
back up in the last stretch of training (overfitting), the final/"latest"
checkpoint is silently worse than an earlier one. Since checkpoints are saved on
the same half-epoch cadence validation runs on (`03_train_lora.py`), every
snapshot has a matching Val loss to compare -- this reads them from the log,
finds the minimum, and copies that snapshot to `best-adapter.safetensors`
(`checkpoints/distilled-adapter/`), the file `04_evaluate.py` should load.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

LOG_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/train_lora.log")
ADAPTER_DIR = (
    Path(sys.argv[2])
    if len(sys.argv) > 2
    else Path(__file__).resolve().parents[1] / "checkpoints" / "distilled-adapter"
)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
VAL_RE = re.compile(r"Iter (\d+): Val loss ([0-9.]+|nan), Val took")


def main() -> None:
    text = ANSI_RE.sub("", LOG_PATH.read_text(errors="replace"))
    val_losses = [
        (int(m.group(1)), float(m.group(2))) for m in VAL_RE.finditer(text) if m.group(2) != "nan"
    ]
    if not val_losses:
        print(f"No 'Val loss' lines found in {LOG_PATH}.", file=sys.stderr)
        sys.exit(1)

    best_it, best_loss = min(val_losses, key=lambda t: t[1])
    print(f"Validation loss at each checkpoint: {val_losses}")
    print(f"Best: iter {best_it}, Val loss {best_loss:.3f}")

    snapshot = ADAPTER_DIR / f"{best_it:07d}_adapters.safetensors"
    if not snapshot.exists():
        # The best point might not land exactly on a --steps-per-save multiple if
        # eval and save cadences ever differ; fall back to the nearest saved one.
        candidates = sorted(ADAPTER_DIR.glob("*_adapters.safetensors"))
        if not candidates:
            print(f"No checkpoint snapshots found in {ADAPTER_DIR}.", file=sys.stderr)
            sys.exit(1)
        snapshot = min(candidates, key=lambda p: abs(int(p.stem.split("_")[0]) - best_it))
        print(f"(no exact snapshot at iter {best_it}; using nearest: {snapshot.name})")

    dest = ADAPTER_DIR / "best-adapter.safetensors"
    shutil.copy2(snapshot, dest)
    print(f"copied {snapshot.name} -> {dest}")


if __name__ == "__main__":
    main()
