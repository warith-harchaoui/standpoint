"""Backfill French `vlm_assess` examples, reusing the images already on disk.

`standpoint.vlm_assess()` gained a `lang` parameter this session (previously
English-only in production, so `02_generate_dataset.py` sent a hardcoded English
prompt for every table regardless of the table's own language). The existing
`data/dataset/vlm_assess.jsonl` (1452 examples, no `lang` field) still serves the
English track fine as-is -- it is not touched here. This script only adds the
missing French counterpart: for each table tagged `lang == "fr"` (388 of the 731
on disk), it reuses the chart PNGs `02_generate_dataset.py` already rendered
(`data/dataset/images/{stem}_pos.png` / `_neg.png`) -- for a French table those
were already drawn with French pole labels (the table's own `lang` drove
`axis_poles()` at generation time), so there is nothing to re-render, only a
fresh *French-language* verdict to collect. The positive example costs one live
teacher VLM call each (~388 calls, image unchanged, prompt now French); the
negative example is deterministic (ground truth known by construction, see
`02_generate_dataset.py::vlm_assess_negative_example`), no call. Appends to the
*same* `vlm_assess.jsonl`, distinguishing rows by the now-present `lang` field --
the same convention `pole_naming.jsonl`/`noun_forms.jsonl` already use.

Resumable via its own log (`data/dataset/.processed_vlm_assess_fr`), independent
of `02_generate_dataset.py`'s combined `.processed` log (which tracks all four
tasks together and must not be touched here, or old tables would be reprocessed
for pole_naming/noun_forms/narrative too).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("gen_dataset", SCRIPTS_DIR / "02_generate_dataset.py")
gen_dataset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_dataset)  # builds SUBJECT_LANG/SUBJECT_NAME, patches llm.chat, captures

import standpoint as sp  # noqa: E402  (after sys.path is set up by the exec_module above)

TABLES_DIR = gen_dataset.TABLES_DIR
IMAGES_DIR = gen_dataset.IMAGES_DIR
OUT_DIR = gen_dataset.OUT_DIR
SINK_PATH = OUT_DIR / "vlm_assess.jsonl"
PROCESSED_LOG = OUT_DIR / ".processed_vlm_assess_fr"


def vlm_assess_positive_fr(image_path: Path) -> dict:
    """Re-verdict an existing chart PNG in French, without re-rendering it."""
    png = image_path.read_bytes()
    gen_dataset._captured.clear()
    sp.vlm_assess(png, lang="fr")
    call = gen_dataset._harvest_one()
    return {
        "lang": "fr",
        "question": call["prompt"],
        "image": str(image_path),
        "answer": json.dumps(call["response"], ensure_ascii=False),
    }


def vlm_assess_negative_fr(image_path: Path) -> dict:
    """Deterministic French negative verdict for an existing 'wrong roles' chart PNG."""
    verdict = {
        "leader_top_right": False,
        "readable": True,
        "axis_labels_visible": True,
        "notes": gen_dataset.VLM_ASSESS_NEGATIVE_NOTES["fr"],
    }
    return {
        "lang": "fr",
        "question": sp.i18n("fr")["vlm_assess_prompt"],
        "image": str(image_path),
        "answer": json.dumps(verdict, ensure_ascii=False),
    }


def main() -> None:
    fr_tables = [
        p
        for p in sorted(TABLES_DIR.glob("*.csv"))
        if gen_dataset.SUBJECT_LANG.get(int(p.stem.split("_", 1)[0])) == "fr"
    ]
    processed = set(PROCESSED_LOG.read_text().split()) if PROCESSED_LOG.exists() else set()
    todo = [p for p in fr_tables if p.stem not in processed]
    print(f"{len(fr_tables)} French tables total, {len(processed)} already done, {len(todo)} to do.")

    counts = 0
    with SINK_PATH.open("a", encoding="utf-8") as sink:
        for n, csv_path in enumerate(todo, 1):
            print(f"[{n}/{len(todo)}] {csv_path.name}...", flush=True)
            pos_path = IMAGES_DIR / f"{csv_path.stem}_pos.png"
            neg_path = IMAGES_DIR / f"{csv_path.stem}_neg.png"
            if not pos_path.exists():
                print(f"  !! missing {pos_path.name}, skipped", file=sys.stderr)
                continue
            try:
                ex = vlm_assess_positive_fr(pos_path)
                sink.write(json.dumps(ex, ensure_ascii=False) + "\n")
                counts += 1

                if neg_path.exists():
                    ex = vlm_assess_negative_fr(neg_path)
                    sink.write(json.dumps(ex, ensure_ascii=False) + "\n")
                    counts += 1

                sink.flush()
                with PROCESSED_LOG.open("a", encoding="utf-8") as f:
                    f.write(csv_path.stem + "\n")
            except Exception as exc:
                # not logged as processed: a table that errors this run is retried next run
                print(f"  !! skipped {csv_path.name}: {exc}", file=sys.stderr)

    print(f"\nDone. {counts} French vlm_assess examples appended to {SINK_PATH}")


if __name__ == "__main__":
    main()
