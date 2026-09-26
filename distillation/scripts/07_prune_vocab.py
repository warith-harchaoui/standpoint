"""Prune the student's vocabulary to what its three tasks actually use.

Qwen3's 151,936-row embedding table exists to cover a hundred languages; this
student answers three schema-constrained tasks in English and French. At fp16
that table is ~311 MB of the ~650 MB browser bundle -- half the download spent
on rows that can never help. This script rebuilds the checkpoint around the
vocabulary the tasks can reach:

- every token that appears when tokenizing the WHOLE corpus (train +
  validation, questions and answers, through the same chat template training
  used), so the training distribution tokenizes bit-identically;
- the results of the first ``--common-merges`` BPE merges (merges are ordered
  by frequency from the original BPE training, so this keeps the most common
  multilingual subwords as a robustness margin for user tables the corpus
  never saw) -- a merge's inputs are earlier merges' results or alphabet
  bytes, so this set is derivation-closed by construction;
- the 256 byte-alphabet tokens (ids 0-255), so ANY string a user types stays
  tokenizable -- unseen words just decompose into more, smaller pieces;
- the 26 added/special tokens (chat template, think markers, ...).

**Correctness hinges on derivation closure.** Greedy BPE builds a token by
merging its parts bottom-up, so a kept token is only reachable if every
intermediate token on its merge path is kept too -- including ones that never
appear in any final tokenization. The keep set is therefore closed over "which
merge produces this token" before filtering the merge list. With that closure,
any merge that ever fired while tokenizing the corpus produced an ancestor of
a kept token and thus survives, in the same relative order -- so corpus
tokenization is provably unchanged, and the script verifies that empirically
over every example before writing anything.

Ids are then remapped contiguously, the embedding rows permuted to match (the
LM head is tied, so one tensor carries both roles), and the special-token ids
in the configs rewritten. Output: a complete HF checkpoint ready for
`05_export_browser.py`-style ONNX export.

Run with the distillation venv::

    .venv/bin/python scripts/07_prune_vocab.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DIST_DIR = Path(__file__).resolve().parents[1]
CHECKPOINTS = DIST_DIR / "checkpoints"
REPO = DIST_DIR.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--weights",
        type=Path,
        default=CHECKPOINTS / "standpoint-qwen3-0.6b-fused",
        help="fused HF checkpoint (weights + config)",
    )
    parser.add_argument(
        "--tokenizer",
        type=Path,
        default=CHECKPOINTS / "llm-engine",
        help="directory holding the UPSTREAM tokenizer files (mlx_lm fuse mangles "
        "tokenizer_config.json -- see 05_export_browser.py -- so the browser "
        "bundle's copy is the trusted source)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=CHECKPOINTS / "standpoint-qwen3-0.6b-pruned",
        help="output checkpoint directory",
    )
    parser.add_argument(
        "--common-merges",
        type=int,
        default=20_000,
        help="keep the results of this many top-frequency BPE merges as a "
        "robustness margin for out-of-corpus words (default: %(default)s)",
    )
    return parser.parse_args()


def corpus_texts(tokenizer) -> list[str]:
    """Every text whose tokenization must survive pruning bit-identically.

    The corpus examples go through the same chat template training used, so
    template literals (role markers, the <think></think> pair) are covered.
    The repo's example tables are added raw AND space-prefixed: a cell value
    tokenizes differently after a space ("ĠPython" vs "Python"), and prompts
    place user words in both positions.
    """
    texts: list[str] = []
    for split in ("train", "validation"):
        path = DIST_DIR / "data" / "dataset" / "combined" / f"{split}.jsonl"
        if not path.exists():
            print(f"{path} missing; run 03_train_lora.py first.", file=sys.stderr)
            sys.exit(1)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ex = json.loads(line)
            texts.append(
                tokenizer.apply_chat_template(
                    [
                        {"role": "user", "content": ex["question"]},
                        {"role": "assistant", "content": ex["answer"]},
                    ],
                    tokenize=False,
                )
            )
    for csv in sorted((REPO / "examples").glob("*.csv")):
        raw = csv.read_text(encoding="utf-8")
        texts.append(raw)
        cells = [c.strip() for line in raw.splitlines() for c in line.split(",")]
        texts.append("".join(" " + c for c in cells if c))
    return texts


def main() -> None:
    args = parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    tok_json = json.loads((args.tokenizer / "tokenizer.json").read_text(encoding="utf-8"))
    vocab: dict[str, int] = tok_json["model"]["vocab"]
    merges: list[list[str]] = tok_json["model"]["merges"]
    added = tok_json["added_tokens"]
    id_to_token = {i: t for t, i in vocab.items()}

    # --- the keep set, as base-vocab token strings -------------------------------
    texts = corpus_texts(tokenizer)
    print(f"tokenizing {len(texts)} corpus texts...")
    added_ids = {a["id"] for a in added}
    used_ids: set[int] = set()
    for text in texts:
        used_ids.update(tokenizer(text, add_special_tokens=False)["input_ids"])
    corpus_tokens = {id_to_token[i] for i in used_ids if i not in added_ids}
    keep = set(corpus_tokens)
    keep.update(id_to_token[i] for i in range(256))  # the byte alphabet
    common = {a + b for a, b in merges[: args.common_merges]}
    keep.update(t for t in common if t in vocab)

    # --- derivation closure ------------------------------------------------------
    # Which merge produces each token (BPE: at most one). A kept token is only
    # reachable if its whole merge path is kept, so close over components.
    produced_by: dict[str, tuple[str, str]] = {}
    for a, b in merges:
        produced_by.setdefault(a + b, (a, b))
    stack = list(keep)
    while stack:
        parts = produced_by.get(stack.pop())
        if not parts:
            continue
        for part in parts:
            if part not in keep:
                keep.add(part)
                stack.append(part)
    print(
        f"keep set: {len(corpus_tokens)} corpus tokens "
        f"+ {args.common_merges} common merges + bytes -> {len(keep)} after closure "
        f"(of {len(vocab)} base tokens)"
    )

    # --- remap: kept base tokens in old-id order, then the added tokens ----------
    kept_old_ids = sorted(vocab[t] for t in keep)
    old_to_new = {old: new for new, old in enumerate(kept_old_ids)}
    next_id = len(kept_old_ids)
    for entry in sorted(added, key=lambda a: a["id"]):
        old_to_new[entry["id"]] = next_id
        next_id += 1
    new_vocab_size = next_id
    print(f"new vocab: {len(kept_old_ids)} base + {len(added)} added = {new_vocab_size}")

    new_vocab = {id_to_token[old]: old_to_new[old] for old in kept_old_ids}
    new_merges = [[a, b] for a, b in merges if a in keep and b in keep and (a + b) in keep]
    print(f"merges: {len(merges)} -> {len(new_merges)}")

    tok_json["model"]["vocab"] = new_vocab
    tok_json["model"]["merges"] = new_merges
    tok_json["added_tokens"] = [
        {**entry, "id": old_to_new[entry["id"]]} for entry in sorted(added, key=lambda a: a["id"])
    ]

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "tokenizer.json").write_text(
        json.dumps(tok_json, ensure_ascii=False), encoding="utf-8"
    )

    # tokenizer_config: same content, added-token ids rewritten.
    tok_cfg = json.loads((args.tokenizer / "tokenizer_config.json").read_text(encoding="utf-8"))
    tok_cfg["added_tokens_decoder"] = {
        str(old_to_new[int(old)]): meta for old, meta in tok_cfg["added_tokens_decoder"].items()
    }
    (args.out / "tokenizer_config.json").write_text(
        json.dumps(tok_cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # config / generation_config: new vocab size, remapped special-token ids.
    def remap_ids(value):
        """bos/eos/pad fields hold one id or a list of ids; remap either shape."""
        if isinstance(value, list):
            return [old_to_new[v] for v in value]
        return old_to_new[value] if isinstance(value, int) else value

    config = json.loads((args.weights / "config.json").read_text(encoding="utf-8"))
    config["vocab_size"] = new_vocab_size
    for field in ("bos_token_id", "eos_token_id", "pad_token_id"):
        if field in config:
            config[field] = remap_ids(config[field])
    (args.out / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    gen = json.loads((args.weights / "generation_config.json").read_text(encoding="utf-8"))
    for field in ("bos_token_id", "eos_token_id", "pad_token_id"):
        if field in gen:
            gen[field] = remap_ids(gen[field])
    (args.out / "generation_config.json").write_text(
        json.dumps(gen, indent=2) + "\n", encoding="utf-8"
    )

    # --- verify BEFORE writing weights: corpus tokenization is unchanged ---------
    pruned_tokenizer = AutoTokenizer.from_pretrained(args.out)
    print("verifying corpus tokenization is bit-identical...")
    for n, text in enumerate(texts):
        before = tokenizer(text, add_special_tokens=False)["input_ids"]
        after = pruned_tokenizer(text, add_special_tokens=False)["input_ids"]
        if [old_to_new[i] for i in before] != after:
            print(f"MISMATCH on corpus text #{n}: pruning would change tokenization.")
            print(repr(text[:200]))
            sys.exit(1)
    print(f"OK: all {len(texts)} corpus texts tokenize identically.")

    # --- permute the one vocab-sized tensor (the LM head is tied to it) ----------
    import torch
    from safetensors.torch import load_file, save_file

    state = load_file(str(args.weights / "model.safetensors"))
    embed = state["model.embed_tokens.weight"]
    rows = kept_old_ids + [a["id"] for a in sorted(added, key=lambda a: a["id"])]
    state["model.embed_tokens.weight"] = embed[torch.tensor(rows)].contiguous()
    print(
        f"embed_tokens: {tuple(embed.shape)} -> "
        f"{tuple(state['model.embed_tokens.weight'].shape)}"
    )
    save_file(state, str(args.out / "model.safetensors"), metadata={"format": "pt"})

    total = sum(f.stat().st_size for f in args.out.glob("*") if f.is_file())
    print(f"\npruned checkpoint ready at {args.out} ({total / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
