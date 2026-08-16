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

**LR warmup is real here, unlike upstream**: `sft_trainer.TrainingArgs` declares
`warmup_steps`/`min_learning_rate` fields, but grepping the whole trainer module
shows nothing ever reads them back -- `optim.Adam(learning_rate=args.learning_rate)`
runs at that flat value from optimizer-update 1. Combined with `grad_clip` being
per-element `mx.clip(g, -c, c)` (not a global gradient-norm clip -- see
`sft_trainer.step()`), a NaN produced by one unlucky early step survives that clip
untouched and permanently poisons Adam's `m`/`v` moving averages, which is
consistent with a retrain that ran clean through iter 200 then went to NaN from
iter 210 on and stayed there. `--warmup-steps` below builds a real ramp via
`mlx.optimizers.linear_schedule(0, lr, warmup_steps)` passed directly as the
optimizer's `learning_rate` (mlx schedules are plain callables the optimizer steps
once per `optimizer.update()` call, i.e. once per grad-accumulated step, not once
per raw iter) -- it does not fix the weak elementwise clip, but keeps the
optimizer's adaptive moment estimates small while the model is least stable.

**A NaN/Inf guard wraps `optimizer.update()` below, applied after warmup was
already validated and still not sufficient**: a full French-track retrain (LR
1e-5, warmup 100, both already validated over a 500-iteration smoke test) ran
epoch 1 (iters 1-940) clean -- val loss 6.5 -> 4.3 -- then went to NaN at iter
950, ten iterations into epoch 2. Root cause: `sft_trainer.iterate_batches`
reshuffles with an *unseeded* `np.random.permutation` at every epoch boundary
(confirmed by reading the installed package), so a smoke test shorter than one
epoch structurally cannot catch an epoch-2-only bad shuffle, and the ordering
that broke it is not reproducible run to run. Rather than chase a specific LR
low enough to survive every possible shuffle, `optimizer.update` is wrapped to
check every gradient array for NaN/Inf right before the real update would run
and skip that one optimizer step (leaving weights and Adam's `m`/`v` moving
averages untouched) if any is found, instead of applying it and poisoning the
optimizer state for the rest of the run -- a single dropped step out of
thousands is a non-event; a permanently NaN adapter is not.

Usage mirrors the subset of `mlx_vlm.lora`'s flags this project actually uses;
see `--help`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mlx_vlm_idefics3_patch  # noqa: F401  (patches Idefics3.__call__ on import)
import mlx.core as mx
import mlx.optimizers as optim
from datasets import load_dataset
from mlx.utils import tree_flatten
from mlx_vlm.lora import setup_model_for_training, transform_dataset_to_messages
from mlx_vlm.trainer.datasets import VisionDataset
from mlx_vlm.trainer.sft_trainer import TrainingArgs, train
from mlx_vlm.trainer.utils import print_trainable_parameters
from mlx_vlm.utils import load


def _guard_against_nan_updates(optimizer: optim.Optimizer) -> None:
    """Skip (not crash, not silently poison) any optimizer step with a non-finite
    gradient -- see module docstring's NaN/Inf guard section for why this exists.
    """
    real_update = optimizer.update
    skipped = 0

    def guarded_update(model, gradients: dict) -> None:
        nonlocal skipped
        is_finite = all(
            bool(mx.all(mx.isfinite(g))) for _, g in tree_flatten(gradients)
        )
        if not is_finite:
            skipped += 1
            print(
                f"WARNING: non-finite gradient at optimizer step "
                f"{optimizer.state.get('step', '?')}, skipping this update "
                f"({skipped} skipped so far)",
                file=sys.stderr,
            )
            return
        real_update(model, gradients)

    optimizer.update = guarded_update


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-path", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--train-vision", action="store_true")
    ap.add_argument("--iters", type=int, required=True)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--gradient-accumulation-steps", type=int, default=1)
    ap.add_argument("--learning-rate", type=float, default=1e-4)
    ap.add_argument(
        "--warmup-steps",
        type=int,
        default=0,
        help="Linear LR ramp from 0 to --learning-rate over this many optimizer "
        "updates (not raw iters -- see module docstring). 0 disables warmup.",
    )
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

    # linear_schedule holds at `end` for every step past `steps` (see mlx docs), so
    # this doubles as "warmup then flat" with no separate decay schedule needed.
    lr = (
        optim.linear_schedule(0.0, args.learning_rate, args.warmup_steps)
        if args.warmup_steps > 0
        else args.learning_rate
    )
    optimizer = optim.Adam(learning_rate=lr)
    _guard_against_nan_updates(optimizer)  # see module docstring's NaN/Inf guard section

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
