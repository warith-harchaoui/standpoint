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
# Substrings every localized LLM prompt must keep, so the pipeline can fill them in.
_PROMPT_REQUIRED = {
    "title_template": ["{plural}"],
    "noun_prompt": ["{word}"],
    "axis_prompt": ["{glossary}", "{left}", "{right}", "{bottom}", "{top}"],
    "ratings_prompt": ["{noun}", "{options}", "{criteria}"],
}


def _placeholders(text: str) -> set[str]:
    """The `{name}` fields in a template (single braces only; `{{ }}` are literals)."""
    return set(re.findall(r"(?<!\{)\{(\w+)\}(?!\})", text))


@pytest.mark.parametrize("lang", sp.SUPPORTED_LANGS)
def test_language_is_complete_and_formats_cleanly(lang: str) -> None:
    """One language's whole i18n table: every required block/placeholder, no format errors.

    Merges what used to be separate checks (blocks present, prompts keep their
    placeholders, `ratings_prompt` formats) since they all walk the same
    `sp.i18n(lang)` table for one language and are cheap/model-free; splitting
    them bought no extra signal, just extra reads of the same fixture.
    """
    d = sp.i18n(lang)
    for key in (*_PROMPT_REQUIRED, "glossary_prefix", "gui"):
        assert key in d, f"{lang} is missing {key!r}"
    for key, needed in _PROMPT_REQUIRED.items():
        for token in needed:
            assert token in d[key], f"{lang}.{key} dropped {token}"
    out = d["ratings_prompt"].format(noun="Language", options="A, B", criteria="X, Y")
    assert "Language" in out and "A, B" in out and "X, Y" in out


def test_gui_keys_match_across_languages() -> None:
    """Every language exposes exactly the same `gui` keys (no gaps, no extras)."""
    reference = set(sp.i18n("en")["gui"])
    for lang in sp.SUPPORTED_LANGS:
        assert set(sp.i18n(lang)["gui"]) == reference, f"{lang}.gui keys diverge"


def test_gui_placeholders_are_known_and_consistent() -> None:
    """GUI strings use only known placeholders, identically across languages."""
    for key in sp.i18n("en")["gui"]:
        sets = {lang: _placeholders(str(sp.i18n(lang)["gui"][key])) for lang in sp.SUPPORTED_LANGS}
        for lang, found in sets.items():
            assert found <= _GUI_PLACEHOLDERS, f"{lang}.gui.{key} has unknown placeholder {found}"
        assert len(set(map(frozenset, sets.values()))) == 1, (
            f"gui.{key} placeholders differ by language"
        )


def test_suggest_ratings_rejects_empty_input() -> None:
    """`suggest_ratings` validates its inputs before touching the model (model-free path)."""
    with pytest.raises(ValueError):
        sp.suggest_ratings("Option", [], ["Speed"])
    with pytest.raises(ValueError):
        sp.suggest_ratings("Option", ["Python"], [])


# --------------------------------------------------------------------------- #
# The canonical file shape, and the loader shared with the rest of the suite
# --------------------------------------------------------------------------- #
def test_the_locale_file_is_readable_by_the_shared_loader() -> None:
    """The file turned round in 0.12.0 so a shared loader could read it at all.

    It used to put the locale first (`en:` / `fr:` / `es:` at the top level)
    and carried no `meta`, which the suite's canonical shape — semantic key
    first, locale second, metadata declared — does not allow. `Locales`
    refused it outright before the change.
    """
    import os_helper as osh

    loc = osh.Locales.from_path(sp._I18N_PATH)
    assert loc.default_locale == "en"
    assert set(loc.supported_locales) == set(sp.SUPPORTED_LANGS)
    assert loc.sections() == [sp._I18N_SECTION]


def test_the_shared_validator_finds_nothing_wrong() -> None:
    """Every key present in all three languages, with matching placeholders.

    `problems()` is the section 21.3.7 check, and it covers the faults nobody
    thought to write a test for — which is the half the hand-rolled checks
    above cannot reach.
    """
    import os_helper as osh

    assert osh.Locales.from_path(sp._I18N_PATH).problems() == []


@pytest.mark.parametrize("lang", ["en", "fr", "es"])
def test_every_language_still_carries_the_same_keys(lang: str) -> None:
    """Transposing a 608-line prompt file is exactly where a key goes missing.

    The templates here drive what a local model writes, in three languages, so
    a silently dropped key would surface as a deliverable in the wrong
    language rather than as an error.
    """
    assert set(sp.i18n(lang)) == set(sp.i18n("en"))
    assert sp.i18n(lang)["title_template"].strip()


def test_an_unknown_language_falls_back_to_english() -> None:
    assert sp.i18n("tlh") == sp.i18n("en")
