"""Testnet helpers: preflight checks and the lREACT faucet."""

from __future__ import annotations

from web3 import Web3

from .config import TESTNET, make_chains, master_account
from .deploy import PARAMS, default_funding

ETH = 10**18
# Reactive's Lasna faucet on Base Sepolia: 1 ETH -> 100 lREACT, max 5 ETH per tx.
FAUCET_BASE_SEPOLIA = "0x2afaFD298b23b62760711756088F75B7409f5967"

# Generous gas budgets for the deployer's own transactions (Base/Unichain
# Sepolia gas is cheap; these are upper bounds, not estimates).
# Lasna gas is ~100 gwei, so the referee deploy + 19 subscriptions need real lREACT.
DEPLOY_GAS_ETH = {"base": 2 * ETH // 1000, "unichain": 3 * ETH // 1000, "lasna": ETH}


def requirements() -> dict[str, int]:
    """Native balance the deployer needs on each chain (wei)."""
    p = PARAMS["testnet"]
    base_roles, uni_roles = default_funding("testnet")
    return {
        "base": DEPLOY_GAS_ETH["base"] + p["escrowFeeFunding"] + sum(base_roles.values()),
        "unichain": DEPLOY_GAS_ETH["unichain"] + p["bondsFeeFunding"] + sum(uni_roles.values()),
        "lasna": DEPLOY_GAS_ETH["lasna"] + p["refereeFunding"],
    }


def preflight() -> bool:
    chains = make_chains("testnet")
    master = master_account("testnet")
    need = requirements()
    ok = True
    print(f"deployer: {master.address}\n")
    for name, chain in chains.items():
        unit = "lREACT" if name == "lasna" else "ETH"
        try:
            cid = chain.w3.eth.chain_id
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name:9s} RPC {chain.rpc} unreachable: {e}")
            ok = False
            continue
        if cid != chain.chain_id:
            print(f"[FAIL] {name:9s} RPC reports chain {cid}, expected {chain.chain_id}")
            ok = False
            continue
        proxy = TESTNET[name].get("callbackProxy") or TESTNET[name].get("system")
        has_code = len(chain.w3.eth.get_code(Web3.to_checksum_address(proxy))) > 0
        bal = chain.w3.eth.get_balance(master.address)
        enough = bal >= need[name]
        ok = ok and enough and has_code
        print(f"[{'ok' if enough and has_code else 'FAIL':4s}] {name:9s} chain {cid}  balance {bal / ETH:.4f} {unit}"
              f"  needs {need[name] / ETH:.4f}  {'proxy/system ok' if has_code else 'NO CODE at ' + proxy}")
        if not enough:
            short = (need[name] - bal) / ETH
            hint = (f"python -m loom faucet --eth {max(short / 100 * 1.1, 0.01):.3f}  (Base Sepolia ETH -> lREACT)"
                    if name == "lasna" else f"send {short:.4f} {unit} to {master.address}")
            print(f"       -> {hint}")
    print("\nREADY" if ok else "\nNOT READY")
    return ok


def faucet(eth: float) -> str:
    """Swap Base Sepolia ETH for Lasna lREACT through Reactive's faucet contract."""
    if eth > 5:
        raise SystemExit("the faucet ignores anything above 5 ETH per transaction")
    chains = make_chains("testnet")
    master = master_account("testnet")
    c = chains["base"].w3.eth.contract(address=Web3.to_checksum_address(FAUCET_BASE_SEPOLIA), abi=[
        {"type": "function", "name": "request", "stateMutability": "payable",
         "inputs": [{"name": "addr", "type": "address"}], "outputs": []}])
    rcpt = chains["base"].send(master, c.functions.request(master.address), value=int(eth * ETH))
    h = rcpt["transactionHash"].hex()
    print(f"requested {eth * 100:g} lREACT for {master.address}: {chains['base'].tx_url(h)}")
    return h
