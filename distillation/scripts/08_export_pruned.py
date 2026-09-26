"""Export the PRUNED student to the browser bundle, embeddings quantised too.

`05_export_browser.py` established the path (ONNX fp16 export, MatMul weights
to 4-bit, browser layout) and its one blind spot: `MatMulNBitsQuantizer` only
touches MatMul weights, and the embedding table is read by a `Gather`, so it
ships at fp16 -- half the bundle. `07_prune_vocab.py` already shrank that
table 3.5x by dropping unreachable rows; this script reuses 05's functions on
the pruned checkpoint (already fused, so no fuse step) and then closes the
blind spot with graph surgery:

    Y = Gather(W_fp16, ids)                        # before: 2 bytes/weight
    Y = Gather(W_int8, ids)                        # after: 1 byte/weight
        -> Cast(fp16) -> Mul(Gather(scales, ids))  # per-row symmetric scales

Per-row symmetric int8 keeps the quantisation error around 0.4% of each row's
peak -- far below what a 4-bit body already tolerates -- and uses only
plain-vanilla ops (Gather / Cast / Mul / Unsqueeze), all supported by
onnxruntime-web's wasm and WebGPU backends; no contrib op, nothing for the
browser runtime to reject. Dequantisation happens on the few GATHERED rows per
step, never on the whole table.

Run with the distillation venv (06_evaluate_onnx.py is the go/no-go gate
afterwards)::

    .venv/bin/python scripts/08_export_pruned.py
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np

DIST_DIR = Path(__file__).resolve().parents[1]
CHECKPOINTS = DIST_DIR / "checkpoints"
SCRIPTS = DIST_DIR / "scripts"


def _load_export05():
    """Import 05_export_browser.py by path for its export/quantize/layout steps."""
    spec = importlib.util.spec_from_file_location("export05", SCRIPTS / "05_export_browser.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["export05"] = module
    spec.loader.exec_module(module)
    return module


def quantize_embedding_int8(q4_file: Path, out_file: Path) -> None:
    """Rewrite the fp16 embedding Gather of `q4_file` to int8 + per-row scales."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    model = onnx.load(str(q4_file), load_external_data=True)
    graph = model.graph
    inits = {init.name: init for init in graph.initializer}

    # The embedding table is the one big fp16 initializer read by a Gather.
    gather = None
    for node in graph.node:
        if node.op_type != "Gather" or node.input[0] not in inits:
            continue
        init = inits[node.input[0]]
        if init.data_type == TensorProto.FLOAT16 and len(init.dims) == 2 and init.dims[0] > 1000:
            gather = node
            break
    if gather is None:
        raise SystemExit("no fp16 embedding Gather found; graph layout changed")

    weight_name = gather.input[0]
    table = numpy_helper.to_array(inits[weight_name]).astype(np.float32)
    rows, hidden = table.shape
    print(f"embedding table {weight_name}: {rows} x {hidden} fp16 -> int8 + fp16 scales")

    # Per-row symmetric quantisation; an all-zero row gets scale 1 to avoid 0/0.
    peak = np.abs(table).max(axis=1)
    scales = np.where(peak > 0, peak / 127.0, 1.0).astype(np.float32)
    q = np.clip(np.rint(table / scales[:, None]), -127, 127).astype(np.int8)

    graph.initializer.remove(inits[weight_name])
    graph.initializer.append(numpy_helper.from_array(q, weight_name + "_q8"))
    graph.initializer.append(
        numpy_helper.from_array(scales.astype(np.float16), weight_name + "_scales")
    )
    axes_name = weight_name + "_unsq_axes"
    graph.initializer.append(numpy_helper.from_array(np.array([-1], dtype=np.int64), axes_name))

    ids = gather.input[1]
    out = gather.output[0]
    nodes = [
        helper.make_node("Gather", [weight_name + "_q8", ids], [out + "_q8"], axis=0),
        helper.make_node("Cast", [out + "_q8"], [out + "_f16"], to=TensorProto.FLOAT16),
        helper.make_node("Gather", [weight_name + "_scales", ids], [out + "_s"], axis=0),
        helper.make_node("Unsqueeze", [out + "_s", axes_name], [out + "_s3"]),
        helper.make_node("Mul", [out + "_f16", out + "_s3"], [out]),
    ]
    # Splice at the Gather's position so topological order survives.
    index = list(graph.node).index(gather)
    graph.node.remove(gather)
    for offset, node in enumerate(nodes):
        graph.node.insert(index + offset, node)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    onnx.checker.check_model(model)
    onnx.save(model, str(out_file), save_as_external_data=False)
    print(f"int8-embedding graph written to {out_file} ({out_file.stat().st_size / 1e6:.0f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--pruned",
        type=Path,
        default=CHECKPOINTS / "standpoint-qwen3-0.6b-pruned",
        help="pruned HF checkpoint from 07_prune_vocab.py",
    )
    args = parser.parse_args()

    ex = _load_export05()
    stem = args.pruned.name  # standpoint-qwen3-0.6b-pruned
    onnx_dir = ex.export_onnx(args.pruned, CHECKPOINTS / f"{stem}-onnx-fp16")
    q4_file = CHECKPOINTS / f"{stem}-onnx-q4f16" / "model_q4f16.onnx"
    if q4_file.exists():
        print(f"q4f16 graph already at {q4_file}, reusing")
    else:
        ex.quantize_q4f16(onnx_dir, q4_file)
    q4e8_file = CHECKPOINTS / f"{stem}-onnx-q4f16-e8" / "model_q4f16.onnx"
    if q4e8_file.exists():
        print(f"int8-embedding graph already at {q4e8_file}, reusing")
    else:
        quantize_embedding_int8(q4_file, q4e8_file)
    # The pruned checkpoint doubles as the tokenizer source: 07 already wrote
    # upstream-derived tokenizer files with remapped ids next to the weights.
    ex.lay_out_for_browser(args.pruned, onnx_dir, q4e8_file, CHECKPOINTS / f"{stem}-browser")


if __name__ == "__main__":
    main()
