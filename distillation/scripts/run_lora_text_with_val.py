"""Text-only LoRA training with a real validation split, prompt masking, warmup,
global-norm gradient clipping and a NaN/Inf guard.

The text-track counterpart of `run_lora_with_val.py`. That script exists because
`mlx_vlm.lora`'s CLI hardcodes `val_dataset=None`; `mlx_lm.lora`'s CLI does not
have that bug, so the reason this script exists is different -- it is the three
things `mlx_lm`'s CLI has no flag for, each of which this project already learned
the hard way on the vision track:

1. **Gradient clipping.** `mlx_lm.tuner.trainer.TrainingArgs` has no `grad_clip`
   field at all (confirmed by reading the installed dataclass), so an outlier
   batch's gradient reaches Adam at full size. The clip applied below is a
   *global-norm* clip (`mlx.optimizers.clip_grad_norm`), deliberately not the
   per-element `mx.clip(g, -c, c)` that `mlx_vlm`'s trainer uses: an elementwise
   clamp rescales no direction, it just flattens the largest components, and
   `run_lora_with_val.py`'s docstring records it failing to stop a NaN cascade.
2. **A NaN/Inf guard.** Same wrapper, same reasoning as the vision track: a
   single non-finite gradient applied once poisons Adam's `m`/`v` moving
   averages for the rest of the run, and `iterate_batches` reshuffles with an
   unseeded permutation at every epoch boundary, so the bad ordering that
   triggers it is not reproducible run to run. Skipping one optimizer step out
   of thousands is a non-event; a permanently NaN adapter is not.
3. **LR warmup**, built here from `--warmup-steps` via
   `mlx.optimizers.linear_schedule` and passed as the optimizer's
   `learning_rate` (mlx schedules are plain callables the optimizer advances
   once per `optimizer.update()`, i.e. once per accumulated step, not once per
   raw iteration). `mlx_lm`'s CLI can express this only through a `--config`
   YAML's `lr_schedule` block; a flag is less to get wrong from a subprocess.

**Prompt masking is on by default** (`mask_prompt`), unlike the vision track,
which trains on the whole sequence because `mlx_vlm` offers no alternative. Every
task here has a long fixed instruction and a short schema-constrained answer, so
without masking most of the loss would be spent re-learning to recite prompts the
model is never asked to produce.

Checkpoint snapshots land as `{iter:07d}_adapters.safetensors` next to
`adapters.safetensors`, and validation prints `Iter N: Val loss X.XXX, Val took
...` -- byte-identical conventions to `mlx_vlm`'s trainer, so
`select_best_checkpoint.py` reads this script's logs unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten, tree_map
from mlx_lm.tuner.datasets import CacheDataset, CompletionsDataset
from mlx_lm.tuner.trainer import TrainingArgs, train
from mlx_lm.tuner.utils import linear_to_lora_layers, print_trainable_parameters
from mlx_lm.utils import load


def _wrap_optimizer(optimizer: optim.Optimizer, max_norm: float | None) -> None:
    """Clip by global norm, then neutralise any step whose gradients are non-finite.

    Both guards live in one wrapper around `optimizer.update` because both have
    to run between the trainer computing gradients and Adam consuming them, and
    `mlx_lm`'s trainer exposes no hook in between -- see the module docstring for
    why each is needed.

    **Everything here stays lazy.** `mlx_lm`'s `step` is wrapped in `mx.compile`,
    so `optimizer.update` runs inside a traced function: reading a value on the
    host (`bool(mx.all(...))`, the way the vision track's guard does it) raises
    "Attempting to eval an array during function transformations". The check is
    therefore expressed as graph operations -- one `mx.where` that swaps the
    whole gradient tree for zeros when any element is non-finite. Adam then takes
    a zero-gradient step, decaying its moments instead of being poisoned by a
    NaN, which is the outcome that mattered. The cost of staying inside the
    compile is that a neutralised step cannot announce itself; a run that hits
    them shows up as a flat stretch in the reported training loss, and
    `select_best_checkpoint.py` already ignores `nan` validation losses.

    Parameters
    ----------
    optimizer
        The optimizer whose `update` is replaced in place.
    max_norm
        Global gradient-norm ceiling, or None to clip nothing.
    """
    real_update = optimizer.update

    def guarded_update(model: nn.Module, gradients: dict) -> None:
        if max_norm is not None:
            gradients, _ = optim.clip_grad_norm(gradients, max_norm)
        # Checked AFTER clipping: clip_grad_norm divides by the norm, so a
        # non-finite norm turns the whole tree non-finite -- testing first would
        # miss a NaN the rescale itself introduced.
        finite = mx.array(True)
        for _, g in tree_flatten(gradients):
            finite = mx.logical_and(finite, mx.all(mx.isfinite(g)))
        gradients = tree_map(lambda g: mx.where(finite, g, mx.zeros_like(g)), gradients)
        real_update(model, gradients)

    optimizer.update = guarded_update


def load_split(dataset_dir: Path, split: str, tokenizer) -> CompletionsDataset:
    """Read one JSONL split into the prompt/completion dataset the trainer wants.

    The corpus already stores `question`/`answer` per row (plus `task`/`lang`
    labels the trainer ignores and `04_evaluate.py` reads back), so the keys are
    passed through as-is rather than rewriting every file into OpenAI's
    `prompt`/`completion` naming.
    """
    path = dataset_dir / f"{split}.jsonl"
    if not path.exists():
        raise SystemExit(f"{path} missing; run 03_train_lora.py first.")
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return CompletionsDataset(
        rows, tokenizer, prompt_key="question", completion_key="answer", mask_prompt=True
    )


# --model-path / --dataset / --output-path stay plain strings rather than
# click.Path, because argparse typed none of them and both directories are
# wrapped in `Path(...)` where they are used; adding `exists=True` here would
# also reject the output directory on a first run, which has to be created.
@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--model-path", required=True, help="Base MLX text model to fine-tune.")
@click.option("--dataset", required=True, help="Directory holding train/validation.jsonl.")
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
    "--learning-rate", type=float, default=1e-5, show_default=True, help="Adam learning rate."
)
@click.option(
    "--warmup-steps",
    type=int,
    default=0,
    show_default=True,
    help="Linear LR ramp over this many optimizer updates (not raw iters); 0 disables.",
)
@click.option(
    "--grad-clip",
    type=float,
    default=None,
    help="Global gradient-norm ceiling; omitted clips nothing.",
)
@click.option("--lora-rank", type=int, default=16, show_default=True, help="LoRA rank.")
@click.option("--lora-scale", type=float, default=20.0, show_default=True, help="LoRA scale.")
@click.option("--lora-dropout", type=float, default=0.0, show_default=True, help="LoRA dropout.")
@click.option(
    "--lora-layers",
    type=int,
    default=-1,
    show_default=True,
    help="Apply LoRA to the last N transformer blocks; -1 means all of them.",
)
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
@click.option(
    "--val-batches", type=int, default=25, show_default=True, help="Validation batches per eval."
)
@click.option(
    "--max-seq-length", type=int, default=2048, show_default=True, help="Token cap per example."
)
@click.option("--seed", type=int, default=42, show_default=True, help="mlx RNG seed.")
@click.option("--output-path", required=True, help="Adapter directory.")
def main(
    model_path: str,
    dataset: str,
    iters: int,
    batch_size: int,
    gradient_accumulation_steps: int,
    learning_rate: float,
    warmup_steps: int,
    grad_clip: float | None,
    lora_rank: int,
    lora_scale: float,
    lora_dropout: float,
    lora_layers: int,
    steps_per_report: int,
    steps_per_eval: int,
    steps_per_save: int,
    val_batches: int,
    max_seq_length: int,
    seed: int,
    output_path: str,
) -> None:
    """LoRA-train an MLX text model with validation, warmup, clipping and a NaN guard.

    \f

    Everything past the form feed is for readers of the source: click renders a
    command's whole docstring in ``--help`` and stops at ``\\f``, so without it
    the Numpy-style block CODING.md Rule 1 asks for would reach the terminal as
    one reflowed paragraph.

    Parameters
    ----------
    model_path : str
        Base MLX text model (`03_train_lora.py` passes the per-language one).
    dataset : str
        Directory holding ``train.jsonl`` and ``validation.jsonl``.
    iters, batch_size, gradient_accumulation_steps, max_seq_length : int
        Training schedule and memory envelope.
    learning_rate : float
        Adam learning rate, also the top of the warmup ramp.
    warmup_steps : int
        Length of the linear LR ramp, counted in optimizer updates rather than
        raw iterations -- see the module docstring.
    grad_clip : float, optional
        Global gradient-norm ceiling; None clips nothing.
    lora_rank, lora_scale, lora_dropout : int or float
        LoRA geometry, recorded in the adapter config as well as applied.
    lora_layers : int
        How many trailing transformer blocks get LoRA; -1 means all of them.
    steps_per_report, steps_per_eval, steps_per_save, val_batches : int
        Reporting, validation and checkpoint cadence.
    seed : int
        mlx RNG seed, so a rerun of the same command trains the same way.
    output_path : str
        Adapter directory; created, and given an ``adapter_config.json``.
    """
    mx.random.seed(seed)

    print(f"Loading model from {model_path}")
    model, tokenizer = load(model_path)

    print(f"Loading dataset from {dataset}")
    dataset_dir = Path(dataset)
    train_dataset = load_split(dataset_dir, "train", tokenizer)
    val_dataset = load_split(dataset_dir, "validation", tokenizer)
    print(f"{len(train_dataset)} train / {len(val_dataset)} val examples")

    model.freeze()
    n_layers = len(model.layers) if lora_layers < 0 else lora_layers
    linear_to_lora_layers(
        model,
        n_layers,
        {"rank": lora_rank, "scale": lora_scale, "dropout": lora_dropout},
    )
    print_trainable_parameters(model)

    # The adapter directory must carry an adapter_config.json next to the
    # weights: that pair is what `mlx_lm.load(..., adapter_path=dir)` and
    # `select_best_checkpoint.py`'s best-adapter copy both expect.
    adapter_dir = Path(output_path)
    adapter_dir.mkdir(parents=True, exist_ok=True)
    adapter_file = adapter_dir / "adapters.safetensors"
    (adapter_dir / "adapter_config.json").write_text(
        json.dumps(
            {
                "fine_tune_type": "lora",
                "num_layers": n_layers,
                "lora_parameters": {
                    "rank": lora_rank,
                    "scale": lora_scale,
                    "dropout": lora_dropout,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # linear_schedule holds at `end` for every step past `steps`, so this is
    # "warm up then stay flat" with no separate decay schedule needed.
    lr = (
        optim.linear_schedule(0.0, learning_rate, warmup_steps)
        if warmup_steps > 0
        else learning_rate
    )
    optimizer = optim.Adam(learning_rate=lr)
    _wrap_optimizer(optimizer, grad_clip)

    training_args = TrainingArgs(
        batch_size=batch_size,
        iters=iters,
        val_batches=val_batches,
        steps_per_report=steps_per_report,
        steps_per_eval=steps_per_eval,
        steps_per_save=steps_per_save,
        max_seq_length=max_seq_length,
        adapter_file=adapter_file,
        grad_checkpoint=False,
        grad_accumulation_steps=gradient_accumulation_steps,
    )
    print(f"Training (sft), {iters} iterations, eval every {steps_per_eval}")
    # CacheDataset is not optional: `iterate_batches` indexes its dataset
    # expecting the *processed* (tokens, offset) tuple, while CompletionsDataset
    # indexes back to the raw row -- mlx_lm's own CLI wraps both splits the same
    # way, and without it the first batch dies on `KeyError: 0`.
    train(
        model=model,
        optimizer=optimizer,
        train_dataset=CacheDataset(train_dataset),
        val_dataset=CacheDataset(val_dataset),
        args=training_args,
    )


if __name__ == "__main__":
    main()
