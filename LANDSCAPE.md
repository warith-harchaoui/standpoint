# Landscape

[🇫🇷](https://github.com/warith-harchaoui/standpoint/blob/main/PAYSAGE.md) · [🇬🇧](https://github.com/warith-harchaoui/standpoint/blob/main/LANDSCAPE.md)

Where does Standpoint sit among the usual ways of drawing a positioning / perceptual
map? The honest way to answer that is to *use Standpoint on itself*, so this page is
a comparison table run through the tool, exactly like any other example.

The comparison (higher is better, on a 1–5 scale):

<!-- TABLE:START -->
| Positioning Maps | Automated Axis Naming | One Command | Local Execution | Reproducible Coordinates | Written Analysis | No-Code Workflow | Multilingual Output | PCA-Based |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standpoint** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| prince | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| PCA | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| factoextra + FactoMineR | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| Tableau | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Power BI | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Gartner Magic Quadrant | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Excel/PowerPoint 2x2 | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Canva/Figma template | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/assets/landscape.png)

The map is a 2-D summary of the eight criteria, so read it as a shape, not a scoreboard. `Standpoint` is at the top-right corner. The axes read **Horizontal — Accessible ↔ Efficient** and **Vertical — Consistent ↔ Expressive**.
<!-- FIGURE:END -->

## How to read it

Two families sit opposite each other:

- **The statistical PCA toolkits** (`prince`, scikit-learn's `PCA`,
  `factoextra` + `FactoMineR`) are strong where it counts mathematically
  (reproducible, scriptable, readable loadings), but they hand you components and
  numbers, not a labelled, written, ready-to-share map. Naming the axes, orienting
  around a reference, colouring, and writing it up is left to you.
- **The BI dashboards and manual layout tools** (`Tableau`, `Power BI`,
  `Excel`/`PowerPoint` 2×2s, `Canva`/`Figma` templates) are quick to pick up and need
  little or no code, but every dot is placed by hand: nothing is derived from the
  data, nothing is reproducible, and the axes mean whatever you decide they mean.
- **Gartner's Magic Quadrant** sits at the written-analysis pole: it ships a labelled
  quadrant with a genuine narrative around it, but the placements are hand-curated by
  analysts: not derived from a matrix, not reproducible, and not something you can
  run yourself.

Standpoint's pitch is the corner none of them occupies: the **derived** map of a
PCA toolkit *plus* the **finished, labelled, written** artefact of a BI layout or an
analyst write-up: axis names, multilingual output, and a three-fold deliverable, from
one command.

## Honest caveats

- **Standpoint is the reference row**, so it is rotated to the top-right by
  construction. This map is our *read of the tradeoffs*, not an objective ranking:
  the ratings are subjective and higher-is-better throughout. Change the reference
  (`--reference "PCA"`) and the same data re-orients around it.
- The maths at the core (correlation PCA, readable loadings) is **exactly what the
  toolkits do well**. Standpoint doesn't claim to out-compute them. What it adds is
  the automation and the finished deliverable around that maths.

## Reproduce it

```bash
python3 -m standpoint assets/landscape.csv --outdir assets --stem landscape
```

The input table lives at [`assets/landscape.csv`](assets/landscape.csv); the run also
writes the Markdown interpretation and the YAML of coordinates next to the figure.

See the [README](https://github.com/warith-harchaoui/standpoint/blob/main/README.md)
for what Standpoint does and how to install it, and
[EXAMPLES.md](https://github.com/warith-harchaoui/standpoint/blob/main/EXAMPLES.md)
for more worked examples.
