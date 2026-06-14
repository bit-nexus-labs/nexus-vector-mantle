# Nexus Vector Proof Registry

This folder contains the Mantle-compatible proof registry contract for the Nexus Vector hackathon MVP.

## Purpose

Nexus Vector generates an AI risk decision as JSON, converts it into a deterministic SHA-256 hash, and anchors that hash on-chain through this registry.

The on-chain proof does not store private trading data or API keys. It stores only:

- decision hash
- decision id
- agent name
- optional metadata URI
- submitter address
- chain id
- timestamp

## MVP Flow

1. AI Risk Agent creates a decision JSON.
2. `proofs/decision_hasher.py` generates a SHA-256 commitment.
3. `NexusVectorProofRegistry.sol` stores that commitment on Mantle-compatible EVM.
4. Dashboard can later verify whether the off-chain decision still matches the on-chain hash.
