# Standpoint

[🇫🇷](https://github.com/warith-harchaoui/standpoint/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/standpoint/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/standpoint/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/standpoint/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/standpoint/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/local--first-Ollama%20%2B%20SVG-brightgreen.svg)](#tout-en-local)

`Standpoint` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![Logo Standpoint](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

Sachez où se situe vraiment chaque option.

Standpoint lit un tableau de comparaison (les options en lignes, les critères en
colonnes, des nombres dans les cellules) et produit une carte de positionnement 2D,
une courte analyse rédigée et un fichier YAML avec toutes les coordonnées et tous
les coefficients. Une seule commande suffit.

La méthode est une analyse en composantes principales (ACP) ordinaire : à partir de
plusieurs colonnes de notes, elle trouve les quelques directions nouvelles où les
options se distinguent le plus, si bien qu'une ligne entière de notes se ramène à
deux nombres qui portent l'essentiel de ce qui la distingue des autres. On s'en sert
de longue date pour les cartes perceptuelles. Standpoint y ajoute le travail que
vous feriez sinon à la main : il oriente la carte autour d'une option de référence,
nomme les axes en mots simples (dans la langue de vos colonnes), colore et étiquette
les points et écrit tout le résultat.

## Tout en local

Tout tourne sur votre machine : la lecture du tableau, l'ACP, l'orientation, la
coloration et le rendu de la figure en SVG écrit à la main, converti en PNG par
[`resvg`](https://github.com/RazrFalcon/resvg). Votre tableau n'est jamais envoyé nulle part ; pas de
télémétrie, pas de compte, rien à créer.

Seuls le nommage des axes et l'analyse rédigée sollicitent un vision-LLM local tournant
sur `localhost`. Standpoint ne fige aucun modèle : il embarque un brief versionné
(`standpoint/llm.brief.yaml`) décrivant la tâche, et
[best-engine-ai-helper](https://pypi.org/project/best-engine-ai-helper/) résout le
meilleur modèle local pour *votre* machine à la première utilisation, en gardant le choix
dans un `standpoint/llm.engine.yaml` ignoré par git. Les poids sont téléchargés une fois,
puis tout fonctionne hors ligne.

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/standingpoint-doc/)

[🗺️ Paysage](https://github.com/warith-harchaoui/standpoint/blob/main/PAYSAGE.md)

[📋 Exemples](https://github.com/warith-harchaoui/standpoint/blob/main/EXEMPLES.md)

Entrée : un tableau d'options et de leurs notes.

| Language | Performance | Ease of Learning | Ecosystem | Concurrency | Type Safety | Job Market | Tooling |
|---|---|---|---|---|---|---|---|
| Python | 2 | 5 | 5 | 2 | 2 | 5 | 4 |
| Rust | 5 | 2 | 3 | 5 | 5 | 3 | 4 |
| Go | 4 | 4 | 4 | 5 | 4 | 4 | 4 |
| JavaScript | 3 | 4 | 5 | 3 | 2 | 5 | 3 |
| … | | | | | | | |

Sortie : une carte de positionnement,

![Carte de positionnement des langages de programmation](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/programming_languages.png)

plus une analyse Markdown (le sens des axes, où la référence l'emporte, quelles
options se distinguent, avec les loadings et un classement) et un fichier YAML avec,
pour chaque option, ses coordonnées, son rôle, sa couleur et ses valeurs d'origine.

## Fonctionnalités

- **Une commande, un livrable en trois volets** : une figure interactive écrite à
  la main, une interprétation Markdown et un YAML de
  coordonnées + coefficients.
- **Axes lisibles** : l'ACP garde les axes sous forme de sommes pondérées de vos
  colonnes ; un modèle local nomme les quatre pôles par des qualités positives,
  avec un garde-fou contre les acronymes, les négatifs et les paires d'antonymes.
- **Multilingue** : les noms d'axes, l'analyse rédigée et le titre de la figure
  sortent dans la langue même du tableau (anglais, français ou espagnol),
  détectée automatiquement à partir des noms de colonnes, si bien qu'un tableau
  français affiche *Voitures dans le quadrant*.
- **Orienté sur une référence** : l'option qui vous intéresse est pivotée en haut à
  droite ; une référence maximale sur tous les critères est placée juste au-delà du
  meilleur concurrent, plutôt qu'en valeur aberrante.
- **Quatre options mises en avant** : le leader, le plus faible globalement et les
  deux concurrents qui vont le plus loin vers les pôles haut et droit.
- **Consciente de la polarité** : marquez une colonne « le plus bas, le meilleur » avec
  `(↓)` (ou `--lower`) et `standpoint` reformule un inconvénient en bénéfice
  (*Abordable* au lieu de « pas cher »).
- **Auto-vérification visuelle** : `--check` demande à un modèle de vision local si
  la figure se lit correctement (leader en haut à droite, étiquettes lisibles,
  légende visible).

**Un moteur, six surfaces d'accès.** Le même pipeline `positioning()` s'utilise via :

- **Bibliothèque** : `import standpoint as sp`.
- **CLI ×2** : `standpoint` (argparse, toujours installée) et `standpoint-click`
  (jumelle click), aux options identiques.
- **GUI** : `standpoint-gui` → une page web sur `/gui` (extra `[gui]`).
- **API HTTP** : une application FastAPI (`POST /api/position`), même extra `[gui]`.
- **MCP** : `standpoint-mcp` publie l'API comme outils MCP sur `/mcp` (extra `[mcp]`).

Elle s'installe aussi comme **skill Claude / OpenCode** ; voir
[skills/standpoint/SKILL.md](https://github.com/warith-harchaoui/standpoint/blob/main/skills/standpoint/SKILL.md)
et le catalogue exhaustif
[TRIGGERS.md](https://github.com/warith-harchaoui/standpoint/blob/main/TRIGGERS.md).

## Installation

### Les deux commandes qui comptent

Si vous avez déjà Python 3.10–3.13, c'est toute l'installation :

```bash
pip install --upgrade standpoint
```

La même commande installe la première fois et met à jour toutes les fois
suivantes : une seule chose à retenir, pas deux. Ajoutez un extra pour la GUI
navigateur / l'API (`pip install --upgrade "standpoint[gui]"`) ou le serveur
MCP (`pip install --upgrade "standpoint[mcp]"`). Avec
[pipx](https://pipx.pypa.io), l'installation reste isolée de tout autre projet
Python : `pipx install standpoint` la première fois, `pipx upgrade standpoint`
ensuite.

Tout ce qui suit est le mode d'emploi complet, prérequis, environnement
virtuel, dépannage, pour une machine sans Python déjà en place ou pour qui
veut plus de contrôle.

**Prérequis :** **Python 3.10–3.13** et **git**, multiplateforme :

- 🍎 **macOS** ([Homebrew](https://brew.sh)) : `brew install python git`
- 🐧 **Ubuntu/Debian** : `sudo apt update && sudo apt install -y python3 python3-pip git`
- 🪟 **Windows** (PowerShell) : `winget install Python.Python.3.12 Git.Git`

Pour les noms d'axes et l'analyse rédigée, installez [Ollama](https://ollama.com) et
démarrez-le. Vous ne choisissez **pas** de modèle : dès la première utilisation,
best-engine-ai-helper résout le meilleur vision-LLM local pour votre machine à
partir de `standpoint/llm.brief.yaml` et le télécharge une seule fois.

- 🍎 **macOS** : `brew install ollama`, puis `ollama serve &`
- 🐧 **Ubuntu/Debian** : `curl -fsSL https://ollama.com/install.sh | sh`, puis `ollama serve &`
- 🪟 **Windows** : installez depuis [ollama.com/download](https://ollama.com/download), puis lancez-le

**Utilisez un environnement virtuel.** Installer dans le Python système est la
première cause de commande introuvable après installation ou de conflit de version
avec un autre projet :

- 🍎 **macOS** / 🐧 **Ubuntu/Debian** :
  ```bash
  python3 -m venv .venv && source .venv/bin/activate
  python -m pip install --upgrade pip   # un pip trop ancien est la première cause d'échec
  ```
- 🪟 **Windows** (PowerShell) :
  ```powershell
  python -m venv .venv; .venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  ```

Nouveau avec les environnements Python : [🥸 Conseils techniques](https://harchaoui.org/warith/4ml/#install).

### Depuis PyPI (recommandé)

```bash
pip install standpoint             # la bibliothèque + les deux CLI
pip install "standpoint[gui]"      # + la GUI navigateur et l'API HTTP
pip install "standpoint[mcp]"      # + le serveur MCP (au-dessus de l'API)
```

### Depuis les sources

```bash
git clone https://github.com/warith-harchaoui/standpoint.git
cd standpoint
pip install -e .          # ou : pip install -r requirements.txt
```

Ou une version précise directement depuis GitHub (le nom d'import est `standpoint`,
voir les [Releases](https://github.com/warith-harchaoui/standpoint/releases) pour
le dernier tag) :

```bash
pip install standpoint
```

### Vérifier l'installation

```bash
python -c "import standpoint; print(standpoint.__version__)"   # affiche la version
standpoint --help                                               # confirme que la CLI est accessible
```

### Dépannage

- 🍎🐧 **`command not found: standpoint`** : l'environnement virtuel n'est pas activé,
  relancez `source .venv/bin/activate` ; ou l'installation a échoué silencieusement,
  relancez `pip install standpoint` et lisez les dernières lignes de sa sortie.
- 🪟 **`standpoint n'est pas reconnu...`** : même cause sous Windows, relancez
  `.venv\Scripts\Activate.ps1`, puis vérifiez avec `Get-Command standpoint`.
- 🍎🐧🪟 **`ModuleNotFoundError: No module named 'standpoint'`** : vous exécutez un
  autre Python que celui où l'installation a eu lieu ; comparez `which python3` /
  `which pip` (macOS/Ubuntu) ou `Get-Command python`, `Get-Command pip` (Windows),
  puis réinstallez avec `python -m pip install standpoint` pour forcer la
  correspondance.
- 🍎🐧 **GUI : « The local Ollama server is not reachable »** : démarrez-le avec
  `ollama serve` (certaines installations le lancent déjà en service), puis vérifiez
  avec `curl http://localhost:11434`.
- 🪟 **GUI : « The local Ollama server is not reachable »** : lancez l'application
  Ollama depuis le menu Démarrer, puis vérifiez avec
  `Invoke-WebRequest http://localhost:11434`.
- 🍎🐧🪟 **GUI : « The model '...' is not installed »** : `ollama pull <tag>` avec le
  tag de l'erreur (celui résolu dans `standpoint/llm.engine.yaml` ou celui du `--model`
  que vous avez passé) ; supprimez ce fichier pour forcer une nouvelle résolution
  après un changement de matériel.
- 🍎🐧 **`Address already in use` sur `standpoint-gui`** : le port 8000 est déjà pris,
  trouvez le processus avec `lsof -i :8000` ou lancez
  `uvicorn standpoint.api:app --port 8001` sur un port libre.
- 🪟 **`Address already in use` sur `standpoint-gui`** : trouvez le processus avec
  `netstat -ano | findstr :8000` ou lancez `uvicorn standpoint.api:app --port 8001`
  sur un port libre.
- 🍎🐧🪟 **Python ancien (< 3.10)** : vérifiez avec `python3 --version` (ou
  `python --version` sous Windows) ; Standpoint requiert 3.10 ou plus. Installez un
  Python plus récent avec les commandes prérequises ci-dessus plutôt que de contourner
  la vérification de version.

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
pos.export("out")                 # écrit out/python.{png,svg,white.png,white.svg,md,yaml}
print(pos.axes)
# {'x': 'Concurrency ↔ Ecosystem', 'y': 'Safety ↔ Learning'}
```

Choisissez un autre modèle local pour les noms d'axes et l'analyse :

```bash
standpoint mon_tableau.csv --model qwen3:8b
```

Plus d'exemples dans [EXEMPLES.md](https://github.com/warith-harchaoui/standpoint/blob/main/EXEMPLES.md).

## En service : GUI, API, MCP, Docker

```bash
pip install "standpoint[gui]"
standpoint-gui                     # appli web → http://localhost:8000/gui
```

![La GUI Standpoint : éditez un tableau, générez le quadrant et l'analyse](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/assets/gui-preview.png)

Le back-end de la GUI est une application FastAPI : `POST /api/position` renvoie le
SVG, l'analyse Markdown et le YAML. Servez-la avec l'endpoint MCP monté,
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
ex. `Price (↓)` ou listez-la dans `--lower`.

## Comment ça marche

1. Standardiser chaque critère à moyenne 0 et écart-type 1. L'ACP est sensible à
   l'échelle ; cette étape met chaque critère sur un pied d'égalité.
2. Lancer l'ACP et garder deux composantes. Les axes restent des sommes pondérées
   des colonnes d'origine, donc on peut les lire directement.
3. Pivoter la carte pour que la référence soit en haut à droite. Si la référence
   obtient le maximum partout, elle est placée juste au-delà du meilleur concurrent
   sur chaque axe, plutôt qu'à l'écart toute seule.
4. Étiqueter. Les quatre options mises en avant (leader, plus faible et les deux
   concurrents les plus proches des pôles haut et droit) découlent directement de la
   géométrie de la carte. Chaque option prend sa propre couleur selon sa position.
   Un modèle local lit les loadings et nomme les quatre extrémités d'axes, comme des
   qualités positives, dans la langue de vos colonnes (anglais, français, espagnol).

La figure se limite à une croix pointillée pour les axes, les mots-pôles aux
extrémités, des étiquettes seulement là où elles rentrent et une légende pour le
reste.

![Voitures électriques, une entrée française donne un titre et des axes en français](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/voitures_electriques.png)

## Notes

- Les noms d'axes viennent d'un modèle local. Un garde-fou les garde positifs,
  distincts et sans acronymes ; un `--model` plus gros aide et `--check` demande au
  modèle de vision si la figure se lit correctement.
- Le plus haut, le meilleur, par défaut. Pour une colonne où le plus bas est le meilleur, marquez
  son en-tête avec `(↓)` (`Price (↓)`, `Latency (↓)`) ou passez `--lower Price,Latency`.
  Standpoint la négativise et nomme le pôle par le bénéfice (« Abordable »,
  « Léger »), jamais par l'inconvénient.
- Chaque figure est écrite deux fois : un `.png` / `.svg` **transparent** qui se pose
  sur n'importe quelle page et une version **fond blanc** `.white.png` / `.white.svg`
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

Le standard de code de ce dépôt est [CODING.md](https://github.com/warith-harchaoui/standpoint/blob/main/CODING.md) ;
la politique de contribution et de versionnage est dans [CONTRIBUTING.md](https://github.com/warith-harchaoui/standpoint/blob/main/CONTRIBUTING.md).

## Auteur

[Warith Harchaoui](https://www.linkedin.com/in/warith-harchaoui)

## Crédits

Les cartes perceptuelles ACP sont classiques (`factoextra` et `FactoMineR` en R,
`prince` et `pca` en Python) ; utiliser un modèle pour lire les composantes est une
idée plus récente. Les couleurs viennent de la palette
["Good Colors"](https://harchaoui.org/warith/colors/). Les figures sont écrites à
la main en SVG et converties en PNG par
[`resvg`](https://github.com/RazrFalcon/resvg).

## Licence

BSD 3-Clause, la même licence que scikit-learn. Voir
[`LICENSE`](https://github.com/warith-harchaoui/standpoint/blob/main/LICENSE).
