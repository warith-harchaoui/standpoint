# Standpoint

[🇫🇷](https://github.com/warith-harchaoui/standingpoint/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/standingpoint/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/standingpoint/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/standingpoint/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/standingpoint/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/local--first-Ollama%20%2B%20Vega--Lite-brightgreen.svg)](#tout-en-local)

`Standpoint` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![Logo Standpoint](https://raw.githubusercontent.com/warith-harchaoui/standingpoint/main/assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

Sachez où se situe vraiment chaque option.

Standpoint lit un tableau de comparaison (les options en lignes, les critères en
colonnes, des nombres dans les cellules) et produit une carte de positionnement 2D,
une courte analyse rédigée, et un fichier YAML avec toutes les coordonnées et tous
les coefficients. Une seule commande suffit.

La méthode est une analyse en composantes principales (ACP) ordinaire, utilisée de
longue date pour les cartes perceptuelles. Standpoint y ajoute le travail que vous feriez sinon à la
main : il oriente la carte autour d'une option de référence, nomme les axes en mots
simples (dans la langue de vos colonnes), colore et étiquette les points, et écrit
tout le résultat.

## Tout en local

Tout tourne sur votre machine : la lecture du tableau, l'ACP, l'orientation, la
coloration et le rendu de la figure avec [`vl-convert`](https://github.com/vega/vl-convert).
Votre tableau n'est jamais envoyé nulle part ; pas de télémétrie, pas de compte, rien à
créer.

Seuls le nommage des axes et l'analyse rédigée sollicitent un modèle
[Ollama](https://ollama.com) tournant sur `localhost`. Ollama récupère les poids du
modèle la première fois, puis fonctionne hors ligne. Et vous pouvez très bien vous en
passer : avec `--no-llm`, vous obtenez la carte entière, les axes prenant simplement le
nom de la colonne la plus forte à chaque extrémité.

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/standingpoint-doc/)

[🗺️ Paysage](https://github.com/warith-harchaoui/standingpoint/blob/main/PAYSAGE.md)

[📋 Exemples](https://github.com/warith-harchaoui/standingpoint/blob/main/EXAMPLES.md)


Entrée : un tableau d'options et de leurs notes.

| Language | Performance | Ease of Learning | Ecosystem | Concurrency | Type Safety | Job Market | Tooling |
|---|---|---|---|---|---|---|---|
| Python | 2 | 5 | 5 | 2 | 2 | 5 | 4 |
| Rust | 5 | 2 | 3 | 5 | 5 | 3 | 4 |
| Go | 4 | 4 | 4 | 5 | 4 | 4 | 4 |
| JavaScript | 3 | 4 | 5 | 3 | 2 | 5 | 3 |
| … | | | | | | | |

Sortie : une carte de positionnement,

![Carte de positionnement des langages de programmation](https://raw.githubusercontent.com/warith-harchaoui/standingpoint/main/examples/programming_languages.png)

plus une analyse Markdown (le sens des axes, où la référence l'emporte, quelles
options se distinguent, avec les loadings et un classement) et un fichier YAML avec,
pour chaque option, ses coordonnées, son rôle, sa couleur et ses valeurs d'origine.

## Fonctionnalités

- **Une commande, un livrable en trois volets** : une figure (PNG + SVG + JSON
  Vega-Lite), une interprétation Markdown, et un YAML de coordonnées + coefficients.
- **Axes lisibles** : l'ACP garde les axes sous forme de sommes pondérées de vos
  colonnes ; un modèle local nomme les quatre pôles par des qualités positives,
  avec un garde-fou contre les acronymes, les négatifs et les paires d'antonymes.
- **Multilingue** : les noms d'axes, l'analyse rédigée et le titre de la figure
  sortent dans la langue même du tableau (anglais, français ou espagnol),
  détectée automatiquement à partir des noms de colonnes — un tableau français
  affiche *Voitures dans le quadrant*.
- **Orienté sur une référence** : l'option qui vous intéresse est pivotée en haut à
  droite ; une référence maximale sur tous les critères est placée juste au-delà du
  meilleur concurrent, plutôt qu'en valeur aberrante.
- **Quatre options mises en avant** : le leader, le plus faible globalement, et les
  deux concurrents qui vont le plus loin vers les pôles haut et droit.
- **Consciente de la polarité** : marquez une colonne « le plus bas, le meilleur » avec
  `(↓)` (ou `--lower`) et Standpoint nomme le bénéfice (*Abordable*, *Léger*),
  jamais l'inconvénient.
- **Repli déterministe** : `--no-llm` ne requiert ni modèle ni réseau.
- **Auto-vérification visuelle** : `--check` demande à un modèle de vision local si
  la figure se lit correctement (leader en haut à droite, étiquettes lisibles,
  légende visible).

**Un moteur, six accès** — le même pipeline `positioning()` s'utilise via :

- **Bibliothèque** : `import standpoint as sp`.
- **CLI ×2** : `standpoint` (argparse, toujours installée) et `standpoint-click`
  (jumelle click), aux options identiques.
- **GUI** : `standpoint-gui` → une page web sur `/gui` (extra `[gui]`).
- **API HTTP** : une application FastAPI (`POST /api/position`), même extra `[gui]`.
- **MCP** : `standpoint-mcp` publie l'API comme outils MCP sur `/mcp` (extra `[mcp]`).

Elle s'installe aussi comme **skill Claude / OpenCode** — voir
[skills/standpoint/SKILL.md](https://github.com/warith-harchaoui/standingpoint/blob/main/skills/standpoint/SKILL.md)
et le catalogue exhaustif
[TRIGGERS.md](https://github.com/warith-harchaoui/standingpoint/blob/main/TRIGGERS.md).

## Installation

**Prérequis** — **Python 3.10–3.13** et **git**, multiplateforme :

- 🍎 **macOS** ([Homebrew](https://brew.sh)) : `brew install python git`
- 🐧 **Ubuntu/Debian** : `sudo apt update && sudo apt install -y python3 python3-pip git`
- 🪟 **Windows** (PowerShell) : `winget install Python.Python.3.12 Git.Git`

Pour les noms d'axes et l'analyse rédigée, installez [Ollama](https://ollama.com) et
téléchargez le modèle par défaut une fois (optionnel — sinon, utilisez `--no-llm`) :

- 🍎 **macOS** : `brew install ollama` — puis `ollama serve &` et `ollama pull qwen2.5vl:7b`
- 🐧 **Ubuntu/Debian** : `curl -fsSL https://ollama.com/install.sh | sh` — puis `ollama pull qwen2.5vl:7b`
- 🪟 **Windows** : installez depuis [ollama.com/download](https://ollama.com/download), puis `ollama pull qwen2.5vl:7b`

Nous recommandons un environnement Python. Si vous ne savez pas comment faire : [🥸 Conseils techniques](https://harchaoui.org/warith/4ml/#install).

### Depuis PyPI (recommandé)

```bash
pip install standpoint             # la bibliothèque + les deux CLI
pip install "standpoint[gui]"      # + la GUI navigateur et l'API HTTP
pip install "standpoint[mcp]"      # + le serveur MCP (au-dessus de l'API)
```

### Depuis les sources

```bash
git clone https://github.com/warith-harchaoui/standingpoint.git
cd standingpoint
pip install -e .          # ou : pip install -r requirements.txt
```

Ou directement depuis GitHub (le nom d'import est `standpoint`) :

```bash
pip install "git+https://github.com/warith-harchaoui/standingpoint.git@v0.4.0"
```

## Utilisation

```bash
standpoint examples/programming_languages.csv --outdir out
# sans installer : python3 -m standpoint examples/programming_languages.csv --outdir out
```

Deux CLI équivalentes sont installées : `standpoint` (argparse) et `standpoint-click`.

En bibliothèque :

```python
import standpoint as sp

pos = sp.positioning("examples/programming_languages.csv")
pos.export("out")                 # écrit out/python.{png,svg,white.png,white.svg,vl.json,md,yaml}
print(pos.axes)
# {'x': 'Concurrency ↔ Ecosystem', 'y': 'Safety ↔ Learning'}
```

Sautez le modèle pour un rendu rapide et déterministe (Ollama inutile) :

```bash
standpoint mon_tableau.csv --no-llm
standpoint mon_tableau.csv --model qwen3:8b
```

Plus d'exemples dans [EXAMPLES.md](https://github.com/warith-harchaoui/standingpoint/blob/main/EXAMPLES.md).

## En service — GUI, API, MCP, Docker

```bash
pip install "standpoint[gui]"
standpoint-gui                     # appli web → http://localhost:8000/gui
```

![La GUI Standpoint — éditez un tableau, générez le quadrant et l'analyse](https://raw.githubusercontent.com/warith-harchaoui/standingpoint/main/assets/gui-preview.png)

Le back-end de la GUI est une application FastAPI : `POST /api/position` renvoie le
spec Vega-Lite, l'analyse Markdown et le YAML. Servez-la avec l'endpoint MCP monté,
pour qu'un agent puisse appeler `position` comme un outil :

```bash
pip install "standpoint[mcp]"
standpoint-mcp                     # API + MCP sur /mcp (la GUI reste sur /gui)
```

Ou tout dans un conteneur (installe depuis `requirements.txt`, sert l'API + MCP) :

```bash
docker build -t standpoint .
docker run --rm -p 8000:8000 standpoint
```

Pour travailler la bibliothèque en local, un environnement conda minimal enveloppe le
même `requirements.txt` :

```bash
conda env create -f environment.yaml && conda activate env-for-standpoint && pip install -e .
```

## Format d'entrée

Un tableau CSV ou Markdown. La première colonne contient les noms des options ; les
suivantes sont des critères numériques sur n'importe quelle échelle. Plus haut vaut
mieux. Les cellules vides prennent le minimum de la colonne : une note
manquante n'avantage jamais une option.

| Language | Performance | Ease of Learning | Ecosystem | Type Safety | Job Market |
|---|---|---|---|---|---|
| Python | 2 | 5 | 5 | 2 | 5 |
| Rust | 5 | 2 | 3 | 5 | 3 |
| Go | 4 | 4 | 4 | 4 | 4 |

La première ligne est la référence et va en haut à droite. Changez-la avec
`--reference "<nom>"`. Marquez une colonne « le plus bas, le meilleur » avec `(↓)`, par
ex. `Price (↓)`, ou listez-la dans `--lower`.

## Comment ça marche

1. Standardiser chaque critère à moyenne 0 et écart-type 1. L'ACP est sensible à
   l'échelle ; cette étape met chaque critère sur un pied d'égalité.
2. Lancer l'ACP et garder deux composantes. Les axes restent des sommes pondérées
   des colonnes d'origine, donc on peut les lire directement.
3. Pivoter la carte pour que la référence soit en haut à droite. Si la référence
   obtient le maximum partout, elle est placée juste au-delà du meilleur concurrent
   sur chaque axe, plutôt qu'à l'écart toute seule.
4. Étiqueter. Les quatre options mises en avant (leader, plus faible, et les deux
   concurrents les plus proches des pôles haut et droit) découlent directement de la
   géométrie de la carte. Chaque option prend sa propre couleur selon sa position.
   Un modèle local lit les loadings et nomme les quatre extrémités d'axes, comme des
   qualités positives, dans la langue de vos colonnes (anglais, français, espagnol).

La figure se limite à une croix pointillée pour les axes, les mots-pôles aux
extrémités, des étiquettes seulement là où elles rentrent, et une légende pour le
reste.

![Voitures électriques, une entrée française donne un titre et des axes en français](https://raw.githubusercontent.com/warith-harchaoui/standingpoint/main/examples/voitures_electriques.png)

## Notes

- Les noms d'axes viennent d'un modèle local. Un garde-fou les garde positifs,
  distincts et sans acronymes ; un `--model` plus gros aide, et `--check` demande au
  modèle de vision si la figure se lit correctement.
- Le plus haut, le meilleur, par défaut. Pour une colonne où le plus bas est le meilleur, marquez
  son en-tête avec `(↓)` (`Price (↓)`, `Latency (↓)`) ou passez `--lower Price,Latency`.
  Standpoint la négativise et nomme le pôle pour le bénéfice (« Abordable »,
  « Léger »), jamais l'inconvénient.
- Chaque figure est écrite deux fois : un `.png` / `.svg` **transparent** qui se pose
  sur n'importe quelle page, et une version **fond blanc** `.white.png` / `.white.svg`
  pour les surfaces sombres où les étiquettes presque noires disparaîtraient sur la
  transparence.
- C'est une projection 2D. Les axes portent une fraction annoncée de la variance :
  à lire comme un résumé, pas comme l'image complète.

## Exemples

Suivis dans `examples/`, le CSV d'entrée et les figures générées :

| Tableau | Langue | Leader |
|---|---|---|
| `programming_languages.csv` | en | Python |
| `cloud_providers.csv` | en | AWS |
| `laptops.csv` | en | MacBook Air (utilise `Price (↓)` / `Weight (↓)`) |
| `voitures_electriques.csv` | fr | Tesla Model 3 |

## Développement

```bash
pip install -r requirements-dev.txt   # ou : pip install -e ".[dev]"
python3 -m pytest tests/ -q           # tests déterministes ; ceux avec modèle s'ignorent
python3 -m ruff check standpoint tests
python3 -m ruff format --check standpoint tests
```

Le standard de code de ce dépôt est [CODING.md](https://github.com/warith-harchaoui/standingpoint/blob/main/CODING.md) ;
la politique de contribution et de versionnage est dans [CONTRIBUTING.md](https://github.com/warith-harchaoui/standingpoint/blob/main/CONTRIBUTING.md).

## Crédits

Les cartes perceptuelles ACP sont classiques (`factoextra` et `FactoMineR` en R,
`prince` et `pca` en Python) ; utiliser un modèle pour lire les composantes est une
idée plus récente. Les couleurs viennent de la palette
["Good Colors"](https://harchaoui.org/warith/colors/). Les figures sont rendues par
[`vl-convert`](https://github.com/vega/vl-convert) au-dessus de
[Vega-Lite](https://vega.github.io/vega-lite/).

## Auteur

[Warith Harchaoui](https://www.linkedin.com/in/warith-harchaoui)

## Licence

BSD 3-Clause, la même licence que scikit-learn. Voir
[`LICENSE`](https://github.com/warith-harchaoui/standingpoint/blob/main/LICENSE).
