"""Phase 1b: turn the generated tables into the distillation dataset (JSONL, per task).

Rather than reconstructing standpoint's internal prompts by hand (a drift risk if
`standpoint/__init__.py` ever changes them), this monkeypatches
`best_engine_ai_helper.llm.chat` -- the one call boundary every one of standpoint's
LLM/VLM jobs goes through -- to *capture* the exact (prompt, images, schema,
response) of each real call made while running the genuine pipeline functions
(`axis_poles`, `noun_forms`, `suggest_ratings`, `vlm_assess`). The captured calls
become training examples with guaranteed fidelity to production behaviour.
(`analysis_markdown` / the `narrative` task is gone for good: the feature was
removed from standpoint itself, so nothing generates or trains on it anymore.)

`vlm_assess` negatives (the leader dot genuinely NOT top-right) are the one
exception: rather than trust the teacher's own judgement on a doctored image (this
is exactly the judgement small VLMs are weakest at -- asking it to *label* a hard
case risks a wrong label), the "best" and "worst" roles are swapped before
rendering, which deterministically moves the red dot to the "worst" point's
position (geometrically the far corner from the reference) -- the correct verdict
is then known by construction, not asked of any model.

Output: ``distillation/data/dataset/{pole_naming,noun_forms,suggest_ratings,vlm_assess}.jsonl``
plus ``distillation/data/dataset/images/`` for the vlm_assess image files.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import best_engine_ai_helper.llm as llm_module
import pandas as pd

import standpoint as sp

SCRIPTS_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPTS_DIR.parent / "data"
TABLES_DIR = DATA_DIR / "tables"
OUT_DIR = DATA_DIR / "dataset"
IMAGES_DIR = OUT_DIR / "images"


def _load_module(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Reuse every 01*_generate_tables*.py script's subject list as the single source of
# truth for each table's language, keyed by its filename's numeric prefix -- rather
# than re-detecting or duplicating it here.
_gen_tables = _load_module("gen_tables", "01_generate_tables.py")
_gen_tables_web = _load_module("gen_tables_web", "01b_generate_tables_from_web.py")
_gen_tables_more = _load_module("gen_tables_more", "01c_generate_tables_more.py")
_gen_tables_final = _load_module("gen_tables_final", "01d_generate_tables_final.py")
SUBJECT_LANG: dict[int, str] = {}
SUBJECT_NAME: dict[int, str] = {}
for i, (subject, lang) in enumerate(_gen_tables.SUBJECTS):
    SUBJECT_LANG[i], SUBJECT_NAME[i] = lang, subject
for i, (subject, lang, _options) in enumerate(_gen_tables_web.WEB_SUBJECTS):
    idx = _gen_tables_web.START_INDEX + i
    SUBJECT_LANG[idx], SUBJECT_NAME[idx] = lang, subject
for i, (subject, lang) in enumerate(_gen_tables_more.SUBJECTS):
    idx = _gen_tables_more.START_INDEX + i
    SUBJECT_LANG[idx], SUBJECT_NAME[idx] = lang, subject
for i, (subject, lang) in enumerate(_gen_tables_final.SUBJECTS):
    idx = _gen_tables_final.START_INDEX + i
    SUBJECT_LANG[idx], SUBJECT_NAME[idx] = lang, subject

# 01e_generate_tables_translated.py's subjects aren't a module-level constant (they
# depend on which EN tables its main() picked+translated at run time, seeded-random
# -- see that script's docstring), so they're read from its persisted manifest
# instead of imported.
_translated_manifest = TABLES_DIR / "translated_manifest.json"
if _translated_manifest.exists():
    for idx_str, (subject, lang) in json.loads(_translated_manifest.read_text()).items():
        SUBJECT_LANG[int(idx_str)], SUBJECT_NAME[int(idx_str)] = lang, subject

PROCESSED_LOG = OUT_DIR / ".processed"

# `vlm_assess()`'s per-language ground-truth notes for the deterministic negative
# example (see `vlm_assess_negative_example` -- the verdict is known by construction,
# not asked of the teacher, so the notes text is written by hand, one per language).
VLM_ASSESS_NEGATIVE_NOTES = {
    "en": "The red-highlighted dot is not in the top-right area of the map.",
    "fr": "Le point rouge en surbrillance n'est pas dans la zone haut-droite de la carte.",
}

# --------------------------------------------------------------------------- #
# capture: monkeypatch the one call boundary every standpoint LLM/VLM job uses
# --------------------------------------------------------------------------- #
_real_chat = llm_module.chat
_captured: list[dict] = []


def _capturing_chat(
    prompt: str,
    *,
    images: list[bytes] | None = None,
    json_schema: dict | None = None,
    **kwargs: object,
) -> str | dict:
    response = _real_chat(prompt, images=images, json_schema=json_schema, **kwargs)
    _captured.append(
        {"prompt": prompt, "images": images, "json_schema": json_schema, "response": response}
    )
    return response


llm_module.chat = _capturing_chat


def _harvest_one() -> dict:
    """Pop and return the single call captured since the last `_captured.clear()`."""
    if len(_captured) != 1:
        raise RuntimeError(f"expected exactly 1 captured call, got {len(_captured)}")
    call = _captured[0]
    _captured.clear()
    return call


# --------------------------------------------------------------------------- #
# per-task example builders
# --------------------------------------------------------------------------- #
def pole_naming_example(result: sp.PCAResult, lang: str) -> dict:
    _captured.clear()
    poles = sp.axis_poles(result, lang=lang)
    call = _harvest_one()
    return {
        "lang": lang,
        "question": call["prompt"],
        "answer": json.dumps(call["response"], ensure_ascii=False),
        "json_schema": call["json_schema"],
        "poles": poles,
    }


def noun_forms_examples(subject: str, lang: str) -> list[dict]:
    examples = []
    # auto-detected language
    _captured.clear()
    sp.noun_forms(subject, lang=lang)
    call = _harvest_one()
    examples.append(
        {
            "lang": lang,
            "question": call["prompt"],
            "answer": json.dumps(call["response"], ensure_ascii=False),
            "json_schema": call["json_schema"],
        }
    )
    # forced cross-language override (the regression this session's own tests guard)
    other = "fr" if lang == "en" else "en"
    _captured.clear()
    sp.noun_forms(subject, lang=other)
    call = _harvest_one()
    examples.append(
        {
            "lang": other,
            "question": call["prompt"],
            "answer": json.dumps(call["response"], ensure_ascii=False),
            "json_schema": call["json_schema"],
        }
    )
    return examples


def suggest_ratings_example(df: pd.DataFrame, lang: str) -> dict:
    """Capture one GUI-style "Flemme" auto-fill call: names in, full ratings matrix out.

    Uses the parsed table BEFORE `resolve_polarity` so the option/criterion names
    match what a GUI user actually typed (polarity markers and all), which is the
    exact input `suggest_ratings` sees in production.
    """
    _captured.clear()
    noun = str(df.index.name or "Option")
    options = [str(o) for o in df.index]
    criteria = [str(c) for c in df.columns]
    sp.suggest_ratings(noun, options, criteria, lang=lang)
    call = _harvest_one()
    return {
        "lang": lang,
        "question": call["prompt"],
        "answer": json.dumps(call["response"], ensure_ascii=False),
        "json_schema": call["json_schema"],
    }


def vlm_assess_positive_example(
    result: sp.PCAResult, roles: list[str], poles: list[str], image_path: Path, lang: str
) -> dict:
    svg = sp.to_svg(result, roles=roles, poles=poles)
    png = sp.png_on_white(svg)
    image_path.write_bytes(png)
    _captured.clear()
    sp.vlm_assess(png, lang=lang)
    call = _harvest_one()
    return {
        "lang": lang,
        "question": call["prompt"],
        "image": str(image_path),
        "answer": json.dumps(call["response"], ensure_ascii=False),
    }


def vlm_assess_negative_example(
    result: sp.PCAResult, roles: list[str], poles: list[str], image_path: Path, lang: str
) -> dict | None:
    """Swap best/worst roles so the red dot moves off the top-right, deterministically.

    The ground-truth verdict is known by construction (the leader dot is at the
    "worst" point's real coordinates, geometrically far from the reference corner),
    so the teacher is not asked to judge this image -- see module docstring.
    """
    if "best" not in roles or "worst" not in roles:
        return None
    wrong_roles = roles.copy()
    best_i, worst_i = roles.index("best"), roles.index("worst")
    wrong_roles[best_i], wrong_roles[worst_i] = wrong_roles[worst_i], wrong_roles[best_i]
    svg = sp.to_svg(result, roles=wrong_roles, poles=poles)
    png = sp.png_on_white(svg)
    image_path.write_bytes(png)
    verdict = {
        "leader_top_right": False,
        "readable": True,
        "axis_labels_visible": True,
        "notes": VLM_ASSESS_NEGATIVE_NOTES[lang],
    }
    question = sp.i18n(lang)["vlm_assess_prompt"]
    return {
        "lang": lang,
        "question": question,
        "image": str(image_path),
        "answer": json.dumps(verdict, ensure_ascii=False),
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--shard-id",
        type=int,
        default=None,
        help="This worker's shard (0-indexed). Requires --num-shards. Writes to "
        "<task>.shard<N>.jsonl and .processed.shard<N> instead of the shared files, "
        "so concurrent shards never write the same file (JSONL lines, especially "
        "narrative text, can exceed the OS's atomic-write size, so two processes "
        "appending to one shared file risks interleaved/corrupted lines) -- merge "
        "with merge_shards.py once all shards finish.",
    )
    ap.add_argument("--num-shards", type=int, default=None)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    sharded = args.shard_id is not None
    if sharded and (args.num_shards is None or not (0 <= args.shard_id < args.num_shards)):
        print("--shard-id requires --num-shards and 0 <= shard-id < num-shards", file=sys.stderr)
        sys.exit(1)
    suffix = f".shard{args.shard_id}" if sharded else ""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    sinks = {
        name: (OUT_DIR / f"{name}{suffix}.jsonl").open("a", encoding="utf-8")
        for name in ("pole_naming", "noun_forms", "suggest_ratings", "vlm_assess")
    }
    shard_log = OUT_DIR / f".processed{suffix}"
    csv_paths = sorted(TABLES_DIR.glob("*.csv"))
    if not csv_paths:
        print(f"No tables found in {TABLES_DIR}; run 01_generate_tables.py first.", file=sys.stderr)
        sys.exit(1)

    # Resumable: a table already recorded in the SHARED log (any prior run, sharded
    # or not) is skipped everywhere, so shards never duplicate work a previous
    # single-process run already did.
    processed = set(PROCESSED_LOG.read_text().split()) if PROCESSED_LOG.exists() else set()
    todo = [p for p in csv_paths if p.stem not in processed]
    if sharded:
        todo = [p for p in todo if int(p.stem.split("_", 1)[0]) % args.num_shards == args.shard_id]
    print(
        f"{len(csv_paths)} tables total, {len(processed)} already processed, "
        f"{len(todo)} to do{f' (shard {args.shard_id}/{args.num_shards})' if sharded else ''}."
    )

    counts = dict.fromkeys(sinks, 0)
    for n, csv_path in enumerate(todo, 1):
        idx = int(csv_path.stem.split("_", 1)[0])
        subject, lang = SUBJECT_NAME[idx], SUBJECT_LANG[idx]
        print(f"[{n}/{len(todo)}] {csv_path.name} ({lang})...", flush=True)
        try:
            df_raw = sp.parse_table(str(csv_path))
            df, lower = sp.resolve_polarity(df_raw)
            result = sp.analyze(df, reference=0, lower_is_better=list(lower))
            roles = sp.assign_roles(result)

            pole_ex = pole_naming_example(result, lang)
            sinks["pole_naming"].write(json.dumps(pole_ex, ensure_ascii=False) + "\n")
            counts["pole_naming"] += 1
            poles = pole_ex["poles"]  # reused below, no second (expensive) axis_poles() call

            for ex in noun_forms_examples(subject.split()[-1].title(), lang):
                sinks["noun_forms"].write(json.dumps(ex, ensure_ascii=False) + "\n")
                counts["noun_forms"] += 1

            ex = suggest_ratings_example(df_raw, lang)
            sinks["suggest_ratings"].write(json.dumps(ex, ensure_ascii=False) + "\n")
            counts["suggest_ratings"] += 1

            pos_path = IMAGES_DIR / f"{csv_path.stem}_pos.png"
            ex = vlm_assess_positive_example(result, roles, poles, pos_path, lang)
            sinks["vlm_assess"].write(json.dumps(ex, ensure_ascii=False) + "\n")
            counts["vlm_assess"] += 1

            neg_path = IMAGES_DIR / f"{csv_path.stem}_neg.png"
            ex = vlm_assess_negative_example(result, roles, poles, neg_path, lang)
            if ex is not None:
                sinks["vlm_assess"].write(json.dumps(ex, ensure_ascii=False) + "\n")
                counts["vlm_assess"] += 1

            with shard_log.open("a", encoding="utf-8") as f:
                f.write(csv_path.stem + "\n")
        except Exception as exc:
            # not logged as processed: a table that errors this run is retried next run
            print(f"  !! skipped {csv_path.name}: {exc}", file=sys.stderr)
        finally:
            for f in sinks.values():
                f.flush()

    for f in sinks.values():
        f.close()
    print(f"\nDone. {counts}")


if __name__ == "__main__":
    main()
