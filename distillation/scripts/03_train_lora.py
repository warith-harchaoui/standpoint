"""Phase 2: combine the four per-task JSONL datasets and LoRA-train SmolVLM2-500M.

`mlx_vlm.lora`'s dataset loader auto-transforms a `question`/`answer`(/`image`)
column dataset into its `messages` conversation format (see
`mlx_vlm.lora.transform_dataset_to_messages`), which already matches every task's
JSONL from `02_generate_dataset.py` exactly -- no reshaping needed beyond
concatenating the four files into one, with `image: null` on the text-only tasks so
the combined file has a consistent schema, then a train/val split.

One LoRA adapter is trained across all four tasks together (matches
`llm.brief.yaml`'s own framing: "one model for all... jobs"), so the model learns to
route its behaviour from the prompt's own content, exactly as the teacher already
does with a single model.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATASET_DIR = DATA_DIR / "dataset"
CHECKPOINTS_DIR = Path(__file__).resolve().parents[1] / "checkpoints"
BASE_MODEL = CHECKPOINTS_DIR / "smolvlm2-500m-mlx"
ADAPTER_OUT = CHECKPOINTS_DIR / "distilled-adapter"

TASKS = ["pole_naming", "noun_forms", "narrative", "vlm_assess"]
VAL_FRACTION = 0.15
SEED = 0


def load_combined() -> list[dict]:
    """One record per example, with a `task` label carried through for Phase 3.

    `mlx_vlm.lora`'s `transform_dataset_to_messages` only reads `question`/
    `answer`/`image` by name (see `mlx_vlm/lora.py`), so the extra `task` and
    `lang` columns ride along untouched -- ignored during training, read back by
    `04_evaluate.py` to score each held-out example against its own task.
    """
    examples = []
    for task in TASKS:
        path = DATASET_DIR / f"{task}.jsonl"
        if not path.exists():
            print(f"warning: {path} missing, skipping {task}", file=sys.stderr)
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                ex = json.loads(line)
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


def main() -> None:
    examples = load_combined()
    if not examples:
        print("No examples found; run 02_generate_dataset.py first.", file=sys.stderr)
        sys.exit(1)

    rng = random.Random(SEED)
    rng.shuffle(examples)
    n_val = max(1, int(len(examples) * VAL_FRACTION))
    val, train = examples[:n_val], examples[n_val:]

    # A dedicated, clean subdirectory: `load_dataset(dir)` auto-discovers every
    # json/jsonl file in the given directory, so the per-task files and the
    # images/ subdirectory in DATASET_DIR must NOT be visible from here.
    combined_dir = DATASET_DIR / "combined"
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
            f"Base model not found at {BASE_MODEL}; run the Phase 0 conversion first.",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = [
        sys.executable,
        str(Path(__file__).parent / "run_lora.py"),
        "--model-path",
        str(BASE_MODEL),
        "--dataset",
        str(combined_dir),
        "--train-vision",  # vlm_assess needs the vision stack to actually learn, not just the LM
        "--iters",
        "600",
        "--batch-size",
        "2",
        "--learning-rate",
        "1e-4",
        "--lora-rank",
        "16",
        "--lora-alpha",
        "32",
        "--steps-per-report",
        "10",
        "--steps-per-save",
        "100",
        "--output-path",
        str(ADAPTER_OUT),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
