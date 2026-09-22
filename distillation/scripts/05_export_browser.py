"""Phase 4: turn the trained adapter into the model the browser actually loads.

Fuses the LoRA adapter into its base, exports to ONNX, quantises the weights to
4-bit, and lays the result out the way `@huggingface/transformers` expects
(`onnx/model_q4f16.onnx` next to the tokenizer files). The output folder drops
straight into `webapp/dist/model/`.

**Why ONNX and not MLC/WebLLM.** The webapp's "Laziness" button currently loads
a generic Qwen2.5-1.5B through WebLLM, which needs weights in MLC's own format.
MLC's macOS nightly wheels are broken at the time of writing -- `import tvm`
dies with a heap-corruption abort inside `libtvm_runtime_extra`'s initialisers,
an ABI mismatch against the released `apache-tvm-ffi` that survives re-signing
the dylibs and pinning every published `apache-tvm-ffi` version. ONNX avoids
that toolchain entirely, and it is the better target anyway: the page already
loads transformers.js for the MiniLM axis-naming embeddings, so serving the
student through the same runtime removes a second inference engine from the
page rather than swapping one for another.

**q4f16, and the fp16 has to come from the exporter, not from a converter.**
`MatMulNBitsQuantizer` only touches MatMul weights. Qwen3's embedding table is
read by `Gather`, not `MatMul`, and at 151936 x 1024 it is 156M of the model's
596M parameters -- a quarter of it, left untouched. Measured: quantising an
fp32 export lands at 996 MB, of which 622 MB is that one fp32 table.

The obvious fix -- quantise, then run `onnxconverter_common.float16` over what
is left -- does not work here. With shape inference off it emits a graph that
loads and then fails ("Type parameter (T) of Optype (Add) bound to different
types") at the first LayerNorm; with shape inference on it fails differently,
on a Cast whose output type contradicts its declared one. Exporting in fp16
from the start, and quantising that, produces a valid graph in one step. Hence
`--dtype fp16` below.

Result: 652 MB, against ~1 GB for the generic Qwen2.5-1.5B the page downloads
through WebLLM today. Verified end to end on CPU through onnxruntime -- valid,
complete JSON on all three tasks in both languages.

Run with the distillation venv::

    python distillation/scripts/05_export_browser.py --lang all
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DIST_DIR = Path(__file__).resolve().parents[1]
CHECKPOINTS = DIST_DIR / "checkpoints"

# Mirrors 03_train_lora.py's BASE_MODELS / adapter_out_for.
BASE_MODELS = {
    "en": CHECKPOINTS / "qwen3-0.6b-mlx-bf16",
    "fr": CHECKPOINTS / "luth-0.6b-mlx-bf16",
    "all": CHECKPOINTS / "qwen3-0.6b-mlx-bf16",
}
# Upstream repos, for the tokenizer only. `mlx_lm fuse` rewrites
# tokenizer_config.json through transformers 5, which drops
# `added_tokens_decoder`, `additional_special_tokens` and the chat template and
# adds transformers-5-only keys -- a config the browser runtime cannot read, and
# missing the very template the model was trained against. The weights come from
# the fuse; the tokenizer comes from here.
HF_REPOS = {
    "en": "Qwen/Qwen3-0.6B",
    "fr": "kurakurai/Luth-0.6B-Instruct",
    "all": "Qwen/Qwen3-0.6B",
}
BLOCK_SIZE = 32  # weights per shared scale; the transformers.js q4 convention


def adapter_for(lang: str) -> Path:
    """The best-checkpoint directory select_best_checkpoint.py wrote for `lang`."""
    stem = "distilled-adapter" if lang == "all" else f"distilled-adapter-{lang}"
    return CHECKPOINTS / stem / "best-adapter"


def run(cmd: list[str]) -> None:
    """Run a subprocess loudly; a non-zero exit aborts the export."""
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True)


def fuse(lang: str, out: Path) -> Path:
    """Merge the adapter into its base model, giving a standalone HF checkpoint."""
    if out.exists():
        print(f"fused model already at {out}, reusing")
        return out
    run(
        [
            sys.executable,
            "-m",
            "mlx_lm",
            "fuse",
            "--model",
            str(BASE_MODELS[lang]),
            "--adapter-path",
            str(adapter_for(lang)),
            "--save-path",
            str(out),
        ]
    )
    return out


def export_onnx(fused: Path, out: Path) -> Path:
    """Export to fp16 ONNX with the KV-cache branches generation needs."""
    if (out / "model.onnx").exists():
        print(f"ONNX export already at {out}, reusing")
        return out
    run(
        [
            str(DIST_DIR / ".venv" / "bin" / "optimum-cli"),
            "export",
            "onnx",
            "--model",
            str(fused),
            # ...-with-past: exports the cached-decoding path too. Without it the
            # runtime re-reads the whole prompt at every token, which for a
            # ratings matrix of several hundred tokens is the difference between
            # a usable click and an unusable one.
            "--task",
            "text-generation-with-past",
            # fp16 at export time, not by converting an fp32 graph afterwards --
            # see the module docstring for what the converter does to this model.
            "--dtype",
            "fp16",
            "--device",
            "cpu",
            str(out),
        ]
    )
    return out


def quantize_q4f16(onnx_dir: Path, out_file: Path) -> None:
    """Block-quantise every MatMul weight of the fp16 graph to 4 bits."""
    import onnx
    from onnxruntime.quantization import matmul_nbits_quantizer as qn

    model = onnx.load(str(onnx_dir / "model.onnx"), load_external_data=True)
    config = qn.DefaultWeightOnlyQuantConfig(
        block_size=BLOCK_SIZE,
        is_symmetric=True,
        # accuracy_level 4 = int8 compute for the quantised MatMuls. The runtime
        # picks its own kernels anyway; this only sets the hint stored in the graph.
        accuracy_level=4,
        bits=4,
    )
    quantizer = qn.MatMulNBitsQuantizer(model, algo_config=config)
    quantizer.process()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    # All-in-one file: transformers.js fetches one URL per ONNX artefact, and a
    # sidecar .onnx_data would need its own fetch and its own correct path.
    onnx.save(quantizer.model.model, str(out_file), save_as_external_data=False)


def upstream_tokenizer_dir(lang: str) -> Path:
    """The cached HF snapshot for `lang`'s base model, for its tokenizer files."""
    from huggingface_hub import snapshot_download

    return Path(
        snapshot_download(
            HF_REPOS[lang],
            allow_patterns=["tokenizer*", "*.json", "chat_template.jinja"],
        )
    )


