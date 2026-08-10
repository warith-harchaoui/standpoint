"""Test suite for Standpoint.

Standpoint always names the axes and writes the analysis with the local model, so the
model is a hard prerequisite of the suite, not an optional extra: `tests/conftest.py`
guarantees the model resolved through the brief -> engine contract (`standpoint.engine()`)
is present (pulling it once if needed) before any test runs. Tests that exercise the
model (axis naming in the table's own
language and the vision assessment of the rendered figure) therefore always call the
real local LLM.

Tests are functional/scenario-shaped rather than one-per-function: several assertions
about the same fixture or the same call are grouped into one test so a failure still
points at a specific behaviour, but redundant setup (and, for `@needs_model` tests,
redundant real LLM calls) isn't repeated. See CODING.md's "rationalize the suite"
rule.
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


@pytest.fixture(scope="module")
def poles(result) -> list[str]:
    """Model-named poles for `result`, computed once and shared by every consumer.

    Only requested by `@needs_model` tests, so the conftest guard still gates it; the
    single shared call avoids re-running the (deterministic, temperature=0) axis
    naming for every test that needs a set of poles.
    """
    return p4m.axis_poles(result)


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def test_parse_table_reads_csv_and_markdown(df):
    assert df.shape == (12, 7)
    assert df.index[0] == "Python"
    assert df.notna().all().all()  # the example has no blanks
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
def test_analyze_orients_the_reference_top_right(result):
    # Shape of the fit...
    assert result.scores.shape == (12, 2)
    assert result.components.shape == (2, 7)
    assert result.reference == "Python"
    assert result.explained_variance_ratio.shape == (2,)
    # ...the reference actually lands top-right (positive on both axes)...
    x, y = result.scores[result.names.index(result.reference)]
    assert x > 0 and y > 0
    # ...at the Pareto-ideal point (no competitor beats it on either axis)...
    others = np.delete(result.scores, result.names.index(result.reference), axis=0)
    assert x == pytest.approx(others[:, 0].max())
    assert y == pytest.approx(others[:, 1].max())
    # ...and the two canonical axes stay an orthonormal basis after rotation.
    gram = result.components @ result.components.T
    assert np.allclose(gram, np.eye(2), atol=1e-6)


def test_reference_never_collides_with_a_dominant_competitor():
    # A reference that is NOT all-max (it loses on "Price") still gets softened onto
    # the Pareto frontier. When a single competitor happens to define that frontier
    # on both axes at once, landing the reference exactly there would tie it
    # pixel-for-pixel with that competitor -- one dot for two options, and
    # label_placements() would fight to caption both. The reference must land
    # strictly past that competitor instead (as README promises: "placed just past
    # the best competitor"), never exactly on top of it.
    df = pd.DataFrame(
        {
            "Price": [1, 2, 4, 5, 3],
            "Quality": [5, 4, 3, 1, 4],
            "Service": [5, 4, 3, 2, 3],
            "Ambiance": [5, 4, 2, 1, 2],
        },
        index=["Le Bernardin", "Nobu", "Chipotle", "McDonald's", "In-N-Out Burger"],
    )
    result = p4m.analyze(df, reference=0)
    ref_i = result.names.index("Le Bernardin")
    others = np.delete(result.scores, ref_i, axis=0)
    assert not np.any(np.all(np.isclose(others, result.scores[ref_i]), axis=1))
    # still weakly dominates: at least as far out as every competitor on each axis
    assert result.scores[ref_i, 0] >= others[:, 0].max()
    assert result.scores[ref_i, 1] >= others[:, 1].max()


# --------------------------------------------------------------------------- #
# roles / colours / legend
# --------------------------------------------------------------------------- #
def test_roles_are_geometrically_principled(result, roles):
    role_of = dict(zip(result.names, roles, strict=False))
    assert role_of[result.reference] == "best"
    for r in ("best", "worst", "top", "right"):
        assert roles.count(r) == 1
    # the "top"/"right" highlights are the challengers reaching furthest up the
    # vertical / along the horizontal axis, with the leader excluded.
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


def test_label_placements_dedupe_tied_corners():
    # A point far out on one axis with a near-zero value on the other (e.g. Dacia
    # Spring in examples/voitures_electriques.csv: axis_1=-3.22, axis_2=-0.01) is a
    # near-tie between two diagonal corners and can win both "tl" and "bl". Placing
    # it twice made the second pass dodge its own already-placed label as if it were
    # a stranger's, stranding the label far from its dot.
    names = ["Reference", "Runner up", "Extreme"]
    features = ["a", "b"]
    scores = np.array([[3.0, 3.0], [1.0, 1.0], [-3.2, -0.01]])
    result = p4m.PCAResult(
        names=names,
        features=features,
        scores=scores,
        components=np.zeros((2, 2)),
        explained_variance_ratio=np.array([0.8, 0.1]),
        rotation_deg=0.0,
        reference="Reference",
        x_std=np.zeros((3, 2)),
    )
    ext = p4m.corner_extremes(scores)
    assert ext["tl"] == ext["bl"] == 2  # the tie this test guards against
    placements = p4m.label_placements(result, view_x=4.0, view_y=4.0)
    lx, ly, _ = placements[2]
    # the label stays close to its dot (within a couple of label rows), not off
    # chasing a phantom collision with itself
    assert abs(lx - scores[2, 0]) < 1.0
    assert abs(ly - scores[2, 1]) < 1.0


# --------------------------------------------------------------------------- #
# pole-name guard (the quality rules, enforced in code)
# --------------------------------------------------------------------------- #
def test_finalize_poles_enforces_its_invariants():
    # distinct/antonym words across the four labels are rejected...
    shared = p4m.finalize_poles(
        ["Cost Efficient", "High Cost", "User Friendly", "Privacy First"],
        ["Value", "Budget", "Simplicity", "Trust"],
    )
    words = [p4m._content_words(o) for o in shared]
    for a in range(4):
        for b in range(a + 1, 4):
            assert not (words[a] & words[b])  # no antonym/shared-word pair
    # ...negative/drawback words are rejected...
    negatives = p4m.finalize_poles(
        ["High Cost", "Slow", "Complex", "Weak"],
        ["Affordable", "Speed", "Simplicity", "Strength"],
    )
    assert not (p4m._content_words(" ".join(negatives)) & p4m._NEGATIVE_WORDS)
    # ...and the result is always four distinct labels, even from an empty model
    # response (the loading-derived fallback path).
    empty = p4m.finalize_poles(["", "", "", ""], ["Alpha", "Beta", "Gamma", "Delta"])
    assert len(empty) == 4 and len(set(empty)) == 4


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
# hand-authored SVG (render is deterministic; full rasterised export is
# needs_model, below, since it goes through the real deliverable pipeline)
# --------------------------------------------------------------------------- #
def test_to_svg_structure(result):
    roles = p4m.assign_roles(result)
    svg = p4m.to_svg(result, roles=roles, poles=["Left", "Right", "Bottom", "Top"])
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert svg.count("<circle") == len(result.names)  # one dot per approach
    for name in result.names:
        assert name in svg  # every approach is named somewhere (dot label or legend)
    # the four pole words are addressable text nodes, for the GUI's live rename
    for which in ("left", "right", "top", "bottom"):
        assert f'data-pole="{which}"' in svg
    assert 'width="' in svg and 'viewBox="0 0' in svg


# --------------------------------------------------------------------------- #
# validation & convenience API
# --------------------------------------------------------------------------- #
def test_validate_table_rejects_degenerate_and_duplicate_input():
    with pytest.raises(ValueError):
        p4m.validate_table(pd.DataFrame({"x": [1.0]}))  # 1 row
    with pytest.raises(ValueError):
        p4m.validate_table(pd.DataFrame({"x": [1.0, 2.0]}))  # 1 column
    with pytest.raises(ValueError):
        p4m.validate_table(pd.DataFrame({"x": [1.0, 2.0], "y": [np.nan, np.nan]}))
    # Two options with identical ratings would coincide on the map.
    dup_rows = pd.DataFrame(
        {"x": [1.0, 2.0, 1.0], "y": [3.0, 4.0, 3.0]}, index=["a", "b", "a_twin"]
    )
    with pytest.raises(ValueError, match="identical ratings"):
        p4m.validate_table(dup_rows)
    # Two criteria with identical columns count the same evidence twice.
    dup_cols = pd.DataFrame(
        {"x": [1.0, 2.0, 3.0], "x_twin": [1.0, 2.0, 3.0], "y": [3.0, 1.0, 2.0]},
        index=["a", "b", "c"],
    )
    with pytest.raises(ValueError, match="identical columns"):
        p4m.validate_table(dup_cols)
    # A distinct table passes cleanly.
    ok = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [3.0, 1.0, 2.0]}, index=["a", "b", "c"])
    p4m.validate_table(ok)


def test_resolve_reference_errors(df):
    with pytest.raises(ValueError):
        p4m.analyze(df, reference="Nope Not Here")
    with pytest.raises(ValueError):
        p4m.analyze(df, reference=999)


# --------------------------------------------------------------------------- #
# per-column polarity (lower-is-better)
# --------------------------------------------------------------------------- #
def test_polarity_marker_is_parsed_and_flips_the_axis():
    marked = pd.DataFrame({"Price (↓)": [1, 2], "Speed": [3, 4]}, index=["a", "b"])
    clean, lower = p4m.resolve_polarity(marked)
    assert "Price" in clean.columns and "Price (↓)" not in clean.columns
    assert lower == frozenset({"Price"})
    plain = pd.DataFrame({"Latency": [1, 2], "Speed": [3, 4]}, index=["a", "b"])
    _, lower2 = p4m.resolve_polarity(plain, ["Latency"])
    assert lower2 == frozenset({"Latency"})

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


# --------------------------------------------------------------------------- #
# model-backed (the local model is a hard prerequisite; see tests/conftest.py)
# --------------------------------------------------------------------------- #
@pytest.mark.needs_model
def test_axis_poles_llm_quality(poles):
    assert len(poles) == 4 and len(set(poles)) == 4
    joined = p4m._content_words(" ".join(poles))
    assert not (joined & p4m._NEGATIVE_WORDS)  # only positive qualities


@pytest.mark.needs_model
def test_export_all_writes_complete_and_focused_deliverable(tmp_path, df, result, roles, poles):
    names = p4m._poles_to_names(poles)
    colors = p4m.gradient_colors(result, roles)
    stem = str(tmp_path / "map")
    written = p4m.export_all(df, result, roles, poles, names, colors, stem)
    # transparent png+svg, white png+svg, then md + yaml
    assert len(written) == 6
    assert Path(f"{stem}.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert Path(f"{stem}.white.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert "<svg" in Path(f"{stem}.svg").read_text()
    assert "<svg" in Path(f"{stem}.white.svg").read_text()
    doc = yaml.safe_load(Path(f"{stem}.yaml").read_text())
    assert doc["meta"]["reference"] == "Python"
    assert len(doc["approaches"]) == 12
    # The analysis ends at the highlighted approaches: no leaderboard coordinate
    # dump and no PCA-units footer (dropped as noise).
    md_text = Path(f"{stem}.md").read_text()
    assert f"# {result.reference}" in md_text
    assert "## Highlighted approaches" in md_text
    assert "Leaderboard" not in md_text
    assert "Coordinates are PCA" not in md_text


@pytest.mark.needs_model
def test_positioning_end_to_end(tmp_path, df):
    # One call through the whole facade: the object's shape/API, then its own
    # export -- the marker-cleaning and path/string-vs-DataFrame dispatch that used
    # to get their own full (expensive) positioning() call are already covered
    # deterministically by test_polarity_marker_is_parsed_and_flips_the_axis and
    # test_parse_table_reads_csv_and_markdown, since positioning() only wraps
    # resolve_polarity()/parse_table() around this same pipeline.
    pos = p4m.positioning(df)
    assert isinstance(pos, p4m.Positioning)
    assert pos.role_of[pos.result.reference] == "best"
    assert set(pos.axes) == {"x", "y"}
    assert list(pos.coords.index) == list(df.index)
    assert pos.to_svg().startswith("<svg")
    assert yaml.safe_load(pos.to_yaml())["meta"]["reference"] == "Python"

    written = pos.export(str(tmp_path), stem="demo")
    assert {Path(w).name for w in written} == {
        "demo.png",
        "demo.svg",
        "demo.white.png",
        "demo.white.svg",
        "demo.md",
        "demo.yaml",
    }


@pytest.mark.needs_model
def test_noun_forms_translates_across_a_forced_language():
    # The GUI's language toggle passes an explicit `lang` that can differ from the
    # table's own language (e.g. an English "Programming Language" column, FR
    # forced). noun_forms() must actually translate the word, not silently echo
    # the original -- a half-translated title ("Programming languages dans le
    # quadrant") is the visible symptom of this regressing.
    s, p = p4m.noun_forms("Programming Language", lang="fr")
    assert s.lower() != "programming language"
    assert p.lower() != "programming languages"
    assert "langage" in s.lower()
    assert "langage" in p.lower()


@pytest.mark.needs_model
def test_noun_forms_guards_synonym_drift_within_same_language():
    # Without a forced cross-language override, the anti-hallucination guard must
    # still catch the model swapping in an unrelated synonym (e.g. Voiture ->
    # Vehicule) -- this must not regress from the cross-language fix above.
    s, p = p4m.noun_forms("Voiture")  # auto-detected as French, no lang override
    assert s.lower().startswith("voitur")
    assert p.lower().startswith("voitur")


@pytest.mark.needs_model
def test_vlm_assessment_of_rendered_figure(result):
    # Assess a white-composited render (the exported figure is transparent, which the
    # model's backend would flatten onto black and misread; see png_on_white).
    verdict = p4m.vlm_assess(p4m.png_on_white(p4m.to_svg(result)))
    assert verdict.get("leader_top_right") is True
    # The four italic pole labels at the edges are always drawn; the per-dot legend is
    # now shown only when crowding drops a label, so the check looks at the poles.
    assert verdict.get("axis_labels_visible") is True


@pytest.mark.needs_model
def test_main_argv_writes_deliverable(tmp_path):
    # `main` is the `standpoint` console script's argv wiring around `run`; nothing
    # else in the suite calls it, so a broken flag name here would only surface at
    # install time.
    p4m.main([str(EXAMPLE), "--outdir", str(tmp_path), "--stem", "argv_demo"])
    written = {p.name for p in tmp_path.iterdir()}
    assert "argv_demo.png" in written
    assert "argv_demo.yaml" in written


@pytest.mark.needs_model
def test_main_click_writes_deliverable(tmp_path):
    # `main_click` is the `standpoint-click` console script's argv wiring; same
    # rationale as test_main_argv_writes_deliverable above, for the click CLI.
    from click.testing import CliRunner

    from standpoint.click_cli import main_click

    result = CliRunner().invoke(
        main_click, [str(EXAMPLE), "--outdir", str(tmp_path), "--stem", "click_demo"]
    )
    assert result.exit_code == 0, result.output
    written = {p.name for p in tmp_path.iterdir()}
    assert "click_demo.png" in written
    assert "click_demo.yaml" in written
