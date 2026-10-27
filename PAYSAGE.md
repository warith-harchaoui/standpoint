# Paysage

[🇫🇷](https://github.com/warith-harchaoui/standpoint/blob/main/PAYSAGE.md) · [🇬🇧](https://github.com/warith-harchaoui/standpoint/blob/main/LANDSCAPE.md)

Où se situe Standpoint parmi les manières habituelles de dessiner une carte de
positionnement (carte perceptuelle) ? La façon honnête d'y répondre est d'*utiliser
Standpoint sur lui-même* : cette page est donc un tableau de comparaison passé dans
l'outil, exactement comme n'importe quel autre exemple.

## En un coup d'œil

La comparaison (le plus haut, le meilleur, sur une échelle de 1 à 5) :

<!-- TABLE:START -->
| Cartes de positionnement | Nommage Automatique des Axes | Une Seule Commande | Exécution Locale | Coordonnées Reproductibles | Sans Code | Sortie Multilingue | Fondé sur l'ACP |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standpoint** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| prince | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| PCA | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| Tableau | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Gartner Magic Quadrant | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Excel/PowerPoint 2x2 | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Modèle Canva/Figma | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/assets/paysage.png)

La carte est un résumé en 2D des 7 critères : à lire comme une forme, pas comme un classement. « Standpoint » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal — Ingéniosité ↔ Maîtrise** et **Vertical — Stabilité ↔ Clarté**.
<!-- FIGURE:END -->

Les en-têtes du tableau étant en français, la carte sort **entièrement en français** :
titre et noms des axes. De quoi illustrer au passage le côté multilingue de
l'outil.

## Positionnement

Deux familles se font face :

- **Les boîtes à outils statistiques d'analyse en composantes principales (ACP)**
  (`prince`, le `PCA` de scikit-learn) sont fortes là où ça compte
  mathématiquement : reproductibles, scriptables, loadings lisibles. Mais elles
  rendent des composantes et des nombres, pas une carte étiquetée et prête à
  partager. Nommer les axes et orienter autour d'une référence reste à votre
  charge.
- **Les outils de mise en page manuels et sans code** (`Tableau`, les 2×2 sous
  `Excel`/`PowerPoint`, les modèles `Canva`/`Figma` et le `Magic Quadrant de
  Gartner`) sont rapides à prendre en main et avec peu ou pas de code, mais chaque
  point est placé à la main : rien n'est dérivé des données, rien n'est
  reproductible et les axes veulent dire ce que l'auteur décide. La version de
  Gartner ajoute un véritable jugement d'analyste et un texte riche autour du
  quadrant, mais les placements restent arbitrés à la main : non dérivés d'une
  matrice et impossibles à exécuter soi-même.

Standpoint occupe le coin qu'aucun d'eux ne couvre : la
carte **dérivée** d'une boîte à outils ACP *plus* l'artéfact **fini et étiqueté**
d'un outil de mise en page manuel : noms d'axes, sortie multilingue et livrable
en deux volets, en une seule commande.

## Réserves honnêtes

- **Standpoint est ici la référence**, donc pivoté en haut à droite par
  construction. Cette carte est notre *lecture des compromis*, pas un classement
  objectif : les notes sont subjectives et « le plus haut, le meilleur » partout. Changez
  la référence (`--reference "PCA"`) et les mêmes données se
  réorientent autour d'elle.
- Le cœur mathématique (ACP de corrélation, loadings lisibles) est **exactement ce
  que les boîtes à outils font bien** : Standpoint ne prétend pas mieux calculer. Ce
  qu'il ajoute, c'est l'automatisation et le livrable fini autour de ce calcul.

## Reproduire

```bash
python3 -m standpoint assets/paysage.csv --outdir assets --stem paysage
```

Le tableau d'entrée est dans [`assets/paysage.csv`](assets/paysage.csv) ; l'exécution
écrit aussi le YAML des coordonnées à côté de la figure.

## Quand choisir quoi

Une comparaison qui ne recommande jamais qu'elle-même est une publicité. Voici donc
la liste pour choisir, lignes où Standpoint est la mauvaise réponse comprises.

- **Vous avez déjà les notes et voulez un placement auditable** : prenez
  Standpoint. Même CSV en entrée, mêmes coordonnées en sortie, plus un YAML qui dit
  quel critère a tiré quelle option où. Cette traçabilité est tout le produit.
- **Vous voulez la décomposition elle-même, pas une image finie** : prenez `prince`
  ou le `PCA` de scikit-learn. Standpoint s'engage sur une seule ACP de corrélation
  tronquée à deux composantes et cache les réglages ; `prince` couvre aussi l'AFC,
  l'ACM, l'AFDM et l'AFM, gère les lignes et colonnes supplémentaires et vous laisse
  le tracé.
- **Les points ne viennent pas d'une matrice de notes** : prenez `Tableau`, `Excel`
  ou `PowerPoint`. Une feuille de route, un plan de table, un 2×2 d'opinions : il n'y
  a aucune matrice à projeter et Standpoint refuse de dessiner ce qu'il ne peut pas
  calculer.
- **Le livrable doit coller au pixel à une charte de présentation** : prenez `Canva`
  ou `Figma`. Le SVG de Standpoint est écrit à la main et modifiable, mais la mise en
  page est la sienne, pas celle de votre système de design.
- **Il vous faut un jugement sur un marché dont vous n'avez aucun chiffre** : lisez
  un `Magic Quadrant de Gartner`. Standpoint n'a aucun avis sur aucun fournisseur ; il
  ne fait qu'arranger les nombres qu'on lui donne et si ces nombres sont des
  suppositions, la carte est une image de vos suppositions.
- **Le tableau est minuscule ou unidimensionnel** : ne prenez ni l'un ni l'autre.
  Standpoint exige au moins deux options et deux critères qui varient vraiment, et
  une comparaison sur un seul critère est une liste triée, pas une carte.

## Sources et date de relevé

**Relevé le 27/10/2026.** Les étoiles ci-dessus sont *notre lecture* de chaque outil
face à chaque critère. Ce ne sont pas des chiffres publiés par ces projets ; rien
sur cette page n'est un banc d'essai : rien n'a été chronométré. Les notes sont
versionnées à côté de la figure qu'elles produisent
([`assets/paysage.csv`](assets/paysage.csv) en français,
[`assets/landscape.csv`](assets/landscape.csv) en anglais), si bien qu'un désaccord
se règle en modifiant une cellule puis en relançant la commande.

Ce qui a servi de base ligne par ligne :

| Ligne | Ce que nous avons regardé |
|---|---|
| `prince` | le README du projet : une implémentation à l'API scikit-learn de l'ACP, de l'AFC, de l'ACM, de l'AFDM, de l'AFM, de la GPA et de la PGA, avec un tracé via Altair — [MaxHalford/prince](https://github.com/MaxHalford/prince) |
| `PCA` | la référence de la classe : `components_` et `explained_variance_ratio_` sont exposés ; `get_feature_names_out()` nomme les axes `pca0`, `pca1`, … ; la classe elle-même ne trace rien — [`sklearn.decomposition.PCA`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html) |
| `Tableau` | le produit tel qu'il est livré, [tableau.com](https://www.tableau.com) |
| `Gartner Magic Quadrant` | les quadrants publiés eux-mêmes, [gartner.com](https://www.gartner.com). La note basse en « Coordonnées Reproductibles » dit que nous n'avons trouvé aucune matrice d'entrée publiée derrière un quadrant, pas que nous savons qu'il n'en existe pas |
| `Excel/PowerPoint 2x2` | les outils de nuage de points et de formes de Microsoft Office tels qu'ils sont livrés |
| `Modèle Canva/Figma` | les modèles de quadrant livrés par les deux éditeurs |

Aucun numéro de version n'apparaît dans le tableau, volontairement. Une note épinglée
à une version est périmée la semaine suivante, alors que ces critères portent sur ce
à quoi chaque outil *sert*, ce qui ne bouge pas d'une version à l'autre. Le seul
critère où l'écart est catégoriel plutôt qu'une affaire de degré est le « Nommage
Automatique des Axes » : chez les six alternatives, un axe porte le champ qu'on y a
déposé ou une formule tapée par l'auteur ; aucune ne lit les loadings pour
proposer des mots aux deux pôles.

Voir le [LISEZMOI](https://github.com/warith-harchaoui/standpoint/blob/main/LISEZMOI.md)
pour ce que fait Standpoint et comment l'installer ; voir
[EXEMPLES.md](https://github.com/warith-harchaoui/standpoint/blob/main/EXEMPLES.md)
pour d'autres exemples travaillés.
