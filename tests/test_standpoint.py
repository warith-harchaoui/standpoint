"""Test suite for Standpoint.

Standpoint always names the axes and writes the analysis with the local model, so the
model is a hard prerequisite of the suite, not an optional extra: `tests/conftest.py`
guarantees `standpoint.DEFAULT_MODEL` is present (pulling it once if needed) before
any test runs. Tests that exercise the model (axis naming in the table's own
language and the vision assessment of the rendered figure) therefore always call the
real local LLM.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

import standpoint as p4m

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "programming_languages.csv"
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return p4m.parse_table(str(EXAMPLE))


@pytest.fixture(scope="module")
def result(df) -> p4m.PCAResult:
    return p4m.analyze(df, reference=0)


@pytest.fixture(scope="module")
def roles(result) -> list[str]:
    return p4m.assign_roles(result)


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def test_parse_csv_shape(df):
    assert df.shape == (12, 7)
    assert df.index[0] == "Python"
    assert df.notna().all().all()  # the example has no blanks


def test_parse_markdown_matches_csv():
    md = "| Tool | Speed | Safety |\n|---|---|---|\n| a | 1 | 2 |\n| b | 3 | 4 |\n"
    d = p4m.parse_table(md)
    assert list(d.index) == ["a", "b"]
    assert d.loc["a", "Speed"] == 1.0 and d.loc["b", "Safety"] == 4.0


def test_cell_to_number_blanks_and_numbers():
    assert p4m._cell_to_number("3.5") == 3.5
    assert p4m._cell_to_number("1,5") == 1.5  # comma decimal
    for blank in ("", "-", "n/a", "?"):
        assert np.isnan(p4m._cell_to_number(blank))


def test_impute_uses_column_minimum():
    d = pd.DataFrame({"x": [1.0, np.nan, 5.0], "y": [np.nan, 2.0, 8.0]})
    out = p4m.impute(d)
    assert out["x"].tolist() == [1.0, 1.0, 5.0]
    assert out["y"].tolist() == [2.0, 2.0, 8.0]


# --------------------------------------------------------------------------- #
# analyze / orientation
# --------------------------------------------------------------------------- #
def test_analyze_shapes(result):
    assert result.scores.shape == (12, 2)
    assert result.components.shape == (2, 7)
    assert result.reference == "Python"
    assert result.explained_variance_ratio.shape == (2,)


def test_reference_lands_top_right(result):
    x, y = result.scores[result.names.index(result.reference)]
    assert x > 0 and y > 0


def test_reference_at_pareto_ideal(result):
    i = result.names.index(result.reference)
    others = np.delete(result.scores, i, axis=0)
    assert result.scores[i, 0] == pytest.approx(others[:, 0].max())
    assert result.scores[i, 1] == pytest.approx(others[:, 1].max())


def test_components_orthonormal(result):
    gram = result.components @ result.components.T
    assert np.allclose(gram, np.eye(2), atol=1e-6)


# --------------------------------------------------------------------------- #
# roles / colours / legend
# --------------------------------------------------------------------------- #
def test_roles_are_principled(result, roles):
    role_of = dict(zip(result.names, roles, strict=False))
    assert role_of[result.reference] == "best"
    for r in ("best", "worst", "top", "right"):
        assert roles.count(r) == 1


def test_axis_champions_are_geometric(result, roles):
    # the "top"/"right" highlights are the challengers reaching furthest up the
    # vertical / along the horizontal axis, with the leader (and top) excluded.
    role_of = dict(zip(result.names, roles, strict=False))
    idx = {n: k for k, n in enumerate(result.names)}
    leader = result.reference
    non_leader = [k for k, n in enumerate(result.names) if n != leader]
    top_name = next(n for n, r in role_of.items() if r == "top")
    assert idx[top_name] == max(non_leader, key=lambda k: result.scores[k, 1])
    right_name = next(n for n, r in role_of.items() if r == "right")
    rest = [k for k in non_leader if result.names[k] != top_name]
    assert idx[right_name] == max(rest, key=lambda k: result.scores[k, 0])


def test_colors_distinct_valid_and_roles_fixed(result, roles):
    colors = p4m.gradient_colors(result, roles)
    assert len(colors) == len(result.names)
    assert all(HEX.match(c) for c in colors)
    assert len(set(colors)) == len(colors)  # every dot its own colour
    for i, role in enumerate(roles):
        if role != "competitor":
            assert colors[i] == p4m.ROLE_STYLE[role]["color"]


def test_legend_order_is_a_permutation(result):
    order = p4m.legend_order(result.scores)
    assert sorted(order) == list(range(len(result.names)))
    # starts in the top band (highest y among the first row)
    first = order[0]
    top_band_size = max(1, round(len(result.names) ** 0.5))
    top_ys = sorted(result.scores[:, 1])[-top_band_size:]
    assert result.scores[first, 1] >= min(top_ys)


def test_corner_extremes(result):
    ext = p4m.corner_extremes(result.scores)
    assert set(ext) == {"tr", "tl", "br", "bl"}
    # the reference (top-right) is the tr extreme
    assert result.names[ext["tr"]] == result.reference


# --------------------------------------------------------------------------- #
# pole-name guard (the quality rules, enforced in code)
# --------------------------------------------------------------------------- #
def test_finalize_poles_rejects_shared_words():
    out = p4m.finalize_poles(
        ["Cost Efficient", "High Cost", "User Friendly", "Privacy First"],
        ["Value", "Budget", "Simplicity", "Trust"],
    )
    words = [p4m._content_words(o) for o in out]
    for a in range(4):
        for b in range(a + 1, 4):
            assert not (words[a] & words[b])  # no antonym/shared-word pair


def test_finalize_poles_rejects_negatives():
    out = p4m.finalize_poles(
        ["High Cost", "Slow", "Complex", "Weak"],
        ["Affordable", "Speed", "Simplicity", "Strength"],
    )
    joined = p4m._content_words(" ".join(out))
    assert not (joined & p4m._NEGATIVE_WORDS)


def test_finalize_poles_four_distinct():
    out = p4m.finalize_poles(["", "", "", ""], ["Alpha", "Beta", "Gamma", "Delta"])
    assert len(out) == 4 and len(set(out)) == 4


def test_deacronym_expands_and_drops():
    assert p4m._deacronym("TCO") == "Cost"
    assert "UX" not in p4m._deacronym("Operator UX")


# --------------------------------------------------------------------------- #
# i18n
# --------------------------------------------------------------------------- #
def test_i18n_all_languages_present_and_formattable():
    for lang in p4m.SUPPORTED_LANGS:
        tpl = p4m.i18n(lang)
        assert {
            "glossary_prefix",
            "axis_prompt",
            "narrative_prompt",
            "noun_prompt",
            "title_template",
        } <= set(tpl)
        tpl["axis_prompt"].format(glossary="", left="a", right="b", bottom="c", top="d")
        tpl["title_template"].format(plural="Cars")
        tpl["narrative_prompt"].format(
            left="a",
            right="b",
            bottom="c",
            top="d",
            reference="r",
            best="x",
            worst="y",
            champ_top="z",
            champ_right="w",
            leaderboard="l",
        )
        tpl["noun_prompt"].format(word="Language")


def test_detect_language():
    assert (
        p4m.detect_language(["Real-time streaming", "Operator experience", "On-prem privacy"])
        == "en"
    )
    assert (
        p4m.detect_language(
            ["Diffusion en temps réel", "Confidentialité des données", "Qualité de l'expérience"]
        )
        == "fr"
    )


# --------------------------------------------------------------------------- #
# vega spec + full export (render is deterministic via vl_convert)
# --------------------------------------------------------------------------- #
def test_to_vega_structure(result):
    spec = p4m.to_vega(result)
    assert spec["$schema"].endswith("v5.json")
    assert spec["layer"] and spec["width"] > 0 and spec["height"] > 0
    # the colour legend enumerates every approach
    for layer in spec["layer"]:
        scale = layer.get("encoding", {}).get("color", {}).get("scale", {})
        if isinstance(scale, dict) and "domain" in scale:
            assert set(scale["domain"]) == set(result.names)
            break
    else:
        pytest.fail("no legend domain found")


@pytest.mark.needs_model
def test_export_all_writes_three_fold(tmp_path, df, result, roles):
    poles = p4m.axis_poles(result)
    names = p4m._poles_to_names(poles)
    colors = p4m.gradient_colors(result, roles)
    stem = str(tmp_path / "map")
    written = p4m.export_all(df, result, roles, poles, names, colors, stem)
    # transparent png+svg, white png+svg, then vl.json + md + yaml
    assert len(written) == 7
    assert Path(f"{stem}.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert Path(f"{stem}.white.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert "<svg" in Path(f"{stem}.svg").read_text()
    assert "<svg" in Path(f"{stem}.white.svg").read_text()
    doc = yaml.safe_load(Path(f"{stem}.yaml").read_text())
    assert doc["meta"]["reference"] == "Python"
    assert len(doc["approaches"]) == 12
    assert f"# {result.reference}" in Path(f"{stem}.md").read_text()


@pytest.mark.needs_model
def test_markdown_is_focused(result, roles):
    # The analysis ends at the highlighted approaches: no leaderboard coordinate
    # dump and no PCA-units footer (dropped as noise).
    poles = p4m.axis_poles(result)
    md = p4m.analysis_markdown(result, roles, poles)
    assert "## Highlighted approaches" in md
    assert "Leaderboard" not in md
    assert "Coordinates are PCA" not in md


# --------------------------------------------------------------------------- #
# validation & convenience API
# --------------------------------------------------------------------------- #
def test_validate_table_rejects_degenerate_input():
    with pytest.raises(ValueError):
        p4m.validate_table(pd.DataFrame({"x": [1.0]}))  # 1 row
    with pytest.raises(ValueError):
        p4m.validate_table(pd.DataFrame({"x": [1.0, 2.0]}))  # 1 column
    with pytest.raises(ValueError):
        p4m.validate_table(pd.DataFrame({"x": [1.0, 2.0], "y": [np.nan, np.nan]}))


def test_resolve_reference_errors(df):
    with pytest.raises(ValueError):
        p4m.analyze(df, reference="Nope Not Here")
    with pytest.raises(ValueError):
        p4m.analyze(df, reference=999)


# --------------------------------------------------------------------------- #
# per-column polarity (lower-is-better)
# --------------------------------------------------------------------------- #
def test_resolve_polarity_marker_and_explicit():
    marked = pd.DataFrame({"Price (↓)": [1, 2], "Speed": [3, 4]}, index=["a", "b"])
    clean, lower = p4m.resolve_polarity(marked)
    assert "Price" in clean.columns and "Price (↓)" not in clean.columns
    assert lower == frozenset({"Price"})
    plain = pd.DataFrame({"Latency": [1, 2], "Speed": [3, 4]}, index=["a", "b"])
    _, lower2 = p4m.resolve_polarity(plain, ["Latency"])
    assert lower2 == frozenset({"Latency"})


def test_lower_is_better_flips_the_axis():
    data = pd.DataFrame(
        {"Price": [1, 5, 3], "Quality": [3, 3, 3]}, index=["cheap", "pricey", "mid"]
    )
    hi = p4m.analyze(data, reference=0)  # naive higher-better
    lo = p4m.analyze(data, reference=0, lower_is_better=["Price"])
    assert "Price" in lo.lower
    j = lo.features.index("Price")
    ci, pi = lo.names.index("cheap"), lo.names.index("pricey")
    # lower-is-better: the cheap option scores higher on the (negated) Price column
    assert lo.x_std[ci, j] > lo.x_std[pi, j]
    assert hi.x_std[ci, j] < hi.x_std[pi, j]  # opposite without it


@pytest.mark.needs_model
def test_positioning_lower_marker_cleaned():
    marked = pd.DataFrame(
        {"Price (↓)": [1, 5, 3, 2], "Quality": [3, 2, 4, 5]}, index=["a", "b", "c", "d"]
    )
    pos = p4m.positioning(marked)
    assert "Price" in pos.result.lower
    assert "Price" in pos.df.columns  # marker stripped


@pytest.mark.needs_model
def test_positioning_api(df):
    pos = p4m.positioning(df)
    assert isinstance(pos, p4m.Positioning)
    assert pos.role_of[pos.result.reference] == "best"
    assert set(pos.axes) == {"x", "y"}
    assert list(pos.coords.index) == list(df.index)
    assert pos.to_vega()["layer"]
    assert yaml.safe_load(pos.to_yaml())["meta"]["reference"] == "Python"


@pytest.mark.needs_model
def test_positioning_export(tmp_path, df):
    pos = p4m.positioning(df)
    written = pos.export(str(tmp_path), stem="demo")
    assert {Path(w).name for w in written} == {
        "demo.png",
        "demo.svg",
        "demo.white.png",
        "demo.white.svg",
        "demo.vl.json",
        "demo.md",
        "demo.yaml",
    }


@pytest.mark.needs_model
def test_positioning_accepts_path_and_string(df):
    from_path = p4m.positioning(str(EXAMPLE))
    assert from_path.df.shape == df.shape


# --------------------------------------------------------------------------- #
# model-backed (the local model is a hard prerequisite; see tests/conftest.py)
# --------------------------------------------------------------------------- #
@pytest.mark.needs_model
def test_axis_poles_llm_quality(result):
    poles = p4m.axis_poles(result)
    assert len(poles) == 4 and len(set(poles)) == 4
    joined = p4m._content_words(" ".join(poles))
    assert not (joined & p4m._NEGATIVE_WORDS)  # only positive qualities


@pytest.mark.needs_model
def test_vlm_assessment_of_rendered_figure(result):
    # Assess a white-composited render (the exported figure is transparent, which the
    # model's backend would flatten onto black and misread; see png_on_white).
    verdict = p4m.vlm_assess(p4m.png_on_white(p4m.to_vega(result)))
    assert verdict.get("leader_top_right") is True
    # The four italic pole labels at the edges are always drawn; the per-dot legend is
    # now shown only when crowding drops a label, so the check looks at the poles.
    assert verdict.get("axis_labels_visible") is True
