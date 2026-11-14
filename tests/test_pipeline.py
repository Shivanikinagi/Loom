"""The ML half of LOOM: splitting, determinism, and catching a cheating stage."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from loom.ml.gpt2 import GPT2
from loom.ml.pipeline import (
    TOLERANCE,
    Pipeline,
    commitment,
    dataset_blob,
    max_divergence,
    pack,
    plan_stages,
    unpack,
)
from loom.ml.tiny import make_tiny_gpt2

TEXTS = [
    "An absolute joy from start to finish, I loved every minute.",
    "Broken on arrival and support never answered. Waste of money.",
    "It does what it says.",
]

REAL = Path(os.environ.get("LOOM_MODEL_DIR", "models/gpt2"))


@pytest.fixture(scope="module")
def pipe(tmp_path_factory) -> Pipeline:
    d = make_tiny_gpt2(tmp_path_factory.mktemp("tiny"))
    return Pipeline(GPT2(d), n_stages=3)


def test_plan_splits_layers_evenly():
    assert [(s.first_block, s.last_block) for s in plan_stages(12, 3)] == [(0, 4), (4, 8), (8, 12)]
    assert [s.layers for s in plan_stages(6, 4)] == [2, 2, 1, 1]
    stages = plan_stages(12, 3)
    assert stages[0].embeds and not stages[0].heads
    assert stages[-1].heads and not stages[-1].embeds


def test_blob_roundtrip():
    a = np.arange(12, dtype=np.float32).reshape(3, 4) / 7
    kind, xs, meta = unpack(pack("act0", [a, a[:1]], {"k": 1}))
    assert kind == "act0" and meta == {"k": 1}
    np.testing.assert_allclose(xs[0], np.round(a, 4))
    assert xs[1].shape == (1, 4)


def test_honest_runs_are_bit_identical(pipe):
    a = pipe.run_all(TEXTS)
    b = pipe.run_all(TEXTS)
    assert [commitment(x) for x in a] == [commitment(x) for x in b]


def test_commitments_chain(pipe):
    blobs = pipe.run_all(TEXTS)
    # Each stage's input is exactly the previous stage's committed output.
    assert pipe.run_stage(pipe.stages[1], blobs[0]) == blobs[1]
    assert pipe.run_stage(pipe.stages[2], blobs[1]) == blobs[2]
    assert pipe.run_stage(pipe.stages[0], dataset_blob(TEXTS)) == blobs[0]


def test_pipeline_matches_unsplit_model(pipe):
    """Splitting across providers must not change the answer."""
    _, [scores], meta = unpack(pipe.run_all(TEXTS)[-1])
    for i, t in enumerate(TEXTS):
        logits = pipe.model.forward(pipe.enc.encode(f"Review: {t}\nSentiment:"))
        np.testing.assert_allclose(scores[i], logits[pipe.label_ids], atol=1e-3)
    assert len(meta["labels"]) == len(TEXTS)


@pytest.mark.parametrize("cheat", ["skip", "noise"])
def test_verifier_pins_the_cheating_stage(pipe, cheat):
    honest = pipe.run_all(TEXTS)
    bad = pipe.run_all(TEXTS, cheats={1: cheat})

    # Stage 0 is untouched; stage 1 and everything downstream differ.
    assert commitment(bad[0]) == commitment(honest[0])
    assert commitment(bad[1]) != commitment(honest[1])
    assert commitment(bad[2]) != commitment(honest[2])

    # A verifier re-runs only the disputed stage from its agreed input.
    recomputed = pipe.run_stage(pipe.stages[1], bad[0])
    assert max_divergence(recomputed, bad[1]) > TOLERANCE * 10

    # Stage 2 was honest *given its input*: re-running it from the bad input
    # reproduces the committed output, so stage 2 is not blamed.
    assert max_divergence(pipe.run_stage(pipe.stages[2], bad[1]), bad[2]) <= TOLERANCE


def test_dataset_commitment_is_canonical():
    assert commitment(dataset_blob(["a", "b"])) == commitment(dataset_blob(["a", "b"]))
    assert json.loads(dataset_blob(["x"]))["texts"] == ["x"]


@pytest.mark.skipif(not (REAL / "model.safetensors").exists(), reason="real GPT-2 weights not downloaded")
def test_real_gpt2_classifies_sentiment():
    p = Pipeline(GPT2(REAL), n_stages=3)
    _, _, meta = unpack(p.run_all(TEXTS[:2])[-1])
    assert meta["labels"] == ["positive", "negative"]
