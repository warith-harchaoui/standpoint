"""Workaround for an upstream mlx-vlm bug affecting SmolVLM2 (Idefics3) LoRA training.

`mlx_vlm.trainer.sft_trainer.vision_language_loss_fn` calls every model
positionally as ``model(input_ids, pixel_values, attention_mask, **kwargs)``. The
Idefics3 model class's (SmolVLM/SmolVLM2's architecture) third positional
parameter is named/used as ``cache``, not ``attention_mask`` -- so the trainer's
attention-mask array lands in the cache slot, and `create_attention_mask` then
tries to bool-convert a multi-element mx.array and raises ``ValueError: [convert]
Only length-1 arrays can be converted to Python scalars.``

Verified against mlx-vlm 0.6.10 (`Blaizzy/mlx-vlm`, see `models/idefics3/idefics3.py`
`Model.__call__`). This module must be imported before any Idefics3/SmolVLM model is
constructed or trained, so it is imported first thing in every `distillation/scripts/`
entry point that touches training. Safe to delete once upstream fixes the trainer's
positional call convention for Idefics3-family models.
"""

from __future__ import annotations

import mlx.core as mx
from mlx_vlm.models.idefics3 import idefics3 as _idefics3_module


def _patched_call(
    self,
    input_ids: mx.array,
    pixel_values: mx.array,
    attention_mask: mx.array | None = None,  # noqa: ARG001 (accepted, unused: training-only forward pass needs no KV cache)
    cache=None,
    **kwargs,
):
    input_embeddings_features = self.get_input_embeddings(input_ids, pixel_values, **kwargs)
    logits = self.language_model(
        inputs=input_ids,
        cache=cache,
        inputs_embeds=input_embeddings_features.inputs_embeds,
    )
    return logits


_idefics3_module.Model.__call__ = _patched_call
