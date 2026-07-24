"""Standpoint — know where each option actually stands.

Explainable 2D PCA positioning map from any comparison table.

Turn a table of *approaches x criteria* (CSV or Markdown, numeric ratings on any
scale) into a competitive positioning map, plus a written interpretation and a
full dump of the coefficients — a three-fold deliverable from one input file.

Pipeline
--------
1. parse   : CSV or Markdown table -> numeric DataFrame (blanks -> minimum value
             of the non-blank, non-NaN values in that column).
2. prepare : normalization (default = z-score standardization, i.e. correlation
             PCA, because PCA is scale-sensitive and criteria carry different
             variances). Missing cells are imputed with the column minimum.
3. pca_2d  : PCA onto 2 components, keeping the canonical axes (loadings) so
             every axis stays a readable linear combination of the criteria.
4. orient  : rigidly rotate the 2D scatter so the reference row (the first row by
             default) leads in the TOP-RIGHT, and reposition an all-max reference
             to the best Pareto point; RECOMPUTE the canonical axes in the rotated
             frame (new_components = R(alpha) @ components).

Then: automatic roles by principled projection, distinct OKLCH colours by map
position, local-LLM axis pole names from the loadings, and a de-cluttered
Vega-Lite figure. `export_all` writes PNG + SVG + Vega JSON + a Markdown analysis
+ a YAML of coordinates and coefficients.

Author
------
Warith Harchaoui — https://www.linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

__author__ = "Warith Harchaoui"
__url__ = "https://www.linkedin.com/in/warith-harchaoui"
__version__ = "0.4.0"

import argparse
import json
import logging
import math
import os
import re
from dataclasses import dataclass

import numpy as np
import ollama
import pandas as pd
import vl_convert as vlc
import yaml
from langdetect import DetectorFactory
from langdetect import detect as _langdetect
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

DetectorFactory.seed = 0  # deterministic language detection

# Library diagnostics go through logging, never bare print (a library must not
# grab stdout). The CLI in `run()` is the one place that prints on purpose.
logger = logging.getLogger("standpoint")

# "Good Colors" Apple-base palette — https://harchaoui.org/warith/colors/.
# The four highlighted roles keep a fixed identity hue; the axis cross and labels
# use neutrals. Every other dot is coloured by its map position (`gradient_colors`).
PALETTE = {
    "reference": "#FF3B30",  # Red    — the reference leader (best), sits top-right
    "right": "#007AFF",  # Blue   — challenger that most defines the right pole
    "worst": "#A52A2A",  # Brown  — weakest overall, sits bottom-left
    "top": "#AF52DE",  # Purple — challenger that most defines the top pole
    "competitor": "#8E8E93",  # Gray   — placeholder; overridden by gradient_colors
    "axis": "#C7C7CC",  # light gray for the centred, dotted axis cross
    "label": "#1C1C1E",  # near-black label text
}
FONT = "Roboto, -apple-system, Helvetica, Arial, sans-serif"

# One qwen vision-LLM for everything: axis pole names, the written analysis, and
# the visual assessment of the rendered figure (see `vlm_assess`). This is the
# single source of truth for the model; override it once via the shared
# AI_HELPERS_LLM_MODEL env var. No other model is used.
DEFAULT_MODEL = os.environ.get("AI_HELPERS_LLM_MODEL", "qwen2.5vl:7b")

__all__ = [
    "positioning",
    "Positioning",
    "parse_table",
    "analyze",
    "PCAResult",
    "assign_roles",
    "axis_poles",
    "gradient_colors",
    "to_vega",
    "render_figures",
    "png_on_white",
    "export_all",
    "analysis_markdown",
    "results_yaml",
    "validate_table",
    "resolve_polarity",
    "detect_language",
    "i18n",
    "vlm_assess",
    "run",
    "main",
]


# --------------------------------------------------------------------------- #
# 1. parse
# --------------------------------------------------------------------------- #
def _cell_to_number(cell: str) -> float:
    """Convert one table cell to a number (int or float); blanks -> NaN."""
    cell = cell.replace("**", "").strip()
    if cell.lower() in {"", "-", "—", "?", "n/a", "na", "null", "none"}:
        return np.nan
    try:
        return float(cell.replace(",", "."))
    except ValueError:
        return np.nan


def _looks_like_markdown(text: str) -> bool:
    """True if any line starts with a pipe, i.e. the text is a Markdown table."""
    return any(line.lstrip().startswith("|") for line in text.splitlines())


def _parse_markdown(text: str) -> pd.DataFrame:
    """Parse a GitHub-flavoured Markdown table into a numeric DataFrame.

    The first pipe-delimited row is the header (its first cell names the index);
    the separator row (only pipes/dashes/colons) is dropped, and every remaining
    cell is coerced to a number via `_cell_to_number`.
    """
    rows = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    # A GitHub separator row is only pipes/dashes/colons/spaces.
    rows = [r for r in rows if not re.fullmatch(r"[|\s:\-]+", r)]

    def split(row: str) -> list[str]:
        """Split one table row into stripped cell strings, dropping edge pipes."""
        return [c.strip() for c in row.strip().strip("|").split("|")]

    header = split(rows[0])
    records, index = [], []
    for row in rows[1:]:
        cells = split(row)
        name = cells[0].replace("**", "").strip()
        index.append(name)
        records.append([_cell_to_number(c) for c in cells[1:]])
    frame = pd.DataFrame(records, index=index, columns=header[1:])
    frame.index.name = header[0]  # keep the first-column name (e.g. "Language")
    return frame


def parse_table(source: str) -> pd.DataFrame:
    """Parse a markdown/CSV table (path or raw string) into a numeric DataFrame.

    The first column becomes the row index (approach names); every other cell is
    parsed as a number (int or float); blanks become NaN.
    """
    text = source
    is_path = "\n" not in source and len(source) < 4096
    if is_path:
        try:
            with open(source, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, ValueError):
            text, is_path = source, False  # not a real path -> treat as raw text

    if _looks_like_markdown(text):
        return _parse_markdown(text)

    df = pd.read_csv(source if is_path else pd.io.common.StringIO(text), index_col=0)
    return df.map(lambda c: _cell_to_number(str(c)))


# --------------------------------------------------------------------------- #
# i18n — detect the table's language and localize the LLM prompts
# --------------------------------------------------------------------------- #
SUPPORTED_LANGS = ("en", "fr", "es")
_I18N_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales", "i18n.yaml")
_I18N_CACHE: dict | None = None


def i18n(lang: str = "en") -> dict:
    """Prompt templates for `lang` (falls back to English), loaded from i18n.yaml."""
    global _I18N_CACHE
    if _I18N_CACHE is None:
        with open(_I18N_PATH, encoding="utf-8") as fh:
            _I18N_CACHE = yaml.safe_load(fh)
    return _I18N_CACHE.get(lang, _I18N_CACHE["en"])


def detect_language(texts: list[str]) -> str:
    """Detect the language (one of SUPPORTED_LANGS) from text; default English.

    Used on the table's column names so the pole labels and written analysis come
    out in the table's own language.
    """
    sample = " ".join(t for t in texts if t).strip()
    if not sample:
        return "en"
    try:
        lang = _langdetect(sample)
    except Exception:
        return "en"
    return lang if lang in SUPPORTED_LANGS else "en"


# --------------------------------------------------------------------------- #
# 2. prepare (normalization / preprocessing)
# --------------------------------------------------------------------------- #
def validate_table(df: pd.DataFrame) -> None:
    """Raise a clear ``ValueError`` if the table can't be positioned.

    Needs at least 2 options (rows) and 2 numeric criteria (columns) with some
    variation, and no fully-empty column — otherwise PCA is undefined or degenerate.
    """
    if df.shape[0] < 2:
        raise ValueError(f"need at least 2 options (rows); got {df.shape[0]}.")
    if df.shape[1] < 2:
        raise ValueError(f"need at least 2 criteria (columns); got {df.shape[1]}.")
    all_nan = [c for c in df.columns if df[c].isna().all()]
    if all_nan:
        raise ValueError(f"criteria with no numeric values at all: {all_nan}.")
    constant = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
    if len(constant) == df.shape[1]:
        raise ValueError("every criterion is constant; nothing to position.")


def _resolve_reference(df: pd.DataFrame, reference: int | str) -> int:
    """Return the row index of the reference, with a helpful error if it's unknown."""
    if isinstance(reference, str):
        if reference not in df.index:
            raise ValueError(f"reference {reference!r} is not one of the options.")
        return int(df.index.get_loc(reference))
    if not -df.shape[0] <= reference < df.shape[0]:
        raise ValueError(f"reference index {reference} is out of range (0..{df.shape[0] - 1}).")
    return int(reference % df.shape[0])


