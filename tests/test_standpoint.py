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
def poles(result, model_guard) -> list[str]:
    """Model-named poles for `result`, computed once and shared by every consumer.

    Requests `model_guard` itself: module fixtures are set up BEFORE the function-scoped
    conftest guard, so without it a down Ollama errors here instead of skipping. The
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
            "noun_prompt",
            "title_template",
        } <= set(tpl)
        tpl["axis_prompt"].format(glossary="", left="a", right="b", bottom="c", top="d")
        tpl["title_template"].format(plural="Cars")
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


def test_to_svg_tooltip_prefers_attribute_values_over_coordinate_fallback(df, result):
    roles = p4m.assign_roles(result)
    with_attrs = p4m.to_svg(
        result, roles=roles, poles=["Left", "Right", "Bottom", "Top"], attributes=df
    )
    without_attrs = p4m.to_svg(result, roles=roles, poles=["Left", "Right", "Bottom", "Top"])
    # With attributes, the tooltip lists the raw criterion values (what the user
    # typed), not the abstract axis coordinates.
    assert "Performance: " in with_attrs
    assert "axis1:" not in with_attrs
    # Without attributes, it falls back to role + coordinates.
    assert "Performance: " not in without_attrs
    assert "axis1:" in without_attrs


def test_export_all_forwards_attributes_so_the_deliverable_gets_the_rich_tooltip(
    tmp_path, df, result, roles
):
    # export_all receives df but used to build the SVG without passing it on as
    # `attributes`, so every actually-exported figure (the CLI/GUI deliverable)
    # silently got the degraded role+coordinates tooltip instead of the intended
    # per-criterion one, even though Positioning.to_svg() (a separate convenience
    # method) already did this correctly.
    poles = ["Left", "Right", "Bottom", "Top"]
    colors = p4m.gradient_colors(result, roles)
    stem = str(tmp_path / "map")
    p4m.export_all(df, result, roles, poles, poles, colors, stem)
    svg_text = Path(f"{stem}.svg").read_text()
    assert "Performance: " in svg_text
    assert "axis1:" not in svg_text


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
    # transparent png+svg, white png+svg, then the written analysis, then yaml
    assert len(written) == 6
    assert Path(f"{stem}.md").read_text(encoding="utf-8").startswith("# ")
    assert Path(f"{stem}.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert Path(f"{stem}.white.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert "<svg" in Path(f"{stem}.svg").read_text()
    assert "<svg" in Path(f"{stem}.white.svg").read_text()
    doc = yaml.safe_load(Path(f"{stem}.yaml").read_text())
    assert doc["meta"]["reference"] == "Python"
    assert len(doc["approaches"]) == 12


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

    assert pos.to_markdown().startswith("# ")

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


def _positioning_without_naming(result, roles, lang: str) -> p4m.Positioning:
    """A Positioning built from the deterministic half of the pipeline only.

    `positioning()` itself calls the model for pole names, noun forms and the
    title; `assess_layout` reads none of that except the four pole strings, so
    the test supplies fixed ones and stays offline.
    """
    poles = ["Top", "Right", "Bottom", "Left"]
    return p4m.Positioning(
        df=p4m.parse_table(str(EXAMPLE)),
        result=result,
        roles=roles,
        poles=poles,
        axis_names=["axis 1", "axis 2"],
        colors=p4m.gradient_colors(result, roles),
        lang=lang,
    )


def test_assess_layout_reads_the_geometry(result, roles):
    """The deterministic --check verdict, and its one genuine failure mode.

    No `needs_model` marker on purpose: replacing the vision model with geometry
    is exactly what makes this checkable offline. The negative case is built the
    way the distillation corpus built its own ground truth -- swap the
    best/worst roles, which puts the red leader in the opposite corner.
    """
    pos = _positioning_without_naming(result, roles, "en")
    verdict = p4m.assess_layout(pos)
    assert verdict["leader_top_right"] is True
    assert verdict["axis_labels_visible"] is True
    assert verdict["readable"] is True
    assert verdict["notes"] == p4m.i18n("en")["check_ok"]

    swapped = ["worst" if r == "best" else "best" if r == "worst" else r for r in roles]
    flipped = p4m.assess_layout(_positioning_without_naming(result, swapped, "en"))
    assert flipped["leader_top_right"] is False
    assert "top-right" in flipped["notes"]

    # A missing pole label is reported, not silently passed.
    blank = _positioning_without_naming(result, roles, "en")
    blank.poles = ["Top", "", "Bottom", "Left"]
    assert p4m.assess_layout(blank)["axis_labels_visible"] is False

    # Same verdict, notes localized: the CLI prints them to the user.
    fr = p4m.assess_layout(_positioning_without_naming(result, roles, "fr"))
    assert fr["notes"] == p4m.i18n("fr")["check_ok"]


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


# --------------------------------------------------------------------------- #
# A placement you cannot audit is not auditable
# --------------------------------------------------------------------------- #
# A blank cell is filled with its column's minimum. That default is defensible
# -- a missing rating should not flatter an option -- and it stays. What it was
# not is *visible*: the invented number reached the YAML looking exactly like a
# measurement. And because each criterion is z-scored, it moves that column's
# mean and spread, so every option's coordinates shift, not only the one with
# the gap.


def _gapped() -> pd.DataFrame:
    return pd.DataFrame(
        {"Speed": [5, 4, 3, 2, 1], "Safety": [5, 3, np.nan, 4, 2], "Cost": [4, 5, 3, 2, 1]},
        index=["alpha", "beta", "gamma", "delta", "epsilon"],
    )


def _complete() -> pd.DataFrame:
    df = _gapped()
    df.loc["gamma", "Safety"] = 5
    return df


def test_imputed_cells_names_every_gap() -> None:
    assert p4m.imputed_cells(_gapped()) == [("gamma", "Safety")]


def test_a_complete_table_reports_no_imputation() -> None:
    assert p4m.imputed_cells(_complete()) == []


def test_one_blank_cell_moves_every_option() -> None:
    """The reason disclosure matters: the effect is not local.

    z-scoring means an invented value changes its column's mean and standard
    deviation, so it perturbs the whole space -- including options whose own
    row was complete.
    """
    gapped = p4m.analyze(_gapped(), reference="alpha")
    complete = p4m.analyze(_complete(), reference="alpha")
    moved = [
        name
        for name, g, c in zip(gapped.names, gapped.scores, complete.scores, strict=True)
        if abs(g[0] - c[0]) > 1e-6 or abs(g[1] - c[1]) > 1e-6
    ]
    assert "gamma" in moved
    assert len(moved) > 1, "a gap must be shown to perturb more than its own row"


def _yaml_for(df: pd.DataFrame) -> dict:
    """Render the deliverable YAML without needing a model for axis naming."""
    result = p4m.analyze(df, reference="alpha")
    n = len(result.names)
    return yaml.safe_load(
        p4m.results_yaml(
            df,
            result,
            roles=["best"] + ["other"] * (n - 1),
            poles=["L", "R", "B", "T"],
            axis_names=["axis one", "axis two"],
            colors=["#FF3B30"] * n,
        )
    )


def test_the_yaml_declares_what_was_invented() -> None:
    """Both table-wide and per option, so one row is readable on its own."""
    doc = _yaml_for(_gapped())
    assert doc["meta"]["imputed_cells"] == [{"option": "gamma", "criterion": "Safety"}]
    by_name = {a["name"]: a for a in doc["approaches"]}
    assert by_name["gamma"]["imputed_attributes"] == ["Safety"]
    assert by_name["alpha"]["imputed_attributes"] == []


def test_a_complete_table_declares_nothing() -> None:
    doc = _yaml_for(_complete())
    assert doc["meta"]["imputed_cells"] == []
    assert all(a["imputed_attributes"] == [] for a in doc["approaches"])


def test_the_invented_value_is_still_the_column_minimum() -> None:
    """Disclosure, not a change of strategy: the number itself is unchanged."""
    by_name = {a["name"]: a for a in _yaml_for(_gapped())["approaches"]}
    assert by_name["gamma"]["attributes"]["Safety"] == 2.0  # min of the column


# --------------------------------------------------------------------------- #
# the written analysis — the third face of the deliverable
# --------------------------------------------------------------------------- #
_FAKE_POLES = ["Adaptable", "Modular", "Resourceful", "Insightful"]
_FAKE_AXES = ["Adaptable ↔ Modular", "Resourceful ↔ Insightful"]


def test_the_written_analysis_owns_its_numbers(df, result, monkeypatch) -> None:
    """Every figure in the document is computed here, never quoted by the model.

    The prompt forbids the model from stating a percentage precisely so that
    this holds: a model asked to narrate its own variance will occasionally
    round one differently and contradict the file it sits in.
    """
    monkeypatch.setattr(p4m, "analysis_prose", lambda *a, **k: "Some reading.")
    md = p4m.analysis_markdown(df, result, _FAKE_POLES, _FAKE_AXES)
    evr = result.explained_variance_ratio
    assert f"~{100 * float(evr[0]):.0f}%" in md
    assert f"~{100 * float(evr[1]):.0f}%" in md
    assert f"~{100 * float(evr.sum()):.0f}%" in md
    assert "Some reading." in md


def test_the_axes_section_is_machine_readable(df, result, monkeypatch) -> None:
    """A downstream generator must lift the poles without a model, and without
    reading the prose. This is the contract `gen_landscape.py` consumes."""
    import re

    monkeypatch.setattr(p4m, "analysis_prose", lambda *a, **k: "x")
    md = p4m.analysis_markdown(df, result, _FAKE_POLES, _FAKE_AXES)
    found = re.findall(r"\*\*(Horizontal|Vertical): (.+?) ↔ (.+?)\*\*", md)
    assert [(a, b, c) for a, b, c in found] == [
        ("Horizontal", "Adaptable", "Modular"),
        ("Vertical", "Resourceful", "Insightful"),
    ]


def test_the_analysis_is_complete_when_the_model_is_absent(df, result, monkeypatch) -> None:
    """A missing model degrades the prose, never the document.

    The figure and the YAML are the load-bearing halves and neither needs a
    model, so an unreachable Ollama must not cost the reader the axes, the
    variance or the imputation notice. And the absence has to be stated: a
    silently missing section is indistinguishable from a map with nothing to
    say about itself.
    """

    def explode(*a, **k):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(p4m.llm, "chat", explode)
    assert p4m.analysis_prose(df, result, _FAKE_POLES, _FAKE_AXES) == ""
    md = p4m.analysis_markdown(df, result, _FAKE_POLES, _FAKE_AXES)
    assert "Adaptable ↔ Modular" in md
    assert "local model" in md


def test_the_prompt_hands_the_model_words_not_coordinates(df, result, monkeypatch) -> None:
    """The regression that made the first version of this feature wrong.

    Given "Amazon Lex (-2.24, -2.08)" and the pole names, the model inverted the
    horizontal axis: it filed the reference -- pinned top-right by construction
    -- as a left-hand option. Naming the pole was not enough either, since
    "Adaptable + Resourceful" still leaves it to guess which side Adaptable is.
    So the prompt now carries the direction word first, and no coordinates at
    all.
    """
    captured: dict[str, str] = {}

    def capture(prompt, **kwargs):
        captured["prompt"] = prompt
        return "ok"

    monkeypatch.setattr(p4m.llm, "chat", capture)
    p4m.analysis_prose(df, result, _FAKE_POLES, _FAKE_AXES)
    prompt = captured["prompt"]

    # The reference is pinned top-right, so that is what the prompt must say.
    assert f"{result.reference}: right-top" in prompt
    # Every option gets a quadrant, and every quadrant leads with a direction.
    for name in result.names:
        assert name in prompt
    assert "left-bottom" in prompt or "left-top" in prompt
    # No coordinate PAIRS anywhere: that is the whole point. Criterion loadings
    # are still passed as signed numbers and should be -- they are weights, not
    # positions, and the prompt asks the model to name the heaviest of them.
    # What must never appear is "(+2.47, +2.08)", the thing it read backwards.
    import re

    assert not re.search(r"\([-+]?\d+\.\d+,\s*[-+]?\d+\.\d+\)", prompt), (
        "a coordinate pair leaked into the prompt"
    )


def test_export_writes_the_markdown_face(df, result, roles, tmp_path, monkeypatch) -> None:
    """`export_all` promised PNG + SVG + Markdown + YAML and wrote three."""
    monkeypatch.setattr(p4m, "analysis_prose", lambda *a, **k: "reading")
    stem = str(tmp_path / "out")
    written = p4m.export_all(
        df, result, roles, _FAKE_POLES, _FAKE_AXES, ["#000"] * len(result.names), stem
    )
    assert f"{stem}.md" in written
    assert (tmp_path / "out.md").read_text(encoding="utf-8").startswith("# ")


def test_the_analysis_declares_what_was_invented(monkeypatch) -> None:
    """The imputation notice reaches the prose face too, not only the YAML.

    A reader handed the written analysis and not the YAML would otherwise be
    told what the placement means without being told that one of its inputs
    was a fill rather than a measurement.
    """
    import io

    table = io.StringIO("Domain,Alpha,Beta,Gamma\nref,5,5,4\nb,2,,1\nc,3,1,5\nd,1,2,2\n")
    gapped = p4m.parse_table(table.getvalue())
    fit = p4m.analyze(gapped, reference=0)
    monkeypatch.setattr(p4m, "analysis_prose", lambda *a, **k: "reading")
    md = p4m.analysis_markdown(gapped, fit, _FAKE_POLES, _FAKE_AXES)
    assert "b / Beta" in md


@pytest.fixture(scope="module")
def voice_fit() -> p4m.PCAResult:
    """A fit whose option names are the ones the prose below talks about.

    Self-contained rather than reusing the module's example table, whose
    options are programming languages: a checker that finds no name in a
    sentence reports nothing, so testing it against the wrong table would pass
    for the wrong reason.
    """
    table = (
        "Spoken Conversation,Local,Barge-in,Latency,Library,Testable,Swappable,Telephony\n"
        "discussion-helper,5,5,5,5,5,5,1\n"
        "LiveKit Agents,3,5,4,3,3,5,5\n"
        "Pipecat,3,4,3,4,3,5,5\n"
        "Vocode,3,3,2,4,2,4,4\n"
        "Vapi,1,4,2,1,1,2,5\n"
        "Amazon Lex,1,2,1,1,1,1,5\n"
        "Rasa,4,1,1,3,4,3,3\n"
        "speech_recognition + pyttsx3,5,1,1,5,2,3,1\n"
    )
    return p4m.analyze(p4m.parse_table(table), reference=0)


def test_the_checker_catches_a_miscalled_side(voice_fit) -> None:
    """The failure that prompted this check, replayed from a real run.

    The model placed three options correctly and filed two left-hand ones under
    "lower right" in the same breath. Nothing but the coordinates could tell.
    """
    prose = (
        "Notably, discussion-helper occupies the upper-right corner. "
        "LiveKit Agents shares the upper region but leans towards adaptability, "
        "while several options including Amazon Lex, Vapi, Rasa, "
        "speech_recognition + pyttsx3 and Vocode are grouped in the lower-right "
        "quadrant."
    )
    problems = p4m.check_analysis(prose, voice_fit)
    assert len(problems) == 2, problems
    assert any("Amazon Lex" in p and "right" in p for p in problems)
    assert any("Vapi" in p and "right" in p for p in problems)


def test_the_checker_does_not_cry_wolf(voice_fit) -> None:
    """Precision matters more than recall here.

    A first version attributed every direction word in a sentence to every
    option named in it, and reported nine problems on the prose above where two
    were real. A warning channel that cries wolf is no better than the silence
    it replaced.
    """
    good = (
        "discussion-helper occupies the upper-right corner. "
        "Amazon Lex and Vapi both sit in the lower left. "
        "Those on the right prioritise modularity."
    )
    assert p4m.check_analysis(good, voice_fit) == []


def test_a_statement_about_the_axis_is_not_a_claim_about_anybody(voice_fit) -> None:
    """ "Those on the right are modular" names no option, so it cannot be wrong."""
    assert p4m.check_analysis("Options on the left are more adaptable.", voice_fit) == []
    assert p4m.check_analysis("", voice_fit) == []


def test_the_written_analysis_is_reproducible(df, result, monkeypatch) -> None:
    """Same table, same document. The analysis call runs at temperature 0.

    Reproducibility is a stated property of this package, and the Markdown face
    must not be the one file that changes between identical runs.
    """
    seen: list[float] = []

    def record(prompt, **kwargs):
        seen.append(kwargs.get("temperature"))
        return "prose"

    monkeypatch.setattr(p4m.llm, "chat", record)
    first = p4m.analysis_markdown(df, result, _FAKE_POLES, _FAKE_AXES)
    second = p4m.analysis_markdown(df, result, _FAKE_POLES, _FAKE_AXES)
    assert first == second
    assert seen == [0, 0]


def test_the_checker_reads_both_word_orders(voice_fit) -> None:
    """The blind spot that let a wrong grouping pass a clean run.

    "Vapi sits on the right" puts the name before the direction word; "in the
    bottom-right corner are Vapi and Rasa" puts it after. The first version
    only looked backwards, so it reported a real run clean while the prose
    filed a left-hand option in the bottom-right corner. Found by reading the
    coordinates against the prose by hand, which is exactly the work this
    function exists to remove.
    """
    after = "The options grouped in the bottom-right corner are Vocode, Vapi and Rasa."
    before = "Vapi sits in the bottom-right corner."
    for prose in (after, before):
        problems = p4m.check_analysis(prose, voice_fit)
        assert any("Vapi" in p and "right" in p for p in problems), prose
        # Vocode and Rasa really are bottom-right, so they must not be flagged.
        assert not any("Vocode" in p or "Rasa" in p for p in problems), problems


def test_the_prompt_hands_over_the_corner_membership(df, result, monkeypatch) -> None:
    """Naming a group has to be copying, not assembling.

    Per-option quadrants were not enough: the model still wrote "the options in
    the bottom-right corner" and listed one that was in the bottom-left. The
    four corners therefore arrive with their exact membership. Third time the
    same remedy applies in this function -- compute the thing and hand it over,
    rather than hand over its inputs and hope.
    """
    captured: dict[str, str] = {}

    def capture(prompt, **kwargs):
        captured["prompt"] = prompt
        return "ok"

    monkeypatch.setattr(p4m.llm, "chat", capture)
    p4m.analysis_prose(df, result, _FAKE_POLES, _FAKE_AXES)
    prompt = captured["prompt"]

    # The reference is pinned top-right, so a "right-top" corner must be listed
    # with the reference among its members. Matched on the membership syntax
    # ("corner: a, b | corner: c") rather than on a character window, because
    # the per-option quadrant list uses the same corner names earlier on.
    import re

    corners = {
        m.group(1): m.group(2) for m in re.finditer(r"(\w+-\w+) \([^)]*\): ([^|\n]+)", prompt)
    }
    assert "right-top" in corners, corners
    assert result.reference in [n.strip() for n in corners["right-top"].split(",")]


def test_exported_svg_files_end_with_a_newline(df, result, tmp_path) -> None:
    """A figure on disk is a text file, and text files end with a newline.

    `to_svg` returns a string ending at `</svg>`, so writing it unchanged
    produced a no-final-newline file: POSIX-incomplete, flagged as
    `\\ No newline at end of file` in every diff that touches it, and a red
    `end-of-file-fixer` in each consumer repo that vendors these figures and
    runs pre-commit over them (vocal-helper hit exactly that). Both the
    transparent and the white variant are checked, since each is written
    separately.
    """
    svg = p4m.to_svg(result, title="Trailing newline")
    written = p4m.render_figures(svg, str(tmp_path / "fig"))

    svgs = [path for path in written if path.endswith(".svg")]
    assert len(svgs) == 2, f"expected a transparent and a white SVG, got {svgs}"
    for path in svgs:
        text = Path(path).read_text(encoding="utf-8")
        assert text.endswith("\n"), f"{Path(path).name} does not end with a newline"
        assert not text.endswith("\n\n"), f"{Path(path).name} gained a blank line"


def test_a_contrastive_clause_does_not_lend_its_names_backwards(voice_fit) -> None:
    """Two true claims in one sentence, reported as three errors.

    Found while regenerating ann-router's map, where this shape -- "A clusters
    upper left, while B, C and D sit lower right" -- is how the model names two
    groups at once. Every claim in the French prose was correct against the
    coordinates, and the checker reported eight problems.

    The cause is the forward attribution window: it runs from a direction word
    to the *next* direction word, so "left" reached past `while` and claimed
    the names belonging to the "lower right" clause. A checker that cries wolf
    on correct prose is worse than no checker, because the next eight real
    warnings get waved through with it.
    """
    both_true = (
        "LiveKit Agents clusters in the upper left, while Rasa, "
        "speech_recognition + pyttsx3 and Vocode sit in the lower right."
    )
    assert p4m.check_analysis(both_true, voice_fit) == []


def test_a_nameless_span_does_not_inherit_across_a_contrast(voice_fit) -> None:
    """The documented rule, which the implementation did not keep.

    `check_analysis` states that "a span that names nobody is ignored" and also
    that a direction word with no names of its own inherits the previous one's
    -- the second is for compound directions like "lower right", but it applied
    at any distance, so a generic aside swallowed the subject of the sentence
    and contradicted prose that was right. Here the aside is about *other*
    options by construction.
    """
    aside = (
        "Interestingly, discussion-helper sits in the upper right, but other "
        "options, like those in the left-top corner, reach precision differently."
    )
    assert p4m.check_analysis(aside, voice_fit) == []


def test_clause_splitting_is_language_specific(voice_fit) -> None:
    """The break vocabulary is translated, like every other word list here.

    The bug surfaced on French prose; an English-only break list would have
    left `tandis que` unsplit and the French map still mis-audited.
    """
    for lang in ("en", "fr", "es"):
        assert p4m.i18n(lang)["analysis_md"]["clause_break_words"].strip()
    french = (
        "LiveKit Agents se regroupe en haut à gauche, tandis que Rasa, "
        "speech_recognition + pyttsx3 et Vocode se positionnent en bas à droite."
    )
    assert p4m.check_analysis(french, voice_fit, lang="fr") == []


def test_two_coordinated_claims_keep_their_own_subjects(voice_fit) -> None:
    """A compound direction is one claim, and the proof is two of them joined.

    "Chroma sits in the lower left, and ann-router in the upper right" is the
    shape that survived the clause-splitting fix, because `and` is not a
    contrast: reading direction words one at a time, `left` found no name
    before it -- `lower` had taken the only one -- so its forward window
    reached past the comma and claimed the *second* corner's subject. Grouping
    adjacent direction words into the corner they actually name fixes it, and
    this sentence has both corners correct.
    """
    coordinated = (
        "Amazon Lex sits in the lower left, and discussion-helper, alone, takes the upper right."
    )
    assert p4m.check_analysis(coordinated, voice_fit) == []


def test_a_corner_still_catches_a_wrong_member(voice_fit) -> None:
    """Grouping must not blunt the check it was added to keep honest.

    The compound now reports as one claim, so both of its words have to be
    tested against every name it claims -- otherwise "Vapi is in the
    bottom-right" passes on `bottom` and never looks at `right`.
    """
    problems = p4m.check_analysis("Vapi sits in the bottom-right corner.", voice_fit)
    assert any("Vapi" in p and "right" in p for p in problems), problems


def test_the_house_comma_rule_is_applied_not_merely_requested() -> None:
    """The French prompt asks for this already; the model does it anyway.

    "Never write a comma before et or ou" has been in the French prompt from
    the start, and a freshly generated analysis still broke it twice. Same
    lesson as `check_analysis`: an instruction in a prompt is a request, not a
    guarantee. A comma can be fixed outright rather than reported, since
    removing one before a coordinating conjunction changes no meaning.
    """
    assert p4m._house_style("A gagne, et B perd, ou C renonce.", "fr") == (
        "A gagne et B perd ou C renonce."
    )
    # A word that merely starts with the conjunction must survive.
    assert p4m._house_style("Des index, etc.", "fr") == "Des index, etc."
    # Languages with no stated rule are untouched, Oxford comma included.
    assert p4m._house_style("A, B, and C.", "en") == "A, B, and C."
    for lang in ("en", "fr", "es"):
        assert "no_comma_before" in p4m.i18n(lang)["analysis_md"]
