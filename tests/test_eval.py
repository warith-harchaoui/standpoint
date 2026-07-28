"""DeepEval evaluation of Standpoint's LLM axis-pole naming (coding standard, Rule 16).

Standpoint uses a local model to name the four axis poles. The deterministic
`finalize_poles` guard already enforces the hard invariants in code; this file adds
an *evaluation* layer on top, expressed with DeepEval, that scores the model's real
output on every tracked example: the four labels must be distinct, positive (no
drawback word), and free of acronyms: the qualities a good pole label has.

It is intentionally heavy and model-dependent: it runs whenever `deepeval` (the
``eval`` extra) is installed, and drives the real local model, which is a hard
prerequisite that `tests/conftest.py` guarantees.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import standpoint as sp

# Skip the whole module unless the DeepEval framework is installed (`pip install
# -e ".[eval]"`); importorskip records the reason on the skip.
pytest.importorskip("deepeval")

from deepeval.metrics import BaseMetric  # noqa: E402  (after importorskip by design)
from deepeval.test_case import LLMTestCase  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
_JOIN = " | "  # separator that carries the poles through the test case's output

# Naming quality is judged against the real model output; the local model is a hard
# prerequisite that `tests/conftest.py` guarantees, so the eval always runs it.


class PoleQualityMetric(BaseMetric):
    """A deterministic DeepEval metric scoring one set of axis-pole labels.

    Scores 1.0 only when the four poles (carried in ``test_case.actual_output``,
    joined by ``_JOIN``) are all distinct, contain no negative/drawback word, and
    show no leftover acronym; otherwise 0.0 with a human-readable reason. No external
    judge model is used: the invariants are Standpoint's own, checked in code.
    """

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase) -> float:
        """Score the poles on the case and record `score`, `success`, and `reason`."""
        poles = test_case.actual_output.split(_JOIN)
        problems: list[str] = []
        if len(set(poles)) != 4:
            problems.append(f"not four distinct labels: {poles}")
        negatives = sp._content_words(" ".join(poles)) & sp._NEGATIVE_WORDS
        if negatives:
            problems.append(f"contains negative words: {sorted(negatives)}")
        acronyms = [tok for p in poles for tok in p.split() if tok.isupper() and len(tok) <= 5]
        if acronyms:
            problems.append(f"contains acronyms: {acronyms}")
        self.score = 1.0 if not problems else 0.0
        self.success = self.score >= self.threshold
        self.reason = "; ".join(problems) or "four distinct, positive, acronym-free labels"
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        """Async shim required by BaseMetric; defers to the sync `measure`."""
        return self.measure(test_case)

    def is_successful(self) -> bool:
        """Whether the last `measure` met the threshold."""
        return self.success

    @property
    def __name__(self) -> str:  # shown in DeepEval output
        """Human-readable metric name for DeepEval reporting."""
        return "Pole Quality"


@pytest.mark.parametrize(
    "csv",
    ["programming_languages.csv", "cloud_providers.csv", "voitures_electriques.csv"],
)
@pytest.mark.needs_model
def test_pole_naming_quality(csv: str) -> None:
    """Every example's model-named poles pass the DeepEval quality metric."""
    pos = sp.positioning(str(EXAMPLES / csv))
    case = LLMTestCase(
        input=f"Name the four axis poles for {csv}",
        actual_output=_JOIN.join(pos.poles),
    )
    metric = PoleQualityMetric()
    metric.measure(case)
    assert metric.is_successful(), f"{csv}: {metric.reason} (poles={pos.poles})"
