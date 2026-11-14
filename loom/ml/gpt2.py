"""GPT-2 in plain NumPy, runnable one layer range at a time.

LOOM splits a single model across several providers the way pooled-GPU
inference does (Parallax-style pipeline parallelism): provider A runs the
embedding plus blocks 0-3, provider B runs blocks 4-7, provider C runs blocks
8-11 plus the head. Each provider only ever sees the activations handed to it
by the previous stage.

Plain NumPy (no torch) keeps every stage deterministic on a given machine, so
an honest re-execution by a verifier reproduces the provider's activations, and
a lazy or malicious provider stands out by orders of magnitude.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class GPT2Config:
    n_layer: int
    n_head: int
    n_embd: int
    n_ctx: int
    vocab_size: int


def load_safetensors(path: Path) -> dict[str, np.ndarray]:
    """Minimal safetensors reader: 8-byte LE header length, JSON header, raw data."""
    raw = Path(path).read_bytes()
    (hlen,) = struct.unpack("<Q", raw[:8])
    header = json.loads(raw[8 : 8 + hlen])
    base = 8 + hlen
    dtypes = {"F32": np.float32, "F16": np.float16, "BF16": None}
    out: dict[str, np.ndarray] = {}
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        dt = dtypes[meta["dtype"]]
        if dt is None:
            raise ValueError("bf16 weights are not supported")
        start, end = meta["data_offsets"]
        arr = np.frombuffer(raw, dtype=dt, count=(end - start) // np.dtype(dt).itemsize, offset=base + start)
        out[name] = arr.reshape(meta["shape"]).astype(np.float32)
    return out


def _gelu(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + np.tanh(np.float32(0.7978845608) * (x + np.float32(0.044715) * x * x * x)))


def _layer_norm(x: np.ndarray, g: np.ndarray, b: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    mean = x.mean(axis=-1, keepdims=True)
    var = ((x - mean) ** 2).mean(axis=-1, keepdims=True)
    return g * (x - mean) / np.sqrt(var + np.float32(eps)) + b


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


class GPT2:
    """GPT-2 weights plus forward passes that can start and stop at any block."""

    def __init__(self, model_dir: Path):
        model_dir = Path(model_dir)
        cfg = json.loads((model_dir / "config.json").read_text())
        self.cfg = GPT2Config(cfg["n_layer"], cfg["n_head"], cfg["n_embd"], cfg["n_ctx"], cfg["vocab_size"])
        w = load_safetensors(model_dir / "model.safetensors")
        # HF checkpoints sometimes prefix weights with "transformer."
        self.w = {k.removeprefix("transformer."): v for k, v in w.items()}

    # -- pieces -------------------------------------------------------------
    def embed(self, tokens: list[int]) -> np.ndarray:
        t = np.asarray(tokens, dtype=np.int64)
        return self.w["wte.weight"][t] + self.w["wpe.weight"][: len(t)]

    def block(self, x: np.ndarray, i: int) -> np.ndarray:
        p = f"h.{i}."
        w = self.w
        n_head = self.cfg.n_head
        T, C = x.shape

        h = _layer_norm(x, w[p + "ln_1.weight"], w[p + "ln_1.bias"])
        qkv = h @ w[p + "attn.c_attn.weight"] + w[p + "attn.c_attn.bias"]
        q, k, v = np.split(qkv, 3, axis=-1)
        q = q.reshape(T, n_head, C // n_head).transpose(1, 0, 2)
        k = k.reshape(T, n_head, C // n_head).transpose(1, 0, 2)
        v = v.reshape(T, n_head, C // n_head).transpose(1, 0, 2)
        att = (q @ k.transpose(0, 2, 1)) / np.float32(np.sqrt(C // n_head))
        mask = np.triu(np.full((T, T), -1e10, dtype=np.float32), k=1)
        att = _softmax(att + mask)
        y = (att @ v).transpose(1, 0, 2).reshape(T, C)
        x = x + (y @ w[p + "attn.c_proj.weight"] + w[p + "attn.c_proj.bias"])

        h = _layer_norm(x, w[p + "ln_2.weight"], w[p + "ln_2.bias"])
        h = _gelu(h @ w[p + "mlp.c_fc.weight"] + w[p + "mlp.c_fc.bias"])
        return x + (h @ w[p + "mlp.c_proj.weight"] + w[p + "mlp.c_proj.bias"])

    def blocks(self, x: np.ndarray, start: int, end: int) -> np.ndarray:
        for i in range(start, end):
            x = self.block(x, i)
        return x

    def head(self, x: np.ndarray) -> np.ndarray:
        """Final layer norm and tied unembedding; returns logits for the last position."""
        h = _layer_norm(x[-1:], self.w["ln_f.weight"], self.w["ln_f.bias"])
        return (h @ self.w["wte.weight"].T)[0]

    def forward(self, tokens: list[int]) -> np.ndarray:
        return self.head(self.blocks(self.embed(tokens), 0, self.cfg.n_layer))