def impute(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing cells with each column's minimum observed value.

    A blank criterion is treated as the worst (minimum) value for that criterion,
    rather than the mean — a missing rating should not flatter an approach.
    """
    return df.fillna(df.min(numeric_only=True))


# A header marker declaring a criterion as lower-is-better, e.g. "Price (↓)",
# "Latency (lower)", "Errors (lower is better)". Stripped from the shown name.
_LOWER_MARK = re.compile(
    r"\s*\(?\s*(↓|lower(?:\s+is\s+better)?|less\s+is\s+better)\s*\)?\s*$", re.I
)


def resolve_polarity(
    df: pd.DataFrame, lower_is_better: list[str] | None = None
) -> tuple[pd.DataFrame, frozenset[str]]:
    """Detect lower-is-better criteria and return a clean-named copy + their names.

    A criterion is lower-is-better if its header carries a marker (``Price (↓)``,
    ``Latency (lower)``) or is named in `lower_is_better`. Markers are stripped from
    the column name; the returned set uses the cleaned names.
    """
    explicit = {c.strip() for c in (lower_is_better or [])}
    rename, lower = {}, set()
    for col in df.columns:
        clean = _LOWER_MARK.sub("", str(col)).strip()
        if clean != col:  # had a marker
            lower.add(clean)
        if clean in explicit or col in explicit:
            lower.add(clean)
        rename[col] = clean
    out = df.rename(columns=rename)
    return out, frozenset(lower & set(out.columns))


def prepare(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Impute missing cells (column minimum), then z-score standardize -> correlation PCA.

    Standardization (mean 0, sd 1 per criterion) is the right normalization here,
    always: PCA is scale-sensitive, and criteria live on different scales and units,
    so each must get an equal say. A criterion with a larger numeric spread would
    otherwise dominate the components purely because of its units.
    """
    x = StandardScaler().fit_transform(impute(df).to_numpy(dtype=float))
    return x, list(df.columns)


# --------------------------------------------------------------------------- #
# 3./4. PCA + orientation
# --------------------------------------------------------------------------- #
def _rotation(alpha: float) -> np.ndarray:
    """The 2x2 counter-clockwise rotation matrix for an angle `alpha` (radians)."""
    c, s = np.cos(alpha), np.sin(alpha)
    return np.array([[c, -s], [s, c]])


@dataclass
class PCAResult:
    names: list[str]  # row labels
    features: list[str]  # attribute names
    scores: np.ndarray  # (n, 2) oriented coordinates
    components: np.ndarray  # (2, p) oriented canonical axes (loadings)
    explained_variance_ratio: np.ndarray  # from the original PCA fit
    rotation_deg: float  # alpha applied, in degrees
    reference: str  # row placed top-right
    x_std: np.ndarray  # (n, p) normalized feature matrix (PCA input)
    lower: frozenset[str] = frozenset()  # criteria where lower is better (negated)

    def loadings(self) -> pd.DataFrame:
        """Criterion weights per oriented axis, as a features x (axis-1, axis-2) frame."""
        return pd.DataFrame(self.components.T, index=self.features, columns=["axis-1", "axis-2"])

    def coords(self) -> pd.DataFrame:
        """Oriented (axis-1, axis-2) coordinates, one row per option."""
        return pd.DataFrame(self.scores, index=self.names, columns=["axis-1", "axis-2"])


def analyze(
    df: pd.DataFrame,
    reference: int | str = 0,
    soften_reference: float = 1.0,
    lower_is_better: list[str] | None = None,
) -> PCAResult:
    """Run the full pipeline: prepare -> PCA(2) -> rotate reference to top-right.

    The reference row is rotated onto the +45 deg diagonal (equal, positive
    coordinates = top-right corner). The canonical axes are then recomputed in
    the rotated frame so their loadings describe the *displayed* axes.

    `soften_reference` repositions an all-max reference (a straight-5-stars first
    row otherwise lands as a far outlier) to the best **Pareto** point: max x and
    max y of the competitors, times this factor (default 1.0 = exactly best-in-class
    on each axis, so it weakly dominates everyone without being an outlier). Set to
    0 or None to keep the raw PCA position.

    `lower_is_better` names criteria where a lower value is better (price, latency).
    They are negated before the PCA so the whole space is uniformly higher-is-better;
    header markers like ``Price (↓)`` are picked up automatically too.
    """
    df, lower = resolve_polarity(df, lower_is_better)
    validate_table(df)
    ref_idx = _resolve_reference(df, reference)
    signed = df.copy()
    if lower:
        signed[list(lower)] = -signed[list(lower)]  # flip so higher is better
    x, features = prepare(signed)

    pca = PCA(n_components=2)
    scores = pca.fit_transform(x)  # (n, 2) in original PC frame
    components = pca.components_  # (2, p) rows = PC1, PC2

    ref_vec = scores[ref_idx]
    phi = np.arctan2(ref_vec[1], ref_vec[0])  # current angle of the reference
    alpha = np.pi / 4 - phi  # rotate it onto +45 deg

    r = _rotation(alpha)
    scores_rot = scores @ r.T  # rotate every point
    components_rot = r @ components  # recompute canonical axes

    if soften_reference:
        # Place the reference at the best *Pareto* point: just beyond best-in-class
        # on each axis, so it weakly dominates every competitor without being a far
        # outlier. Realistic leader, top-right, on the frontier.
        others = np.delete(scores_rot, ref_idx, axis=0)
        ideal_x = max(float(others[:, 0].max()), 0.0) * soften_reference
        ideal_y = max(float(others[:, 1].max()), 0.0) * soften_reference
        if ideal_x > 0 and ideal_y > 0:
            scores_rot[ref_idx] = [ideal_x, ideal_y]

    # Centre the cloud on the origin (mid-range), so the axis cross sits in its
    # middle with equal margins on every side. Because the reference is the max on
    # both axes, this leaves it at the exact top-right corner.
    scores_rot = scores_rot - (scores_rot.max(axis=0) + scores_rot.min(axis=0)) / 2

    return PCAResult(
        names=list(df.index),
        features=features,
        scores=scores_rot,
        components=components_rot,
        explained_variance_ratio=pca.explained_variance_ratio_,
        rotation_deg=float(np.degrees(alpha)),
        reference=str(df.index[ref_idx]),
        x_std=x,
        lower=lower,
    )


# --------------------------------------------------------------------------- #
# roles (colour semantics)
# --------------------------------------------------------------------------- #
# Four highlighted roles, each a *domain-agnostic* pick from the map geometry
# (see `assign_roles`): the leader, the weakest, and the two challengers that
# reach furthest toward the top and right poles. Highest priority last (wins
# ties): competitor < right < top < worst < best.
ROLE_ORDER = ["competitor", "right", "top", "worst", "best"]
ROLE_STYLE = {
    "best": {"color": PALETTE["reference"], "size": 170, "bold": True},
    "worst": {"color": PALETTE["worst"], "size": 120, "bold": True},
    "top": {"color": PALETTE["top"], "size": 120, "bold": True},
    "right": {"color": PALETTE["right"], "size": 120, "bold": True},
    "competitor": {"color": PALETTE["competitor"], "size": 70, "bold": False},
}


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    """Convert an (r, g, b) triple in [0, 1] to a clamped ``#RRGGBB`` hex string."""
    r, g, b = (max(0, min(255, round(c * 255))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def _oklab_to_hex(lightness: float, a: float, b: float) -> str:
    """Convert an OKLab colour (Ottosson 2020) to a clamped sRGB hex string."""
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    lc, mc, sc = l_**3, m_**3, s_**3
    rgb_lin = (
        +4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc,
        -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc,
        -0.0041960863 * lc - 0.7034186147 * mc + 1.7076147010 * sc,
    )

    def gamma(u: float) -> float:
        """Apply the sRGB transfer function to one clamped linear channel."""
        u = max(0.0, min(1.0, u))
        return 1.055 * u ** (1 / 2.4) - 0.055 if u > 0.0031308 else 12.92 * u

    return _rgb_to_hex(tuple(gamma(c) for c in rgb_lin))


# Dot-colour tuning: competitors get vivid OKLCH hues spread EVENLY around the
# circle (ordered by map direction) so hues are balanced — no muddy midtones, no
# clumping toward pink — with a gentle per-name lightness spread for extra variety.
_DOT_CHROMA = 0.125
_L_LO, _L_HI = 0.62, 0.82


def gradient_colors(result: PCAResult, roles: list[str]) -> list[str]:
    """Distinct, clean per-approach colours.

    Competitors are placed at EVENLY spaced hues around the OKLCH circle in order
    of their direction on the map — balanced hues, every colour vivid (fixed
    chroma, never a muddy centre), all distinct. Lightness gets a small per-name
    spread for extra separation. Named roles keep their fixed identity hue.
    """
    scores = result.scores
    n = len(scores)
    comps = [i for i in range(n) if roles[i] == "competitor"]

    # Order competitors by map direction, then hand out evenly spaced hues.
    angles = np.arctan2(scores[:, 1], scores[:, 0])
    ordered = sorted(comps, key=lambda i: float(angles[i]))
    m = max(1, len(ordered))
    lightness_key = sorted(comps, key=lambda i: (sum(map(ord, result.names[i])), i))
    l_of = {
        i: _L_LO + (_L_HI - _L_LO) * (rank / max(1, len(comps) - 1))
        for rank, i in enumerate(lightness_key)
    }

    colors = [""] * n
    for rank, i in enumerate(ordered):
        hue = 2 * math.pi * (rank / m)  # evenly spaced around the wheel
        colors[i] = _oklab_to_hex(l_of[i], _DOT_CHROMA * math.cos(hue), _DOT_CHROMA * math.sin(hue))
    for i, role in enumerate(roles):
        if role != "competitor":
            colors[i] = ROLE_STYLE[role]["color"]
    return colors


def legend_order(scores: np.ndarray) -> list[int]:
    """Indices in reading order that matches the map, starting at the extreme
    top-right: banded rows top -> bottom, and within each row right -> left.
    """
    n = len(scores)
    if n == 0:
        return []
    bands = max(1, round(n**0.5))
    per = math.ceil(n / bands)
    top_to_bottom = sorted(range(n), key=lambda i: -float(scores[i][1]))
    order: list[int] = []
    for b in range(bands):
        row = top_to_bottom[b * per : (b + 1) * per]
        row.sort(key=lambda i: -float(scores[i][0]))  # right -> left within the row
        order.extend(row)
    return order


def corner_extremes(scores: np.ndarray) -> dict[str, int]:
    """Index of the most extreme point toward each corner (tr, tl, br, bl)."""
    sx, sy = scores[:, 0], scores[:, 1]
    return {
        "tr": int(np.argmax(sx + sy)),
        "tl": int(np.argmax(sy - sx)),
        "br": int(np.argmax(sx - sy)),
        "bl": int(np.argmax(-sx - sy)),
    }


# Candidate label placements around a dot, as (dir_x, dir_y): right, left, up, down,
# then the four diagonals — the first that doesn't collide wins.
_LABEL_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)]


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """True if two axis-aligned boxes ``(x0, y0, x1, y1)`` intersect."""
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def label_placements(
    result: PCAResult,
    view_x: float,
    view_y: float,
    width_px: int = 900,
    height_px: int = 760,
    font_px: float = 11.0,
) -> dict[int, tuple[float, float]]:
    """Greedy de-clutter: choose which approaches to label and *where* to put each
    label. For every dot (corner extremes first, then outermost), try eight
    placements around it and keep the first that overlaps neither another label nor
    any dot marker. Returns {index: (label_x, label_y)} for the labels that fit.

    `view_x` / `view_y` are the half-extents of each axis's domain (they can differ),
    so the pixel-to-data conversion is correct even when the map is not square.
    """
    scores = result.scores
    sx = 2 * view_x / width_px  # data units per pixel, x
    sy = 2 * view_y / height_px  # data units per pixel, y
    pad = 4 * sx
    dot_rx, dot_ry = 7 * sx, 7 * sy
    boxes = [(x - dot_rx, y - dot_ry, x + dot_rx, y + dot_ry) for x, y in scores]

    corners = list(corner_extremes(scores).values())
    others = sorted(
        (i for i in range(len(result.names)) if i not in corners),
        key=lambda i: -float(np.hypot(*scores[i])),
    )
    placements: dict[int, tuple[float, float]] = {}
    for i in corners + others:
        x, y = scores[i]
        w = len(result.names[i]) * 0.58 * font_px * sx
        h = 1.3 * font_px * sy
        best = None  # (distance, box, (lx, ly)) — pick the free side nearest the dot
        for ox, oy in _LABEL_DIRS:
            lx = x + ox * (dot_rx + pad + w / 2)  # clear the dot marker, then pad
            ly = y + oy * (dot_ry + pad + h / 2)
            box = (lx - w / 2, ly - h / 2, lx + w / 2, ly + h / 2)
            if any(_overlaps(box, b) for b in boxes):
                continue
            dist = math.hypot(lx - x, ly - y)
            if best is None or dist < best[0]:
                best = (dist, box, (float(lx), float(ly)))
        if best is not None:
            boxes.append(best[1])
            placements[i] = best[2]
    return placements


def _axis_champion(axis_values: np.ndarray, exclude: set[int]) -> int:
    """Index of the option reaching furthest (largest value) along one axis.

    Parameters
    ----------
    axis_values : np.ndarray
        One column of the oriented scores, e.g. every option's axis-1 coordinate.
    exclude : set[int]
        Row indices to skip (typically the leader, and an already-claimed champion),
        so the same option is never highlighted twice.

    Returns
    -------
    int
        Row index of the highest not-excluded value along `axis_values`.
    """
    order = np.argsort(axis_values)[::-1]  # highest coordinate first
    return int(next(i for i in order if int(i) not in exclude))


def assign_roles(
    result: PCAResult,
    top: str | None = None,
    right: str | None = None,
) -> list[str]:
    """Label four options by domain-agnostic map geometry; the rest are competitors.

    Every pick is read straight off the oriented coordinates, so it means the same
    thing for any table (no per-domain keyword list):

    best   the reference, sitting at the top-right corner by construction;
    worst  the weakest overall: the minimum projection onto the top-right hero
           diagonal (equivalently the smallest axis-1 + axis-2);
    top    the challenger reaching furthest up the vertical axis — the peer that
           most defines the map's *top* pole (the leader excluded);
    right  the challenger reaching furthest along the horizontal axis — the peer
           that most defines the *right* pole (leader and top champion excluded).

    Parameters
    ----------
    result : PCAResult
        The oriented positioning (`scores` and `reference`).
    top, right : str, optional
        Force a specific option into the top-pole / right-pole highlight by exact
        name, bypassing the geometric pick.

    Returns
    -------
    list[str]
        One role per option, aligned with ``result.names``; collisions resolve by
        ``ROLE_ORDER`` (best beats worst beats the two champions).
    """
    names = result.names
    scores = result.scores
    best_idx = names.index(result.reference)

    # Hero axis = the +45 deg diagonal after orientation; project onto (1, 1)/sqrt(2).
    hero_projection = scores @ (np.ones(2) / np.sqrt(2))
    worst_idx = int(next(i for i in np.argsort(hero_projection) if i != best_idx))

    # The leader is the max on both axes, so a champion is the *next* option out
    # along each axis — the challenger that best embodies that winning pole.
    top_idx = names.index(top) if top is not None else _axis_champion(scores[:, 1], {best_idx})
    right_idx = (
        names.index(right)
        if right is not None
        else _axis_champion(scores[:, 0], {best_idx, top_idx})
    )

    roles = ["competitor"] * len(names)
    for role in ROLE_ORDER[1:]:  # skip "competitor" (default); low -> high priority
        idx = {"right": right_idx, "top": top_idx, "worst": worst_idx, "best": best_idx}[role]
        roles[idx] = role
    return roles


# --------------------------------------------------------------------------- #
# axis naming (local LLM interprets the loading weights + column names)
# --------------------------------------------------------------------------- #
# Expand common acronyms to real words — never show acronyms in the figure.
_ACRONYM_WORDS = {
    "tco": "Cost",
    "pii": "Privacy",
    "gdpr": "Compliance",
    "ux": "Experience",
    "fr": "French",
    "ev": "Vehicles",
    "ai": "Intelligence",
    "qa": "Quality",
    "stt": "Speech",
    "api": "Interface",
    "diy": "Homemade",
}


def _deacronym(label: str) -> str:
    """Expand or drop acronym tokens in a label so the figure shows real words."""
    out = []
    for tok in label.split():
        if tok.isupper() and len(tok) <= 5:  # looks like an acronym
            expanded = _ACRONYM_WORDS.get(tok.lower())
            if expanded:
                out.append(expanded)
            # unknown acronym -> drop it
        else:
            out.append(tok)
    return " ".join(out).strip()


def _one_word(feature: str) -> str:
    """A single real word from an attribute name — longest non-acronym token,
    expanding known acronyms so the figure never shows abbreviations.
    """
    toks = re.findall(r"[^\W\d_]+", feature, re.UNICODE)  # Unicode letters (keeps é, à, ç…)
    words = [t for t in toks if len(t) > 1 and not t.isupper()]  # drop acronyms
    if words:
        return max(words, key=len).capitalize()
    for tok in toks:  # only acronyms left
        if tok.lower() in _ACRONYM_WORDS:
            return _ACRONYM_WORDS[tok.lower()]
    return _ACRONYM_WORDS.get(feature.strip().lower(), feature.strip().capitalize())


# Small stop-words ignored when comparing labels for shared content words.
_LABEL_STOP = {
    "and",
    "the",
    "for",
    "with",
    "your",
    "our",
    "per",
    "les",
    "des",
    "las",
    "los",
    "una",
    "por",
    "con",
    "sur",
    "del",
}

# A pole must be a positive quality; these markers signal a drawback (en/fr/es) and
# get the label rejected — e.g. "High Cost", "Slow", "Expensive" never appear.
_NEGATIVE_WORDS = {
    "high",
    "low",
    "expensive",
    "costly",
    "slow",
    "complex",
    "complicated",
    "poor",
    "weak",
    "insecure",
    "unreliable",
    "difficult",
    "limited",
    "hidden",
    "risky",
    "lack",
    "worse",
    "bad",
    "élevé",
    "eleve",
    "cher",
    "lent",
    "complexe",
    "coûteux",
    "couteux",
    "difficile",
    "faible",
    "alto",
    "caro",
    "lento",
    "complejo",
    "costoso",
    "débil",
    "debil",
    "riesgo",
}


def _content_words(label: str) -> set[str]:
    """Significant lowercase words in a label (>= 3 letters, minus stop-words)."""
    return {
        t for t in re.findall(r"[a-zA-Z]+", label.lower()) if len(t) >= 3 and t not in _LABEL_STOP
    }


def _clean_label(label: str) -> str:
    """Expand acronyms, split camelCase, and keep at most three words."""
    label = _deacronym(label) if label else ""
    label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label).strip()  # split camelCase
    return " ".join(label.split()[:3])


