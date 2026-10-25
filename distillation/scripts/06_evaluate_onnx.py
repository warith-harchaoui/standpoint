"""Evaluate the BROWSER artifact (ONNX q4f16 bundle) on the held-out split.

`04_evaluate.py` scores the bf16 MLX checkpoint -- the thing training produced.
This scores what visitors actually download: the fused, ONNX-exported,
4-bit-quantised bundle laid out by `05_export_browser.py` (and any later
surgery, e.g. vocabulary pruning or int8 embeddings). Same held-out split, same
structural checks -- imported straight from 04 so the two reports are
comparable line for line -- different executable.

This is the go/no-go gate for shipping a reworked bundle: run it once on the
current production bundle for a reference report, again on the candidate, and
compare per task/language. Generation runs through onnxruntime on CPU, exactly
the graph the browser runs (WebGPU changes the kernels, not the numbers that
matter at these tolerances).

Run with the distillation venv::

    .venv/bin/python scripts/06_evaluate_onnx.py \
        --bundle checkpoints/llm-engine --suffix onnx
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import click

DIST_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = DIST_DIR / "scripts"


def _load_eval04():
    """Import 04_evaluate.py by path (its name is not a valid module name)."""
    # 04 imports `standpoint` from the repo checkout, the way running it from
    # the repo root implicitly allows; make that explicit here.
    repo_root = str(DIST_DIR.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    spec = importlib.util.spec_from_file_location("eval04", SCRIPTS / "04_evaluate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval04"] = module
    spec.loader.exec_module(module)
    return module


# No ``exists=True`` on either path: argparse validated neither, and --bundle in
# particular is checked by hand below so the message names the missing graph
# rather than the directory.
@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--bundle",
    type=click.Path(path_type=Path),
    default=DIST_DIR / "checkpoints" / "llm-engine",
    show_default=True,
    help="Browser bundle directory (tokenizer at root, onnx/model_q4f16.onnx).",
)
@click.option(
    "--split",
    "split_path",
    type=click.Path(path_type=Path),
    default=DIST_DIR / "data" / "dataset" / "combined" / "validation.jsonl",
    show_default=True,
    help="Held-out split to score; the default is the bilingual run's.",
)
@click.option(
    "--suffix",
    default="onnx",
    show_default=True,
    help="Report lands in data/eval_report_<suffix>.json.",
)
@click.option(
    "--limit",
    type=int,
    default=0,
    show_default=True,
    help="Score only the first N examples (0 = all).",
)
def main(bundle: Path, split_path: Path, suffix: str, limit: int) -> None:
    """Score the ONNX q4f16 browser bundle on the held-out split.

    \f

    Everything past the form feed is for readers of the source: click renders a
    command's whole docstring in ``--help`` and stops at ``\\f``, so without it
    the Numpy-style block CODING.md Rule 1 asks for would reach the terminal as
    one reflowed paragraph.

    Parameters
    ----------
    bundle : Path
        The browser bundle to score, as laid out by `05_export_browser.py` or
        `08_export_pruned.py`.
    split_path : Path
        The held-out JSONL split (the ``--split`` flag, bound to this name so it
        reads as a path rather than a train/validation split label).
    suffix : str
        Names this run's report and failure log, so a reference bundle and a
        candidate never overwrite each other.
    limit : int
        Score only the first N examples; ``0`` scores the whole split.
    """
    ev = _load_eval04()

    from optimum.onnxruntime import ORTModelForCausalLM
    from transformers import AutoTokenizer

    graph = bundle / "onnx" / "model_q4f16.onnx"
    if not graph.exists():
        print(f"{graph} missing; not a browser bundle.", file=sys.stderr)
        sys.exit(1)
    print(f"Loading {bundle} through onnxruntime (CPU)...")
    tokenizer = AutoTokenizer.from_pretrained(bundle)
    model = ORTModelForCausalLM.from_pretrained(
        bundle, file_name="model_q4f16.onnx", use_cache=True
    )
    # optimum sizes the empty KV-cache tensors as hidden/num_heads for qwen3,
    # but Qwen3 declares an explicit head_dim (128, not 1024/16): honour it.
    if getattr(model.config, "head_dim", None):
        model.embed_size_per_head = model.config.head_dim

    examples = ev.load_val_examples(split_path)
    if limit:
        examples = examples[:limit]
    print(f"{len(examples)} held-out examples.\n")

    scores: dict[tuple[str, str], list[bool]] = defaultdict(list)
    deviations: dict[tuple[str, str], list[float]] = defaultdict(list)
    failures: list[dict] = []
    started = time.time()
    for i, ex in enumerate(examples):
        task = ex.get("task", "unknown")
        lang = ex.get("lang") or "n/a"
        # The same chat template training used (04_evaluate.student_answer), but
        # generated through the ONNX graph instead of mlx.
        inputs = tokenizer.apply_chat_template(
            [{"role": "user", "content": ex["question"]}],
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
        output = model.generate(
            **inputs, max_new_tokens=600, do_sample=False, pad_token_id=tokenizer.eos_token_id
        )
        answer = tokenizer.decode(
            output[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )
        candidate = ev.strip_reasoning(answer)

        if task == "pole_naming":
            ok = ev.pole_naming_ok(candidate)
        elif task == "noun_forms":
            ok = ev.noun_forms_ok(candidate)
        elif task == "suggest_ratings":
            mad = ev.suggest_ratings_deviation(candidate, ex["answer"])
            if mad is not None:
                deviations[(task, lang)].append(mad)
            ok = mad is not None and mad <= ev.RATINGS_MAD_THRESHOLD
        else:
            ok = bool(candidate.strip())

        scores[(task, lang)].append(ok)
        if not ok:
            failures.append(
                {
                    "task": task,
                    "lang": lang,
                    "question": ex["question"],
                    "expected": ex["answer"],
                    "candidate": candidate,
                }
            )
        rate = (time.time() - started) / (i + 1)
        print(
            f"[{i + 1}/{len(examples)}] {task}/{lang}: {'PASS' if ok else 'FAIL'}"
            f"  ({rate:.1f}s/ex)",
            flush=True,
        )

    report = {}
    print(f"\n--- ONNX bundle report ({bundle.name}) ---")
    for (task, lang), oks in sorted(scores.items()):
        rate = sum(oks) / len(oks)
        entry = {"pass": sum(oks), "total": len(oks), "rate": rate}
        line = f"{task:15s} {lang:5s} {sum(oks):3d}/{len(oks):3d}  ({rate:.0%})"
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

    report_path = DIST_DIR / "data" / f"eval_report_{suffix}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nWritten to {report_path}")

    failures_path = DIST_DIR / "data" / f"eval_failures_{suffix}.jsonl"
    failures_path.write_text(
        "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in failures), encoding="utf-8"
    )
    print(f"{len(failures)} failing answers written to {failures_path}")


if __name__ == "__main__":
    main()
