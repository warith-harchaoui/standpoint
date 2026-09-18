# Landscape

[🇫🇷](https://github.com/warith-harchaoui/standpoint/blob/main/PAYSAGE.md) · [🇬🇧](https://github.com/warith-harchaoui/standpoint/blob/main/LANDSCAPE.md)

Where does Standpoint sit among the usual ways of drawing a positioning / perceptual
map? The honest way to answer that is to *use Standpoint on itself*, so this page is
a comparison table run through the tool, exactly like any other example.

The comparison (higher is better, on a 1–5 scale):

<!-- TABLE:START -->
| Positioning Maps | Automated Axis Naming | One Command | Local Execution | Reproducible Coordinates | No-Code Workflow | Multilingual Output | PCA-Based |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standpoint** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| prince | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| PCA | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| Tableau | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Gartner Magic Quadrant | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| Excel/PowerPoint 2x2 | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Canva/Figma template | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/assets/landscape.png)

The map is a 2-D summary of the seven criteria, so read it as a shape, not a scoreboard. `Standpoint` is at the top-right corner. The axes read **Horizontal — Accessible ↔ Efficient** and **Vertical — Consistent ↔ Intuitive**.
<!-- FIGURE:END -->

## How to read it

Two families sit opposite each other:

- **The statistical PCA toolkits** (`prince`, scikit-learn's `PCA`) are strong where
  it counts mathematically (reproducible, scriptable, readable loadings), but they
  hand you components and numbers, not a labelled, ready-to-share map. Naming the
  axes and orienting around a reference is left to you.
- **The manual, no-code layout tools** (`Tableau`, `Excel`/`PowerPoint` 2×2s,
  `Canva`/`Figma` templates, and `Gartner's Magic Quadrant`) are quick to pick up and
  need little or no code, but every dot is placed by hand: nothing is derived from
  the data, nothing is reproducible, and the axes mean whatever the author decides
  they mean. Gartner's version adds real analyst judgment and a rich write-up
  around the quadrant, but the placements are still hand-curated: not derived from
  a matrix, and not something you can run yourself.

Standpoint's pitch is the corner none of them occupies: the **derived** map of a
PCA toolkit *plus* the **finished, labelled** artefact of a manual layout tool: axis
names, multilingual output, and a two-fold deliverable, from one command.

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
writes the YAML of coordinates next to the figure.

See the [README](https://github.com/warith-harchaoui/standpoint/blob/main/README.md)
for what Standpoint does and how to install it, and
[EXAMPLES.md](https://github.com/warith-harchaoui/standpoint/blob/main/EXAMPLES.md)
for more worked examples.
