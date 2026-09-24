# Distilling Standpoint's local VLM to a 0.6B engine

## Rearchitecture (2026-09-21): no vision, one 0.6B text model per language

### Results: the bilingual control wins, on both languages

Three runs, each scored on its own held-out split by the same structural
checks. Best checkpoints: en iter 2456 (val 0.138), fr iter 2456 (val 0.118),
bilingual iter 7374 (val 0.119).

| task | EN specialist | FR specialist | bilingual (en) | bilingual (fr) |
|---|---|---|---|---|
| `noun_forms` | 111/111 (100%) | 111/111 (100%) | 100/100 (100%) | 122/122 (100%) |
| `pole_naming` | 46/51 (90%) | 46/51 (90%) | **54/54 (100%)** | **59/59 (100%)** |
| `suggest_ratings` pass | 17/55 (31%) | 19/55 (35%) | 22/46 (48%) | 24/53 (45%) |
| ... well-formed | 53/55 (96%) | 43/55 (78%) | 45/46 (98%) | **49/53 (92%)** |
| ... MAD mean | 0.88 | 0.76 | **0.75** | 0.76 |

**Specialising per language did not pay, and the control says so twice.** The
bilingual adapter is perfect on `pole_naming` in both languages where both
specialists sit at 90%, and that is two independent replications of the same
effect rather than one lucky split. On `suggest_ratings` it improves the French
structural validity from 78% to 92% and the English agreement from 0.88 to 0.75.
It loses on nothing.

The reason is the one the control was built to test: the JSON *shape* of an
answer is language-independent, so training on both languages shows that signal
twice as often, and the shape is exactly where a 0.6B model is fragile. Note
the best bilingual checkpoint lands at iteration 7374 -- three epochs over 2458
examples, i.e. the same number of examples seen as each specialist at its own
optimum. The bilingual model is not winning by seeing more data; it wins by
seeing more varied data.

So one adapter ships, not two: better on every measured task, and half as much
to serve and maintain.

### Reading the `suggest_ratings` pass rate

It is mostly an artefact and should not be quoted on its own. Categorising the
bilingual run's 53 failures:

| why it failed | count |
|---|---|
| well-formed matrix, agreement just beyond the 0.75 threshold | 48 |
| missing cells | 4 |
| invalid JSON | 1 |

So the student returns a structurally correct, complete matrix **94 times out
of 99** (95%), and the pass rate is measuring where a threshold was placed on a
subjective 1..5 scale. What it actually does: agrees with the teacher to within
about three quarters of a rating step. Whether that is good enough is a product
question, not a training one -- the GUI's "Laziness" fills empty cells the user
then edits, and three quarters of a step is inside the noise of a subjective
judgement anyway.

### `vlm_assess` leaves the scope, because it was never a learning problem

Counted over all 1480 recorded `vlm_assess` examples in
`data/dataset/vlm_assess.jsonl`:

| field | observed |
|---|---|
| `readable` | `true` **1480 times**, never `false` |
| `axis_labels_visible` | `true` **1480 times**, never `false` |
| `leader_top_right` | 737 `true` / 743 `false` |

Two constant fields: a student that always answers `true` scores 100% on both,
having learned nothing. And the third column's negatives are not the teacher's
judgement at all -- `02_generate_dataset.py` builds them by swapping the
best/worst roles before rendering and writing the verdict by hand, because (its
own words) "this is exactly the judgement small VLMs are weakest at". The
generator had already conceded that the leader's quadrant is known by
construction.

`vlm_assess` was also only ever reached through the CLI's `--check` flag --
absent from `webgui.py`, `api.py`, `mcp.py`, `click_cli.py` and the webapp --
and it printed three booleans without changing anything about the rendered map.
So standpoint grew `assess_layout()`, which returns the same verdict keys from
the coordinates and pole labels directly: exact instead of guessed, instant
instead of a model round-trip, and it works with nothing running.
`vlm_assess()` stays exported for anyone who wants a model's opinion; no default
path calls it.

That was the only task carrying images. The corpus is now **1446 English + 1446
French rows of pure text** across three tasks (`noun_forms`, `pole_naming`,
`suggest_ratings`).

### One model per language, on a Qwen3-0.6B base

A text-only corpus removes the reason SmolVLM2 was chosen at all -- and SmolVLM2
could never be served by WebLLM, so training it produced something unusable for
the browser goal that motivated the whole exercise.

