"""Phase 1a (final scale-up): the last subjects, taking the corpus to ~500 tables.

Same approach as `01_generate_tables.py`/`01c_generate_tables_more.py`. User
settled on ~500 tables total (down from an initial "thousands"/"hundreds" ask,
after seeing the real measured throughput: ~90s/table combined across Phase 1a+1b
on this machine, making 1000 an ~25-hour undertaking). Continues the index range
after `01c_generate_tables_more.py`'s 50..294.
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
START_INDEX = 295  # continues 01c_generate_tables_more.py's 50..294

SUBJECTS: list[tuple[str, str]] = [
    # -- more en -------------------------------------------------------- #
    ("wireless chargers", "en"),
    ("laptop stands", "en"),
    ("webcams", "en"),
    ("USB-C docking stations", "en"),
    ("external SSDs", "en"),
    ("NAS devices", "en"),
    ("home theater receivers", "en"),
    ("record players", "en"),
    ("guitar amps", "en"),
    ("digital pianos", "en"),
    ("microphones for podcasting", "en"),
    ("ring lights", "en"),
    ("tripods", "en"),
    ("camera lenses", "en"),
    ("photo printers", "en"),
    ("scanners", "en"),
    ("label makers", "en"),
    ("paper shredders", "en"),
    ("office desks", "en"),
    ("filing cabinets", "en"),
    ("whiteboards", "en"),
    ("business card printing services", "en"),
    ("logo design services", "en"),
    ("freelance marketplaces", "en"),
    ("stock market news apps", "en"),
    ("personal finance newsletters", "en"),
    ("retirement planning apps", "en"),
    ("robo-advisors", "en"),
    ("expense tracking apps", "en"),
    ("invoicing software", "en"),
    ("time tracking software", "en"),
    ("scheduling software", "en"),
    ("appointment booking apps", "en"),
    ("virtual assistant services", "en"),
    ("transcription services", "en"),
    ("translation services", "en"),
    ("resume builder tools", "en"),
    ("job search platforms", "en"),
    ("interview prep platforms", "en"),
    ("online tutoring platforms", "en"),
    ("coding practice platforms", "en"),
    ("data science bootcamps", "en"),
    ("cybersecurity certifications", "en"),
    ("cloud certifications", "en"),
    ("project management certifications", "en"),
    ("yoga mat brands", "en"),
    ("resistance bands brands", "en"),
    ("dumbbell brands", "en"),
    ("home gym equipment brands", "en"),
    ("protein bar brands", "en"),
    ("meal replacement shake brands", "en"),
    ("multivitamin brands", "en"),
    ("sleep tracking devices", "en"),
    ("white noise machines", "en"),
    ("weighted blankets", "en"),
    ("essential oil diffusers", "en"),
    ("air quality monitors", "en"),
    ("smart scales", "en"),
    ("blood pressure monitors", "en"),
    ("pulse oximeters", "en"),
    ("first aid kit brands", "en"),
    ("pet food brands", "en"),
    ("pet insurance providers", "en"),
    ("dog training apps", "en"),
    ("cat litter brands", "en"),
    ("aquarium equipment brands", "en"),
    ("garden hose brands", "en"),
    ("lawn mower brands", "en"),
    ("leaf blower brands", "en"),
    ("pressure washer brands", "en"),
    ("cordless drill brands", "en"),
    ("tool storage brands", "en"),
    ("paint brands", "en"),
    ("home security systems", "en"),
    ("video doorbell brands", "en"),
    ("smart lock brands", "en"),
    ("garage door opener brands", "en"),
    ("solar panel installers", "en"),
    ("home battery storage brands", "en"),
    ("EV home charger brands", "en"),
    ("moving companies", "en"),
    ("storage unit companies", "en"),
    ("home warranty companies", "en"),
    ("pest control companies", "en"),
    ("lawn care services", "en"),
    ("house cleaning services", "en"),
    ("laundry delivery services", "en"),
    ("dry cleaning chains", "en"),
    ("tailoring services", "en"),
    ("shoe repair services", "en"),
    ("watch repair services", "en"),
    ("phone repair chains", "en"),
    ("computer repair chains", "en"),
    ("car repair chains", "en"),
    ("oil change chains", "en"),
    ("tire brands", "en"),
    ("car wash chains", "en"),
    ("car insurance companies", "en"),
    ("motorcycle brands", "en"),
    ("scooter sharing services", "en"),
    ("parking apps", "en"),
    ("toll pass providers", "en"),
    ("public transit apps", "en"),
    ("travel insurance providers", "en"),
    ("luggage tracking devices", "en"),
    ("travel backpack brands", "en"),
    ("hiking boot brands", "en"),
    ("camping tent brands", "en"),
    ("sleeping bag brands", "en"),
    ("cooler brands", "en"),
    ("water bottle brands", "en"),
    ("hydration pack brands", "en"),
    ("ski resort brands", "en"),
    ("surf brands", "en"),
    ("skateboard brands", "en"),
    ("snowboard brands", "en"),
    ("golf club brands", "en"),
    ("tennis racket brands", "en"),
    ("basketball shoe brands", "en"),
    ("swimwear brands", "en"),
    ("yoga apparel brands", "en"),
    ("denim brands", "en"),
    ("t-shirt brands", "en"),
    ("sneaker resale platforms", "en"),
    ("secondhand clothing apps", "en"),
    ("subscription box services", "en"),
    ("flower delivery services", "en"),
    ("gift card marketplaces", "en"),
    ("greeting card apps", "en"),
    ("photo printing services", "en"),
    ("custom mug printing services", "en"),
    ("t-shirt printing services", "en"),
    ("3D printing services online", "en"),
    ("online design tools for beginners", "en"),
    ("mind mapping tools", "en"),
    ("whiteboard collaboration tools", "en"),
    ("kanban board tools", "en"),
    ("okr tracking tools", "en"),
    ("employee engagement platforms", "en"),
    ("performance review software", "en"),
    ("applicant tracking systems", "en"),
    ("background check services", "en"),
    ("payroll outsourcing companies", "en"),
    ("benefits administration platforms", "en"),
    ("coworking space chains", "en"),
    ("virtual office providers", "en"),
    ("business phone systems", "en"),
    ("call center software", "en"),
    ("live chat software", "en"),
    ("knowledge base software", "en"),
    ("documentation platforms", "en"),
    ("api gateway platforms", "en"),
    ("feature flag platforms", "en"),
    ("error monitoring tools", "en"),
    ("log management platforms", "en"),
    ("uptime monitoring tools", "en"),
    ("CI/CD platforms", "en"),
    ("container orchestration platforms", "en"),
    ("infrastructure as code tools", "en"),
    ("secrets management tools", "en"),
    ("feature-rich note apps for research", "en"),
    ("citation management tools", "en"),
    ("plagiarism checkers", "en"),
    ("grammar checking tools", "en"),
    ("AI writing assistants", "en"),
    ("AI image generators", "en"),
    ("AI voice generators", "en"),
    ("AI video generators", "en"),
    ("AI coding assistants", "en"),
    # -- en francais ----------------------------------------------------- #
    ("chargeurs sans fil", "fr"),
    ("supports d'ordinateur portable", "fr"),
    ("webcams", "fr"),
    ("disques ssd externes", "fr"),
    ("stations d'accueil usb-c", "fr"),
    ("amplis guitare", "fr"),
    ("pianos numeriques", "fr"),
    ("microphones podcast", "fr"),
    ("trepieds photo", "fr"),
    ("imprimantes photo", "fr"),
    ("scanners de bureau", "fr"),
    ("destructeurs de documents", "fr"),
    ("bureaux de travail", "fr"),
    ("tableaux blancs", "fr"),
    ("services de design de logo", "fr"),
    ("plateformes de freelance", "fr"),
    ("applications de suivi budgetaire", "fr"),
    ("logiciels de facturation en ligne", "fr"),
    ("logiciels de suivi du temps", "fr"),
    ("applications de prise de rendez-vous", "fr"),
    ("services de transcription", "fr"),
    ("services de traduction", "fr"),
    ("plateformes de recherche d'emploi", "fr"),
    ("plateformes de cours de code", "fr"),
    ("certifications en cybersecurite", "fr"),
    ("marques de tapis de yoga", "fr"),
    ("marques d'equipement de fitness", "fr"),
    ("marques de barres proteinees", "fr"),
    ("marques de multivitamines", "fr"),
    ("appareils de suivi du sommeil", "fr"),
    ("machines a bruit blanc", "fr"),
    ("couvertures lestees", "fr"),
    ("diffuseurs d'huiles essentielles", "fr"),
    ("moniteurs de qualite de l'air", "fr"),
    ("balances connectees", "fr"),
    ("tensiometres", "fr"),
    ("marques de nourriture pour animaux", "fr"),
    ("assurances pour animaux", "fr"),
    ("marques de litiere pour chat", "fr"),
    ("marques de tondeuses a gazon", "fr"),
    ("marques de perceuses sans fil", "fr"),
    ("marques de peinture", "fr"),
    ("systemes de securite domestique", "fr"),
    ("marques de sonnettes connectees", "fr"),
    ("marques de serrures connectees", "fr"),
    ("installateurs de panneaux solaires", "fr"),
    ("bornes de recharge domestiques", "fr"),
    ("entreprises de demenagement", "fr"),
    ("entreprises de garde-meuble", "fr"),
    ("entreprises de nettoyage a domicile", "fr"),
    ("pressings", "fr"),
    ("chaines de reparation de telephones", "fr"),
    ("chaines de reparation automobile", "fr"),
    ("marques de pneus", "fr"),
    ("chaines de lavage auto", "fr"),
    ("assurances auto", "fr"),
    ("marques de motos", "fr"),
    ("services d'autopartage", "fr"),
    ("applications de stationnement", "fr"),
    ("applications de transport public", "fr"),
    ("assurances voyage", "fr"),
    ("marques de sacs de voyage", "fr"),
    ("marques de chaussures de randonnee", "fr"),
    ("marques de tentes de camping", "fr"),
    ("marques de sacs de couchage", "fr"),
    ("marques de glacieres", "fr"),
    ("marques de gourdes", "fr"),
    ("stations de ski", "fr"),
    ("marques de skateboards", "fr"),
    ("marques de snowboards", "fr"),
    ("marques de clubs de golf", "fr"),
    ("marques de raquettes de tennis", "fr"),
    ("marques de maillots de bain", "fr"),
    ("marques de vetements de yoga", "fr"),
    ("marques de jeans", "fr"),
    ("plateformes de revente de sneakers", "fr"),
    ("applications de vetements d'occasion", "fr"),
    ("services d'abonnement box", "fr"),
    ("services de livraison de fleurs", "fr"),
    ("plateformes de cartes cadeaux", "fr"),
    ("services d'impression photo", "fr"),
    ("outils de conception pour debutants", "fr"),
    ("outils de cartes mentales", "fr"),
    ("outils de tableau blanc collaboratif", "fr"),
    ("outils de tableau kanban", "fr"),
    ("plateformes d'engagement des employes", "fr"),
    ("logiciels d'evaluation de performance", "fr"),
    ("logiciels de suivi des candidatures", "fr"),
    ("services de verification des antecedents", "fr"),
    ("entreprises d'externalisation de paie", "fr"),
    ("chaines d'espaces de coworking", "fr"),
    ("fournisseurs de bureau virtuel", "fr"),
    ("systemes telephoniques professionnels", "fr"),
    ("logiciels de centre d'appels", "fr"),
    ("logiciels de chat en direct", "fr"),
    ("logiciels de base de connaissances", "fr"),
    ("plateformes de documentation", "fr"),
    ("outils de monitoring d'erreurs", "fr"),
    ("plateformes de gestion de logs", "fr"),
    ("outils de monitoring de disponibilite", "fr"),
    ("plateformes CI/CD", "fr"),
    ("outils de gestion des secrets", "fr"),
    ("outils de gestion de citations", "fr"),
    ("outils de detection de plagiat", "fr"),
    ("outils de correction grammaticale", "fr"),
    ("assistants d'ecriture IA", "fr"),
    ("generateurs d'images IA", "fr"),
    ("generateurs de voix IA", "fr"),
    ("generateurs de video IA", "fr"),
    ("assistants de code IA", "fr"),
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
        w.writerow([subject.title(), *criteria])
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
