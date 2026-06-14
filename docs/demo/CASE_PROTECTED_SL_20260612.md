# Case Study: PROTECTED_SL_EXIT — Breakeven Stop Protection

Date: 2026-06-12
Agent: Nexus Vector
Market: XRP/USDT
Timeframe: 5m
Event Type: PROTECTED_SL_EXIT
Decision Type: EXIT_POSITION
Close Reason: CLOSED_SL

## Summary

Nexus Vector opened a long position after a valid FVG setup, then protected the trade by moving the stop-loss to breakeven during a flat-market phase.

The position did not reach the original take-profit target. Instead, the protected stop-loss was triggered, and the agent closed the position with a small positive result.

This is not a simple losing stop-loss case. It is a protected risk-management exit.

## Key Metrics

- Entry: 1.1313
- Initial SL: 1.1264
- Protected SL: 1.1315
- TP: 1.1577
- Exit: 1.1325
- Quantity: 26.51 XRP
- Position size: 29.99 USDT
- Final PnL: +0.0318 USDT
- Result: +0.11%

## Agent Timeline

- 18:56:35 — BUY LIMIT placed
- 18:56:41 — BUY LIMIT filled
- 18:56:41 — Position moved to SELL_ACTIVE
- 19:31:41 — Flat manager moved SL to breakeven protection
- 19:36:12 — Protected SL condition triggered
- 19:36:20 — SELL balance check completed
- 19:36:27 — Suspicious exit price fields rejected
- 19:36:27 — Average execution price verified
- 19:36:27 — Trade history saved
- 19:36:46 — Agent returned to IDLE with CLOSED_SL cooldown

## Why This Matters

This case demonstrates that Nexus Vector does not simply wait for take-profit or accept uncontrolled losses.

The agent applied a breakeven protection rule, then executed a controlled exit when the protected stop was reached.

The important behavior is:

- the stop-loss was moved from risk to protection;
- the exit was executed only after a live balance check;
- inconsistent exchange price fields were rejected;
- the verified average execution price was used;
- trade history was written;
- the agent returned to IDLE with cooldown.

## Execution Verification

The exchange returned inconsistent price candidates after SELL execution.

Rejected candidates:

- Source: price, Exit: 1.1095, Deviation: 1.94%
- Source: info.price, Exit: 1.1095, Deviation: 1.94%

Accepted candidate:

- Source: average
- Exit: 1.1325
- Deviation: 0.09%

This prevented incorrect PnL calculation and preserved accounting integrity.

## Final State

- Position closed: true
- Close reason: CLOSED_SL
- BotStatus: RUNNING
- Stage: IDLE
- Cooldown reason: CLOSED_SL
- Cooldown seconds: 2700

## Interpretation

Nexus Vector acted as a verifiable AI risk agent:

- It detected a valid setup.
- It capped position size.
- It synchronized state after BUY fill.
- It moved SL to breakeven protection.
- It closed the position when the protected stop was reached.
- It rejected suspicious exchange price fields.
- It saved the final trade result.
- It returned to a clean IDLE state.

## Proof Hash

decision_hash: 0x6a9f6d62c2a0cac5a618085aaea51132779c1402e07869511f29034a757144ed
