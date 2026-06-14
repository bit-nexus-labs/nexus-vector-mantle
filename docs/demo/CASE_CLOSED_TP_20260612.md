# Case Study: CLOSED_TP — Verified Take-Profit Execution

Date: 2026-06-12  
Agent: Nexus Vector  
Market: XRP/USDT  
Timeframe: 5m  
Event Type: `CLOSED_TP`  
Decision Type: `EXIT_POSITION`

## Summary

Nexus Vector detected a valid FVG long setup, placed a BUY LIMIT order, and transitioned the position into active monitoring after the order was filled.

The market reached the take-profit condition. The agent executed a market SELL, validated the real exit price, rejected suspicious exchange-returned price fields, saved the trade result, activated cooldown, and returned the position state to `IDLE`.

Result:

```text
Entry: 1.1359
TP: 1.1424
Exit trigger: 1.1431
Verified exit: 1.1439
Qty: 26.41 XRP
Position size: 30.00 USDT
PnL: +0.2113 USDT
Result: +0.70%
```

## Agent Timeline

```text
17:30 — FVG long setup detected
17:30 — BUY LIMIT placed at 1.1359
17:32 — BUY LIMIT filled, position moved to SELL_ACTIVE
17:37 — Take-profit condition reached
17:37 — Market SELL executed
17:37 — Exit price verified through average execution price
17:37 — Trade history saved
17:37 — Position moved to CLOSED_TP
17:37 — Cooldown activated for 900 seconds
```

## Exit Price Validation

The exchange response contained suspicious price fields that were far away from the live fallback price. Nexus Vector rejected them and accepted only the verified average execution price.

```text
Rejected: Source=price      | Exit=1.1208 | Fallback=1.1431 | Deviation=1.95%
Rejected: Source=info.price | Exit=1.1208 | Fallback=1.1431 | Deviation=1.95%
Accepted: Source=average    | Exit=1.1439 | Fallback=1.1431 | Deviation=0.07%
```

This matters because incorrect exchange-returned fields could distort PnL, break reporting, or create false trade history. The agent selected a safe and verified exit price before marking the trade as closed.

## Why This Matters

This case demonstrates a full successful trade lifecycle:

```text
Signal detected
Risk checked
BUY LIMIT placed
Position filled
TP reached
SELL executed
Exit price verified
Trade history saved
Cooldown activated
State returned to IDLE
```

The agent did not only generate an entry signal. It completed the full state-machine cycle and produced a verifiable decision record.

## Public Data Handling

The original exchange order ID is intentionally redacted.

```text
order_id: REDACTED
order_id_redacted: true
```

This keeps the public demo safe while preserving the verifiable decision structure.

## Proof Hash

decision_hash: 0xa3cb4a674a237518820f728631cab25d0051f57665ef1b4fd23e67d0ed75f971
