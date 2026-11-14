"""Turn the cross-chain event timeline into a verifiable evidence report.

Every row is an on-chain event with its transaction hash (and explorer link on
testnet). Loop latencies are measured from block timestamps, so anyone can
re-derive them from the chain.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from web3 import Web3

from .chain import ROOT, abi
from .config import Network
from .indexer import Indexer, short

OUT = ROOT / "evidence"

# Legs of the loop worth timing: (label, from (chain, event), to (chain, event)).
LEGS = [
    ("schedule: job posted -> providers assigned", ("base", "JobCreated"), ("base", "ProvidersAssigned")),
    ("challenge -> Reactive counts quorum", ("base", "Challenged"), ("lasna", "QuorumReached")),
    ("quorum vote -> fault resolved on Base", ("base", "VerdictVote"), ("base", "FaultResolved")),
    ("fault resolved on Base -> slashed on Unichain", ("base", "FaultResolved"), ("unichain", "ProviderSlashed")),
    ("deadline missed -> stage rerouted", ("lasna", "TimerFired"), ("base", "StageReassigned")),
    ("window closed -> settled", ("base", "ResultProposed"), ("base", "JobSettled")),
    ("settled -> reputation on Unichain", ("base", "JobSettled"), ("unichain", "ReputationUpdated")),
]


PHASES = ["None", "Assigning", "Running", "Proposed", "Disputed", "Resolving", "Done"]


def _selectors() -> dict[str, str]:
    out = {}
    for contract, chain in (("LoomEscrow", "base"), ("LoomBonds", "unichain")):
        for item in abi(contract):
            if item.get("type") == "function":
                sig = f"{item['name']}({','.join(i['type'] for i in item['inputs'])})"
                out[Web3.keccak(text=sig)[:4].hex()] = f"{chain}.{item['name']}"
    return out


SELECTORS = _selectors()


def _job_events(idx: Indexer, job_id: int) -> list[dict]:
    """All events about a job across chains, plus the Unichain events it caused."""
    with idx.lock:
        evs = [e for e in idx.timeline if e["args"].get("jobId") == job_id]
        j = idx.jobs.get(job_id)
        settled_tx_times = [e["time"] for e in evs if e["event"] == "JobSettled"]
        if j and settled_tx_times:
            # ReputationUpdated has no jobId; attach the ones right after this job's settlement.
            # Only the first recordSuccess transaction after this job settled.
            t = settled_tx_times[0]
            provs = {p.lower() for p in j.providers}
            rep = [e for e in idx.timeline if e["chain"] == "unichain" and e["event"] == "ReputationUpdated"
                   and e["args"]["provider"].lower() in provs and e["time"] >= t]
            if rep:
                first_tx = min(rep, key=lambda e: e["seq"])["tx"]
                evs += [e for e in rep if e["tx"] == first_tx]
    return sorted(evs, key=lambda e: (e["time"], e.get("seq", 0)))


def _legs(evs: list[dict]) -> list[dict]:
    out = []
    for label, (c1, e1), (c2, e2) in LEGS:
        a = next((e for e in evs if e["chain"] == c1 and e["event"] == e1), None)
        if a is None:
            continue
        b = next((e for e in evs if e["chain"] == c2 and e["event"] == e2 and e["time"] >= a["time"]), None)
        if b is None:
            continue
        out.append({"leg": label, "seconds": b["time"] - a["time"], "from_tx": a["tx"], "to_tx": b["tx"],
                    "from_chain": c1, "to_chain": c2})
    return out


def _fmt_args(e: dict) -> str:
    a = e["args"]
    keep = []
    for k in ("stage", "round", "faulty", "accused", "faulty", "newProvider", "provider", "replacement", "amount",
              "bounty", "votesFaulty", "votesHonest", "phase"):
        if k in a:
            v = a[k]
            if isinstance(v, str) and v.startswith("0x") and len(v) == 42:
                v = short(v)
            elif isinstance(v, int) and k in ("amount", "bounty"):
                v = f"{v / 1e18:g} ETH"
            keep.append(f"{k}={v}")
    if e["event"] == "ProvidersSelected" or e["event"] == "ProvidersAssigned":
        keep.append("providers=" + ",".join(short(p) for p in a["providers"]))
    if e["event"] == "CallbackSent":
        sel = bytes(a["selector"]).hex()
        keep.append("-> " + SELECTORS.get(sel, f"chain {a['chainId']} 0x{sel}") + "()")
    if e["event"] == "TimerFired":
        keep = [f"phase={PHASES[a['phase']]} expired"]
    return " ".join(dict.fromkeys(keep))


def _link(net: Network, chain: str, tx: str) -> str:
    tx = tx if tx.startswith("0x") else "0x" + tx
    c = net.chains[chain]
    return f"[`{tx[:10]}…`]({c.tx_url(tx)})" if c.explorer else f"`{tx[:10]}…`"


def render(net: Network, idx: Indexer, results=None, reports=None, relay_stats=None) -> tuple[str, dict]:
    lines = [f"# LOOM evidence ({net.name})", "", f"Generated {time.strftime('%Y-%m-%d %H:%M:%S %Z')}.", ""]
    if net.name == "local":
        lines += ["> Local run on three anvil chains with the real chain IDs. Reactive's relaying is emulated by",
                  "> `loom/local_reactive.py`; on testnet the same contracts are driven by Reactive Lasna itself.", ""]
    lines += ["## Contracts", "", "| Role | Chain | Address |", "|---|---|---|"]
    for role, chain in (("LoomReferee (reactive)", "lasna"), ("LoomEscrow", "base"), ("LoomBonds", "unichain")):
        key = {"lasna": "referee", "base": "escrow", "unichain": "bonds"}[chain]
        addr = net.contracts[key]
        c = net.chains[chain]
        a = f"[`{addr}`]({c.explorer}/address/{addr})" if c.explorer else f"`{addr}`"
        lines.append(f"| {role} | {chain} ({c.chain_id}) | {a} |")
    lines.append("")

    data = {"network": net.name, "contracts": net.contracts, "jobs": []}
    job_ids = [r.job_id for r in results] if results else sorted(idx.jobs)
    for job_id in job_ids:
        evs = _job_events(idx, job_id)
        if not evs:
            continue
        j = idx.jobs[job_id]
        res = next((r for r in (results or []) if r.job_id == job_id), None)
        title = f"Job {job_id}" + (f" — {res.name}" if res else "")
        lines += [f"## {title}", ""]
        if res:
            lines += [f"**{'PASS' if res.ok else 'FAIL'}** in {res.seconds:.1f}s", ""]
            lines += [f"- [{'x' if ok else ' '}] {label}" for label, ok in res.checks]
            if res.labels:
                lines += ["", f"Result labels: {', '.join(res.labels)}"]
            lines.append("")
        t0 = evs[0]["time"]
        sent = [e for e in evs if e["event"] == "CallbackSent"]
        n_react = len({e["tx"] for e in evs if e["chain"] == "lasna"})
        lines += [f"Reactive transactions on Lasna: **{n_react}**, callbacks requested: **{len(sent)}** "
                  f"({sum(1 for e in sent if e['args']['chainId'] == net.base.chain_id)} to Base, "
                  f"{sum(1 for e in sent if e['args']['chainId'] == net.unichain.chain_id)} to Unichain).", ""]
        lines += ["| t+s | chain | event | details | tx |", "|---:|---|---|---|---|"]
        for e in evs:
            lines.append(f"| {e['time'] - t0} | {e['chain']} | {e['event']} | {_fmt_args(e)} | {_link(net, e['chain'], e['tx'])} |")
        legs = _legs(evs)
        if legs:
            lines += ["", "| loop leg | seconds |", "|---|---:|"]
            lines += [f"| {l['leg']} | {l['seconds']} |" for l in legs]
        lines.append("")
        data["jobs"].append({
            "jobId": job_id, "status": j.status, "providers": j.providers, "payouts": {k: str(v) for k, v in j.payouts.items()},
            "scenario": res.name if res else None, "passed": res.ok if res else None,
            "checks": res.checks if res else None, "legs": legs,
            "events": [{"chain": e["chain"], "event": e["event"], "tx": e["tx"], "time": e["time"], "block": e["block"]}
                       for e in evs],
        })

    if reports:
        lines += ["## What the agents saw", "", "| role | job | action | detail |", "|---|---|---|---|"]
        for r in reports:
            action = r.get("action") or ("vote FAULTY" if r.get("faulty") else "vote ok" if "faulty" in r else "")
            detail = r.get("detail", "")
            if "compute_s" in r:
                detail = f"stage {r['stage']} in {r['compute_s']}s" + (f" (cheat: {r['cheat']})" if r.get("cheat") else "")
            lines.append(f"| {r['role']} | {r.get('job', '')} | {action} | {detail} |")
        lines.append("")
        data["reports"] = [{k: (v if not isinstance(v, float) or v == v and v != float("inf") else str(v))
                            for k, v in r.items()} for r in reports]
    if relay_stats:
        lines += ["## Local relay", "", f"`{relay_stats}`", ""]
        data["relay"] = relay_stats
    return "\n".join(lines), data


def write_report(actors, results, relay_stats=None, label: str = "run") -> Path:
    md, data = render(actors.net, actors.idx, results, actors.reports(), relay_stats)
    OUT.mkdir(exist_ok=True)
    (OUT / f"{label}-run.json").write_text(json.dumps(data, indent=2, default=str))
    path = OUT / f"{label}-run.md"
    path.write_text(md, encoding="utf-8")
    return path


def collect(net: Network) -> Path:
    idx = Indexer(net)
    for name in ("base", "unichain", "lasna"):
        idx.sync_once(name)
    md, data = render(net, idx)
    OUT.mkdir(exist_ok=True)
    (OUT / f"{net.name}.json").write_text(json.dumps(data, indent=2, default=str))
    path = OUT / f"{net.name}.md"
    path.write_text(md, encoding="utf-8")
    return path
