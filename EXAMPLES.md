# Examples

Every example uses a table from
[`examples/`](https://github.com/warith-harchaoui/standpoint/tree/main/examples).
Each run writes six files: the transparent figure `<name>.png` / `<name>.svg`, a
white-background `<name>.white.png` / `<name>.white.svg` (for dark surfaces where the
dark labels would vanish on transparency), the `<name>.md` analysis, and the
`<name>.yaml` data.

## As a library

```python
import standpoint as sp

pos = sp.positioning("examples/programming_languages.csv")   # path, string, or DataFrame
pos.axes            # {'x': 'Scalability ↔ Versatility', 'y': 'Flexibility ↔ Accessibility'}
pos.coords          # DataFrame: axis-1 / axis-2 per option
pos.loadings        # DataFrame: criterion weights per axis
pos.role_of         # {'Python': 'best', 'Rust': 'worst', ...}
pos.export("out")   # writes out/python.{png,svg,white.png,white.svg,md,yaml}
```

Pass a DataFrame if you already have one, and name the reference:

```python
import pandas as pd, standpoint as sp
df = pd.read_csv("examples/cloud_providers.csv", index_col=0)
sp.positioning(df, reference="AWS").export("out")
```

Choose a different local model for the axis names and analysis:

```python
sp.positioning(df, model="qwen2.5vl:7b").export("out")
```

## From the command line

```bash
standpoint examples/cloud_providers.csv --reference AWS --outdir out
standpoint examples/programming_languages.csv --lower "Ease of Learning" --outdir out
standpoint examples/laptops.csv --outdir out
standpoint examples/voitures_electriques.csv --model qwen2.5vl:7b --check --outdir out
```

## The examples

### Programming languages (English)

Leader: Python. The axis names come from the loadings.

![Programming languages positioning map](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/programming_languages.png)

### Cloud providers (English)

Leader: AWS.

![Cloud providers positioning map](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/cloud_providers.png)

### Laptops (English)

Leader: MacBook Air. `Price (↓)` and `Weight (↓)` show the inline notation for a
column where lower is better, no `--lower` flag needed.

![Laptops positioning map](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/laptops.png)

### Voitures électriques (French)

The column names are French, so the axis names and the written analysis come out in
French. Leader: Tesla Model 3.

![Carte de positionnement des voitures électriques](https://raw.githubusercontent.com/warith-harchaoui/standpoint/main/examples/voitures_electriques.png)

## The output files

- `.png` and `.svg`: the figure on a **transparent** background, so it drops onto any
  page. The SVG is hand-authored and interactive (hover tooltips, no Vega): edit or
  embed it anywhere.
- `.white.png` and `.white.svg`: the same figure on a **white** background, for dark
  surfaces (e.g. GitHub dark mode) where the near-black labels would otherwise vanish.
- `.md`: a short written analysis. What the axes mean, where the leader wins, which
  groups stand out, plus the loadings and a ranking.
- `.yaml`: metadata (variance, rotation), each axis's loadings, and every option's
  coordinates, role, colour, and original values.
