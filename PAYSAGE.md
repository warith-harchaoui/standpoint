# Paysage

[🇫🇷](https://github.com/warith-harchaoui/standpoint/blob/main/PAYSAGE.md) · [🇬🇧](https://github.com/warith-harchaoui/standpoint/blob/main/LANDSCAPE.md)

Où se situe Standpoint parmi les manières habituelles de dessiner une carte de
positionnement (carte perceptuelle) ? La façon honnête d'y répondre est d'*utiliser
Standpoint sur lui-même* : cette page est donc un tableau de comparaison passé dans
l'outil, exactement comme n'importe quel autre exemple.

La comparaison (le plus haut, le meilleur, sur une échelle de 1 à 5) :

<!-- TABLE:START -->
| Cartes de positionnement | Nommage Automatique des Axes | Une Seule Commande | Exécution Locale | Coordonnées Reproductibles | Analyse Rédigée | Sans Code | Sortie Multilingue | Fondé sur l'ACP |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standpoint** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| prince | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| PCA (scikit-learn) | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| factoextra + FactoMineR | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| Tableau | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Power BI | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Gartner Magic Quadrant | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Excel/PowerPoint 2x2 | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Modèle Canva/Figma | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/assets/paysage.png)

La carte est un résumé en 2D des 8 critères : à lire comme une forme, pas comme un classement. « Standpoint » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal — Simplicité ↔ Compréhensibilité** et **Vertical — Précision ↔ Accessibilité**.
<!-- FIGURE:END -->

Les en-têtes du tableau étant en français, la carte sort **entièrement en français** :
titre, noms des axes et analyse. De quoi illustrer au passage le côté multilingue de
l'outil.

## Comment la lire

Deux familles se font face :

- **Les boîtes à outils statistiques d'analyse en composantes principales (ACP)**
  (`prince`, le `PCA` de scikit-learn, `factoextra` + `FactoMineR`) sont fortes là où
  ça compte mathématiquement :
  reproductibles, scriptables, loadings lisibles. Mais elles rendent des
  composantes et des nombres, pas une carte étiquetée, rédigée et prête à partager.
  Nommer les axes, orienter autour d'une référence, colorer et rédiger reste à votre
  charge.
- **Les tableaux de bord BI et outils de mise en page manuels** (`Tableau`,
  `Power BI`, les 2×2 sous `Excel`/`PowerPoint`, les modèles `Canva`/`Figma`) sont
  rapides à prendre en main et avec peu ou pas de code, mais chaque point est placé à
  la main : rien n'est dérivé des données, rien n'est reproductible et les axes
  veulent dire ce que vous décidez.
- **Le Magic Quadrant de Gartner** occupe le pôle de l'analyse rédigée : il livre un
  quadrant étiqueté accompagné d'un véritable texte, mais les placements sont
  arbitrés à la main par des analystes — non dérivés d'une matrice, non
  reproductibles et impossibles à exécuter soi-même.

Standpoint occupe le coin qu'aucun d'eux ne couvre : la
carte **dérivée** d'une boîte à outils ACP *plus* l'artéfact **fini, étiqueté et
rédigé** d'une mise en page BI ou d'un write-up d'analyste : noms d'axes, sortie
multilingue et livrable en trois volets, en une seule commande.

## Réserves honnêtes

- **Standpoint est ici la référence**, donc pivoté en haut à droite par
  construction. Cette carte est notre *lecture des compromis*, pas un classement
  objectif : les notes sont subjectives et « le plus haut, le meilleur » partout. Changez
  la référence (`--reference "PCA (scikit-learn)"`) et les mêmes données se
  réorientent autour d'elle.
- Le cœur mathématique (ACP de corrélation, loadings lisibles) est **exactement ce
  que les boîtes à outils font bien** : Standpoint ne prétend pas mieux calculer. Ce
  qu'il ajoute, c'est l'automatisation et le livrable fini autour de ce calcul.

## Reproduire

```bash
python3 -m standpoint assets/paysage.csv --outdir assets --stem paysage
```

Le tableau d'entrée est dans [`assets/paysage.csv`](assets/paysage.csv) ; l'exécution
écrit aussi l'interprétation Markdown et le YAML des coordonnées à côté de la figure.

Voir le [LISEZMOI](https://github.com/warith-harchaoui/standpoint/blob/main/LISEZMOI.md)
pour ce que fait Standpoint et comment l'installer.
