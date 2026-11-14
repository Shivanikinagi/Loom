"""Networks, deployments and role keys."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from eth_account.signers.local import LocalAccount
from web3 import Web3

from .chain import ROOT, Chain, account

DEPLOYMENTS = ROOT / "deployments"

# Reactive Omni testnet values (docs: Origins & Destinations, Lasna Testnet).
TESTNET = {
    "base": {
        "chainId": 84532,
        "rpc": os.environ.get("BASE_SEPOLIA_RPC", "https://sepolia.base.org"),
        "explorer": "https://sepolia.basescan.org",
        "callbackProxy": "0x476F44b11F5C942c58f4c8E3d0300E5710743585",
    },
    "unichain": {
        "chainId": 1301,
        "rpc": os.environ.get("UNICHAIN_SEPOLIA_RPC", "https://sepolia.unichain.org"),
        "explorer": "https://sepolia.uniscan.xyz",
        "callbackProxy": "0x775c9B990ADe401060B78D0e98684eEf8d2466C1",
    },
    "lasna": {
        "chainId": 5318007,
        "rpc": os.environ.get("LASNA_RPC", "https://lasna-rpc.rnk.dev/"),
        "explorer": "https://lasna.reactscan.net",
        "system": "0x8888888888888888888888888888888888888888",
    },
}

# Local anvil chains use the same chain IDs and proxy addresses (impersonated).
LOCAL = {
    "base": {**TESTNET["base"], "rpc": "http://127.0.0.1:8545", "explorer": ""},
    "unichain": {**TESTNET["unichain"], "rpc": "http://127.0.0.1:8546", "explorer": ""},
    "lasna": {**TESTNET["lasna"], "rpc": "http://127.0.0.1:8547", "explorer": ""},
}

# Default anvil account 0: only ever used for local chains.
ANVIL_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

ROLES = ["buyer", "challenger", *[f"gpu{i}" for i in range(5)], *[f"verifier{i}" for i in range(3)]]


@dataclass
class Network:
    name: str
    chains: dict[str, Chain]
    contracts: dict[str, str]
    start: dict[str, int]
    params: dict
    blobd: str
    master: LocalAccount

    @property
    def base(self) -> Chain:
        return self.chains["base"]

    @property
    def unichain(self) -> Chain:
        return self.chains["unichain"]

    @property
    def lasna(self) -> Chain:
        return self.chains["lasna"]

    def escrow(self):
        return self.base.contract(self.contracts["escrow"], "LoomEscrow")

    def bonds(self):
        return self.unichain.contract(self.contracts["bonds"], "LoomBonds")

    def referee(self):
        return self.lasna.contract(self.contracts["referee"], "LoomReferee")

    def role(self, name: str) -> LocalAccount:
        return role_account(self.master, name)


def role_account(master: LocalAccount, name: str) -> LocalAccount:
    """Role keys are derived from the deployer key, so one funded wallet runs everything."""
    return account(Web3.keccak(bytes(master.key) + name.encode()).hex())


def master_account(network: str) -> LocalAccount:
    if network == "local":
        return account(ANVIL_KEY)
    key = os.environ.get("LOOM_PRIVATE_KEY") or _dotenv().get("LOOM_PRIVATE_KEY")
    if not key:
        raise SystemExit("Set LOOM_PRIVATE_KEY (funded deployer key) in the environment or .env")
    return account(key)


def chain_presets(network: str) -> dict:
    return LOCAL if network == "local" else TESTNET


def make_chains(network: str) -> dict[str, Chain]:
    presets = chain_presets(network)
    poll = 0.5 if network == "local" else 2.0
    return {k: Chain(k, v["chainId"], v["rpc"], v["explorer"], poll) for k, v in presets.items()}


def load(network: str) -> Network:
    path = DEPLOYMENTS / f"{network}.json"
    if not path.exists():
        raise SystemExit(f"{path} not found - deploy first (python -m loom deploy --network {network})")
    d = json.loads(path.read_text())
    return Network(
        name=network,
        chains=make_chains(network),
        contracts=d["contracts"],
        start=d["startBlocks"],
        params=d["params"],
        blobd=os.environ.get("LOOM_BLOBD", d.get("blobd", "http://127.0.0.1:8700")),
        master=master_account(network),
    )


def save(network: str, data: dict) -> Path:
    DEPLOYMENTS.mkdir(exist_ok=True)
    path = DEPLOYMENTS / f"{network}.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def _dotenv() -> dict:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env
