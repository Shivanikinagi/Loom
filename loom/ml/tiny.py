"""A tiny, randomly initialised GPT-2 with the real architecture and vocabulary.

Used by the test-suite and by `--tiny` local runs so nothing depends on the
548 MB checkpoint. It has GPT-2's tokenizer, layer structure and parameter
names, just far fewer and smaller layers, so the pipeline code path is
identical.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np


def write_safetensors(path: Path, tensors: dict[str, np.ndarray]) -> None:
    header, offset, blobs = {}, 0, []
    for name, arr in tensors.items():
        b = np.ascontiguousarray(arr, dtype="<f4").tobytes()
        header[name] = {"dtype": "F32", "shape": list(arr.shape), "data_offsets": [offset, offset + len(b)]}
        offset += len(b)
        blobs.append(b)
    h = json.dumps(header).encode()
    h += b" " * ((8 - len(h) % 8) % 8)
    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(h)))
        f.write(h)
        for b in blobs:
            f.write(b)


# Bump when the initialisation changes so cached tiny models are regenerated.
TINY_VERSION = 2


def make_tiny_gpt2(out_dir: Path, n_layer: int = 6, n_embd: int = 64, n_head: int = 4, seed: int = 0) -> Path:
    out_dir = Path(out_dir)
    cfg = out_dir / "config.json"
    if (out_dir / "model.safetensors").exists() and cfg.exists() and json.loads(cfg.read_text()).get("tiny") == TINY_VERSION:
        return out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    vocab, n_ctx = 50257, 256
    rng = np.random.default_rng(seed)

    def w(*shape, scale=0.02):
        return (rng.standard_normal(shape) * scale).astype(np.float32)

    # Embeddings at GPT-2-like scale (hidden states around 1), so rounding
    # activations between stages is as harmless here as in the real model.
    t: dict[str, np.ndarray] = {"wte.weight": w(vocab, n_embd, scale=0.5), "wpe.weight": w(n_ctx, n_embd, scale=0.1)}
    for i in range(n_layer):
        p = f"h.{i}."
        t[p + "ln_1.weight"] = np.ones(n_embd, np.float32)
        t[p + "ln_1.bias"] = np.zeros(n_embd, np.float32)
        t[p + "attn.c_attn.weight"] = w(n_embd, 3 * n_embd)
        t[p + "attn.c_attn.bias"] = np.zeros(3 * n_embd, np.float32)
        t[p + "attn.c_proj.weight"] = w(n_embd, n_embd)
        t[p + "attn.c_proj.bias"] = np.zeros(n_embd, np.float32)
        t[p + "ln_2.weight"] = np.ones(n_embd, np.float32)
        t[p + "ln_2.bias"] = np.zeros(n_embd, np.float32)
        t[p + "mlp.c_fc.weight"] = w(n_embd, 4 * n_embd)
        t[p + "mlp.c_fc.bias"] = np.zeros(4 * n_embd, np.float32)
        t[p + "mlp.c_proj.weight"] = w(4 * n_embd, n_embd)
        t[p + "mlp.c_proj.bias"] = np.zeros(n_embd, np.float32)
    t["ln_f.weight"] = np.ones(n_embd, np.float32)
    t["ln_f.bias"] = np.zeros(n_embd, np.float32)

    write_safetensors(out_dir / "model.safetensors", t)
    (out_dir / "config.json").write_text(
        json.dumps({"n_layer": n_layer, "n_head": n_head, "n_embd": n_embd, "n_ctx": n_ctx, "vocab_size": vocab,
                    "tiny": TINY_VERSION})
    )
    return out_dir