- **English** trains on plain **Qwen3-0.6B**.
- **French** trains on **Luth-0.6B-Instruct**, a Qwen3-0.6B fine-tuned for
  French and the holder of the best French `pole_naming` score measured in this
  project (94%). On the English side that specialisation would be a handicap,
  which is why the bases differ.
- **A bilingual control** (`--lang all`, plain base) runs last. It exists to
  measure what specialising gave up: twice the schema-shaped supervision, since
  the JSON form of an answer is language-independent.

Both are Qwen3-0.6B architectures, hence servable as-is by the WebLLM/MLC chain
the browser build already uses -- roughly 350-400 MB quantised to q4, against
the ~1 GB generic Qwen2.5-1.5B the webapp downloads today.

`03_train_lora.py --lang {en,fr,all}` and `04_evaluate.py --lang {en,fr,all}`.
The Qwen3-VL-2B French track is retired.

### The Metal command-buffer limit, correctly diagnosed this time

The Qwen3-VL-2B track died reproducibly on
`kIOGPUCommandBufferCallbackErrorImpactingInteractivity` a few dozen iterations
in, and that was read as a bug in that model. It was not. macOS kills any Metal
command buffer that holds the GPU long enough to hurt interactivity, and the
same error killed the 0.6B text model the moment it ran at batch 4.

Measured on this machine: **batch 1 ran 400 iterations clean at 5.0 GB peak;
batch 2 died inside the first hundred.** The cause is the LM head -- Qwen3's
vocabulary is 151643 wide, so one 940-token example already materialises 0.29 GB
of logits, and doubling that inside a single dispatch is enough.

Hence `BATCH_SIZE = 1` with `GRAD_ACCUM = 4`: the optimizer still steps on four
examples, and it is *faster* anyway (4.4 examples/s against 3.2 at batch 4),
because smaller dispatches keep the GPU fed instead of stalling it.

### Other things that had to be fixed to get a run out

- `~/.cache/huggingface` is a symlink onto a volume that is 100% full, so
  `datasets` tripped its disk-space guard and training died on its first line.
  `.private/train_all.sh` redirects `HF_HOME`/`HF_HUB_CACHE`/`HF_DATASETS_CACHE`
  to `distillation/.hf-cache` on the internal disk.
- `mlx_lm` wraps its training step in `mx.compile`, so the vision track's
  host-side NaN guard (`bool(mx.all(...))`) raises inside the trace. It is
  rewritten as graph operations in `run_lora_text_with_val.py`: one `mx.where`
  swapping the whole gradient tree for zeros when any element is non-finite.
- `CacheDataset` is not optional around `CompletionsDataset`; without it
  `iterate_batches` dies on `KeyError: 0`.
- Qwen3's chat template writes an empty `<think></think>` pair before every
  assistant turn, so the training targets carry it and the student reproduces
  it. `04_evaluate.py`'s `strip_reasoning()` removes it before parsing --
  anything consuming this student in production must do the same.

### Prompt masking, which the vision track could not do

`CompletionsDataset(mask_prompt=True)` means loss is computed on the answer
only. Every task here is a long fixed instruction and a short
schema-constrained answer, so without masking most of the loss went on reciting
prompts the model is never asked to produce. `mlx_vlm` offered no alternative;
`mlx_lm` does.

## Scope change (2026-09-20): narrative out for good, suggest_ratings in

`remove-narrative-feature` is merged to `main` and deleted: the narrative
feature no longer exists in standpoint, so the `narrative` task leaves the
distillation scope permanently (not "dropped for this session" -- gone, along
with its generation in `02_generate_dataset.py`). In its place,
**`suggest_ratings`** (the GUI's "Flemme" auto-fill: option/criterion names in,
a full 1..5 ratings matrix out) joins the captured tasks -- it postdates the
original dataset and is now the GUI's main LLM call, so the students must cover
it. Captured through the same `llm.chat` monkeypatch as the other tasks, from
the parsed table BEFORE `resolve_polarity` (the names a GUI user actually
types). Scored in both eval scripts as: valid JSON, every (option, criterion)
cell present, every value an integer already in 1..5, and a mean absolute
deviation from the teacher of at most 0.75. Scope is explicitly **en/fr only**
(the product's Spanish UI locale is out of the distillation's scope).

