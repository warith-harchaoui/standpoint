"""Phase 1a (scale-up): many more subjects, reaching "hundreds" of tables total.

Same approach as `01_generate_tables.py` (teacher invents real, well-known option
names for a hand-curated subject, from its own knowledge) -- this file exists
separately just to keep the original 30-subject batch's index range undisturbed
while table generation from it may still be running. Continues the index range
after `01b_generate_tables_from_web.py`'s 30..49.
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
START_INDEX = 50  # continues 01b_generate_tables_from_web.py's 30..49

SUBJECTS: list[tuple[str, str]] = [
    # -- tech & software (en) --------------------------------------------- #
    ("tablets", "en"),
    ("smart speakers", "en"),
    ("wireless earbuds", "en"),
    ("mechanical keyboards", "en"),
    ("computer mice", "en"),
    ("4K monitors", "en"),
    ("home printers", "en"),
    ("wifi mesh routers", "en"),
    ("antivirus software", "en"),
    ("note-taking apps", "en"),
    ("to-do list apps", "en"),
    ("calendar apps", "en"),
    ("email clients", "en"),
    ("email marketing platforms", "en"),
    ("CRM software", "en"),
    ("accounting software for small business", "en"),
    ("video editing software", "en"),
    ("photo editing software", "en"),
    ("website builders", "en"),
    ("e-commerce platforms", "en"),
    ("payment processors", "en"),
    ("point-of-sale systems", "en"),
    ("HR software", "en"),
    ("payroll software", "en"),
    ("learning management systems", "en"),
    ("online course platforms", "en"),
    ("webinar platforms", "en"),
    ("e-signature tools", "en"),
    ("form builder tools", "en"),
    ("survey tools", "en"),
    ("search engines", "en"),
    ("messaging apps", "en"),
    ("social media platforms", "en"),
    ("code editors", "en"),
    ("relational databases", "en"),
    ("no-code app builders", "en"),
    ("3D printers", "en"),
    ("drones for photography", "en"),
    ("mirrorless cameras", "en"),
    ("action cameras", "en"),
    ("home security cameras", "en"),
    ("smart doorbells", "en"),
    ("smart thermostats", "en"),
    ("smart light bulbs", "en"),
    ("portable power banks", "en"),
    ("electric toothbrushes", "en"),
    ("fitness trackers", "en"),
    ("treadmills", "en"),
    ("air fryers", "en"),
    ("blenders", "en"),
    ("stand mixers", "en"),
    ("dishwashers", "en"),
    ("washing machines", "en"),
    ("refrigerators", "en"),
    ("air purifiers", "en"),
    ("space heaters", "en"),
    ("mattresses", "en"),
    ("office chairs", "en"),
    ("gaming chairs", "en"),
    ("gaming laptops", "en"),
    ("graphics cards", "en"),
    ("gaming monitors", "en"),
    ("board games publishers", "en"),
    ("video game consoles", "en"),
    ("digital audio workstations", "en"),
    ("music streaming services", "en"),
    ("podcast hosting platforms", "en"),
    ("audiobook services", "en"),
    ("fitness apps", "en"),
    ("meditation apps", "en"),
    ("language learning apps", "en"),
    ("dating apps", "en"),
    ("ride-sharing apps", "en"),
    ("grocery delivery apps", "en"),
    ("food delivery apps", "en"),
    ("hotel booking sites", "en"),
    ("flight booking sites", "en"),
    ("car rental companies", "en"),
    ("luggage brands", "en"),
    ("backpack brands", "en"),
    ("sunglasses brands", "en"),
    ("watch brands", "en"),
    ("perfume brands", "en"),
    ("skincare brands", "en"),
    ("sunscreen brands", "en"),
    ("protein powder brands", "en"),
    ("energy drink brands", "en"),
    ("coffee bean brands", "en"),
    ("tea brands", "en"),
    ("chocolate brands", "en"),
    ("ice cream brands", "en"),
    ("cereal brands", "en"),
    ("yogurt brands", "en"),
    ("olive oil brands", "en"),
    ("hot sauce brands", "en"),
    ("craft beer breweries", "en"),
    ("wine regions", "en"),
    ("whisky distilleries", "en"),
    ("fast food chains", "en"),
    ("pizza chains", "en"),
    ("coffee shop chains", "en"),
    ("sandwich chains", "en"),
    ("donut chains", "en"),
    ("burger chains", "en"),
    ("credit cards for travel rewards", "en"),
    ("investment brokerage apps", "en"),
    ("budgeting apps", "en"),
    ("tax filing software", "en"),
    ("insurance companies for home", "en"),
    ("life insurance companies", "en"),
    ("student loan providers", "en"),
    ("mortgage lenders", "en"),
    ("banks for small business", "en"),
    ("crypto exchanges", "en"),
    ("stock trading platforms", "en"),
    ("universities for computer science", "en"),
    ("MBA programs", "en"),
    ("coding bootcamps", "en"),
    ("productivity methodologies", "en"),
    ("cloud compute providers", "en"),
    ("CDN providers", "en"),
    ("DNS providers", "en"),
    ("domain registrars", "en"),
    ("web hosting companies", "en"),
    ("SSL certificate providers", "en"),
    ("backup services", "en"),
    ("note-syncing services", "en"),
    ("customer support helpdesk software", "en"),
    ("chatbot platforms", "en"),
    ("A/B testing tools", "en"),
    ("analytics platforms", "en"),
    ("SEO tools", "en"),
    ("social media scheduling tools", "en"),
    ("graphic design tools", "en"),
    ("stock photo websites", "en"),
    ("font foundries", "en"),
    ("icon libraries", "en"),
    ("3D modeling software", "en"),
    ("CAD software", "en"),
    ("spreadsheet apps", "en"),
    ("presentation software", "en"),
    ("PDF editing tools", "en"),
    ("screen recording software", "en"),
    ("video conferencing hardware", "en"),
    ("noise-cancelling earbuds", "en"),
    ("Bluetooth speakers", "en"),
    ("soundbars", "en"),
    ("home theater projectors", "en"),
    ("4K TVs", "en"),
    ("streaming media players", "en"),
    ("universal remotes", "en"),
    ("dash cams", "en"),
    ("car GPS navigation systems", "en"),
    ("electric toothbrush brands", "en"),
    ("hair dryers", "en"),
    ("hair straighteners", "en"),
    ("electric razors", "en"),
    ("humidifiers", "en"),
    ("air conditioners portable", "en"),
    # -- francais --------------------------------------------------------- #
    ("assurances habitation", "fr"),
    ("mutuelles sante", "fr"),
    ("fournisseurs internet", "fr"),
    ("forfaits mobiles", "fr"),
    ("plateformes de e-commerce", "fr"),
    ("logiciels de facturation", "fr"),
    ("outils de gestion de projet", "fr"),
    ("banques traditionnelles", "fr"),
    ("courtiers en bourse", "fr"),
    ("applications de meditation", "fr"),
    ("applications de fitness", "fr"),
    ("marques de cosmetiques", "fr"),
    ("marques de parfums", "fr"),
    ("marques de chocolat", "fr"),
    ("marques de biere artisanale", "fr"),
    ("chaines de fast-food", "fr"),
    ("chaines de restauration rapide", "fr"),
    ("enseignes de supermarche", "fr"),
    ("plateformes de livraison de repas", "fr"),
    ("agences de voyage en ligne", "fr"),
    ("compagnies de location de voitures", "fr"),
    ("marques de valises", "fr"),
    ("marques de sacs a dos", "fr"),
    ("marques de montres", "fr"),
    ("ecoles d'ingenieurs", "fr"),
    ("universites francaises", "fr"),
    ("plateformes de cours en ligne", "fr"),
    ("hebergeurs web", "fr"),
    ("registrars de noms de domaine", "fr"),
    ("logiciels de comptabilite pour TPE", "fr"),
    ("outils de facturation en ligne", "fr"),
    ("applications bancaires", "fr"),
    ("cartes bancaires premium", "fr"),
    ("plateformes d'investissement", "fr"),
    ("assurances auto", "fr"),
    ("marques de trottinettes electriques", "fr"),
    ("marques de robots aspirateurs", "fr"),
    ("marques d'aspirateurs", "fr"),
    ("marques de televiseurs", "fr"),
    ("marques d'enceintes connectees", "fr"),
    ("marques de casques audio", "fr"),
    ("marques de claviers mecaniques", "fr"),
    ("marques d'imprimantes", "fr"),
    ("marques de routeurs wifi", "fr"),
    ("logiciels antivirus", "fr"),
    ("applications de prise de notes", "fr"),
    ("applications de messagerie", "fr"),
    ("moteurs de recherche", "fr"),
    ("reseaux sociaux", "fr"),
    ("editeurs de code", "fr"),
    ("bases de donnees relationnelles", "fr"),
    ("imprimantes 3D", "fr"),
    ("drones photo", "fr"),
    ("appareils photo hybrides", "fr"),
    ("cameras de sport", "fr"),
    ("cameras de surveillance", "fr"),
    ("sonnettes connectees", "fr"),
    ("thermostats connectes", "fr"),
    ("ampoules connectees", "fr"),
    ("batteries externes", "fr"),
    ("brosses a dents electriques", "fr"),
    ("montres connectees sportives", "fr"),
    ("tapis de course", "fr"),
    ("friteuses a air", "fr"),
    ("blenders et mixeurs", "fr"),
    ("robots patissiers", "fr"),
    ("lave-vaisselle", "fr"),
    ("lave-linge", "fr"),
    ("refrigerateurs", "fr"),
    ("purificateurs d'air", "fr"),
    ("radiateurs d'appoint", "fr"),
    ("matelas", "fr"),
    ("chaises de bureau", "fr"),
    ("chaises gamer", "fr"),
    ("ordinateurs portables gamer", "fr"),
    ("cartes graphiques", "fr"),
    ("ecrans gamer", "fr"),
    ("consoles de jeux video", "fr"),
    ("services de streaming musical premium", "fr"),
    ("plateformes de podcasts", "fr"),
    ("services de livres audio", "fr"),
    ("applications de rencontre", "fr"),
    ("applications de covoiturage longue distance", "fr"),
    ("plateformes de livraison de courses", "fr"),
    ("sites de reservation d'hotels", "fr"),
    ("sites de reservation de vols", "fr"),
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
        prompt, engine=sp.engine(), kind="vlm", json_schema=TABLE_SCHEMA, temperature=0.5
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
    ratings = dedupe_ratings(criteria, ratings)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Option", *criteria])
        for name, row in zip(options, ratings, strict=True):
            w.writerow([name, *row])


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ok, failed = 0, []
    for offset, (subject, lang) in enumerate(SUBJECTS):
        i = START_INDEX + offset
        slug = _slugify(subject)
        out_path = DATA_DIR / f"{i:02d}_{slug}.csv"
        if out_path.exists():
            ok += 1
            continue
        print(f"[{offset + 1}/{len(SUBJECTS)}] generating {subject!r} ({lang})...", flush=True)
        try:
            data = generate_table(subject, lang)
            write_csv(out_path, subject, data)
            print(
                f"  -> {out_path.name}: {len(data['options'])} options x {len(data['criteria'])} criteria"
            )
            ok += 1
        except Exception as exc:
            print(f"  !! failed: {exc}", file=sys.stderr)
            failed.append(subject)
    print(f"\n{ok}/{len(SUBJECTS)} tables generated. Failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
