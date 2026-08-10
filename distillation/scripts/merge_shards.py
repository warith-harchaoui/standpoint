"""Merge sharded Phase 1b output (from `02_generate_dataset.py --shard-id ...`) into
the main dataset files, then delete the shard files.

Each JSONL line is validated (`json.loads`) before merging; a shard process killed
mid-write could in principle leave a truncated final line (each shard writes to its
own file, so this can't corrupt another shard's or the main files' *other* lines --
see `02_generate_dataset.py`'s module docstring) and such a line is dropped rather
than crashing the merge.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "dataset"
TASKS = ["pole_naming", "noun_forms", "narrative", "vlm_assess"]


def merge_jsonl(task: str) -> int:
    main_path = OUT_DIR / f"{task}.jsonl"
    shard_paths = sorted(OUT_DIR.glob(f"{task}.shard*.jsonl"))
    added = 0
    with main_path.open("a", encoding="utf-8") as out:
        for shard_path in shard_paths:
            for line in shard_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    json.loads(line)  # validate; re-serializing isn't needed, line is already JSON
                except json.JSONDecodeError:
                    print(f"  dropping malformed line in {shard_path.name}")
                    continue
                out.write(line + "\n")
                added += 1
            shard_path.unlink()
    return added


def merge_processed_log() -> int:
    main_log = OUT_DIR / ".processed"
    shard_logs = sorted(OUT_DIR.glob(".processed.shard*"))
    existing = set(main_log.read_text().split()) if main_log.exists() else set()
    added = set()
    for shard_log in shard_logs:
        added |= set(shard_log.read_text().split()) - existing
        shard_log.unlink()
    if added:
        with main_log.open("a", encoding="utf-8") as f:
            for stem in sorted(added):
                f.write(stem + "\n")
    return len(added)


def main() -> None:
    for task in TASKS:
        n = merge_jsonl(task)
        print(f"{task}: merged {n} lines")
    n = merge_processed_log()
    print(f".processed: merged {n} new stems")


if __name__ == "__main__":
    main()
