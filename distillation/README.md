# Distilling Standpoint's local VLM to a 500M engine

Status: **Phase 0, 1, and 2 done (including a full retrain for exact EN/FR
parity). Phase 3 (evaluation) running.** Not yet usable — the current production
engine (resolved via `best-engine-ai-helper`, per `standpoint/llm.brief.yaml`)
remains the default and the only supported path until Phase 3 produces real,
reported numbers.

## Phase 2 findings (2026-08-11 -> 2026-08-12)

Every one of these was confirmed by direct evidence (reading the installed
library's source, or a live crash/log) before being fixed -- not guessed:

1. **Batch-size-2 collation crash**: `mlx_vlm.trainer.sft_trainer.iterate_batches`
   forms batches from *contiguous* dataset slices (its shuffle only reorders which
   batch runs next, never batch composition), and its `pixel_values` collation
   only inspects `items[0]` -- a batch mixing one text-only and one image example
   crashes `mx.stack()`. Fixed in `03_train_lora.py`: the combined dataset is
   grouped into modality-homogeneous contiguous blocks (all-text, then
   all-image) before writing `train.jsonl`/`validation.jsonl`, each block trimmed
   to a multiple of the batch size.
2. **Still crashed within one modality at batch-size 2**: logits came back with
   batch dimension 1 against targets with batch dimension 2 on a text-only batch
   -- something in the SmolLM2/idefics3 layer stack doesn't reliably preserve
   batch size 2 through the forward pass. Sidestepped by dropping to
   `--batch-size 1` with `--gradient-accumulation-steps 2` for the same effective
   optimizer batch size.
3. **Loss went to `nan` by iteration 10-20**, even after adding `--grad-clip 1.0`
   and lowering the learning rate to `3e-5` -- ruling out plain gradient
   explosion. Root cause: the base checkpoint was converted with
   `--dtype float16` (fine for inference, confirmed in Phase 0), but float16's
   narrow dynamic range is a known instability source once you're actually
   *training* (backprop through `--train-vision`'s unfrozen encoder especially).
   Reconverted the base model with `--dtype bfloat16`
   (`checkpoints/smolvlm2-500m-mlx-bf16/`) and loss dropped smoothly from the
   first iteration (3.74 -> 1.52 over 110 steps, no more nan).
4. **`mlx_vlm.lora`'s own CLI hardcodes `val_dataset=None`**, regardless of
   `--val-batches`/`--steps-per-eval` -- confirmed by grepping the installed
   `lora.py`: both its `train()` and `train_orpo()` call sites pass the literal
   `None`. No validation would ever run through it. `run_lora_with_val.py`
   reproduces the CLI's setup (model load, LoRA/vision-unfreeze, optimizer) by
   importing its helpers directly, then calls `mlx_vlm.trainer.sft_trainer.train()`
   with the real `val_dataset` wired in -- this is what `03_train_lora.py`
   actually invokes, not `mlx_vlm.lora` or `run_lora.py` directly.
5. **`--val-batches -1` would hang forever**: `sft_trainer.evaluate()`'s
   `num_batches=-1` path zips two genuinely infinite generators (`tqdm`'s
   `total=` there is display-only, not a real bound) -- confirmed by reading the
   function before running it, not by hitting the hang. Fixed by passing the
   real validation-split length explicitly.
6. **`select_best_checkpoint.py` first copied the winning snapshot to a bare
   `best-adapter.safetensors` file** -- but `mlx_vlm.trainer.utils.
   apply_lora_layers` requires `adapter_path` to be a *directory* containing
   `adapter_config.json` plus a fixed-name `adapters.safetensors` (confirmed by
   reading it directly). Only surfaced when the first Phase 3 attempt crashed
   with `NotADirectoryError` -- meaning the very first "best adapter" selected
   was never actually loadable. Fixed: it now copies into `best-adapter/`
   (snapshot + a copy of `adapter_config.json`), the layout `04_evaluate.py`
   expects.
7. **GEval's judge crashed the first full Phase 3 run at ~109/489 examples**
   on malformed free-text JSON from the local teacher model (`ValueError:
   Evaluation LLM outputted an invalid JSON`) -- a 7B local model asked for
   free-text JSON occasionally gets it wrong, and DeepEval has no retry for
   that. Fixed by implementing `LocalEngineJudge.generate()`'s optional
   `schema` kwarg (DeepEval's `generate_with_schema` forwards it
   automatically): when present, it passes `schema.model_json_schema()` as
   `llm.chat`'s `json_schema=`, so Ollama grammar-constrains the output to the
   exact shape, then parses it straight into the pydantic instance -- no more
   free-text JSON parsing, no more crashes.

At ~1.3-1.9 it/sec (batch 1, grad-accum 2, `--train-vision` on, M2 Max), the
final 11,127-iteration run (3 epochs over 3,709 train examples) took about
7.5 hours -- noticeably slower per-iteration than the first (unbalanced-dataset)
run, likely machine load from hours of concurrent background work rather than
anything about the run itself.

**Phase 1 final numbers** (after the parity pass, see below): 731 tables
generated (560 original + 171 EN->FR translated), 727 successfully processed --
**3,709 train / 655 val examples** after the train/val split. `pole_naming` and
`narrative` are now **exactly EN/FR balanced (349/349 each)**; `noun_forms` was
already balanced by construction (758/758: it always emits one example in the
table's own language and one forced cross-language, per table, regardless of
that table's language); `vlm_assess` has no language dimension (1,452 examples,
positive + deterministic-negative pairs). `data/tables/` and
`data/dataset/.processed` show the real, current counts at any point --
authoritative over any number in this file.

**On the table count**: asked whether 1000 tables was reachable, I measured actual
throughput rather than guess -- combined Phase 1a+1b cost is ~90s/table on this
machine (one Ollama instance, no true parallelism across the concurrent
generation processes), so 1000 fully-processed tables would take ~25 hours, not
one night. Settled on ~500-570 as a target that's both a meaningfully larger
corpus and achievable within an extended run.

## Language-parity pass (2026-08-12)

The original 01/01b/01c/01d subject lists were EN-skewed (357 en vs 217 fr
subjects), which flowed straight through into `pole_naming` (349 en / 208 fr)
and `narrative` (349 en / 178 fr) -- `noun_forms` was unaffected since it always
gets one example in each direction per table regardless of the table's own
language.

Rather than discard the EN-only surplus to force parity, `01e_generate_tables_
translated.py` **translates** 171 EN tables' *title and criteria only* (one
schema-constrained teacher call each) into new FR tables. Option names are left
untouched -- they are real product/brand names (e.g. "MacBook Pro"), which don't
translate, and ratings are copied verbatim: a laptop's real-world battery-life
reputation doesn't change with the language of the label next to it. Since
`02_generate_dataset.py` builds each task's `lang` tag from its source table,
this closed the gap directly, sized to `narrative`'s larger shortfall (171).

Two follow-on effects needed cleanup, both handled by `07_balance_dataset.py`:

- Re-running `02_generate_dataset.py` picked up not just the 171 new FR tables
  but also 32 tables left over from the original run that had failed *after*
  writing their `pole_naming` example but before completing (so they'd never
  been marked processed, and were legitimately eligible for a retry) -- 30 of
  them succeeded this time, leaving 30 exact-duplicate `pole_naming` rows
  (written once as an orphan, once as part of the now-complete table).
  Deduplicated by (lang, question), keeping one.
- Because `pole_naming` and `narrative` are generated together per table,
  closing `narrative`'s larger gap necessarily overshot `pole_naming`'s smaller
  one. Both are trimmed to the exact EN/FR minimum via seeded (42) random
  sampling after dedup.

Result: `pole_naming` and `narrative` both land at exactly 349 EN / 349 FR.
The model was then fully retrained on the rebalanced dataset (see Phase 2
findings above) rather than just re-evaluated on the old one.

### Checkpoint selection, in bounded-likelihood terms

Per-half-epoch validation loss (nats) and the paper's own bounded score
`Q(theta) = 1 - CE(theta)/ln(K)` (K = 49,280, `LIKELIHOOD-en.pdf` Section 5),
across the full retrain:

| iter | epoch | val loss (CE) | Q |
|---|---|---|---|
| 1 | 0.0 | 3.915 | 0.638 |
| 1854 | 0.5 | 0.779 | 0.928 |
| 3708 | 1.0 | 0.700 | 0.935 |
| 5562 | 1.5 | 0.680 | 0.937 |
| **7416** | **2.0** | **0.664** | **0.939 (best)** |
| 9270 | 2.5 | 0.693 | 0.936 |
| 11124 | ~3.0 | 1.017 | 0.906 |
| 11127 | 3.0 | 1.040 | 0.904 |

Q rises smoothly through epoch 2.0, then **drops** over the final epoch --
real overfitting, not noise (three consecutive worsening checkpoints). Shipping
the last checkpoint would mean deliberately using the more-overfit, worse
model just because it came later; `select_best_checkpoint.py` picks iter 7416
(the true minimum validation loss / maximum Q) instead, and that is what's
copied to `checkpoints/distilled-adapter/best-adapter/`.

## Goal

Standpoint's four LLM/VLM jobs (`axis_poles`, `noun_forms`, `analysis_markdown`,
`vlm_assess`) currently run on one local model (typically `qwen2.5vl:7b`). This
explores distilling that behaviour into a single ~500M-parameter model, scoped to
English and French, trained locally (this machine has no CUDA, so no Unsloth —
training runs via Apple's MLX instead).

## Why this directory is separate from `standpoint/`

`mlx`, `mlx-vlm`, `torch`, and `torchvision` are Apple-Silicon-only, multi-GB, and
irrelevant to developing or testing the `standpoint` package itself. They live in
their own venv (`distillation/.venv`, from `distillation/requirements.txt`) and are
never a `standpoint`/`pyproject.toml` dependency, so CI and Linux/Windows
contributors are unaffected.

```bash
python3 -m venv distillation/.venv
source distillation/.venv/bin/activate
pip install -r distillation/requirements.txt
```

## Student model

**SmolVLM2-500M-Video-Instruct** (`HuggingFaceTB/SmolVLM2-500M-Video-Instruct`,
Apache-2.0) — the only real ~500M-parameter vision-capable model available. Gemma
4's smallest variant is E2B (~2B), too big for the stated budget.

## Phase 0 findings (2026-08-10)

- `mlx_vlm.convert` downloads + converts the HF checkpoint to MLX format cleanly
  (needs `torchvision` installed explicitly — SmolVLM's HF image processor requires
  it as a backend; added to `requirements.txt`).
- Text-only and image+text inference both work via `mlx_vlm.generate`
  (~60 tokens/sec, ~1-2 GB peak memory on an M2 Max). Base-model output quality on
  the vision spatial-reasoning question was poor, as expected before any
  fine-tuning — matches this session's earlier assessment that `vlm_assess` is the
  riskiest of the four jobs to distill.
- **Upstream bug found and worked around**: `mlx_vlm.trainer.sft_trainer`'s SFT loss
  function calls every model positionally as
  `model(input_ids, pixel_values, attention_mask, **kwargs)`, but the Idefics3
  architecture (which SmolVLM/SmolVLM2 use) has `cache` as its third positional
  parameter, not `attention_mask` — the mask array lands in the cache slot and
  `create_attention_mask` crashes trying to bool-convert a multi-element array. See
  `scripts/_mlx_vlm_idefics3_patch.py` for the runtime monkeypatch, imported first
  by both `scripts/run_lora.py` (a thin wrapper around `mlx_vlm.lora`'s own CLI,
  kept for quick manual smoke tests) and `scripts/run_lora_with_val.py` (what
  `03_train_lora.py` actually invokes -- see Phase 2 finding #4 below for why the
  CLI itself isn't enough). Confirmed against mlx-vlm 0.6.10; safe to delete once
  fixed upstream.
- With the patch, LoRA training runs cleanly: `#trainable params: 4.34M / 507.48M
  total (0.856%)`, loss decreasing over 6 steps on an 8-example toy set
  (4.62 -> 4.14), ~300 tokens/sec, ~1.5 GB peak memory.

**Go/no-go: GO.** Proceeding with SmolVLM2-500M-Instruct as planned.

## Phase 4 export path -- revised (2026-08-10)

The original plan assumed GGUF export (via llama.cpp's `convert_hf_to_gguf.py`)
would cover Windows/Ubuntu, alongside native MLX for Mac. **That assumption doesn't
hold for this architecture**: a fresh clone of `llama.cpp` (`checkpoints/llama.cpp/`,
gitignored) has zero references to `idefics3` or `smolvlm` anywhere in
`convert_hf_to_gguf.py` -- confirmed directly by grepping the script, not inferred
from search results, since an earlier GitHub discussion suggesting "Idefics3 not
supported" could have been stale. It is not stale. Community GGUF uploads of
SmolVLM2 exist on Ollama's hub, but not via this conversion path as shipped in
`llama.cpp`'s current `master`.

Revised plan for the two targets the user asked for:

- **Mac**: native MLX, unchanged -- served either through Ollama's MLX engine
  (0.30+, if it accepts a locally fine-tuned MLX model, not just its own curated
  library -- to be confirmed once a trained adapter exists) or directly via
  `mlx_vlm.server`, which ships as its own OpenAI-compatible-ish HTTP server.
- **Windows/Ubuntu**: plain `transformers` inference (SmolVLM2 is a native HF
  `transformers` architecture, runs anywhere `torch` does, GPU or CPU) behind a
  small local HTTP shim that speaks Ollama's `/api/chat` request/response shape.
  `best_engine_ai_helper.llm.chat(backend="ollama", base_url=...)` only needs
  something answering at that URL in that shape -- it doesn't care whether the
  process behind it is real Ollama or this shim, so standpoint's existing
  `--model`/`model=` override still works unmodified, just pointed at a different
  `base_url` on non-Mac platforms.

Exact shim design deferred to Phase 4 itself (after training + Phase 3's real
numbers exist) rather than built speculatively now.

## Layout

```
distillation/
  README.md                 # this file
  requirements.txt
  scripts/
    _table_utils.py             # dedupe_ratings(): enforces validate_table()'s own
                                 # no-duplicate-row/-column rule at generation time
    _mlx_vlm_idefics3_patch.py  # upstream trainer bug workaround (see Phase 0)
    run_lora.py                 # mlx_vlm.lora's own CLI + the patch; manual smoke
                                 # tests only -- no validation (see Phase 2 #4)
    run_lora_with_val.py        # what 03_train_lora.py actually invokes: same
                                 # setup, but with a real val_dataset wired in
    01_generate_tables.py            # Phase 1a: 30 hand-curated subjects
    01b_generate_tables_from_web.py  # Phase 1a: 20 subjects, real web-sourced options
    01c_generate_tables_more.py      # Phase 1a: 245 more curated subjects (scale-up)
    01d_generate_tables_final.py     # Phase 1a: last subjects, ~500 tables total
    01e_generate_tables_translated.py  # Phase 1a (parity pass): 171 EN tables'
                                        # title+criteria translated to FR
    02_generate_dataset.py      # Phase 1b (resumable: data/dataset/.processed)
    03_train_lora.py            # Phase 2: combine + split + launch training
    07_balance_dataset.py       # Phase 1c: dedupe + trim pole_naming/narrative
                                 # to exact EN/FR parity (run once, before 03)
    select_best_checkpoint.py   # picks the half-epoch snapshot with the lowest
                                 # validation loss, not just the last one
    merge_shards.py             # merges 02_generate_dataset.py --shard-id output
    extract_loss_curve.py       # training log -> data/training_loss.csv
    make_loss_figure.py         # CSV -> data/training_loss.svg (pure hand-authored
                                 # SVG; see that script's own docstring for why)
    04_evaluate.py               # Phase 3: distilled vs teacher, per task/language
  data/                      # generated datasets (gitignored; regenerable)
  checkpoints/               # LoRA adapters + merged/converted models (gitignored)
```

## Full plan

See the plan this branch executes: phases, per-task risk assessment, and the
(revised) export architecture are recorded in this session's plan file and
summarized progressively in this README as each phase completes.
