# Landscape

[🇫🇷](https://github.com/warith-harchaoui/standingpoint/blob/main/PAYSAGE.md) · [🇬🇧](https://github.com/warith-harchaoui/standingpoint/blob/main/LANDSCAPE.md)

Where does Standpoint sit among the usual ways of drawing a positioning / perceptual
map? The honest way to answer that is to *use Standpoint on itself* — so this page is
a comparison table run through the tool, exactly like any other example.

The comparison (higher is better, on a 1–5 scale):

<!-- TABLE:START -->
| Positioning Maps | Automated Axis Naming | Multilingual Output | Local Execution | One Command | Threefold Deliverable | Reproducibility | Readable Axes | Ease of Setup |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standpoint** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| prince | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| PCA (scikit-learn) | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| factoextra + FactoMineR | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| QuadrantMaker | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Slides or whiteboard | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/standingpoint/main/assets/landscape.png)

The map is a 2-D summary of the eight criteria, so read it as a shape, not a scoreboard. `Standpoint` is at the top-right corner. The axes read **Horizontal — Clarity ↔ Versatility** and **Vertical — Ease ↔ Comprehensive**.
<!-- FIGURE:END -->

## How to read it

Two families sit opposite each other:

- **The statistical PCA toolkits** (`prince`, scikit-learn's `PCA`,
  `factoextra` + `FactoMineR`) are strong where it counts mathematically —
  reproducible, scriptable, readable loadings — but they hand you components and
  numbers, not a labelled, written, ready-to-share map. Naming the axes, orienting
  around a reference, colouring, and writing it up is left to you.
- **The manual quadrant makers** (QuadrantMaker, or just slides / a whiteboard) are
  quick to pick up and need no code, but every dot is placed by hand: nothing is
  derived from the data, nothing is reproducible, and the axes mean whatever you
  decide they mean.

Standpoint's pitch is the corner neither family occupies: the **derived** map of a
PCA toolkit *plus* the **finished, labelled, written** artefact of a manual maker —
axis names, multilingual output, and a three-fold deliverable, from one command.

## Honest caveats

- **Standpoint is the reference row**, so it is rotated to the top-right by
  construction. This map is our *read of the tradeoffs*, not an objective ranking —
  the ratings are subjective and higher-is-better throughout. Change the reference
  (`--reference "PCA (scikit-learn)"`) and the same data re-orients around it.
- The maths at the core (correlation PCA, readable loadings) is **exactly what the
  toolkits do well** — Standpoint doesn't claim to out-compute them. What it adds is
  the automation and the finished deliverable around that maths.

## Reproduce it

```bash
python3 -m standpoint assets/landscape.csv --outdir assets --stem landscape
```

The input table lives at [`assets/landscape.csv`](assets/landscape.csv); the run also
writes the Markdown interpretation and the YAML of coordinates next to the figure.

See the [README](https://github.com/warith-harchaoui/standingpoint/blob/main/README.md)
for what Standpoint does and how to install it, and
[EXAMPLES.md](https://github.com/warith-harchaoui/standingpoint/blob/main/EXAMPLES.md)
for more worked examples.
