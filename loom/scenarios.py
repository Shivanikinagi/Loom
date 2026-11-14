"""Scripted LOOM runs that check on-chain outcomes, not just logs.

  fraud    gpu1 runs half its layers on job 1. The watcher challenges, verifiers
           vote, Reactive reroutes stage 1, slashes gpu1 on Unichain, settles.
  honest   job 2 runs clean and settles after the challenge window; the
           slashed GPU is no longer scheduled.
  timeout  gpu2 goes offline on job 3. Reactive's clock notices, reroutes the
           stage and charges a small timeout penalty.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from .indexer import JobView
from .network import Actors
from .roles import Buyer, describe

log = logging.getLogger("loom.scenarios")

TEXTS = [
    "An absolute joy from start to finish, I loved every minute of it.",
    "Broken on arrival and support never answered. A total waste of money.",
    "Fast shipping, great quality, would happily buy again.",
    "The screen cracked after two days and the refund took weeks.",
    "Honestly the best purchase I have made this year.",
    "Terrible sound, flimsy build, returned it immediately.",
]

# provider index -> (behaviour, job ids it misbehaves on)
BEHAVIOURS = {1: ("skip", {1}), 2: ("offline", {3})}


@dataclass
class Outcome:
    name: str
    job_id: int
    ok: bool
    checks: list[tuple[str, bool]] = field(default_factory=list)
    seconds: float = 0.0
    labels: list[str] = field(default_factory=list)

    def check(self, label: str, cond: bool) -> None:
        self.checks.append((label, bool(cond)))
        self.ok = self.ok and bool(cond)


def _post(a: Actors, payment: int) -> tuple[int, float]:
    p = a.net.params
    job_id, _ = a.buyer.submit(TEXTS, payment, p["stageTimeout"], p["challengeWindow"])
    return job_id, time.time()


def _wait_status(a: Actors, job_id: int, status: str, timeout: float) -> JobView:
    a.idx.wait_for(lambda: a.idx.jobs.get(job_id) is not None and a.idx.jobs[job_id].status == status, timeout)
    return a.idx.jobs[job_id]


def _events(a: Actors, job_id: int) -> list[str]:
    return [e["event"] for e in a.idx.events_for(job_id)]


def fraud(a: Actors, payment: int, timeout: float) -> Outcome:
    job_id, t0 = _post(a, payment)
    j = _wait_status(a, job_id, "Settled", timeout)
    out = Outcome("fraud caught + rerouted", job_id, True, seconds=time.time() - t0)
    ev = _events(a, job_id)
    cheater = a.providers[1].address
    out.check("watcher challenged", "Challenged" in ev)
    out.check("quorum found stage 1 faulty", "FaultResolved" in ev and j.faulty == [cheater])
    out.check("stage 1 rerouted to a standby GPU", "StageReassigned" in ev and j.providers[1] != cheater)
    slashed = [e for e in a.idx.timeline if e["chain"] == "unichain" and e["event"] == "ProviderSlashed"
               and e["args"]["provider"] == cheater]
    out.check("cheater slashed on Unichain", bool(slashed))
    out.check("job settled", j.status == "Settled")
    out.check("cheater paid nothing", cheater not in j.payouts)
    out.check("payouts == payment", sum(j.payouts.values()) == payment)
    if j.status == "Settled":
        out.labels = Buyer.result(j)["labels"]
    return out


def honest(a: Actors, payment: int, timeout: float) -> Outcome:
    job_id, t0 = _post(a, payment)
    j = _wait_status(a, job_id, "Settled", timeout)
    out = Outcome("honest job settles", job_id, True, seconds=time.time() - t0)
    ev = _events(a, job_id)
    out.check("no challenge", "Challenged" not in ev)
    out.check("settled by Reactive's clock", j.status == "Settled")
    out.check("slashed GPU not scheduled", a.providers[1].address not in j.providers)
    if j.status == "Settled":
        out.labels = Buyer.result(j)["labels"]
    return out


def timeout(a: Actors, payment: int, timeout_s: float) -> Outcome:
    job_id, t0 = _post(a, payment)
    j = _wait_status(a, job_id, "Settled", timeout_s)
    out = Outcome("offline GPU rerouted", job_id, True, seconds=time.time() - t0)
    ev = _events(a, job_id)
    sleepy = a.providers[2].address
    out.check("stage timed out", "StageTimedOut" in ev)
    out.check("rerouted away from offline GPU", sleepy not in j.providers)
    pen = [e for e in a.idx.timeline if e["chain"] == "unichain" and e["event"] == "ProviderTimedOut"
           and e["args"]["provider"] == sleepy]
    out.check("timeout penalty on Unichain", bool(pen))
    out.check("job still settled", j.status == "Settled")
    return out


ALL = {"fraud": fraud, "honest": honest, "timeout": timeout}


def run(a: Actors, names: list[str], payment: int, timeout_s: float) -> list[Outcome]:
    results = []
    for n in names:
        log.info("--- scenario: %s", n)
        o = ALL[n](a, payment, timeout_s)
        log.info("%s %s in %.1fs  %s", "PASS" if o.ok else "FAIL", o.name, o.seconds, describe(a.idx.jobs[o.job_id]))
        for label, ok in o.checks:
            log.info("   [%s] %s", "x" if ok else " ", label)
        results.append(o)
    return results
