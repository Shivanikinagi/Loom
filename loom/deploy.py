"""Deploy LOOM to three chains and wire it up.

Order follows the Reactive docs: the reactive contract first (Lasna), then the
callback contracts that authenticate it (Base, Unichain), then setTargets()
on the referee, which opens the subscriptions.
"""

from __future__ import annotations

import logging

from web3 import Web3

from .chain import Chain, abi
from .config import ROLES, chain_presets, make_chains, master_account, role_account, save

log = logging.getLogger("loom.deploy")

ETH = 10**18

PARAMS = {
    "testnet": {
        "minBond": ETH // 1000,  # 0.001 ETH per provider on Unichain Sepolia
        "timeoutPenalty": ETH // 10000,
        "minChallengeBond": ETH // 2000,
        "quorum": 2,
        "refereeFunding": 2 * ETH,  # lREACT for reactive transactions
        "escrowFeeFunding": ETH // 100,  # destination-chain ETH for callback fees
        "bondsFeeFunding": ETH // 100,
        "stageTimeout": 180,
        "challengeWindow": 90,
    },
    "local": {
        "minBond": ETH // 20,
        "timeoutPenalty": ETH // 200,
        "minChallengeBond": ETH // 100,
        "quorum": 2,
        "refereeFunding": ETH,
        "escrowFeeFunding": ETH // 10,
        "bondsFeeFunding": ETH // 10,
        "stageTimeout": 30,
        "challengeWindow": 12,
    },
}


def deploy(network: str, blobd: str = "http://127.0.0.1:8700") -> dict:
    p = PARAMS[network]
    presets = chain_presets(network)
    chains = make_chains(network)
    master = master_account(network)
    base, uni, lasna = chains["base"], chains["unichain"], chains["lasna"]
    start = {k: c.head() for k, c in chains.items()}

    log.info("deployer %s", master.address)
    referee = lasna.deploy(master, "LoomReferee", base.chain_id, uni.chain_id, p["minBond"], p["quorum"],
                           value=p["refereeFunding"])
    log.info("LoomReferee  (lasna)    %s", referee)
    escrow = base.deploy(master, "LoomEscrow", presets["base"]["callbackProxy"], referee, p["minChallengeBond"])
    log.info("LoomEscrow   (base)     %s", escrow)
    bonds = uni.deploy(master, "LoomBonds", presets["unichain"]["callbackProxy"], referee, p["minBond"],
                       p["timeoutPenalty"])
    log.info("LoomBonds    (unichain) %s", bonds)

    lasna.send(master, lasna.contract(referee, "LoomReferee").functions.setTargets(escrow, bonds))
    esc = base.contract(escrow, "LoomEscrow")
    for i in range(3):
        base.send(master, esc.functions.setVerifier(role_account(master, f"verifier{i}").address, True))

    # Callback fees are billed to the destination contracts in native ETH.
    _fund_callbacks(network, base, presets["base"]["callbackProxy"], escrow, p["escrowFeeFunding"], master)
    _fund_callbacks(network, uni, presets["unichain"]["callbackProxy"], bonds, p["bondsFeeFunding"], master)

    data = {
        "network": network,
        "chains": {k: {"chainId": v["chainId"], "explorer": v["explorer"]} for k, v in presets.items()},
        "contracts": {"referee": referee, "escrow": escrow, "bonds": bonds},
        "startBlocks": start,
        "params": p,
        "blobd": blobd,
        "deployer": master.address,
    }
    path = save(network, data)
    log.info("wrote %s", path)
    return data


def _fund_callbacks(network: str, chain: Chain, proxy: str, target: str, amount: int, master) -> None:
    if network == "local":
        chain.send(master, to=target, value=amount)  # operating balance; the local relay charges nothing
        return
    # Credit reserves through the proxy so fees never touch the contract's own balance.
    c = chain.w3.eth.contract(address=Web3.to_checksum_address(proxy), abi=_DEPOSIT_ABI)
    chain.send(master, c.functions.depositTo(target), value=amount)


_DEPOSIT_ABI = [{"type": "function", "name": "depositTo", "stateMutability": "payable",
                 "inputs": [{"name": "_contract", "type": "address"}], "outputs": []}]


def fund_roles(network: str, base_eth: dict[str, int], uni_eth: dict[str, int]) -> None:
    """Top up role accounts from the deployer (only what each role is missing)."""
    chains = make_chains(network)
    master = master_account(network)
    for chain_name, wants in (("base", base_eth), ("unichain", uni_eth)):
        chain = chains[chain_name]
        for role, amount in wants.items():
            addr = role_account(master, role).address
            have = chain.w3.eth.get_balance(addr)
            if have < amount:
                chain.send(master, to=addr, value=amount - have)
                log.info("funded %-10s on %-8s %.4f ETH", role, chain_name, (amount - have) / ETH)


def default_funding(network: str) -> tuple[dict[str, int], dict[str, int]]:
    p = PARAMS[network]
    gas = ETH // 200 if network == "testnet" else ETH
    base = {r: gas for r in ROLES}
    base["buyer"] = gas + (ETH // 50 if network == "testnet" else 5 * ETH)
    base["challenger"] = gas + 4 * p["minChallengeBond"]
    uni = {f"gpu{i}": p["minBond"] + gas for i in range(5)}
    return base, uni


def register_providers(net, blobd: str, count: int = 5) -> None:
    bonds = net.bonds()
    for i in range(count):
        acct = net.role(f"gpu{i}")
        bond, unlock, *_ = bonds.functions.providers(acct.address).call()
        if bond >= net.params["minBond"] and unlock == 0:
            continue
        net.unichain.send(acct, bonds.functions.register(f"{blobd}#gpu{i}"), value=net.params["minBond"] - bond)
        log.info("gpu%d bonded on unichain: %s", i, acct.address)


__all__ = ["deploy", "fund_roles", "default_funding", "register_providers", "PARAMS", "abi"]