def finalize_poles(raw: list[str], fallback: list[str]) -> list[str]:
    """Turn raw LLM pole labels into four clean, distinct, non-antonymous labels.

    Enforces: real words (no acronyms), at most three words, no label repeated, and
    no two labels sharing a content word — which rules out antonym pairs such as
    'Cost Efficient' / 'High Cost'. A rejected label is replaced by its
    loading-derived fallback (drawn from a different criterion).
    """

    def bad(w: str) -> bool:
        """True if label `w` must be rejected: empty, duplicate, shares a content
        word with an already-accepted label (rules out antonym pairs), or contains
        a negative word (a pole must name a positive quality).
        """
        cw = _content_words(w)
        return (
            not w or w.lower() in seen or bool(cw & used_words) or bool(cw & _NEGATIVE_WORDS)
        )  # never a drawback / negative

    out: list[str] = []
    seen: set[str] = set()
    used_words: set[str] = set()
    for i, (label, fb) in enumerate(zip(raw, fallback, strict=False)):
        w = _clean_label(label)
        if bad(w):
            w = _clean_label(fb)  # fall back to the loading word
            if bad(w):
                w = f"{w} {i}"
        seen.add(w.lower())
        used_words |= _content_words(w)
        out.append(w)
    return out


def _fallback_poles(components: np.ndarray, features: list[str]) -> list[str]:
    """Four distinct pole words [left, right, bottom, top] from the loadings.

    left/right = low/high end of axis-1; bottom/top = low/high end of axis-2.
    Each pole takes the most extreme not-yet-used attribute at that end.
    """
    specs = [(0, 1), (0, -1), (1, 1), (1, -1)]  # (axis, +1=ascending->low end first)
    used: set[str] = set()
    poles: list[str] = []
    for axis, sign in specs:
        order = np.argsort(components[axis])[::sign]  # sign +1 -> low end first
        word = next(
            (w for i in order if (w := _one_word(features[i])).lower() not in used),
            _one_word(features[order[0]]),
        )
        used.add(word.lower())
        poles.append(word)
    return poles


