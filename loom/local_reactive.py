"""A local stand-in for Reactive Network, for development on anvil only.

On testnet none of this runs: Reactive itself delivers origin-chain logs to
LoomReferee.react() and posts the callbacks it requests. Locally we have three
anvil chains (with the real chain IDs) and this relay plays the network's part:

  1. new escrow logs (base) and bonds logs (unichain) -> referee.react(), sent
     from the system contract address on the lasna chain;
  2. CallbackRequest events from the (mock) system contract -> the recipient on
     the destination chain, sent from that chain's callback proxy address with
     the referee's address injected as the first argument;
  3. a Cron10 tick every `cron_every` seconds while the referee is subscribed.
"""

from __future__ import annotations

import logging
import threading
import time

from eth_abi import decode as abi_decode
from web3 import Web3

from .chain import Chain, abi, artifact, get_logs
from .config import Network, chain_presets

log = logging.getLogger("loom.relay")

SYSTEM = "0x8888888888888888888888888888888888888888"
CRON_SOURCE = "0x0000000000000000000000000000000000fffFfF"
CRON10 = 0x04463F7C1651E6B9774D7F85C85BB94654E3C46CA79B0C16FB16D4183307B687
CALLBACK_REQUEST = Web3.keccak(text="CallbackRequest(uint256,address,address,uint64,bytes)")
PROXY_OVERHEAD = 50_000


def install_mock_system(lasna: Chain) -> None:
    code = artifact("MockSystem")["deployedBytecode"]["object"]
    lasna.w3.provider.make_request("anvil_setCode", [SYSTEM, code])


def _impersonate(chain: Chain, addr: str) -> None:
    chain.w3.provider.make_request("anvil_impersonateAccount", [addr])
    chain.w3.provider.make_request("anvil_setBalance", [addr, hex(10**21)])


class LocalReactive:
    def __init__(self, net: Network, cron_every: float = 2.0):
        self.net = net
        self.cron_every = cron_every
        presets = chain_presets("local")
        self.proxy = {net.base.chain_id: presets["base"]["callbackProxy"],
                      net.unichain.chain_id: presets["unichain"]["callbackProxy"]}
        self.dest = {net.base.chain_id: net.base, net.unichain.chain_id: net.unichain}
        self.referee = net.referee()
        self.cursor = {"base": net.start["base"], "unichain": net.start["unichain"], "lasna": net.start["lasna"]}
        self.stats = {"reacts": 0, "callbacks": 0, "callback_failures": 0, "cron": 0}
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="local-reactive")
        _impersonate(net.lasna, SYSTEM)
        for cid, p in self.proxy.items():
            _impersonate(self.dest[cid], p)
        self._mock_abi = abi("MockSystem")

    def start(self) -> "LocalReactive":
        self.thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        last_cron = time.time()
        while not self._stop.is_set():
            try:
                self._deliver("base", self.net.contracts["escrow"])
                self._deliver("unichain", self.net.contracts["bonds"])
                self._callbacks()
                if time.time() - last_cron >= self.cron_every:
                    last_cron = time.time()
                    if self.referee.functions.cronOn().call():
                        self._react(self._cron_record())
                        self.stats["cron"] += 1
                        self._callbacks()
            except Exception:
                log.exception("relay step failed")
            self._stop.wait(0.3)

    # -- origin logs -> react() -----------------------------------------------
    def _deliver(self, name: str, address: str) -> None:
        chain: Chain = self.net.chains[name]
        head = chain.head()
        if head < self.cursor[name]:
            return
        for lg in get_logs(chain, [address], self.cursor[name], head):
            topics = [int.from_bytes(t, "big") for t in lg["topics"]] + [0, 0, 0, 0]
            rec = (chain.chain_id, Web3.to_checksum_address(lg["address"]), topics[0], topics[1], topics[2], topics[3],
                   bytes(lg["data"]), lg["blockNumber"], len(lg["topics"]), int.from_bytes(lg["blockHash"], "big"),
                   int.from_bytes(lg["transactionHash"], "big"), lg["logIndex"])
            self._react(rec)
        self.cursor[name] = head + 1

    def _cron_record(self) -> tuple:
        n = self.net.lasna.head()
        return (self.net.lasna.chain_id, Web3.to_checksum_address(CRON_SOURCE), CRON10, 0, 0, 0,
                n.to_bytes(32, "big"), n, 1, 0, 0, 0)

    def _react(self, rec: tuple) -> None:
        data = self.referee.encode_abi("react", args=[rec])
        w3 = self.net.lasna.w3
        h = w3.eth.send_transaction({"from": SYSTEM, "to": self.referee.address, "data": data, "gas": 900_000})
        rcpt = w3.eth.wait_for_transaction_receipt(h)
        if rcpt["status"] != 1:
            log.warning("react() reverted for topic %s", hex(rec[2]))
        self.stats["reacts"] += 1

    # -- CallbackRequest -> destination -------------------------------------------
    def _callbacks(self) -> None:
        lasna = self.net.lasna
        head = lasna.head()
        if head < self.cursor["lasna"]:
            return
        logs = lasna.w3.eth.get_logs({"address": SYSTEM, "fromBlock": self.cursor["lasna"], "toBlock": head,
                                      "topics": [CALLBACK_REQUEST]})
        self.cursor["lasna"] = head + 1
        for lg in sorted(logs, key=lambda l: (l["blockNumber"], l["logIndex"])):
            chain_id = int.from_bytes(lg["topics"][1], "big")
            sender = "0x" + lg["topics"][2][-20:].hex()
            recipient = Web3.to_checksum_address("0x" + lg["topics"][3][-20:].hex())
            gas_limit, payload = abi_decode(["uint64", "bytes"], bytes(lg["data"]))
            payload = payload[:4] + bytes(12) + bytes.fromhex(sender[2:]) + payload[36:]  # inject the reactive sender
            dest = self.dest[chain_id]
            h = dest.w3.eth.send_transaction({"from": self.proxy[chain_id], "to": recipient, "data": payload,
                                              "gas": gas_limit - PROXY_OVERHEAD})
            rcpt = dest.w3.eth.wait_for_transaction_receipt(h)
            self.stats["callbacks"] += 1
            if rcpt["status"] != 1:
                self.stats["callback_failures"] += 1
                log.warning("callback to %s on %s failed", recipient, dest.name)