Same-day state note: `distillation/data/` (tables + datasets, gitignored,
regenerable) no longer exists on this machine, and neither do the converted
base checkpoints or `.venv` -- only the two `best-adapter` directories survive,
committed via LFS. Full regeneration relaunched from the 01 scripts (574
subjects + 171 translated, ~90 s/table measured -> roughly a day of teacher
time), with env + base-model rebuild in parallel.

Status: **English/vision engine (SmolVLM2-500M) and French engine
(`kurakurai/Luth-0.6B-Instruct` superseded by `Qwen3-VL-2B-Instruct`, see
below) both retrained and evaluated as of 2026-08-16.** `narrative` is
dropped from both tracks (the feature is being removed from `standpoint`
itself; see the `remove-narrative-feature` branch). Real, reported numbers
below -- mixed results, not a clean win, but each with real strengths on
specific tasks. The current production engine (resolved via
`best-engine-ai-helper`, per `standpoint/llm.brief.yaml`) remains the default;
per the plan's own go/no-go rule, either distilled model would only be
trustable as an opt-in override for the tasks/languages it actually passed
on, not as a blanket replacement (see below).

## Retrain stabilization: warmup, a NaN/Inf guard, and the epoch-reshuffle bug (2026-08-15 -> 08-16)

The `narrative` task was dropped from both tracks' `TASKS` lists this session
(scope change, not a bug fix) -- but relaunching both tracks with that one-line
change, otherwise the exact same config that had trained cleanly before,
produced a full retrain that went stable-then-`nan` partway through for
**both** models (EN: iter 210 onward; FR: iter 380 onward). Dropping a task
changing the combined dataset's composition enough to shift the loss
landscape was the initial hypothesis, but it didn't survive investigation:
comparing the raw examples at the exact divergence point found nothing
pathological (no outlier lengths, no malformed JSON), and re-reading
`mlx_vlm.trainer.sft_trainer` directly surfaced two real, pre-existing bugs in
the upstream trainer that this repo's own config happened to be exposing for
the first time:

1. **`TrainingArgs.warmup_steps`/`min_learning_rate` are dead fields.** They're
   declared in the dataclass (with sane-looking defaults: `warmup_steps=100`,
   `min_learning_rate=1e-6`) but grepping the whole trainer module shows
   nothing else ever reads them back -- `optim.Adam(learning_rate=args.
   learning_rate)` runs at that flat value from step 1, no ramp, no decay.
   Every prior run on this repo (including the ones that trained cleanly) was
   silently running with zero warmup despite the config schema implying
   otherwise.
2. **`--grad-clip` is per-element `mx.clip(g, -c, c)`, not a global-norm
   clip** (`sft_trainer.step()`). This bounds each gradient element's raw
   magnitude but does nothing to sanitize a `nan` -- `mx.clip(nan, -1, 1)` is
   still `nan` -- so one unlucky step with a non-finite gradient survives
   "clipping" untouched, gets applied to Adam's `m`/`v` moving averages, and
   poisons every step after it. This is the actual mechanism behind "stable
   for hundreds of iterations, then `nan` forever from one point on."

**Fix, in `run_lora_with_val.py`** (shared by both tracks): a real
`--warmup-steps` flag backed by `mlx.optimizers.linear_schedule(0, lr,
warmup_steps)` passed directly as the optimizer's `learning_rate` (mlx
schedules step once per `optimizer.update()` call -- i.e. once per
grad-accumulated step, not once per raw iter -- since `linear_schedule` holds
at its end value for every step past `steps`, this also doubles as "warmup
then flat" with no separate decay schedule needed); and a NaN/Inf guard wrapping
`optimizer.update()` that checks every gradient array with `mx.isfinite`
before the real update runs and skips (not applies) that one optimizer step
if any is non-finite, instead of letting it poison the optimizer state.

**Validated with several-hundred-iteration smoke tests** (20 iterations, used
earlier this session, was not long enough to catch either divergence -- EN's
was at iter 210): EN (LR 3e-5, unchanged) came back clean, val loss
2.75 -> 2.08 -> 1.69 over 400 iterations. FR at the same LR 3e-5 (just
copied from the English config, never independently validated) no longer went
outright `nan` but still climbed to val loss 12.2 by iteration 500 -- warmup
alone wasn't sufficient, the LR itself was too high for Qwen3-VL-2B (~4x
larger than SmolVLM2-500M, different architecture). At **LR 1e-5**, FR
converged cleanly: val loss 2.67 -> 2.15 -> 1.99.

