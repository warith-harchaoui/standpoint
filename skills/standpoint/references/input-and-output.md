# Input and output

## The input table

A CSV or Markdown table. The **first column** holds the option names; **every other
column** is a numeric criterion, on any scale (1–5, 0–100, prices, latencies…).

- **Higher means better** by default.
- A **blank** cell is filled with that column's minimum — a missing rating never
  flatters an option.
- The **first row is the reference**: it is rotated to the top-right. Change it with
  `--reference "<name>"` (a name) or `--reference 3` (a row index).
- For a criterion where **lower is better**, mark the header `Price (↓)` or list it in
  `--lower Price,Latency`. standpoint negates it and names the pole for the benefit
  ("Affordable", "Portable") — never the drawback.
- Needs at least **2 options and 2 criteria** with some variation, or PCA is undefined.

```
Cloud,Compute,Storage,Network,Price (↓),Docs
AWS,5,5,5,3,4
GCP,4,4,5,3,5
Azure,4,4,4,4,3
DigitalOcean,3,3,3,5,4
```

Markdown tables work identically (first column = names, pipe-delimited).

## What gets written

`export("out")` / `standpoint … --outdir out` writes seven files per table (`<name>`
is derived from the reference, or set with `--stem`):

| File | What it is |
|---|---|
| `<name>.png` / `<name>.svg` | the figure, **transparent** background (drops onto any page) |
| `<name>.white.png` / `<name>.white.svg` | the figure on **white** (for dark surfaces) |
| `<name>.vl.json` | the Vega-Lite spec — edit or embed it anywhere Vega runs |
| `<name>.md` | the written analysis (axes, highlighted options, plain-language read) |
| `<name>.yaml` | metadata, per-axis loadings, and every option's coordinates / role / colour / original values |

## How to read the map

- The **reference** sits top-right (it leads). If it scores top marks on everything, it
  is placed just past the best competitor rather than as a far outlier.
- Four options are highlighted by colour: the **leader** (reference), the **weakest**
  (its exact opposite), and the two **challengers** that reach furthest toward the top
  and right poles.
- Each axis is a readable weighted sum of the criteria; its two ends are named as
  positive qualities, in the table's own language.
- The two axes carry a stated fraction of the information — read the map as a summary,
  not the whole truth.
