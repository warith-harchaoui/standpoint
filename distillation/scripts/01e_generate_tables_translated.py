"""Phase 1a (parity pass): translate EN tables to FR to close the pole_naming /
narrative language gap.

`02_generate_dataset.py` tags each generated example with its source table's
language (via `SUBJECT_LANG`), and `pole_naming`/`narrative` each get exactly one
example per successfully processed table -- so their EN/FR balance directly
mirrors the EN/FR split of the *tables themselves*. The 01/01b/01c/01d subject
lists are EN-skewed (357 en vs 217 fr), which is why the combined dataset ended up
349/208 for pole_naming and 349/178 for narrative instead of parity (`noun_forms`
is unaffected -- it always emits one example in the table's own language and one
in the forced cross-language override, per table, regardless of table language).

Rather than generate 171 brand-new FR tables from scratch (another full teacher
call each, inventing new realistic ratings), this **translates** 171 already-
generated EN tables (`data/tables/*.csv`, en-tagged) into FR: only the subject
title and criteria names go through the teacher's translation, in one JSON-schema
call per table. Option names are left untouched -- they are real product/brand
names (e.g. "MacBook Pro", "Dell XPS 13"), which don't translate, and translating
them would make the table read as fake. Ratings are copied unchanged: a laptop's
real-world battery-life reputation doesn't change with the language of the label
next to it. This is also cheaper and more faithful than fabricating a second,
independent French rating for the same real-world options.

New tables get fresh indices continuing `01d_generate_tables_final.py`'s range
(295..465, so this starts at 466 -- checked against the actual max index in use,
not assumed, since table counts don't perfectly match subject-list lengths when a
few subjects fail to generate).
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

from best_engine_ai_helper import llm

import standpoint as sp

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "tables"
START_INDEX = 574  # one past the highest index in use across 01/01b/01c/01d
N_TO_TRANSLATE = 171  # closes the narrative en/fr gap (349 - 178); see module docstring
SEED = 42
# `02_generate_dataset.py` builds its SUBJECT_LANG/SUBJECT_NAME dicts by importing
# each 01*.py script and reading its module-level `SUBJECTS` constant -- but this
# script's subjects are only known once main() has picked+translated them at run
# time, which 02_generate_dataset.py's import-only `_load_module` never triggers.
# Persisted here instead, so 02_generate_dataset.py can load it as data regardless
# of whether this script's main() ran in the same process.
MANIFEST_PATH = DATA_DIR / "translated_manifest.json"

TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "criteria": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "criteria"],
}

# Subjects registered here for 02_generate_dataset.py to pick up (see that
# script's SUBJECT_LANG loading loop) -- filled in by main() as translation
# succeeds, not hardcoded, since which source tables get picked is seeded-random.
SUBJECTS: list[tuple[str, str]] = []


def _en_csv_paths() -> list[Path]:
    """EN-tagged table CSVs on disk, identified via the four upstream subject lists."""
    import importlib.util

    def load(name: str, filename: str):
        spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / filename)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    a = load("_a", "01_generate_tables.py")
    b = load("_b", "01b_generate_tables_from_web.py")
    c = load("_c", "01c_generate_tables_more.py")
    d = load("_d", "01d_generate_tables_final.py")
    lang: dict[int, str] = {}
    for i, (_s, lg) in enumerate(a.SUBJECTS):
        lang[i] = lg
    for i, (_s, lg, _o) in enumerate(b.WEB_SUBJECTS):
        lang[b.START_INDEX + i] = lg
    for i, (_s, lg) in enumerate(c.SUBJECTS):
        lang[c.START_INDEX + i] = lg
    for i, (_s, lg) in enumerate(d.SUBJECTS):
        lang[d.START_INDEX + i] = lg

    csvs = sorted(DATA_DIR.glob("*.csv"))
    return [p for p in csvs if lang.get(int(p.stem.split("_", 1)[0])) == "en"]


def translate_table(title: str, criteria: list[str]) -> dict:
    """Ask the teacher to translate a table's title + criteria to French only."""
    prompt = (
        "Traduis en francais UNIQUEMENT le titre et les criteres suivants d'un "
        "tableau de comparaison (ne traduis PAS de noms de produits/marques, il n'y "
        "en a pas ici -- seulement du texte descriptif). Garde le meme nombre de "
        f"criteres, dans le meme ordre.\nTitre: {title}\nCriteres: {criteria}\n"
        'Reponds en JSON: {"title": "...", "criteria": ["...", ...]}'
    )
    data = llm.chat(
        prompt, engine=sp.engine(), kind="vlm", json_schema=TRANSLATE_SCHEMA, temperature=0.3
    )
    if not isinstance(data, dict):
        raise ValueError(f"non-JSON translation response: {data!r}")
    return data


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    en_paths = _en_csv_paths()
    rng = random.Random(SEED)
    rng.shuffle(en_paths)
    if len(en_paths) < N_TO_TRANSLATE:
        print(f"only {len(en_paths)} en tables available, need {N_TO_TRANSLATE}", file=sys.stderr)
    picks = en_paths[:N_TO_TRANSLATE]

    manifest: dict[str, list] = (
        json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}
    )

    ok, failed = 0, []
    for offset, src_path in enumerate(picks):
        idx = START_INDEX + offset
        subject = src_path.stem.split("_", 1)[1]
        out_path = DATA_DIR / f"{idx:03d}_{subject}-fr.csv"
        if out_path.exists():
            print(f"[skip] {out_path.name} already exists")
            ok += 1
            SUBJECTS.append((subject, "fr"))
            manifest[str(idx)] = [subject, "fr"]
            continue
        with src_path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        title, criteria = rows[0][0], rows[0][1:]
        option_rows = rows[1:]
        print(f"[{offset + 1}/{len(picks)}] translating {src_path.name}...", flush=True)
        try:
            translated = translate_table(title, criteria)
            new_criteria = translated["criteria"]
            if len(new_criteria) != len(criteria):
                raise ValueError(
                    f"criteria count mismatch: {len(criteria)} -> {len(new_criteria)}"
                )
            with out_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([translated["title"], *new_criteria])
                w.writerows(option_rows)  # option names + ratings copied verbatim
            SUBJECTS.append((subject, "fr"))
            manifest[str(idx)] = [subject, "fr"]
            ok += 1
        except Exception as exc:
            print(f"  !! failed: {exc}", file=sys.stderr)
            failed.append(src_path.name)
        finally:
            MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"\n{ok}/{len(picks)} tables translated. Failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