def _poles_to_names(poles: list[str]) -> list[str]:
    """[left, right, bottom, top] -> ['left ↔ right', 'bottom ↔ top']."""
    left, right, bottom, top = poles
    return [f"{left} ↔ {right}", f"{bottom} ↔ {top}"]


def axis_poles(
    result: PCAResult, model: str = DEFAULT_MODEL, lang: str | None = None
) -> list[str]:
    """Four distinct pole labels [left, right, bottom, top] for the two axes.

    Each PCA axis is a weighted mix of the criteria. The local LLM names each pole
    (1-3 words) for what the approaches at that end are collectively strongest at,
    from the signed loadings and the original column names — in the table's own
    language (auto-detected from the column names; see `i18n.yaml`). Always uses the
    local model; loading-derived words only serve as the per-label robustness fallback
    when the model returns a bad label (see `finalize_poles`).
    """
    feats = result.features
    fallback_poles = _fallback_poles(result.components, feats)
    if lang is None:
        lang = detect_language(feats)
    tpl = i18n(lang)

    try:
        # Every rating is higher-is-better, so a pole is best described by the
        # criteria approaches THERE score high on (its sign of the loading).
        def show(f: str) -> str:
            """Present a criterion to the model, flagging negated (lower-better) ones.

            A lower-is-better criterion was negated for the PCA, so a high score
            means a LOW raw value: show it as "low <name>" so the model names the
            benefit ("Affordable") rather than the drawback ("Expensive").
            """
            return f"low {f}" if f in result.lower else f

        def pole_strengths(k: int, sign: int) -> str:
            """Criteria (with weights) that define one end of axis `k`.

            `sign` selects the end: +1 for the positive-loading pole, -1 for the
            negative one. Returns them strongest-first as a human-readable string,
            or "—" when nothing loads meaningfully on that end.
            """
            pairs = [
                (f, w)
                for f, w in zip(feats, result.components[k], strict=False)
                if (w > 0) == (sign > 0) and abs(w) > 0.05
            ]
            pairs.sort(key=lambda t: -abs(t[1]))
            return ", ".join(f"{show(f)} (weight {abs(w):.2f})" for f, w in pairs) or "—"

        # Glossary of any acronyms present in the columns, so the model translates
        # them instead of echoing them (built from the actual column names).
        present = {
            a.upper(): w
            for a, w in _ACRONYM_WORDS.items()
            if any(a.upper() in f.upper() for f in feats)
        }
        glossary = (
            (tpl["glossary_prefix"] + "; ".join(f"{k} = {v}" for k, v in present.items()) + ".\n\n")
            if present
            else ""
        )
        prompt = tpl["axis_prompt"].format(
            glossary=glossary,
            left=pole_strengths(0, -1),
            right=pole_strengths(0, +1),
            bottom=pole_strengths(1, -1),
            top=pole_strengths(1, +1),
        )
        schema = {
            "type": "object",
            "properties": {k: {"type": "string"} for k in ("left", "right", "bottom", "top")},
            "required": ["left", "right", "bottom", "top"],
        }
        resp = ollama.chat(
            model=model,
            format=schema,
            options={"temperature": 0},
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(resp["message"]["content"])
        raw = [str(data.get(k, "")) for k in ("left", "right", "bottom", "top")]
        # Clean, de-duplicate, and reject antonym/shared-word pairs.
        return finalize_poles(raw, fallback_poles)
    except Exception:  # ollama missing / model absent / bad JSON
        logger.error("axis naming: LLM unavailable; the local model is required")
        raise


def noun_forms(
    word: str, model: str = DEFAULT_MODEL, lang: str | None = None
) -> tuple[str, str]:
    """Singular and plural of `word` (the first-column name), in its own language.

    Used for the figure title and legend heading, so a table of "Language" reads
    "Languages in the Quadrant". The prompt lives in `i18n.yaml`. Always uses the
    local model; a naive `+s` plural only serves as the robustness fallback when the
    model is unreachable or returns a form that drifts from the column word.
    """
    word = (word or "Approach").strip() or "Approach"
    if len(word) > 1 and word.lower().endswith("s"):  # looks plural already
        naive = (word[:-1].capitalize(), word.capitalize())
    else:
        naive = (word.capitalize(), word.capitalize() + "s")
    if lang is None:
        lang = detect_language([word])
    try:
        schema = {
            "type": "object",
            "properties": {"singular": {"type": "string"}, "plural": {"type": "string"}},
            "required": ["singular", "plural"],
        }
        resp = ollama.chat(
            model=model,
            format=schema,
            options={"temperature": 0},
            messages=[{"role": "user", "content": i18n(lang)["noun_prompt"].format(word=word)}],
        )
        data = json.loads(resp["message"]["content"])
        s = (str(data.get("singular") or "").strip() or naive[0]).capitalize()
        p = (str(data.get("plural") or "").strip() or naive[1]).capitalize()
        # Guard against the model swapping in a synonym (e.g. Voiture -> Véhicules):
        # a valid form must share a prefix with the actual column word.
        prefix = word.lower()[: max(3, len(word) - 2)]
        if not s.lower().startswith(prefix):
            s = naive[0]
        if not p.lower().startswith(prefix):
            p = naive[1]
        return s, p
    except Exception:
        return naive


# --------------------------------------------------------------------------- #
# Vega-Lite
# --------------------------------------------------------------------------- #
def to_vega(
    result: PCAResult,
    roles: list[str] | None = None,
    poles: list[str] | None = None,
    colors: list[str] | None = None,
    noun_plural: str = "Approaches",
    title: str | None = None,
) -> dict:
    """Build a self-contained Vega-Lite v5 spec (inline data) for the map.

    Layers, bottom to top: a centred cross of axes through the origin (the neutral
    intersection), every approach coloured by its position (Apple-wheel HSV), the
    four pole words at the axis ends, and labels for the four corner extremes. No
    frame, spines, ticks, numeric scales, or arrows.

    `title` is the fully-localized figure title (e.g. "Voitures dans le quadrant");
    when omitted it defaults to the English "<plural> in the Quadrant" so direct
    callers still get a sensible heading.
    """
    ref = result.reference
    names = result.names
    if roles is None:
        roles = ["best" if n == ref else "competitor" for n in names]
    if poles is None:
        poles = _fallback_poles(result.components, result.features)
    left, right, bottom, top = poles

    if colors is None:
        colors = gradient_colors(result, roles)
    n = len(names)

    # Per-axis extents so each axis fills its own space: a low-variance axis (e.g.
    # PC2) is not squashed flat against the cross. Each axis gets its own domain.
    span_x = float(np.abs(result.scores[:, 0]).max()) or 1.0
    span_y = float(np.abs(result.scores[:, 1]).max()) or 1.0
    # Wide margin: the dots occupy the central ~65%, leaving the outer band clear
    # for the pole phrases at the axis ends.
    view_x, view_y = span_x * 1.55, span_y * 1.55

    # Sizes adapt to the option count: bigger when few, smaller when many.
    def _scaled(lo: int, hi: int, few: int = 8, many: int = 40) -> int:
        """Interpolate a size between `hi` (at `few` options) and `lo` (at `many`).

        Keeps the map legible across table sizes: large glyphs on a sparse map,
        smaller ones once the plot gets crowded. Clamped outside ``[few, many]``.
        """
        t = (min(max(n, few), many) - few) / (many - few)
        return round(hi + (lo - hi) * t)

    label_font = _scaled(11, 17)
    pole_font = _scaled(13, 22)
    legend_font = _scaled(9, 13)
    dot_size = _scaled(90, 240)

    placements = label_placements(result, view_x, view_y, font_px=label_font)

    # Legend follows the map: rows top -> bottom, left -> right within each row.
    order = legend_order(result.scores)
    legend_names = [names[i] for i in order]
    legend_colors = [colors[i] for i in order]

    points = [
        {
            "name": nm,
            "axis1": float(x),
            "axis2": float(y),
            "role": r,
            "color": c,
            "label": nm if i in placements else "",
            "labelx": placements.get(i, (x, y))[0],
            "labely": placements.get(i, (x, y))[1],
        }
        for i, ((x, y), nm, r, c) in enumerate(
            zip(result.scores, names, roles, colors, strict=False)
        )
    ]

    xdom = {"domain": [-view_x, view_x]}
    ydom = {"domain": [-view_y, view_y]}
    bare = {"domain": False, "ticks": False, "labels": False, "grid": False, "title": None}
    xenc = {"field": "axis1", "type": "quantitative", "scale": xdom, "axis": bare}
    yenc = {"field": "axis2", "type": "quantitative", "scale": ydom, "axis": bare}

    def rule(x0: float, x1: float, y0: float, y1: float) -> dict:
        """A Vega-Lite layer drawing one dotted axis segment in data coordinates."""
        return {
            "data": {"values": [{}]},
            "mark": {"type": "rule", "color": PALETTE["axis"], "size": 1.2, "strokeDash": [2, 4]},
            "encoding": {
                "x": {"datum": x0, "type": "quantitative", "scale": xdom, "axis": bare},
                "x2": {"datum": x1},
                "y": {"datum": y0, "type": "quantitative", "scale": ydom, "axis": bare},
                "y2": {"datum": y1},
            },
        }

    def pole_label(x: float, y: float, text: str, align: str, baseline: str) -> dict:
        """A Vega-Lite text layer placing one italic pole word at an axis end."""
        return {
            "data": {"values": [{"x": x, "y": y, "t": text}]},
            "mark": {
                "type": "text",
                "fontSize": pole_font,
                "fontStyle": "italic",
                "color": "#6E6E73",
                "align": align,
                "baseline": baseline,
            },
            "encoding": {
                "x": {"field": "x", "type": "quantitative", "scale": xdom, "axis": bare},
                "y": {"field": "y", "type": "quantitative", "scale": ydom, "axis": bare},
                "text": {"field": "t", "type": "nominal"},
            },
        }

    edge_x, edge_y = view_x * 0.98, view_y * 0.98  # axes span the full view
    gap_x, gap_y = span_x * 0.04, span_y * 0.04  # keep pole words off the lines
    layers = [
        rule(-edge_x, edge_x, 0, 0),  # horizontal axis
        rule(0, 0, -edge_y, edge_y),  # vertical axis
        pole_label(edge_x, gap_y, right, "right", "bottom"),
        pole_label(-edge_x, gap_y, left, "left", "bottom"),
        pole_label(gap_x, edge_y, top, "left", "top"),
        pole_label(gap_x, -edge_y, bottom, "left", "bottom"),
        {  # every dot coloured by position; legend maps name -> colour
            "data": {"values": points},
            "mark": {
                "type": "point",
                "filled": True,
                "opacity": 0.95,
                "stroke": "white",
                "strokeWidth": 1,
                "size": dot_size,
            },
            "encoding": {
                "x": xenc,
                "y": yenc,
                "color": {
                    "field": "name",
                    "type": "nominal",
                    "scale": {"domain": legend_names, "range": legend_colors},
                    "legend": {
                        "title": noun_plural,
                        "symbolLimit": 0,
                        "labelFontSize": legend_font,
                        "symbolOpacity": 1,
                    },
                },
                "tooltip": [
                    {"field": "name", "type": "nominal"},
                    {"field": "role", "type": "nominal"},
                    {"field": "axis1", "type": "quantitative", "format": ".2f"},
                    {"field": "axis2", "type": "quantitative", "format": ".2f"},
                ],
            },
        },
        {  # labels — de-cluttered, placed on whichever side is free
            "data": {"values": points},
            "transform": [{"filter": "datum.label != ''"}],
            "mark": {
                "type": "text",
                "align": "center",
                "baseline": "middle",
                "fontSize": label_font,
                "color": PALETTE["label"],
            },
            "encoding": {
                "x": {"field": "labelx", "type": "quantitative"},
                "y": {"field": "labely", "type": "quantitative"},
                "text": {"field": "label", "type": "nominal"},
            },
        },
    ]

    # The plotting area is tall enough that the one-row-per-approach legend beside
    # it is never taller than the canvas (so it can't be clipped).
    height = max(720, 24 * n + 140)
    if title is None:  # direct callers get the English default; localized via i18n
        title = f"{noun_plural} in the Quadrant"
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": title, "font": FONT, "fontSize": 18},
        # Transparent background: Vega-Lite otherwise bakes an opaque white rectangle
        # into the PNG/SVG. Null lets the map drop cleanly onto any page or slide.
        "background": None,
        "width": 1000,
        "height": height,
        "autosize": {"type": "pad", "resize": True},  # grow to fit the legend
        "config": {
            "font": FONT,
            "padding": 12,
            "view": {"stroke": None},  # no box around the plotting area
            "axis": {
                "grid": False,
                "domain": False,
                "ticks": False,
                "labels": False,
                "labelFont": FONT,
                "titleFont": FONT,
            },
            "text": {"font": FONT},
        },
        "layer": layers,
    }


