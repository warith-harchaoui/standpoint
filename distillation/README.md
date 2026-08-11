# Distilling Standpoint's local VLM to a 500M engine

Status: **Phase 0 and Phase 1 (dataset generation) done.** Working on Phase 2
(LoRA training). Not yet usable — the current production engine (resolved via
`best-engine-ai-helper`, per `standpoint/llm.brief.yaml`) remains the default and
the only supported path until this produces real evaluation numbers (Phase 3).

**Phase 1 final numbers**: 560 tables generated, 528 (94%) successfully processed
into training examples -- **3,252 examples total**: 557 pole_naming, 1,114
noun_forms, 527 narrative, 1,054 vlm_assess (positive + deterministic-negative
pairs). Phase 1b's remaining ~440 tables were processed via 5 parallel shards
(`--shard-id`/`--num-shards`, `merge_shards.py`) after empirically measuring this
machine's actual Ollama concurrency (~1.5x from 5 concurrent requests, not 5x --
compute-bound, not embarrassingly parallel) rather than assuming a speedup.

**On the table count**: asked whether 1000 tables was reachable, I measured actual
throughput rather than guess -- combined Phase 1a+1b cost is ~90s/table on this
machine (one Ollama instance, no true parallelism across the concurrent
generation processes), so 1000 fully-processed tables would take ~25 hours, not
one night. Settled on ~500-570 as a target that's both a meaningfully larger
corpus and achievable within an extended run. `data/tables/` and
`data/dataset/.processed` show the real, current counts at any point --
authoritative over any number in this file.

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
  `scripts/_mlx_vlm_idefics3_patch.py` for the runtime monkeypatch (imported first
  by `scripts/run_lora.py`, which should be used instead of calling
  `python -m mlx_vlm.lora` directly for anything Idefics3/SmolVLM-based). Confirmed
  against mlx-vlm 0.6.10; safe to delete once fixed upstream.
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
    _mlx_vlm_idefics3_patch.py  # upstream trainer bug workaround (see above)
    run_lora.py                 # mlx_vlm.lora, with the patch applied first
    01_generate_tables.py       # Phase 1a: 30 hand-curated subjects
    01b_generate_tables_from_web.py  # Phase 1a: 20 subjects, real web-sourced options
    01c_generate_tables_more.py      # Phase 1a: 245 more curated subjects (scale-up)
    02_generate_dataset.py      # Phase 1b (resumable: data/dataset/.processed)
    03_train_lora.py            # Phase 2
    04_evaluate.py              # Phase 3
    05_export.py                # Phase 4 (design pending Phase 3's numbers, see above)
  data/                      # generated datasets (gitignored; regenerable)
  checkpoints/               # LoRA adapters + merged/converted models (gitignored)
```

## Full plan

See the plan this branch executes: phases, per-task risk assessment, and the
(revised) export architecture are recorded in this session's plan file and
summarized progressively in this README as each phase completes.
