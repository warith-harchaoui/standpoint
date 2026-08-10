# Exemples

Chaque exemple part d'un tableau du dossier
[`examples/`](https://github.com/warith-harchaoui/standpoint/tree/main/examples).
Chaque exécution écrit six fichiers : la figure transparente `<nom>.png` / `<nom>.svg`,
une version fond blanc `<nom>.white.png` / `<nom>.white.svg` (pour les surfaces sombres,
où les libellés foncés disparaîtraient sur fond transparent), l'analyse `<nom>.md` et
les données `<nom>.yaml`.

## En bibliothèque

```python
import standpoint as sp

pos = sp.positioning("examples/programming_languages.csv")   # chemin, chaîne ou DataFrame
pos.axes            # {'x': 'Scalability ↔ Versatility', 'y': 'Flexibility ↔ Accessibility'}
pos.coords          # DataFrame : coordonnées axe 1 / axe 2 par option
pos.loadings        # DataFrame : poids de chaque critère par axe
pos.role_of         # {'Python': 'best', 'Rust': 'worst', ...}
pos.export("out")   # écrit out/python.{png,svg,white.png,white.svg,md,yaml}
```

Passez un DataFrame si vous en avez déjà un et nommez la référence :

```python
import pandas as pd, standpoint as sp
df = pd.read_csv("examples/cloud_providers.csv", index_col=0)
sp.positioning(df, reference="AWS").export("out")
```

Choisissez un autre modèle local pour le nom des axes et l'analyse :

```python
sp.positioning(df, model="qwen2.5vl:7b").export("out")
```

## En ligne de commande

```bash
standpoint examples/cloud_providers.csv --reference AWS --outdir out
standpoint examples/programming_languages.csv --lower "Ease of Learning" --outdir out
standpoint examples/laptops.csv --outdir out
standpoint examples/voitures_electriques.csv --model qwen2.5vl:7b --check --outdir out
```

## Les exemples

### Langages de programmation (anglais)

Leader : Python. Le nom des axes vient directement des poids calculés (loadings).

![Carte de positionnement des langages de programmation](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/programming_languages.png)

### Fournisseurs cloud (anglais)

Leader : AWS.

![Carte de positionnement des fournisseurs cloud](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/cloud_providers.png)

### Ordinateurs portables (anglais)

Leader : MacBook Air. `Price (↓)` et `Weight (↓)` montrent la notation en ligne pour
une colonne où une valeur plus basse est meilleure, sans besoin de l'option `--lower`.

![Carte de positionnement des ordinateurs portables](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/laptops.png)

### Voitures électriques (français)

Les noms de colonnes sont en français, donc le nom des axes et l'analyse écrite sortent
eux aussi en français. Leader : Tesla Model 3.

![Carte de positionnement des voitures électriques](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/voitures_electriques.png)

## Les fichiers de sortie

- `.png` et `.svg` : la figure sur fond **transparent**, prête à déposer sur n'importe
  quelle page. Le SVG est écrit à la main et interactif (infobulles au survol, sans
  Vega) : on peut le modifier ou l'intégrer où l'on veut.
- `.white.png` et `.white.svg` : la même figure sur fond **blanc**, pour les surfaces
  sombres (par exemple le mode sombre de GitHub) où les libellés presque noirs
  deviendraient sinon invisibles.
- `.md` : une courte analyse écrite. Ce que signifient les axes, où le leader l'emporte,
  quels groupes se distinguent, plus les poids et un classement.
- `.yaml` : les métadonnées (variance, rotation), les poids de chaque axe et, pour
  chaque option, ses coordonnées, son rôle, sa couleur et ses valeurs d'origine.