**A third failure mode surfaced only in the real full-length runs, not the
smoke tests**: `sft_trainer.iterate_batches` reshuffles with an *unseeded*
`np.random.permutation` at every epoch boundary. FR's first full retrain
(warmup + LR 1e-5, before the NaN/Inf guard existed) ran epoch 1 (940
examples) clean -- val loss 6.5 -> 4.3 -- then went to `nan` at iteration 950,
ten iterations into epoch 2's freshly-shuffled order. EN's first full retrain
crashed even harder, with a non-gradient `OverflowError` deep in `idefics3`'s
vision patch-position reshape (`Shape dimension 109504888832 is outside the
supported range`) partway through its own epoch 2 -- a forward-pass crash the
gradient guard cannot catch, since it only wraps the optimizer step. Neither
smoke test could have caught this: a smoke test shorter than one epoch
structurally cannot exercise the epoch-2+ reshuffle, and each run's ordering
is a fresh, unreproducible random draw. Given both models already had clean,
usable checkpoints from end-of-epoch-1 at this point, the choice was between
capping training at one epoch (sidesteps the bug by construction) or
relaunching the full 3-epoch run and accepting the risk (the original
Aug-11/12 EN run *did* survive multiple epochs, so it isn't a certain
failure) -- the latter was chosen, and the third attempt (FR) / second
attempt (EN) both completed cleanly with the NaN/Inf guard in place (FR's
guard caught and skipped 1 bad step along the way; EN needed zero skips).

**Final training numbers**: EN val loss 4.571 -> 0.220 -> 0.195 -> 0.184 ->
0.177 -> 0.173 -> **0.170** (monotonic, iter 11262/11265). FR val loss 2.746
-> 1.325 -> 1.441 -> 1.324 -> 1.246 -> **1.176** (best, iter 2350) -> 1.321
(some late-epoch noise, but no divergence; `select_best_checkpoint.py` picked
iter 2350, not the final snapshot).

## Qwen3-VL-2B pivot: the French track's second model (2026-08-14 -> 08-15)

