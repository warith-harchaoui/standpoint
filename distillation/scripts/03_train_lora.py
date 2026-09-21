"""Phase 2: combine the per-task JSONL datasets and LoRA-train a 0.6B text model.

**One model per language** (``--lang en`` / ``--lang fr``), plus an optional
bilingual control (``--lang all``). Standpoint's interface runs in one language
at a time, so a visitor only ever downloads one adapter; spending all of a
0.6B-parameter model's capacity on that one language is the point. The bilingual
run exists to measure what specialising actually bought: it sees twice the
schema-shaped supervision (the JSON form of an answer is language-independent),
which is the one thing specialising gives up. `04_evaluate.py --lang` scores each
run on its own held-out split, so the reports are directly comparable.

**The base model differs per language, on purpose.** French trains on
Luth-0.6B-Instruct, a Qwen3-0.6B fine-tuned for French and the holder of the best
French `pole_naming` score this project has measured (94%). English trains on
plain Qwen3-0.6B, where Luth's French specialisation would be a handicap rather
than a help. The bilingual control uses the plain base, which is the neutral one.
Both are Qwen3-0.6B architectures, so both are servable as-is by the WebLLM/MLC
chain the browser build already uses -- the point of the whole exercise, and the
reason this is no longer a vision-language model (see below).

**Text-only, three tasks.** `vlm_assess` was dropped from the distillation after
measuring what the teacher actually produces for it: across all 1480 recorded
examples, `readable` is `true` 1480 times and `axis_labels_visible` is `true`
1480 times -- two constant fields with nothing to learn -- while the third,
`leader_top_right`, is a geometric fact the renderer already knows by
construction. `02_generate_dataset.py` conceded the point itself: it builds that
field's negative examples by swapping the best/worst roles and writing the
verdict by hand, "rather than trust the teacher's own judgement on a doctored
image". So the CLI's `--check` computes that verdict directly from the positions
now, and the student never needs eyes. Dropping it is what makes a 0.6B text
model -- small enough to ship to a browser -- the right shape for this job.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from sklearn.model_selection import train_test_split

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATASET_DIR = DATA_DIR / "dataset"
CHECKPOINTS_DIR = Path(__file__).resolve().parents[1] / "checkpoints"

# Text-only: vlm_assess is out of scope for the student (see module docstring).
TASKS = ["pole_naming", "noun_forms", "suggest_ratings"]
LANGS = ("en", "fr", "all")

# Per-language base model (see module docstring for why they differ).
BASE_MODELS = {
    "en": CHECKPOINTS_DIR / "qwen3-0.6b-mlx-bf16",
    "fr": CHECKPOINTS_DIR / "luth-0.6b-mlx-bf16",
    "all": CHECKPOINTS_DIR / "qwen3-0.6b-mlx-bf16",
}

VAL_FRACTION = 0.15
SEED = 42
EPOCHS = 6  # ~1230 train rows per language: few enough that 3 epochs leaves the
# adapter undertrained. Overfitting past the sweet spot is handled by
# select_best_checkpoint.py picking the lowest-validation-loss snapshot, not by
# stopping early and hoping.
# Batch size 1, with the optimizer stepping on 4 accumulated examples. Not a
# collation worry this time -- a hard limit of this machine. macOS kills a Metal
# command buffer that holds the GPU too long
# ("kIOGPUCommandBufferCallbackErrorImpactingInteractivity"), and one
# forward+backward over a batch of 2 crosses that line here: measured, batch 1
# ran 400 iterations clean at 5.0 GB peak while batch 2 died within the first
# hundred. The cause is the LM head: Qwen3's vocabulary is 151643 wide, so the
# logits for one 940-token example are already 0.29 GB and a batch of 2 doubles
# that inside a single dispatch. Accumulating costs nothing in quality (the
# optimizer still sees 4 examples per step) and is in fact FASTER here --
# 4.4 examples/s against 3.2 at batch 4.
BATCH_SIZE = 1
GRAD_ACCUM = 4


def dataset_dir_for(lang: str) -> Path:
    """Where the train/validation split for `lang` is written."""
    return DATASET_DIR / ("combined" if lang == "all" else f"combined_{lang}")


def adapter_out_for(lang: str) -> Path:
    """Where the trained adapter for `lang` is written."""
    return CHECKPOINTS_DIR / ("distilled-adapter" if lang == "all" else f"distilled-adapter-{lang}")


def load_combined() -> list[dict]:
    """One record per example, with `task`/`lang` labels carried through.

    The trainer reads only `question`/`answer` (see
    `run_lora_text_with_val.py`'s `load_split`), so the extra columns ride along
    untouched and `04_evaluate.py` reads them back to score each held-out example
    against its own task.
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
                        "task": task,
                        "lang": ex.get("lang"),
                    }
                )
    return examples


