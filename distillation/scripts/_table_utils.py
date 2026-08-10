"""Shared helper: enforce standpoint's own `validate_table` invariants at generation time.

`standpoint.validate_table` rejects a table with two options that have identical
ratings across every criterion (duplicate rows) or two criteria with identical
ratings across every option (duplicate columns) -- see
`test_validate_table_rejects_degenerate_and_duplicate_input` in the main test suite.
A teacher-generated ratings matrix can occasionally land on a tie by chance; rather
than discard the whole table, nudge one differing cell by +-1 (clamped to 1..5) to
break the tie while leaving the rest of the teacher's judgement intact.
"""

from __future__ import annotations


def dedupe_ratings(criteria: list[str], ratings: list[list[int]]) -> list[list[int]]:
    """Return `ratings` with any duplicate row or duplicate column broken by one nudge."""
    ratings = [list(row) for row in ratings]  # local mutable copy

    # duplicate rows (two options with identical ratings across every criterion)
    seen_rows: dict[tuple[int, ...], int] = {}
    for i, row in enumerate(ratings):
        key = tuple(row)
        if key in seen_rows:
            j = 0 if key[0] < 5 else -1  # nudge the first cell, away from its bound
            ratings[i][j] += 1 if ratings[i][j] < 5 else -1
        else:
            seen_rows[key] = i

    # duplicate columns (two criteria with identical ratings across every option)
    n_cols = len(criteria)
    seen_cols: dict[tuple[int, ...], int] = {}
    for c in range(n_cols):
        col = tuple(row[c] for row in ratings)
        if col in seen_cols:
            row0 = ratings[0][c]
            ratings[0][c] = row0 + 1 if row0 < 5 else row0 - 1
        else:
            seen_cols[col] = c

    return ratings
