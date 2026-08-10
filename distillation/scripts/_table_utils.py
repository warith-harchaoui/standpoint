"""Shared helper: enforce standpoint's own `validate_table` invariants at generation time.

`standpoint.validate_table` rejects a table with two options that have identical
ratings across every criterion (duplicate rows) or two criteria with identical
ratings across every option (duplicate columns) -- see
`test_validate_table_rejects_degenerate_and_duplicate_input` in the main test suite.
A teacher-generated ratings matrix can occasionally land on a tie by chance; rather
than discard the whole table, nudge one differing cell to break the tie while
leaving the rest of the teacher's judgement intact.
"""

from __future__ import annotations

_RATING_MIN, _RATING_MAX = 1, 5


def _first_value_that_resolves(current: int, is_still_duplicate) -> int | None:
    """Try every other rating value, nearest-first, until one clears the duplicate.

    Trying every value and *verifying* against `is_still_duplicate` (rather than a
    blind +-1 toggle) is what guarantees termination: a toggle can oscillate
    forever if the cell sits at the midpoint of two different conflicting columns
    (see this function's call sites), but scanning all 5 possible ratings always
    finds a value outside both conflicts, since a single cell can't simultaneously
    equal every other value in a 1..5 range.
    """
    candidates = sorted(range(_RATING_MIN, _RATING_MAX + 1), key=lambda v: (abs(v - current), v))
    for v in candidates:
        if v != current and not is_still_duplicate(v):
            return v
    return None  # pathological: every value still conflicts (not reachable with >1 option)


def _dedupe_rows_once(ratings: list[list[int]]) -> bool:
    """One pass fixing duplicate rows. Returns whether anything changed."""
    changed = False
    i = 0
    while i < len(ratings):
        key = tuple(ratings[i])
        if any(tuple(ratings[k]) == key for k in range(len(ratings)) if k != i):
            j = 0

            def still_dup(v: int, i=i, j=j) -> bool:
                trial = list(ratings[i])
                trial[j] = v
                return any(tuple(ratings[k]) == tuple(trial) for k in range(len(ratings)) if k != i)

            new_v = _first_value_that_resolves(ratings[i][j], still_dup)
            if new_v is not None:
                ratings[i][j] = new_v
                changed = True
        i += 1
    return changed


def _dedupe_cols_once(ratings: list[list[int]], n_cols: int) -> bool:
    """One pass fixing duplicate columns. Returns whether anything changed."""
    changed = False
    c = 0
    while c < n_cols:

        def col_of(cc: int) -> tuple[int, ...]:
            return tuple(row[cc] for row in ratings)

        key = col_of(c)
        if any(col_of(k) == key for k in range(n_cols) if k != c):
            row = 0

            def still_dup(v: int, c=c, row=row) -> bool:
                trial = list(col_of(c))
                trial[row] = v
                return any(col_of(k) == tuple(trial) for k in range(n_cols) if k != c)

            new_v = _first_value_that_resolves(ratings[row][c], still_dup)
            if new_v is not None:
                ratings[row][c] = new_v
                changed = True
        c += 1
    return changed


def dedupe_ratings(criteria: list[str], ratings: list[list[int]]) -> list[list[int]]:
    """Return `ratings` with every duplicate row/column broken, to a fixed point.

    Row and column passes can interact (fixing one duplicate can, by coincidence,
    create a different one), so both run repeatedly until a full round changes
    nothing. Each individual nudge is itself verified before being applied (see
    `_first_value_that_resolves`), which additionally prevents the two passes from
    fighting over the same cell forever.
    """
    ratings = [list(row) for row in ratings]  # local mutable copy
    n_cols = len(criteria)
    for _ in range(_RATING_MAX - _RATING_MIN + 2):  # bounded: each real fix narrows the value space
        rows_changed = _dedupe_rows_once(ratings)
        cols_changed = _dedupe_cols_once(ratings, n_cols)
        if not rows_changed and not cols_changed:
            break
    return ratings
