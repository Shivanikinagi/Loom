"""LOOM command line.

  python -m loom local      [--tiny] [--scenarios fraud,honest,timeout]
  python -m loom preflight
  python -m loom faucet     --eth 0.05
  python -m loom deploy     --network testnet
  python -m loom fund       --network testnet
  python -m loom register   --network testnet
  python -m loom run        --network testnet [--scenarios ...]
  python -m loom evidence   --network testnet
  python -m loom dashboard  --network testnet|local
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from . import config
from .chain import ROOT

ETH = 10**18


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(name)-14s %(message)s", datefmt="%H:%M:%S")
    for noisy in ("web3", "urllib3", "httpx", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def cmd_local(args) -> int:
    """Three anvil chains + local Reactive relay + every actor, then the scenarios."""
    from .deploy import default_funding, deploy, fund_roles, register_providers
    from .evidence import write_report
    from .local_reactive import LocalReactive, install_mock_system
    from .network import Anvils, BlobServer, load_pipeline, start_actors
    from .scenarios import BEHAVIOURS, run

    anvils = Anvils().start()
    blobd = BlobServer(args.blob_port).start()
    try:
        install_mock_system(config.make_chains("local")["lasna"])
        deploy("local", blobd.url)
        fund_roles("local", *default_funding("local"))
        net = config.load("local")
        register_providers(net, blobd.url)
        relay = LocalReactive(net, cron_every=args.cron_every).start()
        pipe = load_pipeline(args.tiny)
        if args.interactive:
            from .dashboard import serve

            actors = start_actors(net, pipe)  # everyone honest; flip behaviours from the dashboard
            serve("local", args.port, net=net, idx=actors.idx, actors=actors, block=False)
            print(f"LOOM is running locally. Open http://127.0.0.1:{args.port}  (Ctrl+C to stop)", flush=True)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return 0
        actors = start_actors(net, pipe, BEHAVIOURS)
        time.sleep(2)  # let the referee learn the bonded providers

        results = run(actors, args.scenarios.split(","), payment=net.params["jobPayment"], timeout_s=args.timeout)
        time.sleep(3)  # trailing reputation callbacks
        for name in ("base", "unichain", "lasna"):
            actors.idx.sync_once(name)
        path = write_report(actors, results, relay_stats=relay.stats, label="local")
        logging.getLogger("loom").info("relay: %s", relay.stats)
        logging.getLogger("loom").info("report: %s", path)
        ok = all(r.ok for r in results) and relay.stats["callback_failures"] == 0
        print("\nALL SCENARIOS PASSED" if ok else "\nSOME SCENARIOS FAILED")
        if args.keep:
            input("network still running - press Enter to stop ")
        relay.stop()
        actors.idx.stop()
        return 0 if ok else 1
    finally:
        blobd.stop()
        anvils.stop()


def cmd_deploy(args) -> int:
    from .deploy import deploy

    d = deploy(args.network, args.blobd)
    print(json.dumps(d["contracts"], indent=2))
    return 0


def cmd_fund(args) -> int:
    from .deploy import default_funding, fund_roles

    fund_roles(args.network, *default_funding(args.network, args.gpus))
    return 0


def cmd_register(args) -> int:
    from .deploy import register_providers

    net = config.load(args.network)
    register_providers(net, net.blobd, args.gpus)
    return 0


def cmd_run(args) -> int:
    """Run every actor against a deployed network (Reactive does the relaying)."""
    from .evidence import write_report
    from .network import BlobServer, load_pipeline, start_actors
    from .scenarios import BEHAVIOURS, run

    net = config.load(args.network)
    blobd = BlobServer(args.blob_port).start() if args.serve_blobs else None
    pipe = load_pipeline(args.tiny)
    actors = start_actors(net, pipe, BEHAVIOURS if args.scenarios else None, n_providers=args.gpus)
    for name in ("base", "unichain", "lasna"):
        actors.idx.sync_once(name)
    if args.dashboard:
        from .dashboard import serve

        serve(args.network, args.port, net=net, idx=actors.idx, actors=actors, block=False)
        print(f"dashboard: http://127.0.0.1:{args.port}")
    try:
        if args.scenarios:
            payment = args.payment or net.params["jobPayment"]
            results = run(actors, args.scenarios.split(","), payment=payment, timeout_s=args.timeout)
            time.sleep(20)
            path = write_report(actors, results, label=args.network)
            print(f"report: {path}")
            return 0 if all(r.ok for r in results) else 1
        print("actors running - Ctrl+C to stop")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    finally:
        if blobd:
            blobd.stop()


def cmd_evidence(args) -> int:
    from .evidence import collect

    path = collect(config.load(args.network))
    print(path)
    return 0


def cmd_preflight(args) -> int:
    from .testnet import preflight

    return 0 if preflight() else 1


def cmd_faucet(args) -> int:
    from .testnet import faucet

    faucet(args.eth)
    return 0


def cmd_dashboard(args) -> int:
    from .dashboard import serve

    serve(args.network, args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="loom", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("local", help="run everything on local anvil chains")
    p.add_argument("--tiny", action="store_true", help="use the tiny random GPT-2 (no download)")
    p.add_argument("--scenarios", default="fraud,honest,timeout")
    p.add_argument("--timeout", type=float, default=150)
    p.add_argument("--cron-every", type=float, default=2.0)
    p.add_argument("--blob-port", type=int, default=8700)
    p.add_argument("--keep", action="store_true")
    p.add_argument("--interactive", action="store_true", help="no scripted scenarios: open the dashboard and drive it")
    p.add_argument("--port", type=int, default=8080)
    p.set_defaults(fn=cmd_local)

    for name, fn in (("deploy", cmd_deploy), ("fund", cmd_fund), ("register", cmd_register),
                     ("evidence", cmd_evidence)):
        p = sub.add_parser(name)
        p.add_argument("--network", default="testnet", choices=["testnet", "local"])
        p.add_argument("--blobd", default="http://127.0.0.1:8700")
        if name in ("fund", "register"):
            p.add_argument("--gpus", type=int, default=5, help="GPU provider accounts gpu0..gpuN-1")
        p.set_defaults(fn=fn)

    p = sub.add_parser("run", help="run providers, verifiers and the watcher against a deployment")
    p.add_argument("--network", default="testnet", choices=["testnet", "local"])
    p.add_argument("--scenarios", default="")
    p.add_argument("--payment", type=int, default=None, help="wei per job (default: the network's jobPayment)")
    p.add_argument("--timeout", type=float, default=600)
    p.add_argument("--tiny", action="store_true")
    p.add_argument("--gpus", type=int, default=5, help="GPU providers to run (gpu0..gpuN-1)")
    p.add_argument("--serve-blobs", action="store_true", default=True)
    p.add_argument("--blob-port", type=int, default=8700)
    p.add_argument("--dashboard", action="store_true")
    p.add_argument("--port", type=int, default=8080)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("preflight", help="check RPCs and balances before a testnet deploy")
    p.set_defaults(fn=cmd_preflight)

    p = sub.add_parser("faucet", help="swap Base Sepolia ETH for Lasna lREACT")
    p.add_argument("--eth", type=float, default=0.05)
    p.set_defaults(fn=cmd_faucet)

    p = sub.add_parser("dashboard")
    p.add_argument("--network", default="testnet", choices=["testnet", "local"])
    p.add_argument("--port", type=int, default=8080)
    p.set_defaults(fn=cmd_dashboard)

    args = ap.parse_args(argv)
    _setup_logging(args.verbose)
    sys.path.insert(0, str(ROOT))
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
