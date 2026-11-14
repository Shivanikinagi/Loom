"""Full LOOM loop on three local anvil chains (slow: about two minutes).

Runs the fraud, honest and timeout scenarios through the local Reactive relay
and checks on-chain outcomes on all three chains.
"""

from __future__ import annotations

import json
import shutil

import pytest

from loom.__main__ import main
from loom.evidence import OUT

pytestmark = [pytest.mark.e2e, pytest.mark.skipif(shutil.which("anvil") is None, reason="needs Foundry's anvil")]


def test_local_network_runs_every_scenario():
    assert main(["local", "--tiny"]) == 0
    report = json.loads((OUT / "local-run.json").read_text())
    jobs = {j["jobId"]: j for j in report["jobs"]}
    assert all(j["passed"] for j in jobs.values())
    assert report["relay"]["callback_failures"] == 0
    chains = {e["chain"] for e in jobs[1]["events"]}
    assert chains == {"base", "unichain", "lasna"}, "the fraud loop touches all three chains"