def split(examples: list[dict]) -> tuple[list[dict], list[dict]]:
    """Train/validation split, each half trimmed to a whole number of batches."""
    train, val = train_test_split(examples, test_size=VAL_FRACTION, random_state=SEED, shuffle=True)
    n_train = (len(train) // BATCH_SIZE) * BATCH_SIZE
    n_val = (len(val) // BATCH_SIZE) * BATCH_SIZE
    return train[:n_train], val[:n_val]  # drop the sub-batch remainder, not worth padding


def parse_args() -> argparse.Namespace:
    """CLI: which language this run specialises in."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--lang",
        choices=LANGS,
        default="all",
        help="train on this language's examples only; 'all' is the bilingual "
        "control (default: %(default)s)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=5e-5,
        help="LoRA learning rate (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lang = args.lang

    examples = load_combined()
    if lang != "all":
        examples = [e for e in examples if e.get("lang") == lang]
    if not examples:
        print(f"No {lang} examples found; run 02_generate_dataset.py first.", file=sys.stderr)
        sys.exit(1)

    train, val = split(examples)
    combined_dir = dataset_dir_for(lang)
    combined_dir.mkdir(parents=True, exist_ok=True)
    for path, rows in (
        (combined_dir / "train.jsonl", train),
        (combined_dir / "validation.jsonl", val),
    ):
        with path.open("w", encoding="utf-8") as f:
            for ex in rows:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"--- {lang} track: {len(train)} train / {len(val)} val -> {combined_dir} ---")

    base_model = BASE_MODELS[lang]
    if not base_model.exists():
        print(
            f"Base model not found at {base_model}; convert it first, e.g.\n"
            f"  python -m mlx_lm convert --hf-path Qwen/Qwen3-0.6B "
            f"--mlx-path {base_model} --dtype bfloat16",
            file=sys.stderr,
        )
        sys.exit(1)

    steps_per_epoch = len(train) // BATCH_SIZE  # batch 1: one iteration per example
    iters = EPOCHS * steps_per_epoch
    half_epoch = max(1, steps_per_epoch // 2)

    cmd = [
        sys.executable,
        str(Path(__file__).parent / "run_lora_text_with_val.py"),  # not mlx_lm's own
        # CLI: that one has no gradient clipping and no NaN guard (see that
        # script's module docstring), both of which this project needed on the
        # vision track and has no reason to give up here
        "--model-path",
        str(base_model),
        "--dataset",
        str(combined_dir),
        "--iters",
        str(iters),
        "--batch-size",
        str(BATCH_SIZE),
        "--gradient-accumulation-steps",
        str(GRAD_ACCUM),
        "--learning-rate",
        str(args.learning_rate),
        "--warmup-steps",
        "60",  # optimizer updates, i.e. ~240 raw iterations at GRAD_ACCUM 4  # ~a third of an epoch: keeps Adam's moment estimates small while
        # the adapter is least stable, the fix that stopped the vision track's
        # stable-then-NaN failure at iter 210
        "--grad-clip",
        "1.0",
        "--lora-rank",
        "16",
        "--lora-scale",
        "20.0",
        "--steps-per-report",
        "100",  # one line per ~100 examples; 10 would bury the log at batch 1
        "--steps-per-save",
        str(half_epoch),  # checkpoint every half epoch...
        "--steps-per-eval",
        str(half_epoch),  # ...on the same cadence validation runs, so every
        # snapshot select_best_checkpoint.py sees has a Val loss to compare
        "--val-batches",
        str(max(1, len(val) // BATCH_SIZE)),  # the whole validation split, as a
        # batch count; NOT -1, which mlx's evaluate() reads as "iterate forever"
        "--output-path",
        str(adapter_out_for(lang)),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
