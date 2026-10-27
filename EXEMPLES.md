# Exemples

[🇫🇷](https://github.com/warith-harchaoui/standpoint/blob/main/EXEMPLES.md) · [🇬🇧](https://github.com/warith-harchaoui/standpoint/blob/main/EXAMPLES.md)

Chaque extrait ci-dessous a été exécuté sur les tableaux suivis dans
[`examples/`](https://github.com/warith-harchaoui/standpoint/tree/main/examples) ;
chaque bloc de sortie est ce qui est revenu. Deux sortes de nombres cohabitent dans
ce fichier, autant les séparer tout de suite : la **géométrie** (variance, rotation,
loadings, coordonnées, rôles, noms de fichiers) est déterministe — le même tableau
donne les mêmes figures — alors que les **mots des pôles** viennent du modèle local
que votre machine a retenu, donc les vôtres se liront autrement. Les exécutions
rapportées ici ont été faites avec un petit `qwen2.5:3b` local.

## Table des matières

- [Mise en place](#mise-en-place)
- [1. Un tableau, une carte](#1-un-tableau-une-carte)
- [2. Lire le tableau avant de le tracer](#2-lire-le-tableau-avant-de-le-tracer)
- [3. Quand le plus bas est le meilleur](#3-quand-le-plus-bas-est-le-meilleur)
- [4. Choisir la référence](#4-choisir-la-référence)
- [5. Les six fichiers écrits par une exécution](#5-les-six-fichiers-écrits-par-une-exécution)
- [6. Les cellules vides sont signalées, jamais cachées](#6-les-cellules-vides-sont-signalées-jamais-cachées)
- [7. Un tableau français donne une carte française](#7-un-tableau-français-donne-une-carte-française)
- [8. Auditer la prose du modèle](#8-auditer-la-prose-du-modèle)
- [9. Navigateur, API HTTP, outil MCP](#9-navigateur-api-http-outil-mcp)
- [Ligne de commande](#ligne-de-commande)
- [Dépannage](#dépannage)

## Mise en place

```bash
pip install --upgrade standpoint          # la bibliothèque + la commande `standpoint`
pip install --upgrade "standpoint[gui]"   # ajoute l'app navigateur et l'API HTTP
pip install --upgrade "standpoint[mcp]"   # ajoute le point d'entrée MCP
```

Tous les extraits Python ci-dessous supposent ces deux lignes, rien de plus :

```python
import pandas as pd
import standpoint as sp
```

Les commandes sont lancées depuis un clone, pour que les chemins `examples/`
existent :

```bash
git clone https://github.com/warith-harchaoui/standpoint
cd standpoint
```

**Une seule dépendance extérieure, une seule fois.** Nommer les pôles des axes et
écrire l'analyse demandent tous deux un modèle local sur `localhost`. Standpoint ne
code en dur aucun nom de modèle : il livre un cahier des charges
(`standpoint/llm.brief.yaml`) que
[best-engine-ai-helper](https://pypi.org/project/best-engine-ai-helper/) résout pour
votre machine à la première utilisation, en gardant le choix dans un
`standpoint/llm.engine.yaml` ignoré par git. Tout ce qui est géométrique — lecture
du tableau, polarité, ACP, orientation, couleurs, le SVG, le YAML, `--check` — n'a
besoin d'aucun modèle : c'est pourquoi les sections 2 à 6 tournent sur une machine
qui ne sert rien.

## 1. Un tableau, une carte

Tout le paquet en un appel. `positioning()` accepte un chemin, une chaîne CSV ou
Markdown brute aussi bien qu'un DataFrame ; il rend un objet qu'on lit ou qu'on
écrit.

```python
pos = sp.positioning("examples/laptops.csv")
print(pos.axes)
print(pos.poles)
```

```
{'x': 'Affordable ↔ Craftsmanship', 'y': 'Efficiency ↔ Portability'}
['Affordable', 'Craftsmanship', 'Efficiency', 'Portability']
```

`poles` est toujours ordonné `[gauche, droite, bas, haut]` ; `axes` est le même
quatuor de mots assemblé en deux titres d'axes. Un appel de plus écrit le livrable :

```python
pos.export("out")
```

```
['out/macbook_air.png', 'out/macbook_air.svg', 'out/macbook_air.white.png',
 'out/macbook_air.white.svg', 'out/macbook_air.md', 'out/macbook_air.yaml']
```

Le radical vient de l'option de référence (`MacBook Air` → `macbook_air`) ; passez
`stem="laptops"` pour le choisir vous-même.

![Carte de positionnement des ordinateurs portables](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/laptops.png)

## 2. Lire le tableau avant de le tracer

`parse_table` est la porte d'entrée des deux formats. Il lit un chemin ou une chaîne
brute, prend la première colonne comme noms d'options et convertit toutes les autres
cellules en nombres :

```python
df = sp.parse_table("examples/programming_languages.csv")
print(df.shape, "|", df.index.name)
print(df.head(3).to_string())
```

```
(12, 7) | Programming Language
                      Performance  Ease of Learning  Ecosystem  Concurrency  Type Safety  Job Market  Tooling
Programming Language
Python                        2.0               5.0        5.0          2.0          2.0         5.0      4.0
Rust                          5.0               2.0        3.0          5.0          5.0         3.0      4.0
Go                            4.0               4.0        4.0          5.0          4.0         4.0      4.0
```

Un tableau Markdown collé depuis un document fonctionne pareil, sans passer par un
fichier :

```python
editors = sp.parse_table("""
| Editor | Speed | Plugins | Learning Curve (↓) |
| --- | --- | --- | --- |
| Neovim | 5 | 5 | 5 |
| VS Code | 3 | 5 | 2 |
| Emacs | 4 | 5 | 5 |
| Sublime | 5 | 3 | 2 |
""")
print(list(editors.columns))
```

```
['Speed', 'Plugins', 'Learning Curve (↓)']
```

`validate_table` est le garde que le pipeline passe pour vous. Il rend `None` quand
le tableau est positionnable et lève une phrase montrable à un utilisateur quand il
ne l'est pas :

```python
print(sp.validate_table(df))
try:
    sp.validate_table(pd.DataFrame({"x": [1.0, 2.0]}))
except ValueError as err:
    print("ValueError:", err)
```

```
None
ValueError: need at least 2 criteria (columns); got 1.
```

Il refuse aussi une colonne sans aucun nombre, un tableau dont tous les critères
sont constants, deux options aux notes identiques (elles tomberaient sur le même
point) ainsi que deux critères identiques (ils compteraient deux fois la même
information).

## 3. Quand le plus bas est le meilleur

Le prix et le poids sont des critères où un nombre *bas* est la bonne nouvelle.
Marquez l'en-tête d'un `(↓)` : Standpoint retire le marqueur, négativise la colonne
puis nomme le pôle par le bénéfice.

```python
laptops = sp.parse_table("examples/laptops.csv")
clean, lower = sp.resolve_polarity(laptops)
print(list(clean.columns))
print("lower is better:", sorted(lower))
```

```
['Price', 'Performance', 'Battery Life', 'Build Quality', 'Weight', 'Screen']
lower is better: ['Price', 'Weight']
```

Si vous ne pouvez pas modifier les en-têtes, nommez les colonnes : les deux chemins
sont équivalents et cumulables.

```python
sp.positioning("examples/laptops.csv", lower_is_better=["Price", "Weight"])
```

```bash
standpoint examples/laptops.csv --lower "Price,Weight" --outdir out
```

C'est pour cela que la carte de la section 1 affiche *Affordable* plutôt que
*Expensive* : le modèle voit `low Price` au lieu de `Price`, donc il nomme ce à quoi
les portables de ce bout sont bons.

## 4. Choisir la référence

La référence est l'option placée en haut à droite ; toute la carte pivote pour l'y
mettre. Le reste de la géométrie ne change pas — c'est bien l'idée : la rotation
change de point de vue, pas de données.

```python
res = sp.analyze(df, reference="Python")
print("reference:", res.reference)
print("rotation: %+.1f deg" % res.rotation_deg)
print("variance kept:", [round(float(v), 4) for v in res.explained_variance_ratio])
print(res.coords().round(2).head(4).to_string())
```

```
reference: Python
rotation: -127.9 deg
variance kept: [0.4936, 0.3042]
            axis-1  axis-2
Python        2.45    2.86
Rust         -1.21   -2.86
Go            0.65   -1.26
JavaScript    2.08    1.57
```

`assign_roles` lit ensuite quatre options directement dans cette géométrie : le
leader, le plus faible au total, puis les deux challengers qui vont le plus loin
vers les pôles du haut et de la droite. Tout le reste est un concurrent.

```python
roles = sp.assign_roles(res)
print({name: role for name, role in zip(res.names, roles) if role != "competitor"})
print(sp.gradient_colors(res, roles)[:4])
```

```
{'Python': 'best', 'Rust': 'worst', 'Java': 'right', 'Ruby': 'top'}
['#FF3B30', '#A52A2A', '#75A857', '#9CB7FF']
```

Forcez une option nommée dans un rôle avec `top=` / `right=` (`--top` / `--right`
en ligne de commande) quand vous voulez parler d'un challenger précis plutôt que du
choix géométrique.

![Carte de positionnement des fournisseurs cloud](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/cloud_providers.png)

## 5. Les six fichiers écrits par une exécution

```python
pos = sp.positioning("examples/laptops.csv")
pos.export("out", stem="laptops")
```

| Fichier | Ce que c'est |
|---|---|
| `laptops.png` | la figure sur fond **transparent**, prête à déposer sur n'importe quelle page |
| `laptops.svg` | la même figure en SVG écrit à la main et interactif (infobulles au survol, sans Vega), modifiable et intégrable |
| `laptops.white.png` | la figure sur fond **blanc**, pour les surfaces sombres où les libellés presque noirs disparaîtraient |
| `laptops.white.svg` | le SVG sur fond blanc |
| `laptops.md` | l'analyse écrite : les faits calculés, puis la lecture du modèle |
| `laptops.yaml` | chaque coordonnée, chaque poids, le rôle, la couleur et les valeurs d'origine |

Chaque face est aussi accessible en mémoire, sans toucher au disque :

```python
print(len(pos.to_svg()), "bytes of SVG")
print("\n".join(pos.to_yaml().splitlines()[:6]))
```

```
6124 bytes of SVG
meta:
  reference: MacBook Air
  rotation_deg: -67.979
  explained_variance_ratio:
  - 0.5268
  - 0.3522
```

Le YAML a trois clés de premier niveau — `meta`, `axes`, `approaches` — et le bloc
`axes` est le contrat stable pour tout ce qui, en aval, veut les noms des pôles sans
relancer de modèle :

```yaml
axes:
  axis_1:
    name: Affordable ↔ Craftsmanship
    pole_left: Affordable
    pole_right: Craftsmanship
    loadings:
      Price: -0.3459
      Performance: 0.1943
      Battery Life: 0.5171
      Build Quality: 0.6472
      Weight: 0.2949
      Screen: 0.2633
```

Enfin `--check` relit les coordonnées écrites pour confirmer que la figure tient.
Aucun modèle n'intervient, donc cela marche hors ligne :

```python
print(sp.assess_layout(pos))
```

```
{'leader_top_right': True, 'readable': True, 'axis_labels_visible': True, 'notes': 'Layout checks passed.'}
```

## 6. Les cellules vides sont signalées, jamais cachées

Une cellule vide est remplie par le minimum de sa colonne : un trou ne flatte donc
jamais une option. Ce choix par défaut est un jugement plutôt qu'une mesure, et
comme chaque critère est centré-réduit avant la projection, il déplace les
coordonnées de *toutes* les options, pas seulement celle qui avait le trou. Chaque
exécution dit donc ce qu'elle a dû inventer.

```python
gaps = sp.parse_table("""
| Tool | Speed | Docs |
| --- | --- | --- |
| A | 5 | 4 |
| B | 3 |  |
| C | 4 | 2 |
""")
print(sp.imputed_cells(gaps))
print(sp.impute(gaps).to_string())
```

```
[('B', 'Docs')]
      Speed  Docs
Tool
A       5.0   4.0
B       3.0   2.0
C       4.0   2.0
```

La ligne de commande le dit sur la sortie d'erreur, avant que la carte n'existe :

```
warning: 1 empty cell(s) filled with the column minimum: Neovim/Docs. Every coordinate below is affected, not just these options -- see meta.imputed_cells in the YAML.
```

et le YAML en garde la trace à deux endroits, une fois globalement puis une fois
par option, pour qu'une ligne seule reste lisible :

```yaml
meta:
  imputed_cells:
  - option: Neovim
    criterion: Docs
```

```yaml
- name: Neovim
  coordinates:
    axis_1: 2.0037
    axis_2: 0.7785
  role: best
  color: '#FF3B30'
  attributes:
    Speed: 5.0
    Plugins: 5.0
    Docs: 3.0
  imputed_attributes:
  - Docs
```

Un tableau complet n'affiche rien du tout. Le but n'est pas de décourager les
trous : c'est qu'un placement inauditable n'est pas auditable.

## 7. Un tableau français donne une carte française

Rien à configurer. La langue est détectée depuis les noms de colonnes, puis elle
pilote les mots des pôles, le nom commun, le titre de la figure et l'analyse.

```python
voitures = sp.parse_table("examples/voitures_electriques.csv")
print(sp.detect_language(list(voitures.columns)))

pos = sp.positioning("examples/voitures_electriques.csv")
print(pos.lang, "|", pos.title)
print(pos.axes)
print({n: r for n, r in pos.role_of.items() if r != "competitor"})
```

```
fr
fr | Voitures dans le quadrant
{'x': 'Économique ↔ Fiable', 'y': 'Sécurisé ↔ Système avancé'}
{'Tesla Model 3': 'best', 'BMW i4': 'right', 'MG4': 'top', 'Dacia Spring': 'worst'}
```

L'anglais, le français et l'espagnol sont pris en charge (`sp.SUPPORTED_LANGS`).
Passez `lang="fr"` pour forcer la langue de sortie quand les noms de colonnes sont
ambigus, voire anglais alors que le lecteur ne l'est pas.

![Carte de positionnement des voitures électriques](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/voitures_electriques.png)

## 8. Auditer la prose du modèle

La face `.md` est découpée exprès : les nombres qu'elle contient (la variance que
garde chaque axe, le cumul, les cellules imputées) sont calculés en Python ; il est
interdit au modèle de citer un pourcentage, une coordonnée ou une note. Il
n'apporte que l'interprétation.

Cela lui laisse quand même la liberté de mettre une option dans le mauvais coin,
donc Standpoint confronte ses propres phrases aux coordonnées. `check_analysis` n'a
besoin d'aucun modèle : il repère les mots de direction, repère les noms d'options
puis compare chaque affirmation au signe de la coordonnée concernée.

```python
pos = sp.positioning("examples/voitures_electriques.csv")
print(sp.check_analysis("Tesla Model 3 sits in the lower left of the map.", pos.result))
print(sp.check_analysis("Tesla Model 3 sits in the upper right of the map.", pos.result))
```

```
['written analysis places Tesla Model 3 on the bottom, but it sits top', 'written analysis places Tesla Model 3 on the left, but it sits right']
[]
```

Chaque exécution le fait pour vous et affiche les désaccords sur la sortie
d'erreur : c'est ainsi que le regroupement abusif d'un petit modèle devient visible
au lieu de partir en production. Extrait d'une vraie exécution sur un tableau de
quatre lignes :

```
written analysis: written analysis places Emacs on the right, but it sits left
written analysis: written analysis places VS Code on the bottom, but it sits top
written analysis: written analysis places VS Code on the right, but it sits left
```

Trois avertissements sur un si petit tableau, c'est le signal honnête que le modèle
est trop petit pour la prose. La figure et le YAML ne sont pas touchés : ils ne sont
jamais passés près d'un modèle.

## 9. Navigateur, API HTTP, outil MCP

Le même pipeline `positioning()`, trois portes de plus. Toutes trois viennent des
extras `[gui]` / `[mcp]` et toutes trois écoutent la boucle locale par défaut, en
respectant `STANDPOINT_HOST` / `STANDPOINT_PORT`.

```bash
standpoint-gui     # Standpoint GUI -> http://127.0.0.1:8000/gui  (Ctrl-C to stop)
standpoint-mcp     # Standpoint API + MCP -> http://127.0.0.1:8000  (MCP at /mcp)
```

`GET /api/example` sert les tableaux suivis, de sorte que la grille du navigateur
part des mêmes fichiers que cette page :

```bash
curl "http://127.0.0.1:8000/api/example?name=laptops"
```

```
Laptop,Price (↓),Performance,Battery Life,Build Quality,Weight (↓),Screen
MacBook Air,3,3,5,5,1,4
MacBook Pro,5,5,4,5,3,5
Dell XPS,4,4,3,4,2,5
```

`POST /api/position` est tout le moteur en un aller-retour. Le corps est le tableau
en texte CSV plus les quelques options que la ligne de commande accepte aussi
(`reference`, `lower`, `model`, `lang`) :

```bash
curl -s -X POST "http://127.0.0.1:8000/api/position" \
  -H 'Content-Type: application/json' \
  -d '{"table":"Editor,Speed,Plugins\nNeovim,5,5\nVS Code,3,5\nEmacs,4,4\n","reference":"Neovim"}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sorted(d)); print(d["axes"]); print(d["roles"]); print(d["slug"], len(d["svg"]), len(d["yaml"]))'
```

```
['axes', 'poles', 'reference', 'roles', 'slug', 'svg', 'yaml']
{'x': 'Innovative ↔ Efficient', 'y': 'Sustainable ↔ Optimized'}
{'Neovim': 'best', 'VS Code': 'worst', 'Emacs': 'right'}
editors 2488 1048
```

Sans `model`, c'est le moteur résolu qui sert ; l'exécution ci-dessus a forcé
`"model": "qwen2.5:3b"` pour que les mots des pôles collent au reste de cette page.

Une entrée invalide revient en code HTTP exploitable plutôt qu'en trace Python :
`400` avec le message de la bibliothèque pour un tableau vide, dégénéré ou une
référence inconnue, `503` quand le modèle local ne sert pas.

```bash
curl -s -X POST "http://127.0.0.1:8000/api/position" \
  -H 'Content-Type: application/json' -d '{"table":""}'
```

```
{"detail":"The table is empty."}
```

`standpoint-mcp` publie ces mêmes routes comme outils MCP sur `/mcp` : un seul
emballage `fastapi-mcp` au-dessus de l'app existante, donc pas de seconde
implémentation qui dériverait. Et `python webapp/build.py` compose la même page en
paquet statique qui fait tourner le moteur dans le navigateur du visiteur via
Pyodide, sans aucun processus serveur ; voir
[GUI.md](https://github.com/warith-harchaoui/standpoint/blob/main/GUI.md).

## Ligne de commande

Une seule commande est installée, `standpoint`, construite avec click.
`python3 -m standpoint` est la même porte sans script de console dans le PATH.

```bash
standpoint --help
```

```
Usage: standpoint [OPTIONS] TABLE

  Turn a comparison TABLE (CSV or Markdown) into a positioning map.

  Writes PNG + interactive SVG + a Markdown analysis + a YAML of every
  coordinate into the output directory, and prints the axis names, the four
  highlighted options and the loadings.

Options:
  -r, --reference TEXT  Option placed top-right: row index or exact name.
                        [default: 0]
  -o, --outdir TEXT     Output directory for the deliverable.  [default: out]
  --stem TEXT           Basename for outputs (default: from reference).
  --top TEXT            Exact name of the option to highlight as strongest
                        toward the top pole.
  --right TEXT          Exact name of the option to highlight as strongest
                        toward the right pole.
  --lower TEXT          Comma-separated criteria where lower is better.
  --model TEXT          Override the local model tag (default: the one
                        resolved in llm.engine.yaml).
  --check               Sanity-check the figure's layout from its geometry.
  -V, --version         Show the version and exit.
  -h, --help            Show this message and exit.
```

Une exécution complète, avec l'auto-vérification de mise en page :

```bash
standpoint examples/laptops.csv --outdir out --check
```

```
Parsed 10 options x 6 criteria
Reference 'MacBook Air' rotated by -68.0 deg onto the top-right diagonal

PCA explained variance: axis-1(PC1)=52.7%  axis-2(PC2)=35.2%  (cumulative 87.9%)

Axis names: axis-1 = 'Affordable ↔ Craftsmanship'   axis-2 = 'Efficiency ↔ Portability'

Highlighted options:
  leader (reference)                : MacBook Air
  weakest overall                   : Lenovo Legion
  strongest toward 'Portability'    : Acer Swift
  strongest toward 'Craftsmanship'  : MacBook Pro

Canonical axes in the oriented frame (loadings):
               axis-1  axis-2
Price          -0.346   0.436
Performance     0.194  -0.515
Battery Life    0.517   0.391
Build Quality   0.647  -0.020
Weight          0.295   0.520
Screen          0.263  -0.349

Deliverable written:
  out/macbook_air.png
  out/macbook_air.svg
  out/macbook_air.white.png
  out/macbook_air.white.svg
  out/macbook_air.md
  out/macbook_air.yaml

Layout self-check:
  leader_top_right: True
  readable        : True
  axis_labels_visible: True
  notes           : Layout checks passed.
```

Les options qui changent la carte :

```bash
standpoint examples/cloud_providers.csv --reference AWS --outdir out
standpoint examples/programming_languages.csv --reference Rust --stem rust --outdir out
standpoint examples/laptops.csv --lower "Price,Weight" --outdir out
standpoint examples/voitures_electriques.csv --model qwen3:8b --check --outdir out
standpoint examples/cloud_providers.csv --top Cloudflare --right "Google Cloud" --outdir out
```

Les quatre tableaux suivis et leur leader :

| Tableau | Langue | Leader (ligne 0) |
|---|---|---|
| `examples/programming_languages.csv` | en | Python |
| `examples/cloud_providers.csv` | en | AWS |
| `examples/laptops.csv` | en | MacBook Air — utilise `Price (↓)` / `Weight (↓)` |
| `examples/voitures_electriques.csv` | fr | Tesla Model 3 |

![Carte de positionnement des langages de programmation](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/programming_languages.png)

## Dépannage

**`Ollama has no model '<tag>'` ou `503 The local model is unavailable`.** Le
nommage des axes a besoin d'un modèle local servi sur `localhost`. Lancez le backend
(`ollama serve`), puis tirez le modèle que le résolveur a retenu ou relancez la
résolution pour cette machine :

```bash
best-engine-ai-helper resolve --brief standpoint/llm.brief.yaml --out standpoint/llm.engine.yaml
```

`standpoint --model qwen3:8b` remplace le nom du modèle pour le nommage des axes
d'une seule exécution. Notez que la figure, le YAML et `--check` n'ont besoin
d'aucun modèle : si la carte vous suffit, une panne ne vous coûte que les mots des
pôles ainsi que la prose.

**`need at least 2 criteria (columns); got 1`.** Une comparaison sur un seul critère
est une liste triée, pas une carte. Le même garde refuse aussi une colonne sans
nombres, un tableau tout constant, des lignes d'options en double ainsi que des
colonnes de critères en double, chaque fois avec une phrase nommant la ligne ou la
colonne fautive.

**`reference '<nom>' not found`.** `--reference` prend soit un indice de ligne (`0`,
par défaut), soit un nom d'option écrit exactement comme dans la première colonne,
espaces et majuscules compris. Mettez les noms à espaces entre guillemets :
`--reference "Google Cloud"`.

**Les noms d'axes sont vagues, répétitifs ou anglais sur un tableau français.** Le
nommage des pôles est la seule étape qui dépende de la qualité du modèle. Un
`--model` plus gros aide le plus ; si la langue est fausse, les noms de colonnes
étaient trop ambigus pour être détectés — passez `lang="fr"` à `positioning()` pour
l'imposer.

**Les libellés sont invisibles sur une page sombre.** Vous regardez le `.png` /
`.svg` transparent. Prenez le `.white.png` / `.white.svg` écrit à côté.

**`Address already in use` au lancement de `standpoint-gui`.** Le port 8000 est très
demandé. Mettez `STANDPOINT_PORT=8001`, sinon lancez vous-même
`uvicorn standpoint.api:app --port 8001`.
