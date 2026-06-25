# Nexus Vector Risk Guard вЂ” Public Overview

**Document date:** 2026-06-25
**Public scope:** redacted architecture and validation summary
**Private runtime:** MEXC spot trading bot, not included in the public repository

## Purpose

Nexus Vector is designed as a verifiable AI risk agent for trading-system decisions. The Risk Guard is the runtime safety layer that prevents the agent from continuing to open new positions when the daily risk state is no longer acceptable.

This document is public-safe. It describes the architecture and safety intent without exposing private exchange credentials, database files, raw logs, full order identifiers, balances, Telegram IDs, or private trading runtime code.

## What the Risk Guard protects against

The Risk Guard is intended to reduce the risk of:

- opening new trades after the daily risk limit has already been reached;
- continuing to trade during a bad market regime without a safety pause;
- counting risk incorrectly after stop-loss, flat-close, or trailing-stop behavior;
- accidentally resuming trading after a manual stop or restart;
- creating duplicate or conflicting BUY orders while a previous state is still active;
- making public claims that are not backed by auditable private runtime evidence.

## R-based risk model

The Risk Guard uses an R-based model rather than a raw dollar-only loss limit.

```text
planned_R_usdt = abs(entry_price - initial_sl_price) * qty
realized_R = pnl_usdt / planned_R_usdt
```

This makes risk measurement portable across different position sizes and symbols. A trade that loses its full planned risk is `-1R`; a trade that gains twice its planned risk is `+2R`.

## Runtime principle

The Risk Guard is a gate before new BUY creation. It is not designed to force-close an active position.

This distinction is intentional:

- blocking a new BUY is a preventive risk-control action;
- force-closing an active position can create additional execution risk;
- active positions should still be managed by the normal state machine, exchange reconciliation, and verified exit logic.

## What Risk Guard does

The Risk Guard can:

- compute daily realized R from persisted trade audit data;
- detect daily hard-lock conditions;
- block new BUY attempts;
- place the runtime into a Risk Guard auto-paused state for day-scoped daily locks;
- allow daily auto-resume only after a new trading day and only after safety checks;
- preserve manual STOP semantics so that a user stop does not auto-resume;
- provide redacted state information for Telegram/status reporting;
- support public proof-layer artifacts without exposing private runtime code.

## What Risk Guard does not do

The Risk Guard does **not**:

- expose private MEXC API keys or Telegram tokens;
- publish the private trading bot runtime;
- guarantee profit;
- replace exchange reconciliation;
- create orders directly;
- cancel orders directly;
- force-close positions;
- override manual STOP;
- auto-start after reboot or unexpected process restart;
- remove the need for state-machine validation.

## Public/private boundary

The private runtime includes exchange integration, state-machine execution, database writes, Telegram control, and full operational logs. These are not included in the public hackathon repository.

The public repository may include:

- redacted architecture documents;
- redacted validation summaries;
- sample decision JSON files;
- proof hashes;
- dashboard/demo artifacts;
- public-safe chart examples with masked identifiers.

The public repository must not include:

- `.env` files;
- database snapshots;
- raw logs;
- API keys or tokens;
- Telegram chat IDs;
- unredacted exchange order IDs;
- private balances;
- private runtime code paths;
- backup folders or patch-transfer files.

## Current validation status

Risk Guard audit persistence and daily auto-resume safety state have been committed in the private runtime branch.

Confirmed validation status:

- Python compile checks passed for patched runtime files.
- Scanner BUY path is gated by Risk Guard before new BUY creation.
- Manual STOP disables auto-resume.
- Final tracked repository hygiene check found no private runtime artifacts or credential-like tracked files.
- Multi-trade R-audit persistence was validated in the private SQLite runtime database.

Remaining limitation:

- full live daily-hard-lock auto-resume scenario remains pending.

## Public claim wording

Recommended wording:

```text
Nexus Vector includes a private-runtime Risk Guard layer that gates new BUY decisions, persists planned/realized R audit data, and supports daily risk lock behavior. The public repository contains redacted architecture, validation summaries, and proof-layer artifacts, not private trading runtime code.
```

Avoid overclaiming:

```text
Risk Guard fully guarantees all trading safety.
Every possible order path is formally proven guarded.
Daily hard-lock auto-resume is fully live-validated in all scenarios.
```
