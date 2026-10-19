"""Liquidity-screened, single-entry tUSDC carry. Base Sepolia only.
No key is required to import. scan() never sends a transaction.
"""
import os
from chain import ADDR, at, erc20, acct_of, send, w3, CHAIN_ID

NAME = "zoe-liquid-carry"
WAD = 10**18
CAP = 100 * WAD
MIN_SIZE = 10 * WAD
MIN_RETURN = WAD // 10  # 0.10 tUSDC over a hypothetical 30 days
MIN_GAS = 10**14
VENUES = ("LendA", "LendB")


def wallet():
    key = os.getenv("AGENT_KEY")
    return acct_of(key).address if key else os.getenv("AGENT_ADDRESS")


def choose(balance, venues):
    """Pure integer sizing; haircut observed yield, never promise a future APR.

    Keep 90% liquid, cap principal at 100 tUSDC, and invest only where
    existing cash covers ten times our deposit. Reject high utilization.
    Any pre-existing lending position prevents repeated heartbeat deposits.
    """
    if balance <= 0 or any(v["shares"] != 0 for v in venues):
        return None
    candidates = []
    for v in venues:
        if not (0 < v["apr"] <= WAD and 0 <= v["util"] <= WAD * 70 // 100):
            continue
        amount = min(CAP, balance // 10, v["cash"] // 10)
        if amount < MIN_SIZE:
            continue
        # 50% APR haircut and a 30-day horizon are assumptions, not a model
        # of this contract's post-deposit interest curve (not shipped here).
        estimated = amount * v["apr"] * 30 // (2 * WAD * 365)
        if estimated >= MIN_RETURN:
            candidates.append({"venue": v["name"], "amount": amount,
                               "expected_30d": estimated})
    return max(candidates, key=lambda x: x["expected_30d"], default=None)


def scan():
    try:
        me = wallet()
        if not me:
            return {"hit": False, "line": "set public AGENT_ADDRESS for read-only wallet scan"}
        if w3.eth.chain_id != CHAIN_ID or CHAIN_ID != 84532:
            raise ValueError("Base Sepolia required")
        block = w3.eth.block_number
        # Pin reads to a common block so venue comparisons are coherent.
        def read(fn):
            return fn.call(block_identifier=block)
        balance = read(erc20("tUSDC").functions.balanceOf(me))
        venues = []
        for name in VENUES:
            p = at(ADDR[name], "LendingPool")
            venues.append(dict(name=name, apr=read(p.functions.supplyAPR()),
                               util=read(p.functions.utilization()),
                               cash=read(p.functions.cash()),
                               shares=read(p.functions.shares(me))))
        picked = choose(balance, venues)
        if w3.eth.get_balance(me, block) < MIN_GAS:
            picked = None
        if not picked:
            return {"hit": False, "line": "skip: position, liquidity, balance, gas or yield limit"}
        return {"hit": True, "line": f"supply {picked['amount']/WAD:.2f} tUSDC to {picked['venue']}; hypothetical haircut 30d yield {picked['expected_30d']/WAD:.4f}",
                "wallet": me, "block": block, **picked}
    except Exception as exc:
        # Do not print exception details: external clients may embed credentials.
        return {"hit": False, "line": f"unavailable data/configuration ({type(exc).__name__})"}


def fire(s):
    """Explicitly authorized invocation only; no fallback to the class funder.

    Exact approval then supply are separate actions. A failed/uncertain send
    propagates immediately; never automatically retry or claim realized yield.
    """
    key = os.getenv("AGENT_KEY")
    if os.getenv("CONFIRM_BASE_SEPOLIA") != "YES" or not key:
        raise RuntimeError("explicit Base Sepolia authorization and AGENT_KEY required")
    if not s.get("hit"):
        raise RuntimeError("no opportunity")
    fresh = scan()
    if not fresh.get("hit") or any(fresh[k] != s.get(k) for k in ("wallet", "venue", "amount")):
        raise RuntimeError("opportunity changed; review a fresh scan")
    me, amount, venue = fresh["wallet"], fresh["amount"], fresh["venue"]
    spender = ADDR[venue]
    token = erc20("tUSDC")
    pool = at(spender, "LendingPool")
    if not w3.eth.get_code(spender) or not w3.eth.get_code(ADDR["tUSDC"]):
        raise RuntimeError("missing contract code")
    # Conservative execution gas budget, separate from token-denominated yield.
    gas_price = w3.eth.gas_price
    if gas_price > 10**9 or w3.eth.get_balance(me) < 2 * 920_000 * gas_price + MIN_GAS:
        raise RuntimeError("gas budget exceeded")
    hashes = []
    allowance = token.functions.allowance(me, spender).call()
    if allowance < amount:
        if allowance != 0:
            raise RuntimeError("existing nonzero allowance requires separate review")
        rcpt = send(token.functions.approve(spender, amount), gas=120_000,
                    key=key, retries=1, gas_price=gas_price)
        hashes.append(rcpt.transactionHash.hex())
    # Approval can take time; recheck all selection/risk conditions afterwards.
    check = scan()
    if not check.get("hit") or any(check[k] != fresh[k] for k in ("wallet", "venue", "amount")):
        raise RuntimeError("conditions changed after approval; stop and review")
    fn = pool.functions.supply(amount)
    fn.call({"from": me})  # preflight only; no transaction broadcast
    rcpt = send(fn, key=key, retries=1, gas_price=gas_price)
    hashes.append(rcpt.transactionHash.hex())
    return {"tx": hashes[-1], "transactions": hashes, "profit": 0.0,
            "principal_tUSDC": amount / WAD,
            "note": "deposit confirmed; interest is unmeasured, not instant profit"}
