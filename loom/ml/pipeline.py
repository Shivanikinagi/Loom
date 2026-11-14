"""The LOOM pipeline: one job, one model, several providers.

A job is a batch of texts to classify (zero-shot sentiment with GPT-2). The
model is cut into stages by layer range. Each stage reads the previous stage's
blob, runs its layers, and writes a new blob. The keccak256 of every blob is
committed on-chain, so the commitments form a chain:

    dataset --stage0--> act0 --stage1--> act1 --stage2--> result

A verifier can re-run any single stage from its committed input blob and check
the committed output, which is how a dispute pins the fault on one provider.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass

import numpy as np
from eth_hash.auto import keccak

from .gpt2 import GPT2

# Activations are rounded before hashing. Honest runs on the same software stack
# are bit-identical anyway; rounding only stops harmless last-bit drift from
# changing the commitment. Verifiers compare with a tolerance on top of that.
ROUND_DECIMALS = 4
TOLERANCE = 1e-2

LABELS = [" positive", " negative"]
PROMPT = "Review: {text}\nSentiment:"
# Contextual calibration (Zhao et al., 2021): GPT-2 is biased towards " positive"
# on its own. A content-free row runs through the pipeline with the real ones
# and its scores are subtracted, which takes zero-shot accuracy on our review
# set from 50% to 90%. It is row 0 of every blob, so it is verified like the rest.
CALIBRATION_TEXT = "N/A"


@dataclass(frozen=True)
class Stage:
    index: int
    first_block: int
    last_block: int  # exclusive
    embeds: bool  # stage 0 tokenizes and embeds
    heads: bool  # last stage applies ln_f + unembedding

    @property
    def layers(self) -> int:
        return self.last_block - self.first_block


def plan_stages(n_layer: int, n_stages: int) -> list[Stage]:
    per, extra = divmod(n_layer, n_stages)
    stages, start = [], 0
    for i in range(n_stages):
        end = start + per + (1 if i < extra else 0)
        stages.append(Stage(i, start, end, embeds=i == 0, heads=i == n_stages - 1))
        start = end
    return stages


# -- blobs -----------------------------------------------------------------
def pack(kind: str, arrays: list[np.ndarray], meta: dict | None = None) -> bytes:
    """Deterministic container: JSON header line + concatenated float32 bytes."""
    arrays = [np.round(np.asarray(a, dtype=np.float32), ROUND_DECIMALS).astype("<f4") for a in arrays]
    header = {"kind": kind, "shapes": [list(a.shape) for a in arrays], "meta": meta or {}}
    buf = io.BytesIO()
    buf.write(json.dumps(header, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    for a in arrays:
        buf.write(np.ascontiguousarray(a).tobytes())
    return buf.getvalue()


def unpack(blob: bytes) -> tuple[str, list[np.ndarray], dict]:
    nl = blob.index(b"\n")
    header = json.loads(blob[:nl])
    off, arrays = nl + 1, []
    for shape in header["shapes"]:
        n = int(np.prod(shape)) if shape else 1
        arrays.append(np.frombuffer(blob, dtype="<f4", count=n, offset=off).reshape(shape))
        off += n * 4
    return header["kind"], arrays, header["meta"]


def dataset_blob(texts: list[str]) -> bytes:
    return json.dumps({"kind": "dataset", "texts": texts}, sort_keys=True, separators=(",", ":")).encode()


def commitment(blob: bytes) -> bytes:
    """bytes32 commitment that goes on-chain."""
    return keccak(blob)


# -- execution ---------------------------------------------------------------
class Pipeline:
    def __init__(self, model: GPT2, n_stages: int = 3):
        import tiktoken

        self.model = model
        self.enc = tiktoken.get_encoding("gpt2")
        self.stages = plan_stages(model.cfg.n_layer, n_stages)
        self.label_ids = [self.enc.encode(l)[0] for l in LABELS]

    def run_stage(self, stage: Stage, input_blob: bytes, cheat: str | None = None) -> bytes:
        """Run one stage. `cheat` simulates a dishonest provider:
        - "skip":  run only half of this stage's layers (lazy provider saving compute)
        - "noise": run the layers, then perturb the activations
        """
        m = self.model
        if stage.embeds:
            texts = [CALIBRATION_TEXT, *json.loads(input_blob)["texts"]]
            xs = [m.embed(self.enc.encode(PROMPT.format(text=t))) for t in texts]
        else:
            _, xs, _ = unpack(input_blob)
            xs = [np.array(x, dtype=np.float32) for x in xs]

        last = stage.last_block
        if cheat == "skip":
            last = stage.first_block + max(1, stage.layers // 2)
        xs = [m.blocks(x, stage.first_block, last) for x in xs]
        if cheat == "noise":
            rng = np.random.default_rng(7)
            xs = [x + rng.normal(0, 0.5, size=x.shape).astype(np.float32) for x in xs]

        if stage.heads:
            scores = np.stack([m.head(x)[self.label_ids] for x in xs])  # row 0 = calibration
            calibrated = scores[1:] - scores[0]
            labels = [LABELS[int(np.argmax(s))].strip() for s in calibrated]
            return pack("result", [scores], {"labels": labels})
        return pack(f"act{stage.index}", xs)

    def run_all(self, texts: list[str], cheats: dict[int, str] | None = None) -> list[bytes]:
        blobs, blob = [], dataset_blob(texts)
        for s in self.stages:
            blob = self.run_stage(s, blob, (cheats or {}).get(s.index))
            blobs.append(blob)
        return blobs


def max_divergence(a: bytes, b: bytes) -> float:
    """Largest absolute difference between two activation/result blobs (inf if shapes differ)."""
    _, xa, _ = unpack(a)
    _, xb, _ = unpack(b)
    if len(xa) != len(xb) or any(p.shape != q.shape for p, q in zip(xa, xb)):
        return float("inf")
    return max(float(np.max(np.abs(p - q))) for p, q in zip(xa, xb))