# --------------------------------------------------------------------------- #
# Three-fold export: figures (PNG + SVG + Vega JSON), markdown, YAML
# --------------------------------------------------------------------------- #
def render_figures(spec: dict, stem: str) -> list[str]:
    """Rasterize/vectorize a Vega-Lite spec to transparent and white PNG + SVG.

    Writes four files: the transparent `<stem>.png` / `<stem>.svg` (the default, for
    dropping onto any coloured page) and a white-background `<stem>.white.png` /
    `<stem>.white.svg` (for dark surfaces — e.g. GitHub dark mode — where the map's
    near-black labels would otherwise vanish on a transparent background). Returns
    the four paths in that order.
    """
    written: list[str] = []
    # `spec` already carries background:null; the ".white" pass overrides it. Same
    # layout both times, so the only difference is the baked-in backdrop.
    for suffix, variant in ((".", spec), (".white.", {**spec, "background": "white"})):
        png_path, svg_path = f"{stem}{suffix}png", f"{stem}{suffix}svg"
        with open(png_path, "wb") as fh:
            fh.write(vlc.vegalite_to_png(vl_spec=variant, scale=2.0))
        with open(svg_path, "w", encoding="utf-8") as fh:
            fh.write(vlc.vegalite_to_svg(vl_spec=variant))
        written += [png_path, svg_path]
    return written


