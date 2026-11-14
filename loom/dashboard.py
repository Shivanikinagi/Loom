"""Live LOOM dashboard: one page over the cross-chain indexer.

Read-only against any deployment (`python -m loom dashboard`), or interactive
when started next to running actors (`python -m loom local --interactive`),
where it can post jobs and switch any GPU into cheating or offline mode.
"""

from __future__ import annotations

import logging
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .chain import ROOT
from .config import Network
from .evidence import SELECTORS
from .indexer import Indexer

log = logging.getLogger("loom.dashboard")
WEB = ROOT / "web"


def _hex(v) -> str:
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    return v


def _jsonable(v):
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    if isinstance(v, int) and abs(v) > 2**53:
        return str(v)
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    return v


class ModeIn(BaseModel):
    mode: str


class JobIn(BaseModel):
    texts: list[str] | None = None


def make_app(net: Network, idx: Indexer, actors=None) -> FastAPI:
    app = FastAPI(title="LOOM dashboard")
    labels_cache: dict[int, list[str]] = {}
    pipe_stages = []
    if actors is not None:
        pipe_stages = [{"stage": s.index, "first": s.first_block, "last": s.last_block - 1} for s in actors.pipe.stages]

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    @app.get("/api/state")
    def state():
        from .roles import Buyer

        with idx.lock:
            jobs = []
            for j in sorted(idx.jobs.values(), key=lambda x: x.id, reverse=True):
                jobs.append({
                    "id": j.id, "status": j.status, "buyer": j.buyer, "payment": str(j.payment),
                    "nStages": j.n_stages, "providers": j.providers, "nextStage": j.next_stage,
                    "commits": {str(s): {"provider": c.provider, "outHash": _hex(c.out_hash), "uri": c.uri, "tx": c.tx}
                                for s, c in j.commits.items()},
                    "disputedStage": j.disputed_stage, "accused": j.accused, "challenger": j.challenger,
                    "round": j.round, "faulty": j.faulty, "payouts": {k: str(v) for k, v in j.payouts.items()},
                    "challengeDeadline": j.challenge_deadline, "labels": labels_cache.get(j.id),
                })
            providers = [{"address": p.address, "bond": str(p.bond), "jobsDone": p.jobs_done, "faults": p.faults,
                          "timeouts": p.timeouts, "exiting": p.exiting} for p in idx.providers.values()]
            timeline = [{"chain": e["chain"], "event": e["event"], "tx": e["tx"], "time": e["time"], "seq": e["seq"],
                         "args": _jsonable(e["args"])} for e in idx.timeline[-400:]]
            settled = [j for j in idx.jobs.values() if j.status == "Settled" and j.id not in labels_cache
                       and (j.n_stages - 1) in j.commits]
        for j in settled:  # fetch result labels once, outside the lock
            try:
                labels_cache[j.id] = Buyer.result(j)["labels"]
            except Exception:  # noqa: BLE001 - blob store may be remote/unavailable
                labels_cache[j.id] = []

        names = {}
        if actors is not None:
            for p in actors.providers:
                names[p.address.lower()] = {"name": p.name, "mode": p.mode if p.cheat_jobs is None else
                                            (p.mode + " on jobs " + ",".join(map(str, sorted(p.cheat_jobs))))
                                            if p.mode != "honest" else "honest"}
            for v in actors.verifiers:
                names[v.acct.address.lower()] = {"name": v.name}
            names[actors.watcher.acct.address.lower()] = {"name": "watcher"}
            names[actors.buyer.acct.address.lower()] = {"name": "buyer"}
        return {
            "network": net.name,
            "interactive": actors is not None,
            "chains": {k: {"chainId": c.chain_id, "explorer": c.explorer} for k, c in net.chains.items()},
            "contracts": net.contracts,
            "stages": pipe_stages,
            "jobs": jobs,
            "providers": providers,
            "timeline": timeline,
            "names": names,
            "reports": _jsonable(actors.reports()[-60:]) if actors is not None else [],
            "selectors": SELECTORS,
        }

    @app.post("/api/jobs")
    def post_job(body: JobIn):
        if actors is None:
            raise HTTPException(403, "read-only dashboard")
        from .scenarios import TEXTS

        p = net.params
        def go():
            try:
                actors.buyer.submit(body.texts or TEXTS, p.get("demoPayment", 3 * 10**17 if net.name == "local" else 10**16),
                                    p["stageTimeout"], p["challengeWindow"])
            except Exception:
                log.exception("job submit failed")
        threading.Thread(target=go, daemon=True).start()
        return {"ok": True}

    @app.post("/api/providers/{addr}/mode")
    def set_mode(addr: str, body: ModeIn):
        if actors is None:
            raise HTTPException(403, "read-only dashboard")
        for p in actors.providers:
            if p.address.lower() == addr.lower():
                if body.mode not in p.MODES:
                    raise HTTPException(400, f"mode must be one of {p.MODES}")
                p.mode, p.cheat_jobs = body.mode, None
                return {"ok": True, "name": p.name, "mode": p.mode}
        raise HTTPException(404, "unknown provider")

    return app


def serve(network: str, port: int = 8080, net: Network | None = None, idx: Indexer | None = None, actors=None,
          block: bool = True):
    import uvicorn

    from .config import load

    net = net or load(network)
    if idx is None:
        idx = Indexer(net).start()
    app = make_app(net, idx, actors)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    log.info("dashboard on http://127.0.0.1:%d", port)
    if block:
        server.run()
        return None
    t = threading.Thread(target=server.run, daemon=True, name="dashboard")
    t.start()
    return server


__all__ = ["serve", "make_app"]
