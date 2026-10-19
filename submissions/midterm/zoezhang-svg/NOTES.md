# Zoe's liquidity-screened carry strategy

GitHub: zoezhang-svg
Public Base Sepolia wallet: `0x8053fB8473eF8A3CF731D09226DDEb7A08c96625`

## Strategy and rationale
My bot supplies idle tUSDC to the eligible lending venue with the largest conservative 30-day interest estimate. It invests at most 10% of the wallet and 100 tUSDC, requires existing venue cash to cover ten times the proposed deposit, and excludes utilization above 70%. Its estimate halves the observed APR and requires at least 0.10 tUSDC of hypothetical interest, while any existing position prevents repeated deposits. The expected return comes from borrowers paying interest; unlike the example rate bot, this strategy enters from idle cash and screens liquidity rather than migrating a fixed position to chase an APR spread. Rates can fall, funds can become temporarily unwithdrawable, and gas or contract losses can exceed interest, so this is a risk-limited carry experiment rather than guaranteed profit.

## Implementation
- `strategy.py` is the complete implementation. `my_strategy_bot.py` exports its required `NAME`, `scan()` and `fire(s)` interface.
- Development implementation: `week-03/code/lab-bot/my_strategy_bot.py` (local only; excluded from the PR to obey the submission-only rule).
- Uses only `chain.py` addresses, ABI and transaction helpers. Reads are pinned to one block. Missing configuration, malformed data and RPC errors skip safely.
- Uses only explicitly configured `AGENT_KEY`; never falls back to PRIVATE_KEY, funder keys or example-bot keys. A public `AGENT_ADDRESS` suffices for scanning.
- `fire()` additionally requires `CONFIRM_BASE_SEPOLIA=YES`. Do not set this until the wallet owner has reviewed and explicitly approved the exact action.
- Checks Base Sepolia, deployed code, ETH budget and fresh opportunity conditions; approves only the exact principal if necessary. No unlimited approvals. A nonzero insufficient allowance stops for review.
- A preflight `eth_call` checks the supply transaction. Transaction errors propagate; sends use one attempt to avoid blindly rebroadcasting uncertain transactions.
- No swaps or borrowed positions: swap fees and swap slippage do not apply. Deposit interest is variable; the 50% haircut is an assumption, not an exact post-deposit APR calculation. The arena lending implementation/interest curve is not shipped with this client.
- Estimated interest is not realized P&L: successful `fire()` reports `profit: 0.0`. Gas is paid in ETH, not subtracted from a fabricated tUSDC profit. There is no trusted ETH/tUSDC conversion oracle here; the token hurdle does not establish net profitability after gas.
- This version enters one position and does not automatically withdraw it. Withdrawal is a separate wallet-owner-reviewed action and can fail if cash is unavailable. The 30-day horizon is an estimate, not a lock or automatic exit.

## Reproduction
From the repository root:

```sh
/Users/zoe/AI_Finance/bin/python -m unittest discover -s submissions/midterm/zoezhang-svg -p 'test_*.py' -v
```

To reconstruct the runnable lab copy from the submission (no reference file changes):

```sh
cp submissions/midterm/zoezhang-svg/strategy.py week-03/code/lab-bot/my_strategy_bot.py
cd week-03/code/lab-bot
export AGENT_ADDRESS=0x8053fB8473eF8A3CF731D09226DDEb7A08c96625
/Users/zoe/AI_Finance/bin/python -u run.py my_strategy_bot
```

The runner loops; stop with Ctrl-C. Do not add `--live` without explicit approval and secure local key configuration. Never paste a signing key into chat, commit it, or put it in command history.

The stock orchestrator accepts `--only my_strategy_bot` and records genuine successful actions in its local `state.json`/`pnl.log`; `dashboard.html` displays that state. This does not establish enrollment on an instructor-hosted leaderboard. A screenshot must show actual execution; no synthetic state is acceptable.

## Evidence status
- No transaction has been sent in this session. Transaction hashes and explorer links are pending.
- A genuine leaderboard screenshot is pending. Instructor leaderboard URL/registration instructions may be needed.
- The Classroom PDF cannot be finalized until actual transaction evidence and a genuine screenshot exist.
- Current market observations and exact test outcomes are in `VALIDATION.md`.
