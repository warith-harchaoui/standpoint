"""Phase 3: evaluate the LoRA-fine-tuned model against the teacher, per task.

Held-out examples (`data/dataset/combined/validation.jsonl`, written by
`03_train_lora.py`'s split, each carrying its source `task`/`lang`) are re-run
through the fine-tuned adapter via mlx-vlm, then scored per task:

- **pole_naming / noun_forms**: structural checks reusing standpoint's own
  `finalize_poles` invariants (JSON-valid, distinct, positive, no acronym) -- the
  hard invariants production already enforces regardless of which model answers.
- **narrative / vlm_assess**: DeepEval's `GEval`, judged by the CURRENT (teacher)
  engine via the same `LocalEngineJudge` pattern as `tests/test_eval.py`, comparing
  the distilled model's answer against the recorded teacher answer for the *same*
  input -- a relative quality comparison, not a pass/fail on the distilled output
  alone. `LocalEngineJudge.generate()` accepts DeepEval's optional `schema` kwarg
  and, when present, constrains the teacher's own output via `llm.chat`'s
  `json_schema=` rather than parsing free-text JSON -- a first full run without
  this crashed partway through on a malformed judge response (see the README's
  Phase 2 findings), since a 7B local model asked for free-text JSON occasionally
  gets it wrong and DeepEval has no retry for that.

Prints per-task, per-language pass rates and writes them to
`distillation/data/eval_report.json`. This is the go/no-go report for Phase 4: a
task that clearly underperforms should be dropped from what the exported model is
trusted for (the calling code keeps using the teacher for that one job), not
shipped as silently worse.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from best_engine_ai_helper import llm
from deepeval.metrics import GEval
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams
from mlx_vlm import generate, load
from mlx_vlm.prompt_utils import apply_chat_template

import standpoint as sp

DIST_DIR = Path(__file__).resolve().parents[1]
BASE_MODEL = DIST_DIR / "checkpoints" / "smolvlm2-500m-mlx-bf16"  # matches 03_train_lora.py
# select_best_checkpoint.py picks the half-epoch snapshot with the lowest Val loss
# (not necessarily the last one -- see that script's docstring) and copies it here
# as a directory (adapter_config.json + adapters.safetensors), the layout
# mlx_vlm.trainer.utils.apply_lora_layers requires.
ADAPTER = DIST_DIR / "checkpoints" / "distilled-adapter" / "best-adapter"
VAL_PATH = DIST_DIR / "data" / "dataset" / "combined" / "validation.jsonl"
REPORT_PATH = DIST_DIR / "data" / "eval_report.json"

JSON_TASKS = {"pole_naming", "noun_forms"}
QUALITATIVE_TASKS = {"narrative", "vlm_assess"}


# --------------------------------------------------------------------------- #
# local-engine judge (same pattern as tests/test_eval.py's LocalEngineJudge)
# --------------------------------------------------------------------------- #
class LocalEngineJudge(DeepEvalBaseLLM):
    """DeepEval judge backed by the current teacher engine, not OpenAI.

    `GEval.measure()` calls `generate_with_schema`, whose default (inherited)
    implementation forwards a pydantic `schema` kwarg straight into `generate()`
    (see `deepeval.models.base_model.DeepEvalBaseLLM.generate_with_schema`). Left
    unhandled, `generate()` would fall back to free-text JSON, which the teacher
    model (a 7B local model, not GPT-4-class) occasionally malforms -- confirmed
    live: it crashed the whole eval run around example 109/489 on an unparsable
    JSON string. Passing `schema.model_json_schema()` as `llm.chat`'s
    `json_schema=` instead makes Ollama grammar-constrain the output to that exact
    shape (the same mechanism `standpoint`'s own calling contract already relies
    on), so the result is schema-valid every time; it's then parsed straight into
    the pydantic instance DeepEval's extractor already knows how to unwrap.
    """

    def load_model(self) -> dict:
        return sp.engine()

    def generate(self, prompt: str, schema: type | None = None, **kwargs: object) -> object:
        if schema is not None:
            data = llm.chat(
                prompt,
                engine=self.model,
                kind="vlm",
                temperature=0.0,
                json_schema=schema.model_json_schema(),
            )
            return schema(**data)
        return llm.chat(prompt, engine=self.model, kind="vlm", temperature=0.0)

    async def a_generate(self, prompt: str, **kwargs: object) -> object:
        return self.generate(prompt, **kwargs)

    def get_model_name(self) -> str:
        return "standpoint-local-engine"


QUALITY_JUDGE = GEval(
    name="Distilled vs Teacher Answer Quality",
    criteria=(
        "The input is a task prompt Standpoint's own pipeline sent to its language "
        "model. The actual output is a candidate answer from a small distilled "
        "500M-parameter model; the expected output is the real teacher model's "
        "answer to the exact same prompt. Judge whether the candidate answer is as "
        "good as the teacher's for this task -- same factual grounding, comparable "
        "fluency and correctness, not obviously worse."
    ),
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
    model=LocalEngineJudge(),
    threshold=0.5,
    async_mode=False,
)


# --------------------------------------------------------------------------- #
# structural checks (pole_naming / noun_forms)
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
        print(f"{VAL_PATH} missing; run 03_train_lora.py first.", file=sys.stderr)
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
        print(f"{ADAPTER} missing; run 03_train_lora.py first.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {BASE_MODEL.name} + adapter {ADAPTER.name}...")
    model, processor = load(str(BASE_MODEL), adapter_path=str(ADAPTER))
    config = model.config

    examples = load_val_examples()
    print(f"{len(examples)} held-out examples.\n")

    # (task, lang) -> list of bool pass/fail
    scores: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for i, ex in enumerate(examples):
        task = ex.get("task", "unknown")
        lang = ex.get("lang") or "n/a"
        candidate = student_answer(model, processor, config, ex["question"], ex.get("image"))

        if task in JSON_TASKS:
            ok = pole_naming_ok(candidate) if task == "pole_naming" else noun_forms_ok(candidate)
        elif task in QUALITATIVE_TASKS:
            case = LLMTestCase(
                input=ex["question"], actual_output=candidate, expected_output=ex["answer"]
            )
            QUALITY_JUDGE.measure(case)
            ok = QUALITY_JUDGE.is_successful()
        else:
            ok = bool(candidate.strip())

        scores[(task, lang)].append(ok)
        print(f"[{i + 1}/{len(examples)}] {task}/{lang}: {'PASS' if ok else 'FAIL'}")

    report = {}
    print("\n--- Phase 3 report ---")
    for (task, lang), oks in sorted(scores.items()):
        rate = sum(oks) / len(oks)
        report[f"{task}/{lang}"] = {"pass": sum(oks), "total": len(oks), "rate": rate}
        print(f"{task:12s} {lang:5s} {sum(oks):3d}/{len(oks):3d}  ({rate:.0%})")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nWritten to {REPORT_PATH}")


if __name__ == "__main__":
    main()
