"""Phase 3: evaluate the LoRA-fine-tuned student against the teacher, per task.

Held-out examples (`data/dataset/combined{,_en,_fr}/validation.jsonl`, written by
`03_train_lora.py`'s split, each carrying its source `task`/`lang`) are re-run
through the fine-tuned adapter via mlx-lm, then scored per task with structural
checks that reuse standpoint's own `finalize_poles` invariants -- JSON-valid,
distinct, positive, no acronym -- plus, for `suggest_ratings`, agreement with the
teacher's matrix to within less than one rating step on average. These are the
hard invariants production already enforces regardless of which model answers.

**No judge model, and no Ollama dependency.** The previous version scored
`vlm_assess` with DeepEval's `GEval` driven by the teacher engine. That task left
the distillation entirely (see `03_train_lora.py`'s module docstring: two of its
three fields are constant across all 1480 recorded examples, and the third is a
geometric fact the renderer computes directly), and it was the only qualitative
task left once `narrative` went out of scope. Every remaining task is a
deterministic structural check, so this script now runs offline, in minutes, with
nothing to download and nothing to judge.

Prints per-task, per-language pass rates and writes them to
`distillation/data/eval_report{,_en,_fr}.json`. This is the go/no-go report: a
task that clearly underperforms should be dropped from what the exported model is
trusted for (the calling code keeps using the teacher for that one job), not
shipped as silently worse.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from mlx_lm import generate, load

import standpoint as sp

DIST_DIR = Path(__file__).resolve().parents[1]
# Per-language base models, mirroring 03_train_lora.py's BASE_MODELS.
BASE_MODELS = {
    "en": DIST_DIR / "checkpoints" / "qwen3-0.6b-mlx-bf16",
    "fr": DIST_DIR / "checkpoints" / "luth-0.6b-mlx-bf16",
    "all": DIST_DIR / "checkpoints" / "qwen3-0.6b-mlx-bf16",
}
# select_best_checkpoint.py picks the half-epoch snapshot with the lowest Val loss
# (not necessarily the last one -- see that script's docstring) and copies it into
# best-adapter/ as a directory (adapter_config.json + adapters.safetensors), the
# layout mlx_lm's `load(..., adapter_path=...)` requires.
# Per-language artefacts, mirroring 03_train_lora.py's --lang: one specialist per
# language plus the bilingual control, each scored on its own held-out split so
# the three reports compare like with like.
LANGS = ("en", "fr", "all")


def adapter_for(lang: str) -> Path:
    """The best-checkpoint directory select_best_checkpoint.py wrote for `lang`."""
    stem = "distilled-adapter" if lang == "all" else f"distilled-adapter-{lang}"
    return DIST_DIR / "checkpoints" / stem / "best-adapter"


def val_path_for(lang: str) -> Path:
    """The held-out split 03_train_lora.py wrote for `lang`."""
    stem = "combined" if lang == "all" else f"combined_{lang}"
    return DIST_DIR / "data" / "dataset" / stem / "validation.jsonl"


def report_path_for(lang: str) -> Path:
    """Where this run's go/no-go numbers land."""
    suffix = "" if lang == "all" else f"_{lang}"
    return DIST_DIR / "data" / f"eval_report{suffix}.json"


JSON_TASKS = {"pole_naming", "noun_forms", "suggest_ratings"}


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


RATINGS_MAD_THRESHOLD = 0.75


def suggest_ratings_deviation(candidate: str, expected: str) -> float | None:
    """Mean absolute deviation from the teacher's matrix, or None if unusable.

    None means the student's answer is structurally wrong -- not valid JSON, a
    missing (option, criterion) cell the teacher scored, or a value that is not
    already an integer in 1..5 (production clamps out-of-range values, but a
    student that needs clamping is off-distribution). A float means the matrix
    is complete and well-formed, and says how far it sits from the teacher on a
    subjective 1..5 scale.

    Kept separate from the pass/fail call on purpose: the deviation is the
    informative quantity and the threshold is a judgement call, so the report
    carries both and nobody has to take the threshold on faith.
    """
    data, ref = valid_json(candidate), valid_json(expected)
    if data is None or ref is None:
        return None
    diffs: list[float] = []
    for option, row in ref.items():
        got = data.get(option)
        if not isinstance(got, dict) or not isinstance(row, dict):
            return None
        for criterion, value in row.items():
            g = got.get(criterion)
            if isinstance(g, bool) or not isinstance(g, int) or not 1 <= g <= 5:
                return None
            try:
                v = max(1.0, min(5.0, float(value)))  # teacher raw output, pre-clamp
            except (TypeError, ValueError):
                continue  # unusable teacher cell: skip it rather than fail the student
            diffs.append(abs(g - v))
    return sum(diffs) / len(diffs) if diffs else None


