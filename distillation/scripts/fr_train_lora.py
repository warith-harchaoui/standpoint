"""French track, Phase 2 equivalent: combine the French JSONL datasets and
LoRA-train Qwen3-VL-2B-Instruct.

Mirrors `03_train_lora.py` exactly, filtered to `lang == "fr"` rows and pointed at
the French base model -- **not** a separate trainer. The previous session's plan
used Luth-0.6B (text-only, via `mlx_lm.lora`) for this track, which needed its own
gradient-clipped trainer fork (`fr_run_lora_with_clip.py`, now removed) because
`mlx_lm.lora` has no gradient-clipping mechanism at all. That whole problem class
goes away with this pivot to a vision-language model: the French track now uses the
exact same `mlx_vlm`-based `run_lora_with_val.py` the English track already uses,
so no French-specific trainer code exists at all.

**Why Qwen3-VL-2B instead of SmolVLM2** for French: `SmolVLM2` scores far weaker on
French multilingual VQA benchmarks (SmolVLM2-2.2B: 53.07 on French MMBench) than
alternatives at a comparable size (Qwen3-VL-2B: 72.47, Qwen2.5-VL-3B: 75.58,
InternVL3.5-2B: 71.95, LFM2-VL-3B: 77.14 -- see
https://artificialanalysis.ai/models/multilingual/french). `mlx-community/
Qwen3-VL-2B-Instruct-bf16` is a pre-converted MLX checkpoint (`mlx-vlm` 0.3.4),
so no local `mlx_vlm.convert` pass is needed, unlike SmolVLM2's Phase 0.

**No `vlm_assess_fr` on this track** (dropped after a real training crash, not a
design choice made up front): `mlx_vlm`'s Qwen3-VL LoRA training path throws
`ValueError: Image features and image tokens do not match` on every image-bearing
batch, reproduced on both `mlx-vlm` 0.6.10 and 0.6.13 -- a known, currently
unresolved upstream bug affecting Qwen3-VL training across multiple frameworks
(see https://github.com/QwenLM/Qwen3-VL/issues/556), not something fixable with a
local patch the way `_mlx_vlm_idefics3_patch.py` fixed SmolVLM2's issue. This
track is therefore **text-only** (`pole_naming`/`noun_forms`), which sidesteps the
bug entirely (confirmed: text-only batches train cleanly). `vlm_assess` keeps
being served by the English-distilled SmolVLM2 adapter for every language, same as
before this pivot -- its judgment is a geometric check on the rendered image, not
really language-dependent (see `standpoint.vlm_assess`'s docstring), so it never
needed its own French-distilled variant in the first place.

Since every example here is text-only, there is no image/text batch-collation
hazard to avoid (unlike `03_train_lora.py`) and no vision stack to train.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sklearn.model_selection import train_test_split

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATASET_DIR = DATA_DIR / "dataset"
CHECKPOINTS_DIR = Path(__file__).resolve().parents[1] / "checkpoints"
BASE_MODEL = CHECKPOINTS_DIR / "qwen3-vl-2b-mlx-bf16"  # bf16, not a quantization:
# LoRA fine-tuning wants the base weights at training precision, same reasoning
# as 03_train_lora.py's float16-instability finding for SmolVLM2 (see that
# module's BASE_MODEL comment) -- to be reconfirmed empirically for this model,
# not assumed identical.
ADAPTER_OUT = CHECKPOINTS_DIR / "distilled-adapter-fr"

TASKS = ["pole_naming", "noun_forms"]  # narrative excluded (out of scope, the
# feature is being removed from standpoint); vlm_assess excluded (Qwen3-VL image
# training crashes, see module docstring) -- served by the English adapter instead
LANG = "fr"
VAL_FRACTION = 0.15
SEED = 42  # same seed as 03_train_lora.py's train_test_split, for consistency
EPOCHS = 3
BATCH_SIZE = 1  # same collation-safety reasoning as 03_train_lora.py


def load_combined() -> list[dict]:
    """One record per French example, with a `task` label carried through for eval."""
    examples = []
    for task in TASKS:
        path = DATASET_DIR / f"{task}.jsonl"
        if not path.exists():
            print(f"warning: {path} missing, skipping {task}", file=sys.stderr)
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                ex = json.loads(line)
                if ex.get("lang") != LANG:
                    continue
                examples.append(
                    {
                        "question": ex["question"],
                        "answer": ex["answer"],
                        "image": ex.get("image"),  # explicit null for text-only tasks
                        "task": task,
                        "lang": ex.get("lang"),
                    }
                )
    return examples


def _split_modality_block(examples: list[dict]) -> tuple[list[dict], list[dict]]:
    """`train_test_split` one modality group, each half a multiple of BATCH_SIZE."""
    if len(examples) < 2:
        return list(examples), []
    train, val = train_test_split(examples, test_size=VAL_FRACTION, random_state=SEED, shuffle=True)
    n_train = (len(train) // BATCH_SIZE) * BATCH_SIZE
    n_val = (len(val) // BATCH_SIZE) * BATCH_SIZE
    return train[:n_train], val[:n_val]  # drop the < BATCH_SIZE remainder, not worth padding


def main() -> None:
    examples = load_combined()
    if not examples:
        print(
            "No French examples found; run 02_generate_dataset.py and "
            "fr_vlm_assess.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    text_examples = [e for e in examples if e["image"] is None]
    image_examples = [e for e in examples if e["image"] is not None]
    text_train, text_val = _split_modality_block(text_examples)
    image_train, image_val = _split_modality_block(image_examples)
    train = text_train + image_train
    val = text_val + image_val

    combined_dir = DATASET_DIR / "combined_fr"
    combined_dir.mkdir(exist_ok=True)
    train_path = combined_dir / "train.jsonl"
    val_path = combined_dir / "validation.jsonl"
    for path, rows in ((train_path, train), (val_path, val)):
        with path.open("w", encoding="utf-8") as f:
            for ex in rows:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"{len(train)} train / {len(val)} val examples -> {train_path.name}, {val_path.name}")

    if not BASE_MODEL.exists():
        print(
            f"Base model not found at {BASE_MODEL}; download "
            "mlx-community/Qwen3-VL-2B-Instruct-bf16 first "
            f"(e.g. huggingface_hub.snapshot_download into {BASE_MODEL}).",
            file=sys.stderr,
        )
        sys.exit(1)

    iters = EPOCHS * len(train)  # batch-size 1: iteration count == examples seen
    half_epoch = len(train) // 2

    cmd = [
        sys.executable,
        str(Path(__file__).parent / "run_lora_with_val.py"),  # same shared trainer
        # the English track uses; see module docstring for why no French-specific
        # trainer script exists for this model
        "--model-path",
        str(BASE_MODEL),
        "--dataset",
        str(combined_dir),
        # no --train-vision: this track is text-only, no vision stack to train
        # (see module docstring for why vlm_assess_fr was dropped)
        "--iters",
        str(iters),
        "--batch-size",
        "1",
        "--gradient-accumulation-steps",
        "2",
        "--learning-rate",
        "1e-5",  # NOT the same as 03_train_lora.py's 3e-5 -- that was an unvalidated
        # assumption ("same starting point as the English config") that turned out
        # wrong for this model: a 500-iteration smoke test at 3e-5 (with
        # --warmup-steps below already active) still climbed to val loss 12.2 by
        # iter 500 (train loss swinging 3-11 throughout, never settling) even
        # though it no longer went outright NaN. The same smoke test at 1e-5
        # converges cleanly instead: val loss 2.67 -> 2.15 -> 1.99 over the same
        # 500 iterations, train loss smoothly down to ~1.9-2.0. Qwen3-VL-2B is
        # ~4x larger than SmolVLM2-500M and a different architecture, so there
        # was never a good reason to expect the same LR to transfer.
        "--warmup-steps",
        "100",  # optimizer-update units (~200 raw iters at grad-accum 2 below); see
        # run_lora_with_val.py's module docstring -- added after this track's
        # earlier full retrain (at the old 3e-5, no warmup) went unstable past
        # iter 350 and NaN from iter 380
        "--grad-clip",
        "1.0",
        "--lora-rank",
        "16",
        "--lora-alpha",
        "32",
        "--steps-per-report",
        "10",
        "--steps-per-save",
        str(half_epoch),
        "--steps-per-eval",
        str(half_epoch),
        "--val-batches",
        str(len(val)),
        "--output-path",
        str(ADAPTER_OUT),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
