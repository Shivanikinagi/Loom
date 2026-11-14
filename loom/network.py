"""Bring up the LOOM actors (and, locally, the chains they run on)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

from .blobd import BlobClient, make_app
from .chain import ROOT
from .config import LOCAL, Network
from .indexer import Indexer
from .ml.gpt2 import GPT2
from .ml.pipeline import Pipeline
from .ml.tiny import make_tiny_gpt2
from .roles import AuditPolicy, Buyer, Provider, Verifier, Watcher

log = logging.getLogger("loom.network")

MODEL_DIR = ROOT / "models" / "gpt2"
TINY_DIR = ROOT / ".loom" / "tiny-gpt2"


def load_pipeline(tiny: bool) -> Pipeline:
    if tiny or not (MODEL_DIR / "model.safetensors").exists():
        if not tiny:
            log.warning("GPT-2 weights not found in %s - using the tiny model (python -m loom.ml.fetch_model)", MODEL_DIR)
        return Pipeline(GPT2(make_tiny_gpt2(TINY_DIR)), n_stages=3)
    return Pipeline(GPT2(MODEL_DIR), n_stages=3)


# ---------------------------------------------------------------- processes
class Anvils:
    PORTS = {"base": 8545, "unichain": 8546, "lasna": 8547}

    def __init__(self):
        self.procs: list[subprocess.Popen] = []

    def start(self) -> "Anvils":
        exe = shutil.which("anvil")
        if not exe:
            raise SystemExit("anvil not found - install Foundry")
        for name, port in self.PORTS.items():
            cid = LOCAL[name]["chainId"]
            self.procs.append(subprocess.Popen([exe, "--port", str(port), "--chain-id", str(cid), "--silent"],
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for name, port in self.PORTS.items():
            _wait_rpc(f"http://127.0.0.1:{port}")
        return self

    def stop(self) -> None:
        for p in self.procs:
            p.terminate()
        for p in self.procs:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()


def _wait_rpc(url: str, timeout: float = 30) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []}, timeout=2)
            return
        except requests.RequestException:
            time.sleep(0.3)
    raise RuntimeError(f"{url} did not start")


class BlobServer:
    def __init__(self, port: int = 8700, store: Path | None = None):
        import uvicorn

        app = make_app(store) if store else make_app()
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, daemon=True, name="blobd")
        self.url = f"http://127.0.0.1:{port}"

    def start(self) -> "BlobServer":
        self.thread.start()
        end = time.time() + 15
        while time.time() < end:
            try:
                requests.get(f"{self.url}/health", timeout=1)
                return self
            except requests.RequestException:
                time.sleep(0.2)
        raise RuntimeError("blob server did not start")

    def stop(self) -> None:
        self.server.should_exit = True


# ------------------------------------------------------------------- actors
@dataclass
class Actors:
    net: Network
    pipe: Pipeline
    idx: Indexer
    buyer: Buyer
    providers: list[Provider] = field(default_factory=list)
    verifiers: list[Verifier] = field(default_factory=list)
    watcher: Watcher | None = None

    def reports(self) -> list[dict]:
        out = []
        for w in [*self.providers, *self.verifiers, *([self.watcher] if self.watcher else [])]:
            out.extend(w.reports)
        return sorted(out, key=lambda r: r["at"])


def start_actors(net: Network, pipe: Pipeline, behaviours: dict[int, tuple[str, set[int] | None]] | None = None,
                 n_providers: int = 5, audit_rate: float = 1.0) -> Actors:
    """Start providers, verifiers and the watcher agent against a deployed network.

    `behaviours` maps provider index -> (mode, job ids it misbehaves on).
    """
    behaviours = behaviours or {}
    blobs = BlobClient(net.blobd)
    idx = Indexer(net)
    layers = [s.layers for s in pipe.stages]
    a = Actors(net, pipe, idx, Buyer(net, blobs, layers))
    for i in range(n_providers):
        mode, jobs = behaviours.get(i, ("honest", None))
        a.providers.append(Provider(net, idx, pipe, blobs, i, mode, jobs).start())
    for i in range(3):
        a.verifiers.append(Verifier(net, idx, pipe, i).start())
    a.watcher = Watcher(net, idx, pipe, AuditPolicy(base_rate=audit_rate)).start()
    idx.start()
    return a
