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
                base = {"from": acct.address, "nonce": nonce, "value": value, "chainId": self.chain_id}
                if gas:
                    base["gas"] = gas
                try:
                    if fn is not None:
                        tx = fn.build_transaction(base)
                    else:
                        tx = {**base, "to": Web3.to_checksum_address(to), "data": data}
                        tx.setdefault("gas", self.w3.eth.estimate_gas(tx))
                        fee = self.w3.eth.gas_price
                        tx.update({"maxFeePerGas": fee * 2, "maxPriorityFeePerGas": min(fee, Web3.to_wei(1, "gwei"))})
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


def get_logs(chain: Chain, addresses: Iterable[str], start: int, end: int, step: int = 2000) -> list[LogReceipt]:
    out: list[LogReceipt] = []
    addrs = [Web3.to_checksum_address(a) for a in addresses]
    s = start
    while s <= end:
        e = min(end, s + step - 1)
        out.extend(chain.w3.eth.get_logs({"address": addrs, "fromBlock": s, "toBlock": e}))
        s = e + 1
    out.sort(key=lambda l: (l["blockNumber"], l["logIndex"]))
    return out


def account(key: str) -> LocalAccount:
    return Account.from_key(key)
