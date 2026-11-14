"""Mirror LOOM's on-chain state from events on all three chains.

One poller per chain (Base: escrow, Unichain: bonds, Lasna: referee) feeds a
single in-memory model. Roles subscribe to decoded events; the dashboard and
the evidence report read the timeline.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from web3 import Web3

from .chain import Chain, EventDecoder, abi, get_logs
from .config import Network

log = logging.getLogger("loom.indexer")


@dataclass
class Commit:
    stage: int
    provider: str
    in_hash: bytes
    out_hash: bytes
    uri: str
    tx: str


@dataclass
class JobView:
    id: int
    buyer: str = ""
    payment: int = 0
    n_stages: int = 0
    dataset_hash: bytes = b""
    dataset_uri: str = ""
    status: str = "Open"
    providers: list[str] = field(default_factory=list)
    next_stage: int = 0
    commits: dict[int, Commit] = field(default_factory=dict)
    result_hash: bytes = b""
    challenge_deadline: int = 0
    round: int = 0
    disputed_stage: int = -1
    accused: str = ""
    challenger: str = ""
    payouts: dict[str, int] = field(default_factory=dict)
    faulty: list[str] = field(default_factory=list)


@dataclass
class ProviderView:
    address: str
    bond: int = 0
    endpoint: str = ""
    jobs_done: int = 0
    faults: int = 0
    timeouts: int = 0
    exiting: bool = False


Listener = Callable[[str, dict], None]


class Indexer:
    def __init__(self, net: Network):
        self.net = net
        self.lock = threading.RLock()
        self.jobs: dict[int, JobView] = {}
        self.providers: dict[str, ProviderView] = {}
        self.timeline: list[dict] = []
        self.listeners: list[Listener] = []
        self._stop = threading.Event()
        self._block_ts: dict[tuple[str, int], int] = {}
        self.cursor: dict[str, int] = {}
        self.sources = {
            "base": (net.contracts["escrow"], {"escrow": abi("LoomEscrow")}),
            "unichain": (net.contracts["bonds"], {"bonds": abi("LoomBonds")}),
            "lasna": (net.contracts["referee"], {"referee": abi("LoomReferee")}),
        }
        self.decoders = {k: EventDecoder(net.chains[k].w3, a) for k, (_, a) in self.sources.items()}
        self.threads: list[threading.Thread] = []

    def on(self, fn: Listener) -> None:
        self.listeners.append(fn)

    def job(self, job_id: int) -> JobView:
        with self.lock:
            return self.jobs.setdefault(job_id, JobView(job_id))

    # -- polling --------------------------------------------------------------
    def start(self) -> "Indexer":
        for name in self.sources:
            t = threading.Thread(target=self._run, args=(name,), daemon=True, name=f"idx-{name}")
            t.start()
            self.threads.append(t)
        return self

    def stop(self) -> None:
        self._stop.set()

    def sync_once(self, name: str) -> int:
        chain: Chain = self.net.chains[name]
        addr, _ = self.sources[name]
        start = self.cursor.get(name, self.net.start.get(name, 0))
        head = chain.head()
        if head < start:
            return 0
        logs = get_logs(chain, [addr], start, head)
        n = 0
        for raw in logs:
            ev = self.decoders[name].decode(raw)
            if ev is None:
                continue
            ev["chain"] = name
            ev["time"] = self._ts(chain, ev["block"])
            self._apply(name, ev)
            n += 1
        self.cursor[name] = head + 1
        return n

    def _run(self, name: str) -> None:
        chain = self.net.chains[name]
        while not self._stop.is_set():
            try:
                self.sync_once(name)
            except Exception as e:  # keep polling through flaky RPCs
                log.warning("%s poll failed: %s", name, e)
            self._stop.wait(chain.poll)

    def _ts(self, chain: Chain, block: int) -> int:
        k = (chain.name, block)
        if k not in self._block_ts:
            self._block_ts[k] = chain.timestamp(block)
        return self._block_ts[k]

    # -- state ------------------------------------------------------------------
    def _apply(self, chain: str, ev: dict) -> None:
        a, name = ev["args"], ev["event"]
        with self.lock:
            ev["seq"] = len(self.timeline)  # arrival order: causal across chains within a second
            self.timeline.append(ev)
            if chain == "base":
                self._apply_escrow(name, a, ev)
            elif chain == "unichain":
                self._apply_bonds(name, a)
        for fn in self.listeners:
            try:
                fn(chain, ev)
            except Exception:
                log.exception("listener failed on %s", name)

    def _apply_escrow(self, name: str, a: dict, ev: dict) -> None:
        if "jobId" not in a:
            return
        j = self.job(a["jobId"])
        if name == "JobCreated":
            j.buyer, j.payment, j.n_stages = a["buyer"], a["payment"], a["nStages"]
            j.dataset_hash, j.dataset_uri = a["datasetHash"], a["datasetURI"]
        elif name == "ProvidersAssigned":
            j.providers, j.status, j.next_stage = list(a["providers"]), "Running", 0
        elif name == "StageCommitted":
            s = a["stage"]
            j.commits[s] = Commit(s, a["provider"], a["inHash"], a["outHash"], a["uri"], ev["tx"])
            j.next_stage = s + 1
        elif name == "ResultProposed":
            j.status, j.result_hash, j.challenge_deadline = "Proposed", a["resultHash"], a["challengeDeadline"]
        elif name == "Challenged":
            j.status, j.round, j.disputed_stage = "Disputed", a["round"], a["stage"]
            j.accused, j.challenger = a["accused"], a["challenger"]
        elif name == "FaultResolved":
            j.faulty.append(a["faulty"])
            for s in list(j.commits):
                if s >= a["stage"]:
                    del j.commits[s]
        elif name == "StageReassigned":
            s = a["stage"]
            while len(j.providers) <= s:
                j.providers.append("")
            j.providers[s], j.next_stage, j.status = a["newProvider"], s, "Running"
            for k in list(j.commits):
                if k >= s:
                    del j.commits[k]
        elif name in ("ChallengeRejected", "ChallengeVoided"):
            j.status = "Proposed"
        elif name == "JobSettled":
            j.status = "Settled"
            j.payouts = {p: amt for p, amt in zip(a["providers"], a["amounts"])}
        elif name == "JobRefunded":
            j.status = "Refunded"

    def _apply_bonds(self, name: str, a: dict) -> None:
        addr = a.get("provider")
        if not addr:
            return
        p = self.providers.setdefault(addr, ProviderView(addr))
        if name == "ProviderBonded":
            p.bond, p.endpoint = a["bond"], a["endpoint"]
        elif name == "ProviderExiting":
            p.exiting = True
        elif name in ("ProviderSlashed", "ProviderWithdrawn"):
            p.bond = 0
        elif name == "ProviderTimedOut":
            p.bond = a["bondLeft"]
        elif name == "ReputationUpdated":
            p.jobs_done, p.faults, p.timeouts = a["jobsDone"], a["faults"], a["timeouts"]

    # -- helpers ----------------------------------------------------------------
    def events_for(self, job_id: int) -> list[dict]:
        with self.lock:
            return [e for e in self.timeline if e["args"].get("jobId") == job_id]

    def wait_for(self, pred: Callable[[], bool], timeout: float, poll: float = 0.5) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                if pred():
                    return True
            time.sleep(poll)
        return False


def short(addr: str) -> str:
    a = Web3.to_checksum_address(addr) if addr else ""
    return f"{a[:6]}..{a[-4:]}" if a else "-"


def counts(timeline: list[dict]) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for e in timeline:
        c[f"{e['chain']}:{e['event']}"] += 1
    return dict(c)
