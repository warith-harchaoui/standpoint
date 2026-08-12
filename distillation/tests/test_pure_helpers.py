"""Unit tests for the distillation pipeline's pure, model-free helper functions.

Most of `distillation/scripts/` drives real teacher/student model calls end to
end and isn't meaningfully unit-testable (that's what Phase 3's held-out
evaluation is for). A handful of functions are pure data transforms with no I/O
or model dependency, though, and are cheap to pin down directly: the ratings
deduplication `01_generate_tables.py` relies on, the balancing pass
`07_balance_dataset.py` runs once before every train/val split, and the
smoothing `make_loss_figure.py` draws on the training curve. These import the
scripts directly (some have numeric-leading filenames, invalid as Python module
names, hence `importlib` rather than a plain `import`) so a refactor that
changes their behaviour is caught here before it reaches an hours-long run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_table_utils = _load("_table_utils", "_table_utils.py")
_balance_mod = _load("balance_dataset", "07_balance_dataset.py")
_figure_mod = _load("make_loss_figure", "make_loss_figure.py")


# --------------------------------------------------------------------------- #
# _table_utils.dedupe_ratings
# --------------------------------------------------------------------------- #
def test_dedupe_ratings_breaks_duplicate_row() -> None:
    criteria = ["Price", "Speed", "Quality"]
    ratings = [[3, 3, 3], [3, 3, 3], [1, 2, 5]]  # rows 0 and 1 are identical
    out = _table_utils.dedupe_ratings(criteria, ratings)
    rows = [tuple(r) for r in out]
    assert len(set(rows)) == len(rows)  # every row now distinct


def test_dedupe_ratings_breaks_duplicate_column() -> None:
    criteria = ["Price", "Speed", "Quality"]
    ratings = [[3, 3, 1], [4, 4, 2], [5, 5, 3]]  # columns 0 and 1 are identical
    out = _table_utils.dedupe_ratings(criteria, ratings)
    cols = [tuple(row[c] for row in out) for c in range(len(criteria))]
    assert len(set(cols)) == len(cols)  # every column now distinct


def test_dedupe_ratings_leaves_already_distinct_input_untouched() -> None:
    criteria = ["Price", "Speed"]
    ratings = [[1, 2], [3, 4], [5, 1]]
    out = _table_utils.dedupe_ratings(criteria, ratings)
    assert out == ratings


def test_dedupe_ratings_does_not_mutate_its_input() -> None:
    criteria = ["Price", "Speed", "Quality"]
    ratings = [[3, 3, 3], [3, 3, 3], [1, 2, 5]]
    original = [row[:] for row in ratings]
    _table_utils.dedupe_ratings(criteria, ratings)
    assert ratings == original  # dedupe_ratings works on its own copy


# --------------------------------------------------------------------------- #
# 07_balance_dataset._dedupe / _balance
# --------------------------------------------------------------------------- #
def test_dedupe_keeps_one_of_each_lang_question_pair() -> None:
    examples = [
        {"lang": "en", "question": "q1", "answer": "a"},
        {"lang": "en", "question": "q1", "answer": "b"},  # duplicate key, differing answer
        {"lang": "fr", "question": "q1", "answer": "c"},  # same question, different lang: kept
    ]
    out = _balance_mod._dedupe(examples)
    keys = [(e["lang"], e["question"]) for e in out]
    assert len(keys) == len(set(keys))
    assert len(out) == 2


def test_balance_trims_majority_language_to_minority_count() -> None:
    examples = [{"lang": "en", "question": f"q{i}"} for i in range(10)]
    examples += [{"lang": "fr", "question": f"q{i}"} for i in range(4)]
    out = _balance_mod._balance(examples, seed=42)
    n_en = sum(1 for e in out if e["lang"] == "en")
    n_fr = sum(1 for e in out if e["lang"] == "fr")
    assert n_en == n_fr == 4


def test_balance_is_deterministic_given_the_same_seed() -> None:
    examples = [{"lang": "en", "question": f"q{i}"} for i in range(10)]
    examples += [{"lang": "fr", "question": f"q{i}"} for i in range(4)]
    out1 = _balance_mod._balance(examples, seed=42)
    out2 = _balance_mod._balance(examples, seed=42)
    assert out1 == out2


# --------------------------------------------------------------------------- #
# make_loss_figure.centered_moving_average
# --------------------------------------------------------------------------- #
def test_centered_moving_average_on_a_linear_ramp() -> None:
    # STEPS_PER_REPORT=10, window_iters=20 -> half = max(1, 20//10//2) = 1 row each side.
    points = [(i * 10, float(i)) for i in range(5)]  # q = 0, 1, 2, 3, 4
    out = _figure_mod.centered_moving_average(points, window_iters=20)
    iters = [it for it, _ in out]
    qs = [round(q, 4) for _, q in out]
    assert iters == [0, 10, 20, 30, 40]
    assert qs == [0.5, 1.0, 2.0, 3.0, 3.5]  # shrinking window at the edges, full window inside


def test_centered_moving_average_preserves_point_count() -> None:
    points = [(i * 10, float(i % 7)) for i in range(50)]
    out = _figure_mod.centered_moving_average(points, window_iters=100)
    assert len(out) == len(points)
    assert [it for it, _ in out] == [it for it, _ in points]  # x-axis untouched
