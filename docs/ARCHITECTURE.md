# Nexus Vector Architecture

Nexus Vector is a hackathon MVP of a Verifiable AI Risk Agent for crypto trading decisions.

The system separates three layers:

~~~text
Trading / Risk Core
        ↓
Verifiable Decision Layer
        ↓
Mantle Proof Registry
~~~

The trading core remains off-chain. The blockchain layer stores only a proof commitment, not private trading data.

---

## Core Principle

Nexus Vector does not put private trading data on-chain.

Instead, it creates a deterministic hash of an AI risk decision and anchors that hash through a Mantle-compatible proof registry.

~~~text
Market data
  -> Risk engine
  -> Structured decision JSON
  -> Deterministic hash
  -> Mantle proof registry
  -> Dashboard verification
~~~

---

## Main Components

### 1. Trading / Risk Core

The Python core monitors market structure, order state, risk limits, position lifecycle, and exit conditions.

The current MVP is focused on safety and lifecycle correctness:

- one active trade cycle at a time
- manual START / STOP control
- SQLite state recovery
- BUY LIMIT monitoring
- position supervision
- verified exit handling
- clean exchange-state checks
- trade history logging

### 2. Decision JSON

A decision JSON describes what the agent decided and why.

Examples:

~~~text
samples/decision.sample.json
docs/demo/decision_closed_flat_20260612.json
~~~

The JSON is the human-readable source of truth for a specific decision.

### 3. Proof Generator

The proof generator creates a deterministic SHA-256 commitment from a canonical JSON representation.

~~~text
proofs/decision_hasher.py
~~~

Same decision content produces the same hash.

### 4. Mantle Proof Registry

The smart contract stores only the proof commitment and minimal metadata.

~~~text
contracts/NexusVectorProofRegistry.sol
~~~

It stores:

- decision hash
- decision id
- agent name
- metadata URI
- submitter address
- chain id
- timestamp

It does not store:

- API keys
- exchange credentials
- Telegram tokens
- wallet private keys
- private balances
- runtime databases
- raw trading logs

### 5. Dashboard

The dashboard is the visual verification layer.

~~~text
frontend/index.html
~~~

It is intended to show:

- latest proofs
- decision hash
- contract address
- Git commit
- demo case reference
- verification status

---

## Demo Case: CLOSED_FLAT

The CLOSED_FLAT case demonstrates capital preservation.

The agent entered a valid XRP/USDT setup, monitored continuation, activated Breathing Room once, and exited almost flat when the market failed to continue.

This proves that Nexus Vector is not only an entry bot.

It is a risk-control agent that can decide to preserve capital when a trade stops developing.

---

## Public Strategy Disclosure Policy

This repository intentionally exposes the risk-agent architecture and verification flow, but not the full proprietary trading edge.

Public:

- lifecycle architecture
- proof flow
- safety principles
- demo case studies
- high-level strategy roadmap

Private:

- exact entry optimization rules
- detailed scoring thresholds
- proprietary FVG retest/revalidation logic
- full strategy parameterization
- production databases and runtime logs

<!-- NEXUS_RUNTIME_STATE_DIAGRAM_START -->
## Runtime state machine

Nexus Vector is designed as a state-machine driven risk agent.  
The public diagram below shows the high-level runtime flow without exposing private strategy thresholds or proprietary setup scoring rules.

~~~mermaid
flowchart TD
    A[Program start] --> B[Restore state from SQLite]

    B --> C{Recovered stage?}
    C -->|No active order| D[STOPPED]
    C -->|BUY_PENDING| E[WAITING_BUY]
    C -->|SELL_ACTIVE| F[HOLDING_SELL]

    D -->|Manual START| G[RUNNING / SCANNING]

    G --> H{Valid setup?}
    H -->|No setup or blocked entry| G
    H -->|Risk checks passed| I[Place BUY LIMIT]

    I --> E

    E --> J{BUY result}
    J -->|Filled| F
    J -->|Timeout / invalidated / cancelled / missed TP| K[Cancel BUY safely]
    K --> G

    F --> L{Exit condition}
    L -->|TP reached| M[Market SELL]
    L -->|SL reached| M
    L -->|Flat timeout| M

    M --> N[Verify exit price]
    N --> O[Save trade history]
    O --> P[Create decision proof hash]
    P --> Q[COOLDOWN]
    Q --> G

    G -->|Manual STOP| D
    E -->|Manual STOP| K
    F -->|Manual STOP| R[Stop scanner, keep monitoring position]
    R --> F
~~~

### Safety properties shown in the diagram

- The bot restores state from SQLite after restart.
- A pending BUY order is monitored until it is filled, cancelled, invalidated, or expired.
- The agent does not open duplicate positions while an active position or SELL exposure exists.
- STOP cancels pending BUY orders but does not blindly abandon an active position.
- Closed trades go through verified exit price selection before trade history is saved.
- Every public demo decision can be represented as a deterministic proof hash.
<!-- NEXUS_RUNTIME_STATE_DIAGRAM_END -->
