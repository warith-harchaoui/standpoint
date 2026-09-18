"""In-browser (Pyodide) glue between the static GUI page and the standpoint engine.

This module mirrors the thin endpoint logic of ``standpoint.api`` (the FastAPI
server) without FastAPI: same behaviours, same error messages, so the static
build and the server build stay interchangeable in front of the same page.
``backend-pyodide.js`` calls :func:`glue_call` with a function name and a JSON
argument object, and gets back a JSON envelope:

- ``{"ok": <result>}`` — the call succeeded;
- ``{"pending": {key, prompt, schema}}`` — the engine needs a model answer
  first (see ``beh_shim.PendingLLM``); the driver generates one, seeds it via
  :func:`glue_seed`, and calls again (memoized replay);
- ``{"error": "<message>"}`` — a clean, user-facing failure message.

Everything crosses the JS/Python boundary as JSON strings: no proxy lifetimes
to manage, no implicit conversions to reason about.
"""

from __future__ import annotations

import base64
import io
import json
import re
import unicodedata
from collections.abc import Callable
from typing import Any

import best_engine_ai_helper as beh
import pandas as pd

import standpoint as sp


def _slugify(text: str) -> str:
    """Display name -> filename stem (lowercase, hyphen-joined); same as api.py."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "standpoint"


def _df_to_csv(df: pd.DataFrame) -> str:
    """Serialize a parsed table back to clean CSV for the grid (ints stay ints)."""
    # `%g` drops the ".0" that read_excel / parse_table introduce, and blanks stay
    # blank, so the grid shows "2" and "" rather than "2.0" and "nan".
    return df.to_csv(float_format="%g")


def i18n_strings(lang: str = "en") -> dict:
    """The GUI's localized string table for `lang` (falls back to English)."""
    return sp.i18n(lang).get("gui") or sp.i18n("en")["gui"]


def upload_table(b64: str, name: str = "") -> str:
    """Decode an uploaded CSV / XLSX file (base64 bytes) to CSV text for the grid.

    Parameters
    ----------
    b64 : str
        The file content, base64-encoded by the browser (binary-safe transport).
    name : str
        The original filename; ``.xlsx`` / ``.xls`` route through pandas + openpyxl.
    """
    content = base64.b64decode(b64)
    try:
        if name.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content), index_col=0)
        else:
            df = sp.parse_table(content.decode("utf-8", errors="replace"))
    except Exception as exc:  # unreadable spreadsheet / not a table -> clean message
        raise ValueError(f"Could not read the file: {exc}") from exc
    return _df_to_csv(df)


def to_xlsx(table: str) -> str:
    """Convert the grid's CSV text to an XLSX workbook, base64-encoded for download."""
    try:
        df = sp.parse_table(table)
    except Exception as exc:
        raise ValueError(f"Could not parse the table: {exc}") from exc
    buf = io.BytesIO()
    df.to_excel(buf)  # index = option names; openpyxl writes the .xlsx
    return base64.b64encode(buf.getvalue()).decode()


def autofill(
    noun: str = "Option",
    options: list[str] | None = None,
    criteria: list[str] | None = None,
    lang: str = "",
) -> dict:
    """ "Laziness" auto-fill: the in-browser model scores every option / criterion."""
    lang_arg = lang if lang in sp.SUPPORTED_LANGS else None
    return sp.suggest_ratings(noun, options or [], criteria or [], lang=lang_arg)


def position(
    table: str,
    reference: str = "0",
    lower: str = "",
    lang: str = "",
    model: str = "",
) -> dict:
    """Full positioning run; returns exactly what ``POST /api/position`` returns."""
    if not table.strip():
        raise ValueError("The table is empty.")
    # A numeric reference arrives as a string ("0"); pass ints through as ints so
    # `positioning` treats it as a row index rather than an option name.
    ref: int | str = int(reference) if str(reference).lstrip("-").isdigit() else reference
    lower_cols = [c.strip() for c in lower.split(",") if c.strip()]
    lang_arg = lang if lang in sp.SUPPORTED_LANGS else None
    pos = sp.positioning(table, reference=ref, lower_is_better=lower_cols, lang=lang_arg)
    return {
        "svg": pos.to_svg(),  # dropped straight into the page's #chart div
        "yaml": pos.to_yaml(),  # coordinates + coefficients, offered as a download
        "axes": pos.axes,  # {'x': ..., 'y': ...} axis titles
        "poles": pos.poles,  # the four pole labels
        "reference": pos.result.reference,  # resolved name of the top-right anchor
        "roles": pos.role_of,  # option -> role, drives the name tinting
        "slug": _slugify(pos.noun_plural),  # export filename stem
    }