def lay_out_for_browser(tokenizer_src: Path, onnx_dir: Path, q4_file: Path, out: Path) -> None:
    """Assemble the folder `@huggingface/transformers` loads from a plain URL.

    The runtime expects the tokenizer and config at the folder root and the
    graphs under ``onnx/``, named by dtype -- ``model_q4f16.onnx`` for
    ``dtype: "q4f16"``. Nothing else from the export is needed in the browser, and
    the 3 GB fp32 graph in particular must not be shipped.
    """
    out.mkdir(parents=True, exist_ok=True)
    (out / "onnx").mkdir(exist_ok=True)
    for name in (
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "vocab.json",
        "merges.txt",
        "chat_template.jinja",
    ):
        src = tokenizer_src / name
        if src.exists():
            shutil.copy2(src, out / name)
    shutil.copy2(onnx_dir / "generation_config.json", out / "generation_config.json")

    # config.json needs one addition the exporter does not make: the runtime
    # reads `transformers.js_config.kv_cache_dtype` to decide what to feed the
    # KV-cache inputs, and defaults to float32. Our graph is fp16, so without
    # this the model downloads, loads, and then dies on the first token with
    # "Unexpected input data type. Actual: (tensor(float)), expected:
    # (tensor(float16))" -- found only by running the deployed model for real.
    config = json.loads((onnx_dir / "config.json").read_text(encoding="utf-8"))
    config["transformers.js_config"] = {
        "kv_cache_dtype": {"q4f16": "float16", "fp16": "float16"},
        "use_external_data_format": False,
    }
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(q4_file, out / "onnx" / "model_q4f16.onnx")

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"\nbrowser bundle ready at {out} ({total / 1e6:.0f} MB)")
    print(
        json.dumps(sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()), indent=1)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lang", choices=("en", "fr", "all"), default="all")
    args = parser.parse_args()

    stem = f"standpoint-qwen3-0.6b{'' if args.lang == 'all' else '-' + args.lang}"
    fused = fuse(args.lang, CHECKPOINTS / f"{stem}-fused")
    onnx_dir = export_onnx(fused, CHECKPOINTS / f"{stem}-onnx-fp16")
    q4_file = CHECKPOINTS / f"{stem}-onnx-q4f16" / "model_q4f16.onnx"
    if q4_file.exists():
        print(f"q4f16 graph already at {q4_file}, reusing")
    else:
        quantize_q4f16(onnx_dir, q4_file)
    lay_out_for_browser(
        upstream_tokenizer_dir(args.lang), onnx_dir, q4_file, CHECKPOINTS / f"{stem}-browser"
    )


if __name__ == "__main__":
    main()
