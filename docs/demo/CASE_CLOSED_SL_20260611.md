# Case Study: CLOSED_SL — Controlled Stop-Loss Exit

Date: 2026-06-11
Agent: Nexus Vector
Market: XRP/USDT
Timeframe: 5m
Event Type: CLOSED_SL
Decision Type: EXIT_POSITION
Close Reason: CLOSED_SL

## Summary

Nexus Vector opened a long position after a valid FVG setup and later closed it through a controlled stop-loss exit.

This case demonstrates that the agent does not hide or ignore losing scenarios. It follows the configured risk boundary, executes SELL, verifies the exit price, saves trade history, and returns to IDLE.

## Key Metrics

- Entry: 1.1211
- SL: 1.1177
- TP: 1.1267
- Exit: 1.1170
- Quantity: 26.75 XRP
- Position size: 29.99 USDT
- Final PnL: -0.1097 USDT
- Result: -0.37%

## Agent Timeline

- 14:55:32 — BUY LIMIT placed
- 15:00:50 — BUY LIMIT filled
- 15:00:50 — Position moved to SELL_ACTIVE
- 15:21:19 — Stop-loss condition triggered
- 15:21:27 — SELL balance check completed
- 15:21:32 — Suspicious exit price fields rejected
- 15:21:32 — Average execution price verified
- 15:21:33 — Trade history saved
- 15:21:52 — Agent returned to IDLE

## Why This Matters

This is a clean controlled stop-loss case.

The agent respected the predefined risk boundary and closed the position after the SL trigger. It did not mark the trade as closed before SELL execution was verified.

The important behavior is:

- the position was monitored in SELL_ACTIVE state;
- SL was triggered by market price;
- live balance was checked before SELL;
- inconsistent exchange price fields were rejected;
- verified average execution price was used;
- trade history was saved;
- the agent returned to IDLE.

## Execution Verification

The exchange returned inconsistent price candidates after SELL execution.

Rejected candidates:

- Source: price, Exit: 1.0947, Deviation: 2.03%
- Source: info.price, Exit: 1.0947, Deviation: 2.03%

Accepted candidate:

- Source: average
- Exit: 1.1170
- Deviation: 0.04%

This prevented incorrect PnL calculation and preserved accounting integrity.

## Runtime Note

Temporary ticker gateway errors occurred shortly before the SL trigger. The agent did not incorrectly close the position during those errors. It kept the position active and completed the exit only after the SL condition and SELL execution were verified.

## Final State

- Position closed: true
- Close reason: CLOSED_SL
- BotStatus: RUNNING
- Stage: IDLE

## Proof Hash

decision_hash: 0x0a3f55e319bbd76f0fb8caa213ff5e0106b1f054cd975a35b952c390ef549a78
