"""Phase 1a: synthesize diverse EN/FR comparison tables for the distillation dataset.

Domain/subject diversity is curated by hand rather than left to the teacher model to
invent (LLMs asked to "come up with a topic" tend to converge on a handful of generic
ones) -- each subject is then filled in by one real, structured call to the current
teacher engine (the same ``best_engine_ai_helper`` pipeline standpoint itself uses),
producing realistic option names, criteria names, and a plausible ratings matrix.

Output: ``distillation/data/tables/<index>_<slug>.csv``, one real standpoint-shaped
input table per file, ready for Phase 1b to run through the actual pipeline.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from best_engine_ai_helper import llm

import standpoint as sp

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "tables"

# (subject, language) pairs. Broader than the 4 committed examples/*.csv, still
# realistic domains a positioning map would plausibly be made for.
SUBJECTS: list[tuple[str, str]] = [
    ("laptops", "en"),
    ("noise-cancelling headphones", "en"),
    ("project management tools", "en"),
    ("meal kit delivery services", "en"),
    ("running shoes", "en"),
    ("web browsers", "en"),
    ("coffee makers", "en"),
    ("smartwatches", "en"),
    ("video conferencing tools", "en"),
    ("static site generators", "en"),
    ("robot vacuum cleaners", "en"),
    ("budget airlines", "en"),
    ("password managers", "en"),
    ("electric scooters", "en"),
    ("standing desks", "en"),
    ("restaurants francais", "fr"),
    ("voitures citadines", "fr"),
    ("smartphones", "fr"),
    ("banques en ligne", "fr"),
    ("plateformes de streaming video", "fr"),
    ("machines a cafe", "fr"),
    ("velos electriques", "fr"),
    ("ecoles de commerce", "fr"),
    ("applications de covoiturage", "fr"),
    ("chaines de television", "fr"),
    ("marques de yaourt", "fr"),
    ("compagnies aeriennes low-cost", "fr"),
    ("logiciels de comptabilite", "fr"),
    ("montres connectees", "fr"),
    ("services de streaming musical", "fr"),
]

TABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "options": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 7},
        "criteria": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 6},
        "ratings": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 5}},
        },
    },
    "required": ["options", "criteria", "ratings"],
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def generate_table(subject: str, lang: str) -> dict:
    """Ask the teacher engine for realistic options/criteria/ratings for one subject."""
    if lang == "fr":
        prompt = (
            f"Tu compares des '{subject}' reels et bien connus. Choisis entre 4 et 7 options "
            "(noms reels de produits/marques/services, pas de noms generiques), entre 4 et 6 "
            "criteres de comparaison pertinents (en francais), et donne une note realiste de 1 a 5 "
            "(5 = meilleur) pour chaque option sur chaque critere, refletant leur reputation reelle. "
            'Reponds en JSON: {"options": [...], "criteria": [...], "ratings": [[...], ...]} '
            "ou ratings[i] correspond a options[i], dans l'ordre de criteria."
        )
    else:
        prompt = (
            f"You are comparing real, well-known '{subject}'. Pick between 4 and 7 options (real "
            "product/brand/service names, not generic placeholders), between 4 and 6 relevant "
            "comparison criteria, and give a realistic 1-5 rating (5 = best) for each option on "
            "each criterion, reflecting their real-world reputation. "
            'Respond as JSON: {"options": [...], "criteria": [...], "ratings": [[...], ...]} '
            "where ratings[i] matches options[i], in the order of criteria."
        )
    data = llm.chat(
        prompt, engine=sp.engine(), kind="vlm", json_schema=TABLE_SCHEMA, temperature=0.7
    )
    if not isinstance(data, dict):
        raise ValueError(f"non-JSON response for {subject!r}: {data!r}")
    return data


def write_csv(path: Path, subject: str, data: dict) -> None:
    options, criteria, ratings = data["options"], data["criteria"], data["ratings"]
    if len(options) != len(ratings) or any(len(row) != len(criteria) for row in ratings):
        raise ValueError(
            f"{subject}: ratings shape mismatch (options={len(options)}, "
            f"criteria={len(criteria)}, ratings={[len(r) for r in ratings]})"
        )
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Option", *criteria])
        for name, row in zip(options, ratings, strict=True):
            w.writerow([name, *row])


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ok, failed = 0, []
    for i, (subject, lang) in enumerate(SUBJECTS):
        slug = _slugify(subject)
        out_path = DATA_DIR / f"{i:02d}_{slug}.csv"
        if out_path.exists():
            print(f"[skip] {out_path.name} already exists")
            ok += 1
            continue
        print(f"[{i + 1}/{len(SUBJECTS)}] generating {subject!r} ({lang})...", flush=True)
        try:
            data = generate_table(subject, lang)
            write_csv(out_path, subject, data)
            print(
                f"  -> {out_path.name}: {len(data['options'])} options x {len(data['criteria'])} criteria"
            )
            ok += 1
        except Exception as exc:  # a bad/malformed teacher response for one subject
            print(f"  !! failed: {exc}", file=sys.stderr)
            failed.append(subject)
    print(f"\n{ok}/{len(SUBJECTS)} tables generated. Failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
