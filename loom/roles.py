"""The off-chain actors of LOOM.

- Provider:  a GPU that runs its assigned stage and commits the output hash.
- Verifier:  re-runs a disputed stage from its agreed input and votes.
- Watcher:   the challenger agent. Audits proposed results by re-running the
             pipeline and challenges when a stage is provably wrong.
- Buyer:     posts jobs and reads results.

None of them talk to each other: they only read events and send transactions.
Every decision about what happens next is taken by LoomReferee on Reactive.
"""

from __future__ import annotations

import logging
import queue
import random
import threading
import time
from dataclasses import dataclass, field

from eth_hash.auto import keccak

from .blobd import BlobClient
from .config import Network
from .indexer import Indexer, JobView, short
from .ml.pipeline import TOLERANCE, Pipeline, dataset_blob, max_divergence, unpack

log = logging.getLogger("loom.roles")


class Worker:
    """Serialises a role's actions on its own thread."""

    def __init__(self, name: str):
        self.name = name
        self.q: queue.Queue = queue.Queue()
        self.thread = threading.Thread(target=self._loop, daemon=True, name=name)
        self.reports: list[dict] = []

    def start(self):
        self.thread.start()
        return self

    def _loop(self):
        while True:
            item = self.q.get()
            try:
                self.handle(item)
            except Exception as e:
                log.warning("%s: %s", self.name, e)

    def handle(self, item) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def report(self, **kw) -> None:
        kw["at"] = time.time()
        kw["role"] = self.name
        self.reports.append(kw)


def input_for(job: JobView, stage: int) -> tuple[str, bytes]:
    """URI and expected hash of a stage's input blob."""
    if stage == 0:
        return job.dataset_uri, job.dataset_hash
    c = job.commits[stage - 1]
    return c.uri, c.out_hash


# ---------------------------------------------------------------- provider
class Provider(Worker):
    MODES = ("honest", "skip", "noise", "offline")

    def __init__(self, net: Network, idx: Indexer, pipe: Pipeline, blobs: BlobClient, n: int,
                 mode: str = "honest", cheat_jobs: set[int] | None = None):
        super().__init__(f"gpu{n}")
        assert mode in self.MODES
        self.net, self.idx, self.pipe, self.blobs = net, idx, pipe, blobs
        self.acct = net.role(f"gpu{n}")
        self.mode = mode
        self.cheat_jobs = cheat_jobs  # None = misbehave on every job
        self.done: set[tuple[int, int]] = set()
        idx.on(self._on_event)

    @property
    def address(self) -> str:
        return self.acct.address

    def _on_event(self, chain: str, ev: dict) -> None:
        if chain != "base":
            return
        name, a = ev["event"], ev["args"]
        if name == "StageReassigned":
            # The stage and everything after it must be recomputed.
            self.done = {(j, s) for (j, s) in self.done if not (j == a["jobId"] and s >= a["stage"])}
        if name in ("ProvidersAssigned", "StageCommitted", "StageReassigned"):
            self.q.put(a["jobId"])

    def misbehaves_on(self, job_id: int) -> bool:
        return self.mode != "honest" and (self.cheat_jobs is None or job_id in self.cheat_jobs)

    def handle(self, job_id: int) -> None:
        with self.idx.lock:
            j = self.idx.jobs.get(job_id)
            if j is None or j.status != "Running":
                return
            s = j.next_stage
            if s >= len(j.providers) or j.providers[s].lower() != self.address.lower() or (job_id, s) in self.done:
                return
            uri, in_hash = input_for(j, s)
        self.done.add((job_id, s))

        cheat = self.mode if self.misbehaves_on(job_id) else None
        if cheat == "offline":
            self.report(job=job_id, stage=s, action="went offline")
            log.info("%s offline on job %s stage %s", self.name, job_id, s)
            return

        inp = BlobClient.get(uri, in_hash)
        t0 = time.time()
        out = self.pipe.run_stage(self.pipe.stages[s], inp, cheat=cheat)
        compute = time.time() - t0
        out_uri = self.blobs.put(out)
        out_hash = keccak(out)
        rcpt = self.net.base.send(self.acct, self.net.escrow().functions.commitStage(job_id, s, in_hash, out_hash, out_uri))
        self.report(job=job_id, stage=s, action="commit", cheat=cheat, compute_s=round(compute, 3),
                    tx=rcpt["transactionHash"].hex())
        log.info("%s committed job %s stage %s%s (%.2fs)", self.name, job_id, s, f" [{cheat}]" if cheat else "", compute)


# ---------------------------------------------------------------- verifier
class Verifier(Worker):
    def __init__(self, net: Network, idx: Indexer, pipe: Pipeline, n: int):
        super().__init__(f"verifier{n}")
        self.net, self.idx, self.pipe = net, idx, pipe
        self.acct = net.role(f"verifier{n}")
        idx.on(self._on_event)

    def _on_event(self, chain: str, ev: dict) -> None:
        if chain == "base" and ev["event"] == "Challenged":
            a = ev["args"]
            self.q.put((a["jobId"], a["round"], a["stage"]))

    def handle(self, item) -> None:
        job_id, rnd, s = item
        with self.idx.lock:
            j = self.idx.jobs[job_id]
            uri, in_hash = input_for(j, s)
            out_commit = j.commits[s]

        try:
            inp = BlobClient.get(uri, in_hash)
            committed = BlobClient.get(out_commit.uri, out_commit.out_hash)
        except Exception as e:  # withheld or tampered data counts against the provider
            faulty, div, why = True, float("inf"), f"data unavailable: {e}"
        else:
            mine = self.pipe.run_stage(self.pipe.stages[s], inp)
            div = max_divergence(mine, committed)
            faulty, why = div > TOLERANCE, f"max |delta| = {div:.4g}"

        try:
            rcpt = self.net.base.send(self.acct, self.net.escrow().functions.vote(job_id, rnd, faulty))
            tx = rcpt["transactionHash"].hex()
        except Exception as e:  # quorum already reached and the dispute closed
            tx, why = None, f"{why}; vote not needed ({type(e).__name__})"
        self.report(job=job_id, round=rnd, stage=s, faulty=faulty, divergence=div, detail=why, tx=tx)
        log.info("%s: job %s stage %s -> %s (%s)", self.name, job_id, s, "FAULTY" if faulty else "ok", why)


