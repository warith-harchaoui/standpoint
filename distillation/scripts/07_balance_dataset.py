"""Phase 1c: deduplicate and trim pole_naming/narrative to exact EN/FR parity.

Two independent effects of this session's parity pass need cleaning up before
`03_train_lora.py` builds the combined dataset:

1. **Duplicates.** `02_generate_dataset.py`'s resumable `.processed` log only
   marks a table done after ALL four tasks succeed; a table that wrote its
   `pole_naming` example but then failed narrative/noun_forms stays "unprocessed"
   and gets retried on the next run. 30 such tables from the original run got a
   clean pass this time, leaving 30 exact-duplicate `pole_naming` rows (same
   lang+question, written once as an orphan and once as part of the completed
   table). `narrative` has none (it's the last task-appropriate write before the
   table is marked processed).
2. **Overshoot.** Translating 171 EN tables to FR (`01e_generate_tables_translated.py`)
   was sized to close `narrative`'s larger EN/FR gap; `pole_naming`'s smaller gap
   overshoots as a result -- and after dedup, both tasks still land FR-heavy
   relative to EN (`noun_forms` is untouched: it already gets exactly one EN and
   one FR example per table regardless of the table's own language, so it stays
   balanced by construction).

This trims each task's FR side down to exactly the EN count via seeded random
sampling (seed=42, matching this project's other splits), so
`data/dataset/{pole_naming,narrative}.jsonl` end up EN/FR-balanced before the
train/val split. Rewrites the files in place; run once, before `03_train_lora.py`.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "dataset"
SEED = 42


def _dedupe(examples: list[dict]) -> list[dict]:
    """Keep the last occurrence of each (lang, question) pair."""
    by_key: dict[tuple[str, str], dict] = {}
    for ex in examples:
        by_key[(ex["lang"], ex["question"])] = ex
    return list(by_key.values())


def _balance(examples: list[dict], seed: int) -> list[dict]:
    """Trim the majority language down to the minority's count."""
    en = [e for e in examples if e["lang"] == "en"]
    fr = [e for e in examples if e["lang"] == "fr"]
    n = min(len(en), len(fr))
    rng = random.Random(seed)
    rng.shuffle(en)
    rng.shuffle(fr)
    return en[:n] + fr[:n]


def main() -> None:
    for task in ("pole_naming", "narrative"):
        path = DATA_DIR / f"{task}.jsonl"
        examples = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        before = len(examples)
        examples = _dedupe(examples)
        after_dedupe = len(examples)
        examples = _balance(examples, SEED)
        after_balance = len(examples)
        with path.open("w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        n_en = sum(1 for e in examples if e["lang"] == "en")
        n_fr = sum(1 for e in examples if e["lang"] == "fr")
        print(
            f"{task}: {before} -> {after_dedupe} (deduped) -> {after_balance} "
            f"(balanced: {n_en} en / {n_fr} fr)"
        )


if __name__ == "__main__":
    main()
