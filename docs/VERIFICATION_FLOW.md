# Nexus Vector Verification Flow

This document explains how a Nexus Vector decision can be verified.

## Goal

The goal is to prove that a specific AI risk decision existed in an unchanged form.

The proof flow is:

~~~text
Decision JSON -> canonical JSON -> SHA-256 hash -> on-chain registry -> later verification
~~~

---

## Step 1: Create a Decision JSON

A decision JSON describes the agent decision.

Examples:

~~~text
samples/decision.sample.json
docs/demo/decision_closed_flat_20260612.json
~~~

A decision may include:

- agent name
- decision type
- market context
- risk checks
- safety layers
- outcome
- proof purpose

---

## Step 2: Generate a Deterministic Hash

Run:

~~~bash
python proofs/decision_hasher.py
~~~

The script creates a canonical JSON representation and calculates a SHA-256 hash.

Example sample hash:

~~~text
0x909597939927a3979cc6841dee5c81038db2f9898814a63f9670445fa48a4224
~~~

---

## Step 3: Register the Hash On-Chain

The hash can be submitted to the Mantle-compatible proof registry contract:

~~~text
contracts/NexusVectorProofRegistry.sol
~~~

The contract records the proof without exposing private trading data.

---

## Step 4: Verify Later

To verify a decision later:

1. Take the original decision JSON.
2. Recompute the deterministic hash.
3. Compare it with the hash registered on-chain.
4. If hashes match, the decision was not changed.

---

## CLOSED_FLAT Demo Verification

The CLOSED_FLAT demo case is located at:

~~~text
docs/demo/CASE_CLOSED_FLAT_20260612.md
docs/demo/decision_closed_flat_20260612.json
docs/demo/xrp_closed_flat_20260612.png
~~~

It demonstrates a capital-preservation decision:

~~~text
Entry: 1.1445
Exit: 1.1444
PnL: -0.0026 USDT
Result: -0.01%
~~~

The agent chose to exit almost flat instead of passively waiting for TP or SL.

This is exactly the type of decision that benefits from verifiable proof.