def png_on_white(spec: dict) -> bytes:
    """Render `spec` to PNG bytes on an opaque white background.

    The exported figures are transparent, but the vision self-check sends the image
    to a model whose backend flattens transparency onto a dark canvas — which would
    hide the near-black labels and legend and make the check misfire. White is the
    figure's intended reading surface, so the check runs against a white-composited
    copy rather than the transparent file on disk.
    """
    return vlc.vegalite_to_png(vl_spec={**spec, "background": "white"}, scale=2.0)


def vlm_assess(image: str | bytes, model: str = DEFAULT_MODEL) -> dict:
    """Ask the qwen vision-LLM to sanity-check a rendered positioning map.

    `image` is a PNG path or raw PNG bytes (bytes let the caller assess a
    white-composited render without touching the transparent file on disk). Returns
    a verdict dict — whether the red leader dot sits top-right, whether the labels
    are readable, and whether the legend is fully visible — plus free-text notes.
    Empty dict if the model or a rendered image is unavailable.
    """
    schema = {
        "type": "object",
        "properties": {
            "leader_top_right": {"type": "boolean"},
            "readable": {"type": "boolean"},
            "legend_visible": {"type": "boolean"},
            "notes": {"type": "string"},
        },
        "required": ["leader_top_right", "readable", "legend_visible", "notes"],
    }
    prompt = (
        "This image is a 2D competitor positioning map. The single RED dot is the "
        "leader and should sit in the TOP-RIGHT area. Assess three things: (1) is "
        "the red leader dot in the top-right? (2) are the point labels readable and "
        "not badly overlapping? (3) is the legend on the right fully visible, not "
        "cut off? Reply as JSON."
    )
    try:
        resp = ollama.chat(
            model=model,
            format=schema,
            options={"temperature": 0},
            messages=[{"role": "user", "content": prompt, "images": [image]}],
        )
        return json.loads(resp["message"]["content"])
    except Exception:
        return {}