# How a lower-is-better criterion reads as a benefit, per language, for the
# embedding-based axis naming (mirrors `show()` inside `axis_poles`, which
# presents "low Price" to the LLM so it names the benefit, not the drawback).
_LOW_TEMPLATES = {"en": "low {f}", "fr": "{f} faible", "es": "{f} bajo"}


def pole_context(
    table: str,
    reference: str = "0",
    lower: str = "",
    lang: str = "",
    model: str = "",
) -> dict:
    """The structured per-pole criteria the browser names the axes from.

    Runs the deterministic front half of `positioning` (parse, polarity, PCA)
    and returns, for each pole, the criteria that load on it — the same
    ``|weight| > 0.05`` selection and lower-is-better presentation
    ``axis_poles`` builds its LLM prompt from — so the embedding-based namer in
    ``backend-pyodide.js`` scores exactly the evidence the model would have
    seen. No LLM call happens here, so this never goes pending.

    Returns
    -------
    dict
        ``{"lang": ..., "poles": {left|right|bottom|top: [{"text", "weight"}]}}``
        with each pole's criteria strongest-first.
    """
    if not table.strip():
        raise ValueError("The table is empty.")
    ref: int | str = int(reference) if str(reference).lstrip("-").isdigit() else reference
    lower_cols = [c.strip() for c in lower.split(",") if c.strip()]
    df, lower_set = sp.resolve_polarity(sp.parse_table(table), lower_cols)
    result = sp.analyze(df, reference=ref, lower_is_better=list(lower_set))
    lang_final = lang if lang in sp.SUPPORTED_LANGS else sp.detect_language(result.features)
    low_tpl = _LOW_TEMPLATES.get(lang_final, _LOW_TEMPLATES["en"])

    def pole(k: int, sign: int) -> list[dict]:
        """Criteria (benefit-phrased, strongest-first) defining one end of axis `k`."""
        pairs = [
            (f, w)
            for f, w in zip(result.features, result.components[k], strict=False)
            if (w > 0) == (sign > 0) and abs(w) > 0.05
        ]
        pairs.sort(key=lambda t: -abs(t[1]))
        return [
            {"text": low_tpl.format(f=f) if f in result.lower else f, "weight": abs(w)}
            for f, w in pairs
        ]

    return {
        "lang": lang_final,
        "poles": {
            "left": pole(0, -1),
            "right": pole(0, +1),
            "bottom": pole(1, -1),
            "top": pole(1, +1),
        },
    }


# The callable surface backend-pyodide.js dispatches on (name -> function).
_FUNCS: dict[str, Callable[..., Any]] = {
    "i18n": i18n_strings,
    "upload": upload_table,
    "xlsx": to_xlsx,
    "autofill": autofill,
    "position": position,
    "pole_context": pole_context,
}


def glue_call(name: str, arg_json: str) -> str:
    """Dispatch one backend call; always returns a JSON envelope (never raises).

    Parameters
    ----------
    name : str
        One of ``i18n | upload | xlsx | autofill | position``.
    arg_json : str
        The call's keyword arguments as a JSON object string.
    """
    try:
        fn = _FUNCS[name]
        args = json.loads(arg_json) if arg_json else {}
        return json.dumps({"ok": fn(**args)})
    except beh.PendingLLM as pending:  # model answer needed: replay after seeding
        return json.dumps({"pending": pending.payload()})
    except ValueError as exc:  # bad table / unknown reference -> clean UI message
        return json.dumps({"error": str(exc)})
    except Exception as exc:  # anything else: name the type, keep the page alive
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


def glue_seed(key: str, answer_json: str) -> None:
    """Seed the shim's answer cache with the browser-generated model reply."""
    beh.seed(key, json.loads(answer_json))