# ----------------------------------------------------------------- watcher
@dataclass
class AuditPolicy:
    """When is re-running a whole pipeline worth it?

    Auditing costs compute; catching a cheater pays half its bond. New or
    previously faulty providers are always audited; proven ones are sampled.
    """

    base_rate: float = 1.0
    trusted_after: int = 5
    rng: random.Random = field(default_factory=lambda: random.Random(42))

    def should_audit(self, providers: list) -> tuple[bool, str]:
        risky = [p for p in providers if p is None or p.faults > 0 or p.jobs_done < self.trusted_after]
        if risky:
            return True, f"{len(risky)} unproven provider(s) in pipeline"
        hit = self.rng.random() < self.base_rate
        return hit, f"sampled at {self.base_rate:.0%}"


class Watcher(Worker):
    def __init__(self, net: Network, idx: Indexer, pipe: Pipeline, policy: AuditPolicy | None = None):
        super().__init__("watcher")
        self.net, self.idx, self.pipe = net, idx, pipe
        self.acct = net.role("challenger")
        self.policy = policy or AuditPolicy()
        idx.on(self._on_event)

    def _on_event(self, chain: str, ev: dict) -> None:
        if chain == "base" and ev["event"] == "ResultProposed":
            self.q.put(ev["args"]["jobId"])

    def handle(self, job_id: int) -> None:
        with self.idx.lock:
            j = self.idx.jobs[job_id]
            if j.status != "Proposed":
                return
            provs = [self.idx.providers.get(p) for p in j.providers]
            commits = [j.commits[s] for s in range(j.n_stages)]
            dataset_uri, dataset_hash = j.dataset_uri, j.dataset_hash

        audit, why = self.policy.should_audit(provs)
        if not audit:
            self.report(job=job_id, action="skip audit", detail=why)
            return

        # Walk the pipeline. Accept each committed stage that our own re-run
        # reproduces (within tolerance) and claim our own hash only from the
        # first stage that is provably wrong. That way the on-chain divergence
        # point lands exactly on the cheater, never on harmless float noise.
        inp = BlobClient.get(dataset_uri, dataset_hash)
        claimed: list[bytes] = []
        bad_stage, div = None, 0.0
        for s, c in enumerate(commits):
            mine = self.pipe.run_stage(self.pipe.stages[s], inp)
            if bad_stage is None:
                try:
                    theirs = BlobClient.get(c.uri, c.out_hash)
                    div = max_divergence(mine, theirs)
                except Exception:
                    theirs, div = None, float("inf")
                if theirs is not None and div <= TOLERANCE:
                    claimed.append(c.out_hash)
                    inp = theirs
                    continue
                bad_stage = s
            claimed.append(keccak(mine))
            inp = mine

        if bad_stage is None:
            self.report(job=job_id, action="audit passed", detail=why)
            log.info("watcher: job %s audit passed", job_id)
            return

        bond = self.net.params["minChallengeBond"]
        rcpt = self.net.base.send(self.acct, self.net.escrow().functions.challenge(job_id, claimed), value=bond)
        self.report(job=job_id, action="challenge", stage=bad_stage, divergence=div, detail=why,
                    tx=rcpt["transactionHash"].hex())
        log.info("watcher: CHALLENGED job %s at stage %s (max |delta| = %.4g)", job_id, bad_stage, div)


# ------------------------------------------------------------------- buyer
class Buyer:
    def __init__(self, net: Network, blobs: BlobClient, pipe_layers: list[int]):
        self.net, self.blobs, self.layers = net, blobs, pipe_layers
        self.acct = net.role("buyer")

    def submit(self, texts: list[str], payment: int, stage_timeout: int, challenge_window: int) -> tuple[int, str]:
        data = dataset_blob(texts)
        uri = self.blobs.put(data)
        fn = self.net.escrow().functions.createJob(keccak(data), uri, self.layers, stage_timeout, challenge_window)
        rcpt = self.net.base.send(self.acct, fn, value=payment)
        ev = self.net.escrow().events.JobCreated().process_receipt(rcpt)[0]
        return ev["args"]["jobId"], rcpt["transactionHash"].hex()

    @staticmethod
    def result(job: JobView) -> dict:
        c = job.commits[job.n_stages - 1]
        _, [scores], meta = unpack(BlobClient.get(c.uri, c.out_hash))
        return {"labels": meta["labels"], "scores": scores.tolist()}


def describe(job: JobView) -> str:
    stages = ", ".join(f"s{i}:{short(p)}" for i, p in enumerate(job.providers))
    return f"job {job.id} [{job.status}] {stages}"