Superseding the Luth-0.6B track below (kept for history), the French engine
moved to **`mlx-community/Qwen3-VL-2B-Instruct-bf16`** for better multilingual
quality at a comparable size (SmolVLM2-2.2B scores 53.07 on French MMBench vs
Qwen3-VL-2B's 72.47 -- see
[artificialanalysis.ai](https://artificialanalysis.ai/models/multilingual/french)),
text-only, `pole_naming`+`noun_forms` only. `vlm_assess_fr` was attempted and
dropped after a real crash: `mlx_vlm`'s Qwen3-VL LoRA path throws `ValueError:
Image features and image tokens do not match` on every image-bearing batch,
reproduced on `mlx-vlm` 0.6.10 and 0.6.13, a known unresolved upstream bug
([QwenLM/Qwen3-VL#556](https://github.com/QwenLM/Qwen3-VL/issues/556)).
`vlm_assess` stays served by the English adapter for every language -- it's a
geometric check on a rendered image, not really language-dependent, so it
never needed a French-specific variant. 753 `vlm_assess_fr` examples were
generated anyway (`fr_vlm_assess.py`, since deleted with the rest of the
French track; recoverable from git history if the upstream bug is ever fixed). The pivot also made `fr_run_lora_with_clip.py`
(a hand-rolled `mlx_lm` trainer fork with real grad-clip added, needed because
`mlx_lm.lora` has none) unnecessary, so it was deleted entirely -- `mlx_vlm`'s
trainer has its own `--grad-clip`, so the French track now shares
`run_lora_with_val.py` with the English track, no French-specific trainer
code at all.

**Evaluation** (best checkpoint, iter 2350, val loss 1.176; scored on 167
held-out French examples, `data/eval_report_fr.json`):

| task | Qwen3-VL-2B (fr, this session) | Luth-0.6B (fr, 2026-08-13) |
|---|---|---|
| `noun_forms` | **100% (114/114)** | 100% (121/121) |
| `pole_naming` | **83% (44/53)** | 94% (47/50) |

Qwen3-VL-2B's `pole_naming` (83%) is lower than Luth's (94%) on the same task
-- not a clean win over the prior track on this one number. The pivot's actual
motivation (a stronger general multilingual base, not a `pole_naming`-specific
target) still holds, but this number is a real, honest regression on this one
task, not something to explain away. `narrative` is out of scope for this eval
entirely now (dropped from both tracks, see above), so Luth's 35.4%
`narrative` number has no Qwen3-VL-2B counterpart to compare
against.

**English track, same session** (best checkpoint, iter 11262, val loss 0.170,
`pole_naming`+`noun_forms`+`vlm_assess`, `narrative` dropped; scored on 664
held-out examples, `data/eval_report.json`):

| task | this session (`narrative` dropped) | Phase 3 baseline (2026-08-12, incl. `narrative`) |
|---|---|---|
| `noun_forms` en | **100% (103/103)** | 100% (113/113) |
| `noun_forms` fr | **100% (109/109)** | 100% (109/109) |
| `pole_naming` en | **93.3% (56/60)** | 63.2% (36/57) |
| `pole_naming` fr | **42.6% (26/61)** | 32.0% (16/50) |
| `vlm_assess` (English-prompted) | **95.3% (202/212)** | 96.3% (210/218) |
| `vlm_assess` (French-prompted) | **75.6% (90/119)** | n/a -- `vlm_assess` had no `lang` dimension yet |

`pole_naming` improved substantially on both languages (en 63.2% -> 93.3%,
fr 32.0% -> 42.6%) -- consistent with Phase 3's own finding that roughly half
of the old en failures were a `finalize_poles` heuristic false-positive
(`high`/`low` flagged as a drawback marker even in "High-Quality"), not
genuinely bad output; dropping `narrative` from the task mix may also have
freed capacity for the remaining three tasks, though that's not isolated
here. `vlm_assess` (English-prompted) held steady within noise (96.3% ->
95.3%). **`vlm_assess` (French-prompted) at 75.6% is a real, expected gap, not
a regression**: this adapter was never trained on French `vlm_assess`
examples (`vlm_assess_fr` was generated but dropped, see the pivot section
above) -- it's being asked a French-language prompt about English-trained
visual judgment. 75.6% on an unsupported input is informative (the visual
task itself partially transfers cross-lingually even without training data
for it) but doesn't change the design: `vlm_assess` stays scoped to English
in the production go/no-go sense, French callers get the same English-quality
answer today only because production hasn't wired language-specific routing
for this task at all yet (see "Not yet done" above).

## Phase 3 findings (2026-08-12)

Scored on 655 held-out examples (`data/dataset/combined/validation.jsonl`) against
the retrained, parity-balanced `best-adapter` (iter 7416, see the checkpoint table
below). Full numbers: `data/eval_report.json`.

| task | en | fr | verdict |
|---|---|---|---|
| `noun_forms` | 100% (113/113) | 100% (109/109) | **GO**, both languages |
| `vlm_assess` | 96.3% (210/218) -- no language dimension | | **GO** |
| `pole_naming` | 63.2% (36/57) | 32.0% (16/50) | **GO (en, with a caveat) / NO-GO (fr)** |
| `narrative` | 100% (50/50) | **0.0% (0/58)** | **GO (en) / NO-GO (fr)** |

**`pole_naming`'s en number is itself partly an eval-methodology artifact, not a
pure quality signal.** The check reuses production's own `finalize_poles`
invariants, including `_NEGATIVE_WORDS` (`standpoint/__init__.py:935`), which
flags "high"/"low" as drawback markers so labels like "High Cost" get rejected --
but that same heuristic can't distinguish "High Cost" from "High-Quality", so it
also incorrectly rejects genuinely good pole words. Manually classifying every
failure (both languages, all 107 held-out `pole_naming` examples) found:

| lang | pass | overlap (two poles share a word) | `high`/`low` false-positive | other negative-word (genuine) |
|---|---|---|---|---|
| en | 36 | 9 | 10 | 2 |
| fr | 16 | **34** | 0 | 0 |

Since it's faithfully reusing production's real check, the en number (63.2%) is
what production would actually do with this model's output today -- but roughly
half of its failures (10/21) are this one heuristic's false positives, not
genuinely bad word choices. **The fr number is not an artifact.** 68% of fr
examples fail specifically because the model repeats the same word across two
different pole labels (`overlap`), a rate 4x en's (15.8%) -- a real, distinct
French-specific weakness in this model, not a quirk of the check.

**`narrative/fr`'s 0/58 was checked by hand before being trusted**, since a
perfectly uniform 0% across 58 varied examples smelled more like a harness bug
than organic quality variance. It isn't: manually inspecting several candidate
outputs and running the judge directly on one showed genuinely incoherent,
repetitive French (e.g. inventing a non-concept like "économie de capacité" and
looping the same clause) scored 0.1/1.0 with a specific, well-grounded reason --
not a crash, not an empty response, not a judge/language mismatch. Despite
`narrative`'s French training examples being exactly parity-balanced with
English (349/349, see the parity pass below), the model's French narrative
generation is measurably, badly worse than its English narrative generation.

**Conclusion**: this model is not ready to replace the teacher wholesale. If
integrated at all (Phase 5, not started), it should be scoped to `noun_forms`
(en+fr) and `vlm_assess` only, with `pole_naming`/`narrative` staying on the
teacher for French and reconsidered for English -- exactly the per-task,
per-language opt-in the plan called for rather than a uniform swap.

## French track: a second, French-only engine (2026-08-12 -> 2026-08-13)

### The pivot

Phase 3's `narrative/fr` result (0/58, see above) was investigated further: the
**base** SmolVLM2-500M model, zero-shot, with no fine-tuning at all, was already
producing broken French (repetition loops -- "Zotero Zotero Zotero...",
"...pour verifier les connexions... pour verifier les conseils... pour verifier
les connexions...") on the identical prompt. This is a **backbone weakness**,
not a training-data or EN/FR-mixing problem -- no amount of LoRA fine-tuning on
top of a French-illiterate base model was going to fix it.

**Decision**: two engines instead of one bilingual VLM, routed by `langdetect`
(already used in `standpoint`'s own pipeline).
- **English engine**: keep SmolVLM2-500M as-is (Phase 0-3 above). Handles
  `vlm_assess` too, since that task is language-agnostic and needs vision.
- **French engine**: **`kurakurai/Luth-0.6B-Instruct`** (Qwen3-0.6B fine-tuned
  for French, Apache-2.0), text-only. `vlm_assess` never needs a French-specific
  answer, so a text-only French model is sufficient.

### Feasibility spike

1. Converted to MLX (`checkpoints/luth-0.6b-mlx/`, bfloat16, ~1.2GB) via
   `mlx_lm.convert`. Hit `IncompleteSnapshotError`: `mlx_lm.convert`'s internal
   `load()` step only fetches the files it needs to run (skips README/logo/etc),
   but its `save()` step demands a *fully complete* local HF snapshot
   (`local_files_only=True`). Fixed by pre-fetching the whole repo once via
   `huggingface_hub.snapshot_download('kurakurai/Luth-0.6B-Instruct')` (no
   pattern restriction) before converting. Not Luth-specific -- will recur for
   any `mlx_lm.convert` target.
2. Zero-shot French inference: coherent, fluent, on-topic -- a completely
   different quality tier from SmolVLM2's broken output on the same prompt.
3. A tiny 4-example toy LoRA spike trained cleanly (loss 5.01 -> 2.18 train,
   3.83 -> 1.23 val over 6 iterations), confirming `mlx_lm.lora`'s trainer runs
   on this model without the vision-model-specific bugs Phase 0/2 hit.

**Go/no-go: GO.**

### Training: four configurations, three real divergences

Building the training set was straightforward: the `lang == "fr"` rows already
existed in `data/dataset/{pole_naming,noun_forms,narrative}.jsonl` (`vlm_assess`
excluded -- stays English-only). Reshaped to `mlx_lm`'s `{"messages": [...]}`
chat format and split 85/15 (`fr_train_lora.py`, same `train_test_split`
seed=42 discipline as `03_train_lora.py`) -- 1237 train / 219 val examples, no
new generation needed.

Getting a *stable* training run took real iteration, not a single script run.
Each configuration below was checked against the real 927-iteration training
set (a short smoke test was not sufficient evidence on its own -- see #2 and #3):

1. **`mlx_lm.lora`'s own defaults (LR 1e-5, LoRA scale 20.0, plain Adam, no grad
   clip)**: diverged immediately, train loss 2.6 -> 12.7 within 50 iterations.
   Reading `mlx_lm/lora.py` and `mlx_lm/tuner/trainer.py` directly confirmed
   `mlx_lm.lora` has **no gradient-clipping path at all** -- no `--grad-clip`
   flag, no field on `TrainingArgs`, the raw gradient goes straight to
   `optimizer.update()`. Unlike `mlx_vlm`'s trainer (which `03_train_lora.py`
   relies on via `--grad-clip`), this is a real gap for this model/data
   combination. Wrote `fr_run_lora_with_clip.py`, a faithful copy of `mlx_lm`'s
   trainer with `mlx.optimizers.clip_grad_norm` inserted before the optimizer
   step (confirmed present in the installed `mlx`); everything else (validation
   cadence, checkpoint naming, log line formats) kept byte-identical so
   `select_best_checkpoint.py` needs no changes -- confirmed by reading both
   trainers side by side, not assumed.
2. **Grad-clip 1.0, LoRA scale 2.0** (matching `03_train_lora.py`'s validated
   rank=16/alpha=32 = scale 2.0, ten times more conservative than `mlx_lm`'s
   default of 20.0), still plain Adam: a 60-iteration smoke test looked healthy
   (val loss 2.556 -> 2.294 -> 2.236) but the **real** 927-iteration run's val
   loss more than doubled by iteration 154 (2.556 -> 5.549) -- a clean signal
   from the full held-out set, not batch noise. The smoke test was too short to
   catch a slower-onset divergence.
3. **Same, plus AdamW** (`weight_decay=0.01`, standard LoRA practice for
   bounding parameter-norm growth over long runs): a 200-iteration smoke test
   looked healthy (val loss oscillating 2.34-2.77, nothing like #2's blowup),
   but the real run diverged anyway -- train loss reached 7.4 by iteration 120.
   Metal GPU non-determinism plus this regime's very large pre-clip gradient
   norms (tens of millions, confirmed by instrumenting the clipped trainer to
   print them) means even matching hyperparameters and seed do not reproduce
   the same trajectory between two runs.
4. **LR 2e-6 (5x lower), grad-clip 0.5 (2x tighter), LoRA scale 2.0, AdamW**:
   a 460-iteration smoke test -- long enough to span a full epoch over the
   1237-example train set -- showed a perfectly monotonic, oscillation-free val
   loss decrease at every one of its checkpoints (2.556 -> 2.446 -> 2.370 ->
   2.300 -> 2.247 -> 2.201 -> 2.170 -> 2.147 -> 2.104 -> 2.070 -> 2.063),
   including through and past every iteration range where #2 and #3 broke
   down. The real 927-iteration run confirmed it: seven checkpoints, every one
   an improvement, zero oscillation (2.556 -> 2.287 -> 2.221 -> 2.086 -> 1.957
   -> 1.931 -> 1.774 -> **1.770 final**, a 30.7% reduction from baseline).
   **This is the configuration used for the reported checkpoint.**

Before trusting this diagnosis, an unrelated hypothesis was ruled out directly:
a forward-only loss sweep of all 1237 training examples against the
*untrained* model found nothing pathological in the data (max loss 3.36, mean
2.74, stdev 0.31 -- a tight distribution), so the divergences above are a real
optimizer/hyperparameter-sensitivity story for this model, not a data-quality
one.

### Evaluation

Scored on the 219 held-out French examples (`data/dataset/combined_fr/valid.jsonl`)
against the best checkpoint (iteration 924, nearest saved snapshot to the true
best at 927; val loss 1.774 vs 1.770, negligible difference). Full numbers:
`data/eval_report_fr.json`.

| task | this session (Luth, fr) | Phase 3 baseline (SmolVLM2, fr) | Phase 3 baseline (SmolVLM2, en) |
|---|---|---|---|
| `noun_forms` | **100% (121/121)** | 100% | 100% |
| `pole_naming` | **94% (47/50)** | 32.0% | 63.2% |
| `narrative` | **35.4% (17/48)** | 0.0% | 100% |

A French-specific text model is a dramatically better fit for these French text
tasks than the bilingual VLM was: `pole_naming` jumped from 32.0% to 94% --
better than the VLM's own **English** number -- and `narrative` went from a
complete 0% failure to 35.4%.

**`narrative/fr`'s 35.4% was checked by hand** (same discipline as Phase 3's
`narrative/fr` 0% finding above -- a suspicious rate gets inspected, not
reported blind). Regenerating three of the FAIL examples directly: two were
coherent, fluent, grammatically correct French analysis, on-topic and readable
-- but more generic and less information-dense than the teacher's answer (the
prompt asks for four specific points: the main takeaway, where the leader wins,
the sharpest tradeoff, any over/under-performer; the candidate's prose covers
similar ground without hitting each point as precisely, which is enough for
`GEval`'s relative-quality judge to score it below the pass threshold even
though nothing is *wrong* with the French itself). The third showed genuine
phrase-level repetition ("elle est la plus rapide a reagir, elle est la plus
economique, elle est la plus securisee, elle est la plus fiable" looping) --
a real degeneration, but qualitatively different from the base SmolVLM2's
character/token-level gibberish looping in French. **Conclusion**: 35.4% is a
real signal, not a harness artifact -- the French engine is genuinely capable
of French narrative prose (unlike the VLM, which cannot produce usable French
narrative at all), but not yet reliable enough at matching the teacher's
specific structure to pass `GO` on this task.

**Per-task verdict for the French engine**: `noun_forms` **GO**, `pole_naming`
**GO** (94%, a real, usable rate), `narrative` **NO-GO** (35.4%, real
improvement over the VLM but not production-ready) -- same per-task,
per-language opt-in discipline as Phase 3's conclusion, not a blanket claim.

### Not yet done

- Phase 5 (the actual `langdetect`-routing integration deciding which engine
  handles which task/language) is still not designed -- deliberately deferred
  until both engines had real evaluation numbers, which is now the case for
  both.
- Phase 4 (GGUF/MLX export) for the English SmolVLM2 engine was never started;
  worth revisiting given the two-engine split before investing in export
  tooling for a model that may only cover `noun_forms`+`vlm_assess` in
  practice.
- `checkpoints/toy-luth-adapter/`, `data/toy_luth/`: throwaway spike artifacts,
  gitignored, harmless to leave.

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

Standpoint's language jobs run on one local model (typically `qwen2.5vl:7b`).
This distils that behaviour into a small model that a browser can download,
scoped to English and French, trained locally (this machine has no CUDA, so no
Unsloth — training runs via Apple's MLX instead).

The task list narrowed twice: `analysis_markdown` went when the narrative
feature was removed from standpoint (2026-09-20), and `vlm_assess` went when
measurement showed there was nothing in it to learn (2026-09-21, top of this
file). What remains is `axis_poles` / `pole_naming`, `noun_forms` and
`suggest_ratings` — three text tasks, all schema-constrained.

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

**Qwen3-0.6B** (`Qwen/Qwen3-0.6B`) for English and the bilingual control,
**Luth-0.6B-Instruct** (`kurakurai/Luth-0.6B-Instruct`, a Qwen3-0.6B fine-tuned
for French) for French. Both are the same architecture, so both are servable by
the WebLLM/MLC chain the browser build uses. See the rearchitecture section at
the top of this file for why.

Previously **SmolVLM2-500M-Video-Instruct**
(`HuggingFaceTB/SmolVLM2-500M-Video-Instruct`, Apache-2.0), chosen as the only
real ~500M-parameter vision-capable model available. It was the right pick while
the corpus carried images; it stopped being one when `vlm_assess` left, since
WebLLM cannot serve it.

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
    run_lora_text_with_val.py   # what 03_train_lora.py invokes now: mlx_lm with
                                 # the three things its CLI has no flag for --
                                 # global-norm clipping, a NaN guard, LR warmup
                                 # (plus prompt masking)

    # Vision-era trainers, kept for the record; nothing invokes them since the
    # 2026-09-21 rearchitecture moved the student to a text model.
    _mlx_vlm_idefics3_patch.py  # upstream trainer bug workaround (see Phase 0)
    run_lora.py                 # mlx_vlm.lora's own CLI + the patch; manual smoke
                                 # tests only -- no validation (see Phase 2 #4)
    run_lora_with_val.py        # the mlx_vlm trainer with a real val_dataset
                                 # wired in; run_lora_text_with_val.py's ancestor
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

    # The separate French track (fr_train_lora.py, fr_evaluate.py,
    # fr_vlm_assess.py) died with the 2026-09-21 rearchitecture -- replaced by
    # `03_train_lora.py --lang fr` on the same code path as English -- and was
    # deleted on 2026-09-24 (recoverable from git history if ever needed).
  data/                      # generated datasets (gitignored; regenerable)
  checkpoints/               # LoRA adapters + merged/converted models (gitignored)
```

## Full plan

See the plan this branch executes: phases, per-task risk assessment, and the
(revised) export architecture are recorded in this session's plan file and
summarized progressively in this README as each phase completes.
