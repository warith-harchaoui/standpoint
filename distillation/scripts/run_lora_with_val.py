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

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mlx_vlm_idefics3_patch  # noqa: F401  (patches Idefics3.__call__ on import)
import click
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
        is_finite = all(bool(mx.all(mx.isfinite(g))) for _, g in tree_flatten(gradients))
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


# --model-path / --dataset / --output-path stay plain strings rather than
# click.Path: argparse typed none of them, and `output_path` in particular is
# string-concatenated below ("/adapters.safetensors") and handed to
# `load_dataset`, which accepts a dataset name as readily as a directory.
@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--model-path", required=True, help="Base MLX vision model to fine-tune.")
@click.option("--dataset", required=True, help="Dataset with train/validation splits.")
@click.option("--train-vision", is_flag=True, help="Unfreeze the vision stack too.")
@click.option("--iters", type=int, required=True, help="Raw training iterations.")
@click.option("--batch-size", type=int, default=1, show_default=True, help="Examples per batch.")
@click.option(
    "--gradient-accumulation-steps",
    type=int,
    default=1,
    show_default=True,
    help="Batches accumulated per optimizer update.",
)
@click.option(
    "--learning-rate", type=float, default=1e-4, show_default=True, help="Adam learning rate."
)
@click.option(
    "--warmup-steps",
    type=int,
    default=0,
    show_default=True,
    help="Linear LR ramp from 0 to --learning-rate over this many optimizer "
    "updates (not raw iters -- see module docstring). 0 disables warmup.",
)
@click.option(
    "--grad-clip",
    type=float,
    default=None,
    help="Per-element gradient clip; omitted clips nothing.",
)
@click.option("--lora-rank", type=int, default=16, show_default=True, help="LoRA rank.")
@click.option("--lora-alpha", type=float, default=32, show_default=True, help="LoRA alpha.")
@click.option("--lora-dropout", type=float, default=0.0, show_default=True, help="LoRA dropout.")
@click.option(
    "--steps-per-report", type=int, default=10, show_default=True, help="Iterations between logs."
)
@click.option(
    "--steps-per-eval", type=int, default=100, show_default=True, help="Iterations between evals."
)
@click.option(
    "--steps-per-save",
    type=int,
    default=100,
    show_default=True,
    help="Iterations between checkpoints.",
)
# The -1 default is kept so existing argv keeps working, but the help no longer
# repeats the comment that used to sit here ("-1 == the whole val split"): it is
# wrong. `sft_trainer.evaluate` turns num_batches=-1 into `iter(int, 1)` and zips
# it with the equally infinite `iterate_batches`, so -1 hangs rather than reading
# the split once -- distillation/README.md, finding 5. Callers therefore pass the
# real batch count, and --help now says so instead of repeating the mistake.
@click.option(
    "--val-batches",
    type=int,
    default=-1,
    show_default=True,
    help="Validation batches per eval. Pass the real count: -1 does NOT mean "
    "the whole split, it makes mlx_vlm's evaluate() loop forever.",
)
@click.option(
    "--max-seq-length", type=int, default=2048, show_default=True, help="Token cap per example."
)
@click.option(
    "--output-path",
    required=True,
    help="Adapter directory, or a .safetensors file to write directly.",
)
@click.option("--full-finetune", is_flag=True, help="Train full weights instead of LoRA.")
def main(
    model_path: str,
    dataset: str,
    train_vision: bool,
    iters: int,
    batch_size: int,
    gradient_accumulation_steps: int,
    learning_rate: float,
    warmup_steps: int,
    grad_clip: float | None,
    lora_rank: int,
    lora_alpha: float,
    lora_dropout: float,
    steps_per_report: int,
    steps_per_eval: int,
    steps_per_save: int,
    val_batches: int,
    max_seq_length: int,
    output_path: str,
    full_finetune: bool,
) -> None:
    """LoRA-train an MLX vision model with a real validation split wired in.

    \f

    Everything past the form feed is for readers of the source: click renders a
    command's whole docstring in ``--help`` and stops at ``\\f``, so without it
    the Numpy-style block CODING.md Rule 1 asks for would reach the terminal as
    one reflowed paragraph.

    Parameters
    ----------
    model_path : str
        Base MLX vision model, loaded with ``trust_remote_code``.
    dataset : str
        Anything `datasets.load_dataset` accepts, carrying ``train`` and
        ``validation`` splits -- both are loaded, which is the whole point of
        this script.
    train_vision, full_finetune : bool
        Passed through to `setup_model_for_training` (unfreeze the vision stack;
        train full weights rather than LoRA).
    iters, batch_size, gradient_accumulation_steps, max_seq_length : int
        Training schedule and memory envelope.
    learning_rate : float
        Adam learning rate, also the top of the warmup ramp.
    warmup_steps : int
        Length of the linear LR ramp, counted in optimizer updates rather than
        raw iterations -- see the module docstring.
    grad_clip : float, optional
        Per-element clip handed to `mlx_vlm`'s trainer; None clips nothing.
    lora_rank, lora_alpha, lora_dropout : int or float
        LoRA geometry, read off the namespace by `setup_model_for_training`.
    steps_per_report, steps_per_eval, steps_per_save : int
        Reporting, validation and checkpoint cadence.
    val_batches : int
        Validation batches per eval. The -1 default is mlx_vlm's own and hangs
        (see the comment above the flag); pass the real count instead.
    output_path : str
        Adapter directory, or a ``.safetensors`` path written as given.
    """
    adapter_file = (
        output_path
        if output_path.endswith(".safetensors")
        else output_path + "/adapters.safetensors"
    )

    print(f"Loading model from {model_path}")
    model, processor = load(model_path, processor_config={"trust_remote_code": True})
    model_type = model.config.model_type
    config = model.config.__dict__

    print(f"Loading dataset from {dataset}")

    def prep(split: str) -> VisionDataset:
        raw = load_dataset(dataset, split=split)
        raw = transform_dataset_to_messages(raw, model_type)
        return VisionDataset(raw, config, processor)

    train_dataset = prep("train")
    val_dataset = prep("validation")
    print(f"{len(train_dataset)} train / {len(val_dataset)} val examples")

    # setup_model_for_training reads full_finetune / train_vision / lora_rank /
    # lora_alpha / lora_dropout off an object's ATTRIBUTES (it was written for
    # mlx_vlm's own argparse.Namespace), so click's keyword arguments have to be
    # re-wrapped into one. Exactly those five names and no more: anything it
    # stopped reading would then be dead weight here, and anything it starts
    # reading will raise rather than silently take a default.
    model = setup_model_for_training(
        model,
        SimpleNamespace(
            full_finetune=full_finetune,
            train_vision=train_vision,
            lora_rank=lora_rank,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
        ),
        adapter_path=None,
    )
    print_trainable_parameters(model)

    # linear_schedule holds at `end` for every step past `steps` (see mlx docs), so
    # this doubles as "warmup then flat" with no separate decay schedule needed.
    lr = (
        optim.linear_schedule(0.0, learning_rate, warmup_steps)
        if warmup_steps > 0
        else learning_rate
    )
    optimizer = optim.Adam(learning_rate=lr)
    _guard_against_nan_updates(optimizer)  # see module docstring's NaN/Inf guard section

    training_args = TrainingArgs(
        batch_size=batch_size,
        iters=iters,
        steps_per_report=steps_per_report,
        steps_per_eval=steps_per_eval,
        steps_per_save=steps_per_save,
        val_batches=val_batches,
        max_seq_length=max_seq_length,
        adapter_file=adapter_file,
        grad_checkpoint=False,
        learning_rate=learning_rate,
        grad_clip=grad_clip,
        gradient_accumulation_steps=gradient_accumulation_steps,
        full_finetune=full_finetune,
    )
    print(f"Training model (sft), {iters} iterations, eval every {steps_per_eval}")
    train(
        model=model,
        optimizer=optimizer,
        train_dataset=train_dataset,
        val_dataset=val_dataset,  # the actual fix: lora.py's CLI hardcodes this to None
        args=training_args,
    )


if __name__ == "__main__":
    main()
