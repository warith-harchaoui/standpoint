# Landscape

[🇫🇷](https://github.com/warith-harchaoui/standpoint/blob/main/PAYSAGE.md) · [🇬🇧](https://github.com/warith-harchaoui/standpoint/blob/main/LANDSCAPE.md)

Where does Standpoint sit among the usual ways of drawing a positioning / perceptual
map? The honest way to answer that is to *use Standpoint on itself*, so this page is
a comparison table run through the tool, exactly like any other example.

## At a glance

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

## Positioning

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

## When to pick what

A comparison that only ever recommends itself is advertising, so here is the
pick-a-tool list, including the rows where Standpoint is the wrong answer.

- **You already have the ratings and want the placement to be auditable** — pick
  Standpoint. Same CSV in, same coordinates out, plus a YAML saying which criterion
  pulled each option where. That audit trail is the whole product.
- **You want the decomposition itself, not a finished picture** — pick `prince` or
  scikit-learn's `PCA`. Standpoint commits to one correlation PCA truncated to two
  components and hides the knobs; `prince` also covers CA, MCA, FAMD and MFA,
  handles supplementary rows and columns, and leaves the plotting to you.
- **The dots are not derived from a rating matrix** — pick `Tableau`, `Excel` or
  `PowerPoint`. A roadmap, a seating plan, a 2×2 of opinions: there is no matrix to
  project, and Standpoint refuses to draw anything it cannot compute.
- **The artefact has to match a brand deck pixel for pixel** — pick `Canva` or
  `Figma`. Standpoint's SVG is hand-authored and editable, but the layout is
  Standpoint's, not your design system's.
- **You need a judgement about a market you have no numbers for** — read a
  `Gartner Magic Quadrant`. Standpoint has no opinion about any vendor; it only
  arranges the numbers you hand it, and if the numbers are guesses the map is a
  picture of your guesses.
- **The table is tiny or one-dimensional** — pick neither. Standpoint needs at
  least two options and two criteria that actually vary, and a single-criterion
  comparison is a sorted list, not a map.

## Sources and as-of date

**As of 2026-10-27.** The star ratings above are *our own reading* of each tool
against each criterion. They are not figures any of these projects publish, and
nothing on this page is a benchmark: nothing was timed. The ratings are versioned
next to the figure they produce — [`assets/landscape.csv`](assets/landscape.csv) in
English, [`assets/paysage.csv`](assets/paysage.csv) in French — so a disagreement is
a one-cell edit and a re-run away.

What each row was read against:

| Row | What we looked at |
|---|---|
| `prince` | the project's own README: a scikit-learn-API implementation of PCA, CA, MCA, FAMD, MFA, GPA and PGA, plotting through Altair — [MaxHalford/prince](https://github.com/MaxHalford/prince) |
| `PCA` | the class reference: `components_` and `explained_variance_ratio_` are exposed, `get_feature_names_out()` names the axes `pca0`, `pca1`, …, and the class itself does no plotting — [`sklearn.decomposition.PCA`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html) |
| `Tableau` | the product as shipped, [tableau.com](https://www.tableau.com) |
| `Gartner Magic Quadrant` | the published quadrants themselves, [gartner.com](https://www.gartner.com). The low `Reproducible Coordinates` rating says we found no published input matrix behind a quadrant — not that we know there is none |
| `Excel/PowerPoint 2x2` | the scatter and shape tools in Microsoft Office as shipped |
| `Canva/Figma template` | the quadrant templates the two editors ship |

No version numbers appear in the table on purpose. A rating pinned to a release
goes stale the week after it is written, and these criteria are about what each
tool is *for*, which does not move release to release. The one criterion where the
gap is categorical rather than a matter of degree is `Automated Axis Naming`: in all
six alternatives an axis carries the field you dropped on it or a phrase the author
typed, and none of them reads the loadings and proposes words for the two poles.

See the [README](https://github.com/warith-harchaoui/standpoint/blob/main/README.md)
for what Standpoint does and how to install it, and
[EXAMPLES.md](https://github.com/warith-harchaoui/standpoint/blob/main/EXAMPLES.md)
for more worked examples.