def _llm_text(prompt: str, model: str, fallback: str) -> str:
    """Free-text completion from the local model; `fallback` if unreachable."""
    try:
        resp = ollama.chat(
            model=model,
            options={"temperature": 0.3},
            messages=[{"role": "user", "content": prompt}],
        )
        return resp["message"]["content"].strip() or fallback
    except Exception:
        return fallback


def _approx_pct(fraction: float) -> str:
    """Format a fraction as an approximate percentage — nearest 5, with a '~' prefix.

    An exact figure like '89%' reads as false precision in a written takeaway; '~90%'
    conveys the same magnitude at an honest resolution.
    """
    return f"~{round(fraction * 20) * 5}%"


def analysis_markdown(
    result: PCAResult,
    roles: list[str],
    poles: list[str],
    model: str = DEFAULT_MODEL,
    lang: str | None = None,
) -> str:
    """A thoughtful, precise interpretation of the map as Markdown.

    Combines data-derived facts (axis loadings, variance, roles, coordinates) with
    an LLM-written narrative in the table's own language (auto-detected). Falls
    back to a templated narrative when the model is unavailable.
    """
    left, right, bottom, top = poles
    evr = result.explained_variance_ratio
    names = result.names
    role_of = dict(zip(names, roles, strict=False))
    coords = result.coords()
    if lang is None:
        lang = detect_language(result.features)

    def order_line(k: int) -> str:
        """Axis `k`'s criteria in order — from the ones pulling toward its positive
        (right/top) pole to those pulling toward the negative one. Names only: the
        ordering is what a reader can use; the raw weights are noise here.
        """
        pairs = sorted(
            zip(result.features, result.components[k], strict=False), key=lambda t: -t[1]
        )
        return " · ".join(f for f, _ in pairs)

    ranked = sorted(names, key=lambda n: -(coords.loc[n].sum()))
    role_rows = {
        r: next((n for n, rr in role_of.items() if rr == r), "—")
        for r in ("best", "worst", "top", "right")
    }

    narrative = _llm_text(
        i18n(lang)["narrative_prompt"].format(
            left=left,
            right=right,
            bottom=bottom,
            top=top,
            reference=result.reference,
            best=role_rows["best"],
            worst=role_rows["worst"],
            champ_top=role_rows["top"],
            champ_right=role_rows["right"],
            leaderboard=", ".join(ranked[:8]),
        ),
        model,
        fallback=(
            f"The map's horizontal axis contrasts **{left}** (left) with **{right}** "
            f"(right); the vertical contrasts **{bottom}** (bottom) with **{top}** "
            f"(top), together capturing {_approx_pct(evr.sum())} of the information that tells "
            f"these approaches apart. **{result.reference}** anchors the top-right as the "
            f"reference leader, strongest on the {right.lower()} and {top.lower()} "
            f"directions. **{role_rows['worst']}** sits opposite as the weakest on "
            f"these dimensions, while among the challengers **{role_rows['top']}** "
            f"reaches furthest toward {top.lower()} and **{role_rows['right']}** "
            f"furthest toward {right.lower()}."
        ),
    )

    lines = [
        f"# {result.reference}",
        "",
        "## Interpretation",
        "",
        narrative,
        "",
        "## Axes",
        "",
        f"**Horizontal — {left} ↔ {right}** — {_approx_pct(evr[0])} of the information.",
        "",
        f"Relevant columns for axis: {order_line(0)}.",
        "",
        f"**Vertical — {bottom} ↔ {top}** — {_approx_pct(evr[1])} of the information.",
        "",
        f"Relevant columns for axis: {order_line(1)}.",
        "",
        f"In two axes, we preserved **{_approx_pct(evr.sum())}** of the information.",
        "",
        "## Highlighted approaches",
        "",
        f"- **Chosen leader reference:** {role_rows['best']}",
        f"- **Exact reference opposite:** {role_rows['worst']} (diametrically opposite the leader on the map)",
        f"- **Strongest toward {top}:** {role_rows['top']} (challenger furthest up "
        "the vertical axis)",
        f"- **Strongest toward {right}:** {role_rows['right']} (challenger furthest "
        "along the horizontal axis)",
        "",
    ]
    return "\n".join(lines)


def results_yaml(
    df: pd.DataFrame,
    result: PCAResult,
    roles: list[str],
    poles: list[str],
    axis_names: list[str],
    colors: list[str],
) -> str:
    """Everything about the fit as YAML: metadata, axis loadings, and per-approach
    coordinates, roles, colours, and original attribute values."""
    evr = result.explained_variance_ratio
    left, right, bottom, top = poles
    feats = result.features
    raw = impute(df)

    doc = {
        "meta": {
            "reference": result.reference,
            "rotation_deg": round(result.rotation_deg, 3),
            "explained_variance_ratio": [round(float(v), 4) for v in evr],
            "cumulative_variance": round(float(evr.sum()), 4),
            "n_approaches": len(result.names),
            "attributes": feats,
            "lower_is_better": sorted(result.lower),
        },
        "axes": {
            "axis_1": {
                "name": axis_names[0],
                "pole_left": left,
                "pole_right": right,
                "loadings": {
                    f: round(float(w), 4) for f, w in zip(feats, result.components[0], strict=False)
                },
            },
            "axis_2": {
                "name": axis_names[1],
                "pole_bottom": bottom,
                "pole_top": top,
                "loadings": {
                    f: round(float(w), 4) for f, w in zip(feats, result.components[1], strict=False)
                },
            },
        },
        "approaches": [
            {
                "name": n,
                "coordinates": {"axis_1": round(float(x), 4), "axis_2": round(float(y), 4)},
                "role": role,
                "color": color,
                "attributes": {f: round(float(raw.loc[n, f]), 3) for f in feats},
            }
            for n, (x, y), role, color in zip(
                result.names, result.scores, roles, colors, strict=False
            )
        ],
    }
    return yaml.dump(doc, sort_keys=False, allow_unicode=True, width=100)


def export_all(
    df: pd.DataFrame,
    result: PCAResult,
    roles: list[str],
    poles: list[str],
    axis_names: list[str],
    colors: list[str],
    stem: str,
    model: str = DEFAULT_MODEL,
    noun_plural: str = "Approaches",
    title: str | None = None,
) -> list[str]:
    """Write the full three-fold deliverable for one table: figures (PNG + SVG +
    Vega JSON), a Markdown interpretation, and a YAML of coordinates + coefficients.
    Returns the list of paths written.
    """
    spec = to_vega(
        result, roles=roles, poles=poles, colors=colors, noun_plural=noun_plural, title=title
    )
    written = render_figures(spec, stem)
    for path, text in [
        (f"{stem}.vl.json", json.dumps(spec, indent=2, ensure_ascii=False)),
        (f"{stem}.md", analysis_markdown(result, roles, poles, model)),
        (f"{stem}.yaml", results_yaml(df, result, roles, poles, axis_names, colors)),
    ]:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        written.append(path)
    return written


