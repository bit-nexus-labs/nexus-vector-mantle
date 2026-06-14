# Public Strategy Roadmap

This document describes the public, non-proprietary strategy roadmap for Nexus Vector.

The purpose is to explain the direction of the system without exposing exact trading edge, private thresholds, or production optimization rules.

---

## Current MVP Focus

The current hackathon MVP focuses on:

- stable bot lifecycle
- safe manual START / STOP behavior
- one active trade cycle at a time
- SQLite-based state recovery
- BUY LIMIT monitoring
- position supervision
- verified exit handling
- clean exchange-state checks
- deterministic decision proofs
- Mantle-compatible proof registry

---

## Strategy Principle

Nexus Vector treats market structure as context, not as an automatic trading command.

A detected structure does not automatically become a trade.

The agent must evaluate whether a decision is safe, explainable, and verifiable.

---

## Post-MVP Strategy Modules

Planned future modules include:

### 1. FVG Zone Registry

A memory layer for detected market imbalance zones.

Purpose:

- remember detected zones
- track zone lifecycle
- avoid repeated analysis of stale zones
- support future quality statistics

### 2. Trade Setup Memory

A separate layer for opportunities that pass trading filters.

Purpose:

- separate raw market structure from executable decisions
- track rejected and accepted setups
- preserve decision context

### 3. Ladder Risk Filter

A risk filter for avoiding late continuation entries when lower unfilled market structures may still create downside risk.

### 4. Trend-Aware Long Filter

A higher-timeframe filter for long-only spot trading.

Purpose:

- avoid opening long spot trades against broader bearish conditions
- reduce risk in neutral conditions
- align entries with market context

### 5. Decision Quality Scoring

A future diagnostic layer that estimates the quality of a setup before execution.

The public MVP does not disclose exact scoring rules or thresholds.

### 6. Retest / Revalidation Logic

A future module for deciding whether a previously missed or used zone can become valid again after new market confirmation.

The public MVP does not disclose proprietary retest/revalidation conditions.

---

## What Is Public

This repository can publicly show:

- high-level risk architecture
- safety lifecycle
- proof generation
- verification flow
- smart contract registry
- demo case studies
- post-MVP module names

---

## What Remains Private

The following remain private strategy material:

- exact scoring formulas
- exact FVG entry optimization rules
- proprietary threshold values
- detailed retest/revalidation conditions
- production trading parameters
- private runtime databases
- exchange credentials
- wallet keys
- raw operational logs

---

## Product Direction

Nexus Vector is not just a trading bot.

It is evolving into a verifiable decision agent that can answer:

~~~text
What did the agent decide?
Why did it decide that?
Which safety layers were active?
Can the decision be verified later?
~~~

That is the core product direction.