def suggest_ratings_ok(candidate: str, expected: str) -> bool:
    """Complete, in-range ratings matrix agreeing with the teacher closely enough.

    Pass = `suggest_ratings_deviation` returns a mean absolute deviation of at
    most `RATINGS_MAD_THRESHOLD`, i.e. under three quarters of a rating step on
    average, without demanding cell-exact agreement on what is a subjective
    1..5 scale.
    """
    mad = suggest_ratings_deviation(candidate, expected)
    return mad is not None and mad <= RATINGS_MAD_THRESHOLD


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def load_val_examples(val_path: Path) -> list[dict]:
    """Read the held-out split, or exit telling the caller which run is missing."""
    if not val_path.exists():
        print(f"{val_path} missing; run 03_train_lora.py first.", file=sys.stderr)
        sys.exit(1)
    return [json.loads(line) for line in val_path.read_text().splitlines() if line.strip()]


_THINK_RE = re.compile(r"\A\s*<think>.*?</think>\s*", re.DOTALL)
_FENCE_RE = re.compile(r"\A\s*```(?:json)?\s*(.*?)\s*```\s*\Z", re.DOTALL)


def strip_reasoning(text: str) -> str:
    """Remove Qwen3's reasoning block and any code fence around the answer.

    Qwen3's chat template writes an empty `<think></think>` pair in front of
    every assistant turn, so the training targets carry it and the student
    reproduces it -- `{"singular": ...}` arrives as
    `<think>\n\n</think>\n\n{"singular": ...}`. Left in place, every
    structural check fails on JSON that is in fact correct. Anything consuming
    this student in production has to do the same (the browser build included),
    so it belongs in the scoring path rather than being hidden by a looser
    parser.
    """
    text = _THINK_RE.sub("", text)
    fenced = _FENCE_RE.match(text)
    return (fenced.group(1) if fenced else text).strip()


def student_answer(model, tokenizer, question: str) -> str:
    """One greedy completion for `question`, through the same chat template training used.

    `03_train_lora.py` trains on `CompletionsDataset`, which wraps every example
    in the tokenizer's chat template -- so inference has to apply the same
    template, or the student sees a prompt shape it was never trained on.
    """
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": question}],
        add_generation_prompt=True,
        tokenize=False,
    )
    result = generate(model, tokenizer, prompt, max_tokens=600, verbose=False)
    return strip_reasoning(result if isinstance(result, str) else str(result))


def parse_args() -> argparse.Namespace:
    """CLI: which language's run to score."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--lang",
        choices=LANGS,
        default="all",
        help="score the adapter trained on this language (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    adapter = adapter_for(args.lang)
    report_path = report_path_for(args.lang)
    if not adapter.exists():
        print(
            f"{adapter} missing; run 03_train_lora.py --lang {args.lang} first.",
            file=sys.stderr,
        )
        sys.exit(1)

    base_model = BASE_MODELS[args.lang]
    print(f"Loading {base_model.name} + adapter {adapter.parent.name}/{adapter.name}...")
    model, tokenizer = load(str(base_model), adapter_path=str(adapter))

    examples = load_val_examples(val_path_for(args.lang))
    print(f"{len(examples)} held-out {args.lang} examples.\n")

    # (task, lang) -> list of bool pass/fail, and the raw suggest_ratings
    # deviations behind those booleans (see suggest_ratings_deviation).
    scores: dict[tuple[str, str], list[bool]] = defaultdict(list)
    deviations: dict[tuple[str, str], list[float]] = defaultdict(list)
    for i, ex in enumerate(examples):
        task = ex.get("task", "unknown")
        lang = ex.get("lang") or "n/a"
        candidate = student_answer(model, tokenizer, ex["question"])

        if task == "pole_naming":
            ok = pole_naming_ok(candidate)
        elif task == "noun_forms":
            ok = noun_forms_ok(candidate)
        elif task == "suggest_ratings":
            mad = suggest_ratings_deviation(candidate, ex["answer"])
            if mad is not None:
                deviations[(task, lang)].append(mad)
            ok = mad is not None and mad <= RATINGS_MAD_THRESHOLD
        else:
            ok = bool(candidate.strip())

        scores[(task, lang)].append(ok)
        print(f"[{i + 1}/{len(examples)}] {task}/{lang}: {'PASS' if ok else 'FAIL'}")

    report = {}
    print(f"\n--- Phase 3 report ({args.lang}) ---")
    for (task, lang), oks in sorted(scores.items()):
        rate = sum(oks) / len(oks)
        entry = {"pass": sum(oks), "total": len(oks), "rate": rate}
        line = f"{task:12s} {lang:5s} {sum(oks):3d}/{len(oks):3d}  ({rate:.0%})"
        # For suggest_ratings the pass rate hides the interesting number: a
        # matrix can be complete, well-formed and one third of a step away from
        # the teacher, yet fail a threshold set elsewhere. Report the distance.
        mads = deviations.get((task, lang))
        if mads:
            mads_sorted = sorted(mads)
            entry["mad_mean"] = sum(mads) / len(mads)
            entry["mad_median"] = mads_sorted[len(mads_sorted) // 2]
            entry["well_formed"] = len(mads)
            line += (
                f"   MAD mean {entry['mad_mean']:.2f} / median "
                f"{entry['mad_median']:.2f} over {len(mads)} well-formed"
            )
        report[f"{task}/{lang}"] = entry
        print(line)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nWritten to {report_path}")


if __name__ == "__main__":
    main()
