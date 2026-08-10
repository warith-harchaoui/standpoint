"""DeepEval evaluation of Standpoint's LLM axis-pole naming (coding standard, Rule 16).

Standpoint uses a local model to name the four axis poles. The hard invariants
(distinct, positive, acronym-free) are deterministic and already covered without
DeepEval by `test_finalize_poles_*` and `test_axis_poles_llm_quality` in
`test_standpoint.py`. What those tests cannot judge is *quality*: is "Accessible <->
Efficient" a better name for an axis than "Good <-> Bad"? That is a subjective call an
LLM judge is suited for, so this file scores it with DeepEval's `GEval`, driven by
Standpoint's own local engine (`best_engine_ai_helper`) rather than DeepEval's default
OpenAI judge, keeping the evaluation local-first like the rest of the project.

It is intentionally heavy and model-dependent: it runs whenever `deepeval` (the
``eval`` extra) is installed, and drives the real local model, which is a hard
prerequisite that `tests/conftest.py` guarantees.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import standpoint as sp

# Skip the whole module unless the DeepEval framework is installed (`pip install
# -e ".[eval]"`); importorskip records the reason on the skip.
pytest.importorskip("deepeval")

from best_engine_ai_helper import llm  # noqa: E402  (after importorskip by design)
from deepeval.metrics import GEval  # noqa: E402
from deepeval.models.base_model import DeepEvalBaseLLM  # noqa: E402
from deepeval.test_case import LLMTestCase, SingleTurnParams  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class LocalEngineJudge(DeepEvalBaseLLM):
    """A DeepEval judge backed by Standpoint's own local engine, not OpenAI.

    `best_engine_ai_helper` resolves the same local Ollama/vLLM backend Standpoint
    uses for axis naming (see `sp.engine()`); routing the judge through it keeps this
    evaluation on-machine, consistent with the project's local-first design.
    """

    def load_model(self) -> dict:
        """Resolve and return the local engine descriptor used for every call."""
        return sp.engine()

    def generate(self, prompt: str, **kwargs: object) -> str:
        """Free-text completion from the local judge model at temperature 0."""
        return llm.chat(prompt, engine=self.model, kind="vlm", temperature=0.0)

    async def a_generate(self, prompt: str, **kwargs: object) -> str:
        """Async shim required by `DeepEvalBaseLLM`; defers to the sync `generate`."""
        return self.generate(prompt, **kwargs)

    def get_model_name(self) -> str:
        """Judge name shown in DeepEval output."""
        return "standpoint-local-engine"


# `async_mode=False` runs `measure()` synchronously, avoiding an event loop inside
# pytest; `threshold` is deliberately lenient (0.6) since a local, non-frontier model
# is doing the judging, not GPT-4-class reasoning.
POLE_QUALITY_JUDGE = GEval(
    name="Axis Pole Word Quality",
    criteria=(
        "The input lists the criteria (and their loadings) driving the low end and "
        "the high end of one PCA axis from a positioning map, separately. The actual "
        "output names a low pole word and a high pole word for that axis. Judge the "
        "low pole word only against the low-end criteria, and the high pole word only "
        "against the high-end criteria (they name different, opposite ends -- a pole "
        "word is not expected to reflect the other end's criteria). For each word, "
        "judge whether it is natural and commonly used (not awkward, generic, or "
        "nonsensical) and whether it plausibly captures what its own end's criteria "
        "have in common."
    ),
    evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
    model=LocalEngineJudge(),
    threshold=0.6,
    async_mode=False,
)


def _pole_criteria(loadings_col: pd.Series, positive: bool, top_n: int = 3) -> str:
    """Describe the criteria driving one end of an axis, strongest-first.

    Mirrors `axis_poles()`'s own `pole_strengths`: a pole is named from the criteria
    that load on ITS sign only, never the opposite end's, so the judge is asked the
    same question the naming model was.
    """
    side = loadings_col[loadings_col > 0] if positive else loadings_col[loadings_col < 0]
    top = side.abs().sort_values(ascending=False).head(top_n)
    return (
        ", ".join(f"{name} ({loadings_col[name]:+.2f})" for name in top.index)
        or "(nothing loads here)"
    )


@pytest.mark.parametrize(
    "csv",
    ["programming_languages.csv", "cloud_providers.csv", "voitures_electriques.csv"],
)
@pytest.mark.needs_model
def test_pole_naming_quality(csv: str) -> None:
    """Every example's model-named poles read as good axis labels to a local judge."""
    result = sp.analyze(sp.parse_table(str(EXAMPLES / csv)))
    poles = sp.axis_poles(result)
    loadings = result.loadings()

    for axis_col, (lo, hi) in (("axis-1", (poles[0], poles[1])), ("axis-2", (poles[2], poles[3]))):
        col = loadings[axis_col]
        case = LLMTestCase(
            input=(
                f"Low-end criteria (loading): {_pole_criteria(col, positive=False)}. "
                f"High-end criteria (loading): {_pole_criteria(col, positive=True)}."
            ),
            actual_output=f"low pole = {lo!r}, high pole = {hi!r}",
        )
        POLE_QUALITY_JUDGE.measure(case)
        assert POLE_QUALITY_JUDGE.is_successful(), (
            f"{csv} {axis_col} ({lo} <-> {hi}): score={POLE_QUALITY_JUDGE.score:.2f} "
            f"reason={POLE_QUALITY_JUDGE.reason}"
        )
