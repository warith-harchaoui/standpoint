"""Integrity tests for the localization file (`standpoint/locales/i18n.yaml`).

These are deterministic and model-free, so they run in CI and locally alike. They
guard the bilingual GUI: a translator who drops a `{placeholder}`, forgets a key in one
language, or adds a stray field would otherwise only be caught at runtime (a blank
label, or a `KeyError` deep inside `str.format`). Here the whole table is checked at
import time instead.
"""

from __future__ import annotations

import re

import pytest

import standpoint as sp

# Placeholders each block is allowed to interpolate (a superset; not every key uses all).
_GUI_PLACEHOLDERS = {"n", "i", "opt", "crit"}
_ANALYSIS_ARGS = {
    "left": "L",
    "right": "R",
    "bottom": "B",
    "top": "T",
    "pct": "~50%",
    "cols": "a · b",
}
# Substrings every localized LLM prompt must keep, so the pipeline can fill them in.
_PROMPT_REQUIRED = {
    "title_template": ["{plural}"],
    "noun_prompt": ["{word}"],
    "axis_prompt": ["{glossary}", "{left}", "{right}", "{bottom}", "{top}"],
    "narrative_prompt": [
        "{left}",
        "{right}",
        "{bottom}",
        "{top}",
        "{reference}",
        "{best}",
        "{worst}",
        "{champ_top}",
        "{champ_right}",
        "{leaderboard}",
    ],
    "ratings_prompt": ["{noun}", "{options}", "{criteria}"],
}


def _placeholders(text: str) -> set[str]:
    """The `{name}` fields in a template (single braces only; `{{ }}` are literals)."""
    return set(re.findall(r"(?<!\{)\{(\w+)\}(?!\})", text))


@pytest.mark.parametrize("lang", sp.SUPPORTED_LANGS)
def test_every_language_has_all_blocks(lang: str) -> None:
    """Each supported language carries the prompt keys plus the `gui` and `analysis` blocks."""
    d = sp.i18n(lang)
    for key in (*_PROMPT_REQUIRED, "glossary_prefix", "gui", "analysis"):
        assert key in d, f"{lang} is missing {key!r}"


def test_gui_and_analysis_keys_match_across_languages() -> None:
    """Every language exposes exactly the same `gui` / `analysis` keys (no gaps, no extras)."""
    for block in ("gui", "analysis"):
        reference = set(sp.i18n("en")[block])
        for lang in sp.SUPPORTED_LANGS:
            assert set(sp.i18n(lang)[block]) == reference, f"{lang}.{block} keys diverge"


def test_gui_placeholders_are_known_and_consistent() -> None:
    """GUI strings use only known placeholders, identically across languages."""
    for key in sp.i18n("en")["gui"]:
        sets = {lang: _placeholders(str(sp.i18n(lang)["gui"][key])) for lang in sp.SUPPORTED_LANGS}
        for lang, found in sets.items():
            assert found <= _GUI_PLACEHOLDERS, f"{lang}.gui.{key} has unknown placeholder {found}"
        assert len(set(map(frozenset, sets.values()))) == 1, (
            f"gui.{key} placeholders differ by language"
        )


def test_analysis_templates_format_without_error() -> None:
    """Every `analysis` template fills cleanly with the real arguments (no stray field)."""
    for lang in sp.SUPPORTED_LANGS:
        for key, template in sp.i18n(lang)["analysis"].items():
            # A stray `{foo}` would raise KeyError here; a missing one is harmless.
            str(template).format(**_ANALYSIS_ARGS), f"{lang}.analysis.{key} failed to format"


@pytest.mark.parametrize("lang", sp.SUPPORTED_LANGS)
def test_prompts_keep_required_placeholders(lang: str) -> None:
    """Each localized prompt keeps the placeholders the pipeline fills in."""
    d = sp.i18n(lang)
    for key, needed in _PROMPT_REQUIRED.items():
        for token in needed:
            assert token in d[key], f"{lang}.{key} dropped {token}"


def test_ratings_prompt_formats_without_error() -> None:
    """`ratings_prompt` fills with its three arguments without a stray-placeholder error."""
    for lang in sp.SUPPORTED_LANGS:
        # A stray `{field}` would raise KeyError; the escaped `{{ }}` JSON example is fine.
        out = sp.i18n(lang)["ratings_prompt"].format(
            noun="Language", options="A, B", criteria="X, Y"
        )
        assert "Language" in out and "A, B" in out and "X, Y" in out


def test_suggest_ratings_rejects_empty_input() -> None:
    """`suggest_ratings` validates its inputs before touching the model (model-free path)."""
    with pytest.raises(ValueError):
        sp.suggest_ratings("Option", [], ["Speed"])
    with pytest.raises(ValueError):
        sp.suggest_ratings("Option", ["Python"], [])
