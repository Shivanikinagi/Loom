"""Thin Web3 layer shared by every LOOM role: contracts, transactions, logs."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3._utils.events import get_event_data
from web3.types import LogReceipt

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "contracts" / "out"


def artifact(name: str, file: str | None = None) -> dict:
    path = ARTIFACTS / f"{file or name}.sol" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run `forge build` in contracts/")
    return json.loads(path.read_text())


def abi(name: str, file: str | None = None) -> list:
    return artifact(name, file)["abi"]


@dataclass
class Chain:
    """One EVM chain plus the accounts that act on it."""

    name: str
    chain_id: int
    rpc: str
    explorer: str = ""
    poll: float = 1.0
    w3: Web3 = field(init=False)
    _locks: dict[str, threading.Lock] = field(default_factory=dict, init=False)
    _nonces: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.w3 = Web3(Web3.HTTPProvider(self.rpc, request_kwargs={"timeout": 30}))

    def contract(self, address: str, name: str):
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi(name))

    def tx_url(self, tx_hash: str) -> str:
        return f"{self.explorer.rstrip('/')}/tx/{tx_hash}" if self.explorer else tx_hash

    # -- transactions --------------------------------------------------------
    def send(self, acct: LocalAccount, fn=None, *, to: str | None = None, value: int = 0, data: bytes = b"",
             gas: int | None = None, retries: int = 3) -> dict:
        """Sign and send, wait for the receipt, raise if it reverted."""
        lock = self._locks.setdefault(acct.address, threading.Lock())
        with lock:
            for attempt in range(retries):
                nonce = max(self.w3.eth.get_transaction_count(acct.address, "pending"), self._nonces.get(acct.address, 0))
                # Explicit fees: Lasna suggests a 0 tip but rejects anything below 1 wei.
                fee = self.w3.eth.gas_price
                base = {"from": acct.address, "nonce": nonce, "value": value, "chainId": self.chain_id,
                        "maxFeePerGas": fee * 2, "maxPriorityFeePerGas": max(1, min(fee, Web3.to_wei(1, "gwei")))}
                if gas:
                    base["gas"] = gas
                try:
                    if fn is not None:
                        tx = fn.build_transaction(base)
                    else:
                        tx = {**base, "to": Web3.to_checksum_address(to), "data": data}
                        tx.setdefault("gas", self.w3.eth.estimate_gas(tx))
                    signed = acct.sign_transaction(tx)
                    h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                    self._nonces[acct.address] = nonce + 1
                    rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=180)
                    if rcpt["status"] != 1:
                        raise RuntimeError(f"{self.name}: tx {h.hex()} reverted")
                    return dict(rcpt)
                except ValueError as e:  # nonce races / underpriced: refresh and retry
                    msg = str(e).lower()
                    if attempt + 1 < retries and ("nonce" in msg or "underpriced" in msg or "already known" in msg):
                        self._nonces.pop(acct.address, None)
                        time.sleep(1.5)
                        continue
                    raise
        raise RuntimeError("unreachable")

    def deploy(self, acct: LocalAccount, name: str, *args, value: int = 0) -> str:
        art = artifact(name)
        c = self.w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"]["object"])
        rcpt = self.send(acct, c.constructor(*args), value=value)
        return rcpt["contractAddress"]

    def head(self) -> int:
        return self.w3.eth.block_number

    def timestamp(self, block: int | str = "latest") -> int:
        return self.w3.eth.get_block(block)["timestamp"]


class EventDecoder:
    """Decode raw logs from a set of contracts by topic0."""

    def __init__(self, w3: Web3, contract_abis: dict[str, list]):
        self.w3 = w3
        self.by_topic: dict[bytes, dict] = {}
        for _, a in contract_abis.items():
            for item in a:
                if item.get("type") != "event":
                    continue
                sig = f"{item['name']}({','.join(_canonical(i) for i in item['inputs'])})"
                self.by_topic[Web3.keccak(text=sig)] = item

    def decode(self, log: LogReceipt) -> dict[str, Any] | None:
        if not log["topics"]:
            return None
        ev = self.by_topic.get(bytes(log["topics"][0]))
        if ev is None:
            return None
        d = get_event_data(self.w3.codec, ev, log)
        return {
            "event": d["event"],
            "args": dict(d["args"]),
            "address": log["address"],
            "block": log["blockNumber"],
            "tx": log["transactionHash"].hex() if hasattr(log["transactionHash"], "hex") else log["transactionHash"],
            "logIndex": log["logIndex"],
        }


def _canonical(inp: dict) -> str:
    t = inp["type"]
    if t.startswith("tuple"):
        return "(" + ",".join(_canonical(c) for c in inp["components"]) + ")" + t[5:]
    return t


# RPC URL -> largest block range it accepts for eth_getLogs, learnt as we go. Known caps: PublicNode
# 50,000, sepolia.unichain.org 1,000 (said only in a 400 response's body), sepolia.base.org 200.
_LOG_STEP: dict[str, int] = {"https://sepolia.unichain.org": 1000, "https://sepolia.base.org": 200}
_SMALLER = (50_000, 10_000, 2_000, 1_000, 200, 100)


# Explorer APIs (Blockscout, no key) that list an address's logs over any range in one request. Every
# free Unichain Sepolia RPC caps eth_getLogs at 1,000 blocks, and PublicNode has pruned old history, so
# a week-old deployment would take ~1,000 RPC calls to read; the explorer says which blocks to fetch.
_LOG_INDEX = {1301: "https://unichain-sepolia.blockscout.com/api"}
_INDEX_LAG = 2_000  # blocks near the head are always scanned over RPC, in case the explorer lags


def _blocks_with_logs(chain: Chain, addrs: list[str], start: int, end: int) -> list[int] | None:
    url = _LOG_INDEX.get(chain.chain_id)
    if not url or end - start < 20_000 or "127.0.0.1" in chain.rpc or "localhost" in chain.rpc:
        return None
    import requests

    blocks: set[int] = set()
    try:
        for a in addrs:
            frm = start
            while True:
                r = requests.get(url, timeout=30, params={"module": "logs", "action": "getLogs", "address": a,
                                                          "fromBlock": frm, "toBlock": end})
                res = r.json().get("result")
                if not isinstance(res, list):
                    return None
                got = {int(x["blockNumber"], 16) for x in res}
                blocks |= got
                if len(res) < 1000 or not got or max(got) <= frm:
                    break
                frm = max(got)  # a full page: continue from its last block (fetched by block, so overlap is harmless)
    except Exception:
        return None
    return sorted(blocks)


def get_logs(chain: Chain, addresses: Iterable[str], start: int, end: int, step: int = 50_000) -> list[LogReceipt]:
    """Fetch logs in windows, shrinking the window whenever an RPC caps the range."""
    out: list[LogReceipt] = []
    addrs = [Web3.to_checksum_address(a) for a in addresses]
    indexed = _blocks_with_logs(chain, addrs, start, end - _INDEX_LAG)
    if indexed is not None:
        for b in indexed:
            out.extend(chain.w3.eth.get_logs({"address": addrs, "fromBlock": b, "toBlock": b}))
        start = end - _INDEX_LAG + 1
    step = _LOG_STEP.get(chain.rpc.rstrip("/"), step)
    s = start
    while s <= end:
        e = min(end, s + step - 1)
        try:
            out.extend(chain.w3.eth.get_logs({"address": addrs, "fromBlock": s, "toBlock": e}))
        except Exception as exc:
            if step <= 100 or not any(k in str(exc).lower() for k in ("range", "400", "413", "too large", "limit")):
                raise
            step = next(n for n in _SMALLER if n < step)
            _LOG_STEP[chain.rpc.rstrip("/")] = step
            continue
        s = e + 1
    out.sort(key=lambda l: (l["blockNumber"], l["logIndex"]))
    return out


def account(key: str) -> LocalAccount:
    return Account.from_key(key)
