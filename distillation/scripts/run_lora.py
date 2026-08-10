"""Run `mlx_vlm.lora` with the Idefics3/SmolVLM2 trainer patch applied first.

Usage mirrors the `mlx_vlm.lora` CLI directly, e.g.:

    python3 scripts/run_lora.py --model-path checkpoints/smolvlm2-500m-mlx \\
        --dataset data/toy --iters 6 --output-path checkpoints/toy-spike-adapter

See `_mlx_vlm_idefics3_patch.py` for why this wrapper exists.
"""

from __future__ import annotations

import runpy
import sys

import _mlx_vlm_idefics3_patch  # noqa: F401  (patches Idefics3.__call__ on import)

if __name__ == "__main__":
    sys.argv[0] = "mlx_vlm.lora"
    runpy.run_module("mlx_vlm.lora", run_name="__main__")
