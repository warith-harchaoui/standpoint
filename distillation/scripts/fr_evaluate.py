"""French track, Phase 3 equivalent: evaluate the LoRA-fine-tuned Qwen3-VL-2B
against its own held-out French examples.

Mirrors `04_evaluate.py`'s structural-check pattern, via `mlx_vlm` (not `mlx_lm`)
since this track is a vision-language model now (see `fr_train_lora.py`'s module
docstring for the Luth-0.6B -> Qwen3-VL-2B pivot and why).

- **pole_naming / noun_forms**: the same structural invariants `04_evaluate.py`
  reuses from `standpoint`'s own `finalize_poles` checks (JSON-valid, distinct,
  positive, no acronym) -- language-agnostic, reused as-is.

No qualitative (GEval/judge) task on this track: `vlm_assess_fr` was dropped after
a real training crash on Qwen3-VL's image batches (see `fr_train_lora.py`'s module
docstring), and `narrative` is out of scope entirely (the feature is being removed
from standpoint itself) -- so every remaining task here is a structural JSON check,
and no French held-out examples exist for a qualitative task to score.

Held-out examples: `data/dataset/combined_fr/validation.jsonl` (written by
`fr_train_lora.py`'s split, all `lang == "fr"`).

Prints per-task pass rates and writes them to `distillation/data/eval_report_fr.json`
(kept separate from `data/eval_report.json`, the English report).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from mlx_vlm import generate, load
from mlx_vlm.prompt_utils import apply_chat_template

import standpoint as sp

DIST_DIR = Path(__file__).resolve().parents[1]
BASE_MODEL = DIST_DIR / "checkpoints" / "qwen3-vl-2b-mlx-bf16"  # matches fr_train_lora.py
# select_best_checkpoint.py picks the half-epoch snapshot with the lowest Val loss
# and copies it here as a directory (adapter_config.json + adapters.safetensors) --
# same layout mlx_vlm.trainer.utils.apply_lora_layers requires for the English
# adapter too, so this script reuses it unmodified.
ADAPTER = DIST_DIR / "checkpoints" / "distilled-adapter-fr" / "best-adapter"
VAL_PATH = DIST_DIR / "data" / "dataset" / "combined_fr" / "validation.jsonl"
REPORT_PATH = DIST_DIR / "data" / "eval_report_fr.json"

JSON_TASKS = {"pole_naming", "noun_forms"}


# --------------------------------------------------------------------------- #
# structural checks (pole_naming / noun_forms) -- identical to 04_evaluate.py
# --------------------------------------------------------------------------- #
def valid_json(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def pole_naming_ok(candidate: str) -> bool:
    data = valid_json(candidate)
    if data is None or len(data) < 2:
        return False
    words = [sp._content_words(str(v)) for v in data.values() if v]
    for a in range(len(words)):
        for b in range(a + 1, len(words)):
            if words[a] & words[b]:
                return False
    joined = set().union(*words) if words else set()
    return bool(words) and not (joined & sp._NEGATIVE_WORDS)


def noun_forms_ok(candidate: str) -> bool:
    data = valid_json(candidate)
    return data is not None and bool(data.get("singular")) and bool(data.get("plural"))


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def load_val_examples() -> list[dict]:
    if not VAL_PATH.exists():
        print(f"{VAL_PATH} missing; run fr_train_lora.py first.", file=sys.stderr)
        sys.exit(1)
    return [json.loads(line) for line in VAL_PATH.read_text().splitlines() if line.strip()]


def student_answer(model, processor, config, question: str, image: str | None) -> str:
    formatted = apply_chat_template(processor, config, question, num_images=1 if image else 0)
    result = generate(
        model, processor, formatted, image=image, max_tokens=300, verbose=False, temperature=0.0
    )
    return result.text if hasattr(result, "text") else str(result)


def main() -> None:
    if not ADAPTER.exists():
        print(f"{ADAPTER} missing; run fr_train_lora.py first.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {BASE_MODEL.name} + adapter {ADAPTER.name}...")
    model, processor = load(str(BASE_MODEL), adapter_path=str(ADAPTER))
    config = model.config

    examples = load_val_examples()
    print(f"{len(examples)} held-out French examples.\n")

    # task -> list of bool pass/fail (single language here, all "fr")
    scores: dict[str, list[bool]] = defaultdict(list)
    for i, ex in enumerate(examples):
        task = ex.get("task", "unknown")
        candidate = student_answer(model, processor, config, ex["question"], ex.get("image"))

        if task in JSON_TASKS:
            ok = pole_naming_ok(candidate) if task == "pole_naming" else noun_forms_ok(candidate)
        else:
            ok = bool(candidate.strip())

        scores[task].append(ok)
        print(f"[{i + 1}/{len(examples)}] {task}: {'PASS' if ok else 'FAIL'}")

    report = {}
    print("\n--- French Phase 3 report ---")
    for task, oks in sorted(scores.items()):
        rate = sum(oks) / len(oks)
        report[task] = {"pass": sum(oks), "total": len(oks), "rate": rate}
        print(f"{task:12s} {sum(oks):3d}/{len(oks):3d}  ({rate:.0%})")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nWritten to {REPORT_PATH}")


if __name__ == "__main__":
    main()
