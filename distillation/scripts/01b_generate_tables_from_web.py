"""Phase 1a (continued): comparison tables seeded with real, web-sourced option names.

Unlike `01_generate_tables.py` (which lets the teacher invent option names too, from
its own knowledge), this script's option names come from actual 2026 "best of" /
comparison articles and Wikipedia (gathered via web search this session -- see the
distillation branch's commit history for the source list). The teacher is only asked
for criteria names and a plausible ratings matrix, not for the options themselves,
so option-name hallucination is structurally impossible here.

Appends to the same `distillation/data/tables/` corpus as `01_generate_tables.py`,
continuing its index range so Phase 1b treats both as one dataset.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from _table_utils import dedupe_ratings
from best_engine_ai_helper import llm

import standpoint as sp

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "tables"
START_INDEX = 30  # continues 01_generate_tables.py's 0..29

# (subject, language, real option names) -- names sourced from web search, not invented.
WEB_SUBJECTS: list[tuple[str, str, list[str]]] = [
    (
        "laptops",
        "en",
        [
            "MacBook Air",
            "Acer Swift 16 AI",
            "Lenovo Yoga Slim 7i",
            "Samsung Galaxy Book 6 Pro",
            "Microsoft Surface Laptop",
            "Asus Zenbook S 16",
        ],
    ),
    (
        "web browsers",
        "en",
        ["Google Chrome", "Safari", "Microsoft Edge", "Firefox", "Samsung Browser", "Opera"],
    ),
    (
        "voitures electriques",
        "fr",
        [
            "Tesla Model 3",
            "Renault Megane E-Tech",
            "Volkswagen ID.4",
            "Tesla Model Y",
            "Peugeot E-3008",
            "BMW iX",
            "Citroen e-C3",
        ],
    ),
    (
        "cloud storage providers",
        "en",
        [
            "Google Drive",
            "Microsoft OneDrive",
            "Dropbox",
            "iCloud",
            "Sync.com",
            "MEGA",
            "pCloud",
            "IDrive",
        ],
    ),
    (
        "smartphones",
        "fr",
        [
            "Samsung Galaxy S26 Ultra",
            "iPhone 17 Pro Max",
            "Google Pixel 10 Pro",
            "Huawei",
            "Xiaomi",
            "OnePlus",
        ],
    ),
    ("streaming services", "en", ["Netflix", "Disney+", "Max", "Apple TV Plus"]),
    (
        "noise-cancelling headphones",
        "en",
        [
            "Sony WH-1000XM6",
            "Bose QuietComfort Ultra",
            "Sennheiser Momentum 5",
            "Soundcore by Anker",
        ],
    ),
    ("password managers", "en", ["RoboForm", "1Password", "NordPass", "Bitwarden", "Dashlane"]),
    (
        "budget airlines",
        "en",
        ["Southwest Airlines", "Breeze Airways", "Frontier", "Allegiant", "JetBlue"],
    ),
    ("banques en ligne", "fr", ["BoursoBank", "Fortuneo", "Hello bank!", "Monabanq", "Revolut"]),
    (
        "running shoes",
        "en",
        [
            "Asics Novablast 5",
            "Mizuno Wave Rider 30",
            "Saucony Ride 19",
            "Hoka Mach 6",
            "Nike Vomero Premium",
        ],
    ),
    (
        "project management software",
        "en",
        ["monday.com", "Smartsheet", "Wrike", "Asana", "ClickUp"],
    ),
    (
        "VPN services",
        "en",
        ["Surfshark", "Proton VPN", "NordVPN", "ExpressVPN", "Private Internet Access"],
    ),
    ("machines a cafe", "fr", ["De'Longhi", "Philips", "Krups", "Jura", "Nespresso", "Melitta"]),
    ("robot vacuum cleaners", "en", ["Roborock", "Dreame", "iRobot", "Eufy", "Shark"]),
    (
        "handheld gaming consoles",
        "en",
        ["Nintendo Switch 2", "Steam Deck OLED", "ASUS ROG Xbox Ally", "Miyoo Mini Plus"],
    ),
    (
        "compagnies aeriennes low-cost",
        "fr",
        ["Wizz Air", "Ryanair", "Vueling", "Transavia", "TAP Air Portugal"],
    ),
    (
        "meal kit delivery services",
        "en",
        ["HelloFresh", "EveryPlate", "Home Chef", "Green Chef", "Factor"],
    ),
    ("e-readers", "en", ["Kindle Paperwhite", "Kindle Scribe", "Kobo Libra Colour", "Kobo Clara"]),
    (
        "velos electriques",
        "fr",
        ["Decathlon Rockrider", "TENWAYS", "Moustache Bikes", "Trek", "Kalkhoff", "Fiido"],
    ),
]

RATINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 6},
        "ratings": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 5}},
        },
    },
    "required": ["criteria", "ratings"],
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def generate_criteria_and_ratings(subject: str, lang: str, options: list[str]) -> dict:
    """Ask the teacher for criteria + a ratings matrix for a GIVEN, real list of options."""
    joined = ", ".join(options)
    if lang == "fr":
        prompt = (
            f"Voici une liste reelle de '{subject}' : {joined}. Choisis entre 4 et 6 criteres de "
            "comparaison pertinents (en francais), et donne une note realiste de 1 a 5 (5 = meilleur) "
            "pour chaque option sur chaque critere, refletant leur reputation reelle. "
            'Reponds en JSON: {"criteria": [...], "ratings": [[...], ...]} ou ratings[i] '
            f"correspond a l'option n{chr(176)}i dans cet ordre : {joined}."
        )
    else:
        prompt = (
            f"Here is a real list of '{subject}': {joined}. Pick between 4 and 6 relevant comparison "
            "criteria, and give a realistic 1-5 rating (5 = best) for each option on each criterion, "
            "reflecting their real-world reputation. "
            'Respond as JSON: {"criteria": [...], "ratings": [[...], ...]} where ratings[i] matches '
            f"the option at index i in this order: {joined}."
        )
    data = llm.chat(
        prompt, engine=sp.engine(), kind="vlm", json_schema=RATINGS_SCHEMA, temperature=0.4
    )
    if not isinstance(data, dict):
        raise ValueError(f"non-JSON response for {subject!r}: {data!r}")
    return data


def write_csv(path: Path, subject: str, options: list[str], data: dict) -> None:
    criteria, ratings = data["criteria"], data["ratings"]
    if len(options) != len(ratings) or any(len(row) != len(criteria) for row in ratings):
        raise ValueError(
            f"{subject}: ratings shape mismatch (options={len(options)}, "
            f"criteria={len(criteria)}, ratings={[len(r) for r in ratings]})"
        )
    ratings = dedupe_ratings(criteria, ratings)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([subject.title(), *criteria])
        for name, row in zip(options, ratings, strict=True):
            w.writerow([name, *row])


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ok, failed = 0, []
    for offset, (subject, lang, options) in enumerate(WEB_SUBJECTS):
        i = START_INDEX + offset
        slug = _slugify(subject)
        out_path = DATA_DIR / f"{i:02d}_{slug}.csv"
        if out_path.exists():
            print(f"[skip] {out_path.name} already exists")
            ok += 1
            continue
        print(
            f"[{offset + 1}/{len(WEB_SUBJECTS)}] {subject!r} ({lang}, {len(options)} real options)...",
            flush=True,
        )
        try:
            data = generate_criteria_and_ratings(subject, lang, options)
            write_csv(out_path, subject, options, data)
            print(
                f"  -> {out_path.name}: {len(options)} options x {len(data['criteria'])} criteria"
            )
            ok += 1
        except Exception as exc:
            print(f"  !! failed: {exc}", file=sys.stderr)
            failed.append(subject)
    print(f"\n{ok}/{len(WEB_SUBJECTS)} web-sourced tables generated. Failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
