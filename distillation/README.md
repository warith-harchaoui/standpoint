# Distilling Standpoint's local VLM to a 500M engine

Status: **Phase 0 (feasibility spike) passed.** Working on Phase 1 (dataset
generation). Not yet usable — the current production engine (resolved via
`best-engine-ai-helper`, per `standpoint/llm.brief.yaml`) remains the default and
the only supported path until this produces real evaluation numbers (Phase 3).

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

## Layout

```
distillation/
  README.md                 # this file
  requirements.txt
  scripts/
    _mlx_vlm_idefics3_patch.py  # upstream trainer bug workaround (see above)
    run_lora.py                 # mlx_vlm.lora, with the patch applied first
    01_generate_tables.py       # Phase 1a (next)
    02_generate_dataset.py      # Phase 1b
    03_train_lora.py            # Phase 2
    04_evaluate.py              # Phase 3
    05_export_gguf.py           # Phase 4a
    06_export_mlx.py            # Phase 4b
  data/                      # generated datasets (gitignored; regenerable)
  checkpoints/               # LoRA adapters + merged/converted models (gitignored)
```

## Full plan

See the plan this branch executes: phases, per-task risk assessment, and the export
architecture (GGUF for Windows/Ubuntu/Mac-via-llama.cpp, native MLX for Mac-native
speed via Ollama's dual backend) are recorded in this session's plan file and
summarized progressively in this README as each phase completes.