# --------------------------------------------------------------------------- #
# Convenience API — the one-liner library face
# --------------------------------------------------------------------------- #
@dataclass
class Positioning:
    """Result of `positioning()` — the map plus everything computed for it."""

    df: pd.DataFrame
    result: PCAResult
    roles: list[str]
    poles: list[str]
    axis_names: list[str]
    colors: list[str]
    noun_singular: str = "Approach"
    noun_plural: str = "Approaches"
    title: str = "Approaches in the Quadrant"  # fully-localized figure title

    @property
    def coords(self) -> pd.DataFrame:
        """Oriented (axis-1, axis-2) coordinates per option."""
        return self.result.coords()

    @property
    def loadings(self) -> pd.DataFrame:
        """Axis loadings (criterion weights) per axis."""
        return self.result.loadings()

    @property
    def axes(self) -> dict[str, str]:
        """The two axis names, e.g. {'x': 'Cost ↔ Innovation', 'y': ...}."""
        return {"x": self.axis_names[0], "y": self.axis_names[1]}

    @property
    def role_of(self) -> dict[str, str]:
        """Map each option name to its role (best / worst / … / competitor)."""
        return dict(zip(self.result.names, self.roles, strict=False))

    def to_vega(self) -> dict:
        """The Vega-Lite spec for the map."""
        return to_vega(
            self.result,
            self.roles,
            self.poles,
            self.colors,
            noun_plural=self.noun_plural,
            title=self.title,
        )

    def to_markdown(self, model: str = DEFAULT_MODEL) -> str:
        """The written interpretation as Markdown."""
        return analysis_markdown(self.result, self.roles, self.poles, model)

    def to_yaml(self) -> str:
        """All coordinates + coefficients as YAML."""
        return results_yaml(
            self.df, self.result, self.roles, self.poles, self.axis_names, self.colors
        )

    def figure(self, stem: str) -> list[str]:
        """Render the map to `<stem>.png` and `<stem>.svg`; returns the paths."""
        return render_figures(self.to_vega(), stem)

    def export(
        self,
        outdir: str = ".",
        stem: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> list[str]:
        """Write the full three-fold deliverable into `outdir`; returns the paths."""
        os.makedirs(outdir, exist_ok=True)
        name = stem or re.sub(r"[^A-Za-z0-9]+", "_", self.result.reference).strip("_").lower()
        return export_all(
            self.df,
            self.result,
            self.roles,
            self.poles,
            self.axis_names,
            self.colors,
            os.path.join(outdir, name),
            model=model,
            noun_plural=self.noun_plural,
            title=self.title,
        )


def positioning(
    data: pd.DataFrame | str,
    reference: int | str = 0,
    top: str | None = None,
    right: str | None = None,
    lower_is_better: list[str] | None = None,
    model: str = DEFAULT_MODEL,
) -> Positioning:
    """Position options from a table in one call.

    `data` is a pandas DataFrame (options × numeric criteria) or a path / raw string
    of a CSV or Markdown table. `lower_is_better` names criteria where a lower value
    is better (also picked up from ``(↓)`` header markers). `top` / `right` force a
    named option into the top-pole / right-pole highlight (see `assign_roles`).
    Returns a `Positioning` with `.coords`, `.loadings`, `.axes`, `.to_vega()`,
    `.to_markdown()`, `.to_yaml()`, and `.export(outdir)`.

    >>> pos = positioning("examples/programming_languages.csv")
    >>> pos.export("out")
    """
    df = data if isinstance(data, pd.DataFrame) else parse_table(data)
    df, lower = resolve_polarity(df, lower_is_better)  # clean names + lower set
    result = analyze(df, reference=reference, lower_is_better=list(lower))
    roles = assign_roles(result, top=top, right=right)
    lang = detect_language(result.features)
    poles = axis_poles(result, model=model, lang=lang)
    singular, plural = noun_forms(
        str(df.index.name or "Approach"), model=model, lang=lang
    )
    # Localize the whole title, not just the noun: a French table reads
    # "Voitures dans le quadrant", never "Voitures in the Quadrant".
    title = i18n(lang)["title_template"].format(plural=plural)
    return Positioning(
        df,
        result,
        roles,
        poles,
        _poles_to_names(poles),
        gradient_colors(result, roles),
        singular,
        plural,
        title,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def run(
    table: str,
    reference: str = "0",
    outdir: str = "out",
    stem: str | None = None,
    top: str | None = None,
    right: str | None = None,
    lower: str = "",
    model: str = DEFAULT_MODEL,
    check: bool = False,
) -> list[str]:
    """Shared CLI core: build the positioning, print a summary, write the files.

    Used by both the argparse (`main`) and click (`main_click`) entry points.
    `top` / `right` force a named option into the top-pole / right-pole highlight.
    Returns the list of written paths.
    """
    ref: int | str = int(reference) if reference.lstrip("-").isdigit() else reference
    lower_cols = [c.strip() for c in lower.split(",") if c.strip()]
    pos = positioning(
        parse_table(table),
        reference=ref,
        top=top,
        right=right,
        lower_is_better=lower_cols,
        model=model,
    )
    result, evr = pos.result, pos.result.explained_variance_ratio

    print(f"Parsed {pos.df.shape[0]} options x {pos.df.shape[1]} criteria")
    print(
        f"Reference '{result.reference}' rotated by {result.rotation_deg:+.1f} deg "
        "onto the top-right diagonal\n"
    )
    print(
        f"PCA explained variance: axis-1(PC1)={evr[0]:.1%}  axis-2(PC2)={evr[1]:.1%}  "
        f"(cumulative {evr.sum():.1%})\n"
    )
    print(f"Axis names: axis-1 = {pos.axis_names[0]!r}   axis-2 = {pos.axis_names[1]!r}\n")
    # poles are [left, right, bottom, top]; name each highlight by its pole word.
    print("Highlighted options:")
    highlights = [
        ("best", "leader (reference)"),
        ("worst", "weakest overall"),
        ("top", f"strongest toward {pos.poles[3]!r}"),
        ("right", f"strongest toward {pos.poles[1]!r}"),
    ]
    for role, label in highlights:
        who = next((n for n, r in pos.role_of.items() if r == role), "—")
        print(f"  {label:34s}: {who}")
    print()
    print("Canonical axes in the oriented frame (loadings):")
    print(pos.loadings.round(3).to_string(), "\n")

    written = pos.export(outdir, stem=stem, model=model)
    print("Three-fold deliverable written:")
    for path in written:
        print(f"  {path}")

    if check:
        # Assess a white-composited render, not the transparent PNG on disk: the
        # vision model's backend would otherwise flatten transparency onto black and
        # wrongly report the dark legend as cut off (see `png_on_white`).
        verdict = vlm_assess(png_on_white(pos.to_vega()), model=model)
        if verdict:
            print("\nVision self-check:")
            for key in ("leader_top_right", "readable", "legend_visible"):
                print(f"  {key:16s}: {verdict.get(key)}")
            if verdict.get("notes"):
                print(f"  notes           : {verdict['notes']}")
        else:
            print("\nVision self-check unavailable (model not reachable).")
    return written


def main(argv: list[str] | None = None) -> None:
    """argparse entry point (console command ``standpoint``)."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("table", help="path to a markdown or CSV table")
    ap.add_argument(
        "-r",
        "--reference",
        default="0",
        help="row placed top-right: index (default 0) or exact name",
    )
    ap.add_argument(
        "-o",
        "--outdir",
        default="out",
        help="output directory for the three-fold deliverable (default out/)",
    )
    ap.add_argument("--stem", help="basename for outputs (default: derived from reference)")
    ap.add_argument(
        "--top",
        help="exact name of the option to highlight as strongest "
        "toward the top pole (default: picked from the map)",
    )
    ap.add_argument(
        "--right",
        help="exact name of the option to highlight as strongest "
        "toward the right pole (default: picked from the map)",
    )
    ap.add_argument(
        "--lower",
        default="",
        help="comma-separated criteria where lower is better (e.g. Price,Latency)",
    )
    ap.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model for axis naming (default {DEFAULT_MODEL})",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="ask the vision model to sanity-check the rendered figure",
    )
    a = ap.parse_args(argv)
    run(a.table, a.reference, a.outdir, a.stem, a.top, a.right, a.lower, a.model, a.check)


if __name__ == "__main__":
    main()
