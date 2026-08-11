"""Train with a real validation split -- `mlx_vlm.lora`'s CLI can't do this.

`mlx_vlm/lora.py`'s `main()` hardcodes `val_dataset=None` at both its `train()`
and `train_orpo()` call sites, regardless of what `--val-batches`/`--steps-per-eval`
are passed or whether the loaded dataset has a `validation` split -- confirmed by
reading the installed package directly (grep `val_dataset` in `lora.py`: both
hits are the literal `None`). The underlying `mlx_vlm.trainer.sft_trainer.train()`
function fully supports a `val_dataset` argument and evaluates on it exactly on
the cadence `--steps-per-eval` implies; the CLI just never passes it through.

This script reproduces `lora.py main()`'s setup (model load, LoRA/vision-unfreeze,
optimizer) by importing its own helpers directly rather than re-implementing them,
loads BOTH the `train` and `validation` splits explicitly, and calls `train()` with
the real `val_dataset` wired in. Also applies the Idefics3/SmolVLM2 positional-
argument patch (`_mlx_vlm_idefics3_patch.py`) first, same as `run_lora.py`.

Usage mirrors the subset of `mlx_vlm.lora`'s flags this project actually uses;
see `--help`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mlx_vlm_idefics3_patch  # noqa: F401  (patches Idefics3.__call__ on import)
import mlx.optimizers as optim
from datasets import load_dataset
from mlx_vlm.lora import setup_model_for_training, transform_dataset_to_messages
from mlx_vlm.trainer.datasets import VisionDataset
from mlx_vlm.trainer.sft_trainer import TrainingArgs, train
from mlx_vlm.trainer.utils import print_trainable_parameters
from mlx_vlm.utils import load


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-path", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--train-vision", action="store_true")
    ap.add_argument("--iters", type=int, required=True)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--gradient-accumulation-steps", type=int, default=1)
    ap.add_argument("--learning-rate", type=float, default=1e-4)
    ap.add_argument("--grad-clip", type=float, default=None)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--lora-alpha", type=float, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.0)
    ap.add_argument("--steps-per-report", type=int, default=10)
    ap.add_argument("--steps-per-eval", type=int, default=100)
    ap.add_argument("--steps-per-save", type=int, default=100)
    ap.add_argument("--val-batches", type=int, default=-1)  # -1 == the whole val split
    ap.add_argument("--max-seq-length", type=int, default=2048)
    ap.add_argument("--output-path", required=True)
    ap.add_argument("--full-finetune", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    output_path = (
        args.output_path
        if args.output_path.endswith(".safetensors")
        else args.output_path + "/adapters.safetensors"
    )

    print(f"Loading model from {args.model_path}")
    model, processor = load(args.model_path, processor_config={"trust_remote_code": True})
    model_type = model.config.model_type
    config = model.config.__dict__

    print(f"Loading dataset from {args.dataset}")

    def prep(split: str) -> VisionDataset:
        raw = load_dataset(args.dataset, split=split)
        raw = transform_dataset_to_messages(raw, model_type)
        return VisionDataset(raw, config, processor)

    train_dataset = prep("train")
    val_dataset = prep("validation")
    print(f"{len(train_dataset)} train / {len(val_dataset)} val examples")

    # setup_model_for_training reads args.full_finetune / args.train_vision /
    # args.lora_rank / args.lora_alpha / args.lora_dropout / an (absent) adapter_path
    # off the namespace directly -- this argparse.Namespace already matches that shape.
    model = setup_model_for_training(model, args, adapter_path=None)
    print_trainable_parameters(model)

    optimizer = optim.Adam(learning_rate=args.learning_rate)

    training_args = TrainingArgs(
        batch_size=args.batch_size,
        iters=args.iters,
        steps_per_report=args.steps_per_report,
        steps_per_eval=args.steps_per_eval,
        steps_per_save=args.steps_per_save,
        val_batches=args.val_batches,
        max_seq_length=args.max_seq_length,
        adapter_file=output_path,
        grad_checkpoint=False,
        learning_rate=args.learning_rate,
        grad_clip=args.grad_clip,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        full_finetune=args.full_finetune,
    )
    print(f"Training model (sft), {args.iters} iterations, eval every {args.steps_per_eval}")
    train(
        model=model,
        optimizer=optimizer,
        train_dataset=train_dataset,
        val_dataset=val_dataset,  # the actual fix: lora.py's CLI hardcodes this to None
        args=training_args,
    )


if __name__ == "__main__":
    main()
