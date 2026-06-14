# Nexus Vector

**Nexus Vector** is a hackathon MVP of a **Verifiable AI Risk Agent** for crypto trading decisions.

It connects an off-chain AI risk decision layer with an on-chain proof registry on a Mantle-compatible EVM network.

The goal is not to store private trading data on-chain.  
The goal is to prove that a specific AI risk decision existed in an unchanged form at a specific moment.

---

## What Nexus Vector Does

Nexus Vector turns an off-chain trading or risk decision into a verifiable proof flow:

1. The trading/risk engine produces a structured decision JSON.
2. The proof layer converts that decision into a deterministic SHA-256 hash.
3. The hash can be registered on-chain through the Mantle proof registry contract.
4. A dashboard can later verify whether the decision JSON still matches the registered proof.

In short:

~~~
AI decision JSON -> deterministic hash -> Mantle proof registry -> dashboard verification
~~~

---

## Why It Matters

Most trading bots only show the final result: profit, loss, or open position.

Nexus Vector focuses on something deeper:

- What did the agent decide?
- Why did it decide that?
- Which safety layers were active?
- Can that decision be verified later?
- Can the proof survive outside the local machine?

This makes Nexus Vector useful not only as a trading assistant, but as a verifiable risk-control agent.

---

## Hackathon MVP Scope

This repository contains:

- Python trading/risk core prototype
- Sample AI risk decision JSON
- Deterministic decision proof generator
- Mantle-compatible proof registry smart contract
- Interactive frontend dashboard
- Demo documentation
- Real demo case study: CLOSED_FLAT capital preservation event

---

## Repository Structure

~~~
contracts/
  NexusVectorProofRegistry.sol
  README.md

proofs/
  decision_hasher.py
  decision.proof.sample.json

samples/
  decision.sample.json

docs/
  LEGACY_CORE_README.md
  demo/
    CASE_CLOSED_FLAT_20260612.md
    decision_closed_flat_20260612.json
    VIDEO_SCRIPT_20260612.md
    xrp_closed_flat_20260612.png

frontend/
  index.html
~~~

---

## Sample Proof Flow

A sample AI risk decision is stored in:

~~~
samples/decision.sample.json
~~~

The proof generator creates a deterministic hash:

~~~bash
python proofs/decision_hasher.py
~~~

Example generated hash:

~~~
0x909597939927a3979cc6841dee5c81038db2f9898814a63f9670445fa48a4224
~~~

The generated proof file is stored in:

~~~
proofs/decision.proof.sample.json
~~~

---

## Mantle Proof Registry

The Mantle-compatible proof registry contract is located at:

~~~
contracts/NexusVectorProofRegistry.sol
~~~

It stores:

- decision hash
- decision id
- agent name
- optional metadata URI
- submitter address
- chain id
- timestamp

It does **not** store:

- API keys
- exchange credentials
- Telegram tokens
- wallet private keys
- private balances
- runtime databases
- raw trading logs

---

## Real Demo Case: CLOSED_FLAT

The repository includes a real capital-preservation case:

~~~
docs/demo/CASE_CLOSED_FLAT_20260612.md
docs/demo/decision_closed_flat_20260612.json
docs/demo/xrp_closed_flat_20260612.png
~~~

In this case, Nexus Vector entered a valid XRP/USDT setup, monitored the trade, activated Breathing Room once, and then closed the position almost flat when the market failed to confirm continuation.

Result:

~~~
Entry: 1.1445
Exit: 1.1444
PnL: -0.0026 USDT
Result: -0.01%
~~~

Final exchange state after exit:

~~~
XRP free: 0.00
XRP used/locked: 0.00
XRP total: 0.00
BUY orders: 0
SELL orders: 0
Open orders: none
~~~

This is the key behavior Nexus Vector demonstrates:

~~~
No continuation -> extend observation once -> no confirmation -> exit near breakeven
~~~

That makes the case useful for a verifiable proof layer because the agent chose capital preservation instead of passively waiting for take-profit or stop-loss.

---

## Demo Video

The demo script is located at:

~~~
docs/demo/VIDEO_SCRIPT_20260612.md
~~~

Planned structure:

- Problem
- What is Nexus Vector
- Live Agent Case: CLOSED_FLAT
- Mantle Proof Layer
- Dashboard / GitHub / Proof
- Closing

---

## Frontend Dashboard

The interactive dashboard is located at:

~~~
frontend/index.html
~~~

The MVP dashboard is intended to show:

- latest proofs
- decision hash
- contract address
- Git commit
- proof status
- demo case references

---

## Security

Runtime and secret files are excluded from Git:

- local databases
- `.env` files
- logs
- terminal output
- cache files
- virtual environments
- frontend build folders

Never commit:

- real API keys
- Telegram bot tokens
- wallet private keys
- seed phrases
- exchange credentials
- production runtime databases

---

## Current MVP Status

Completed:

- Clean public submission repository
- Python trading/risk core prototype
- Sample verifiable decision JSON files
- SHA-256 proof generator
- Mantle-compatible proof registry contract
- Interactive frontend dashboard
- Verification flow documentation
- Runtime architecture overview
- Public demo case studies
- Telegram monitoring snapshots
- Demo presentation video prepared outside the repository

Submission notes:

- The repository does not include private runtime databases, API keys, wallet keys, logs, terminal output, or video files.
- The demo video is submitted separately as the working demonstration / project presentation.
- The proof registry contract is designed for Mantle-compatible deployment.

---

## Positioning

**Nexus Vector = Verifiable AI Risk Agent**

It is designed to answer one question:

> Can we prove that an AI trading/risk decision was made according to a specific rule set before or at the moment of execution?

For the hackathon MVP, the answer is:

~~~
Yes: decision JSON -> deterministic hash -> Mantle proof registry -> dashboard verification
~~~

<!-- NEXUS_HACKATHON_FINAL_START -->
## Hackathon demo package

Nexus Vector is presented as a **verifiable AI risk agent**, not as a profit-only trading bot.

The MVP demonstrates that an automated trading agent can produce structured, auditable decision records for both profitable and defensive outcomes:

- blocked entries;
- controlled losses;
- protected exits;
- flat liquidation;
- verified take-profit execution.

### Demo dashboard

Open the local one-page dashboard:

- `frontend/index.html`

The dashboard includes the Nexus Vector visual identity, the public proof matrix, demo case links, decision JSON links, and chart previews.

### Verifiable decision cases

#### Entry blocked

- Event: `ENTRY_TOO_CLOSE`
- Decision: `BLOCK_ENTRY`
- Result: `0 USDT at risk`
- Case: [Markdown](docs/demo/CASE_ENTRY_TOO_CLOSE_20260612.md)
- Decision record: [JSON](docs/demo/decision_entry_too_close_20260612.json)
- Proof hash: `0x66388c31f1528c8157ebda04acd2d36d0bf3e4aa69395d9dabdf73ebb05ca025`
#### Controlled stop-loss

- Event: `CLOSED_SL`
- Decision: `EXIT_POSITION`
- Result: `-0.37%`
- Case: [Markdown](docs/demo/CASE_CLOSED_SL_20260611.md)
- Decision record: [JSON](docs/demo/decision_closed_sl_20260611.json)
- Proof hash: `0x0a3f55e319bbd76f0fb8caa213ff5e0106b1f054cd975a35b952c390ef549a78`
#### Protected SL exit

- Event: `PROTECTED_SL_EXIT`
- Decision: `EXIT_POSITION`
- Result: `+0.11%`
- Case: [Markdown](docs/demo/CASE_PROTECTED_SL_20260612.md)
- Decision record: [JSON](docs/demo/decision_protected_sl_20260612.json)
- Proof hash: `0x6a9f6d62c2a0cac5a618085aaea51132779c1402e07869511f29034a757144ed`
#### Flat liquidation

- Event: `CLOSED_FLAT`
- Decision: `EXIT_POSITION`
- Result: `-0.01%`
- Case: [Markdown](docs/demo/CASE_CLOSED_FLAT_20260612.md)
- Decision record: [JSON](docs/demo/decision_closed_flat_20260612.json)
  - Chart: [PNG](docs/demo/xrp_closed_flat_20260612.png)
- Proof hash: `0xfd97a117bc486c743b1d1ad90376bf7ca381a1d1814d6b0d0482f7b11842497a`
#### Verified take-profit

- Event: `CLOSED_TP`
- Decision: `EXIT_POSITION`
- Result: `+0.70%`
- Case: [Markdown](docs/demo/CASE_CLOSED_TP_20260612.md)
- Decision record: [JSON](docs/demo/decision_closed_tp_20260612.json)
  - Chart: [PNG](docs/demo/xrp_closed_tp_20260612.png)
- Proof hash: `0xa3cb4a674a237518820f728631cab25d0051f57665ef1b4fd23e67d0ed75f971`

### Verification flow

Each public decision record follows the same verification path:

1. `decision_*.json`
2. Canonical JSON serialization
3. SHA-256 decision hash
4. Proof-ready decision record
5. Mantle Proof Registry contract

The proof layer is designed to verify the decision record. It does not expose exchange credentials, private Telegram data, balances, or raw runtime logs.

### Mantle layer

The repository includes a Solidity proof registry contract:

- `contracts/NexusVectorProofRegistry.sol`

For the hackathon MVP, Mantle is used as the verification direction: decision records are made registry-ready through deterministic hashes. The trading venue and the proof venue are intentionally separated.

### Exchange scope

Current execution adapter:

- MEXC Spot

The proof layer is exchange-agnostic. Future exchange adapters can be added through the same abstraction layer without changing the decision-proof format.

Possible future roadmap:

- MEXC adapter: current live MVP validation
- Bybit adapter: possible future Mantle-aligned execution route
- Other CEX adapters: possible through the same adapter abstraction

No claim is made that the current MVP executes on Bybit or Binance. The current tested execution venue is MEXC Spot.

### Public safety policy

Public demo files follow these rules:

- Exchange order IDs are redacted.
- API keys are not included.
- Database files are not included.
- Runtime logs are not included.
- Telegram control is protected by an authorized chat guard.

This keeps the demo safe while preserving verifiable decision structure.
<!-- NEXUS_HACKATHON_FINAL_END -->



---

## Mantle Deployment

The Nexus Vector proof registry contract has been deployed to Mantle Sepolia.

- Network: Mantle Sepolia
- Chain ID: 5003
- Contract: NexusVectorProofRegistry
- Contract address:  xBe21FEa166213a5cdCf49a1964B3841eb5517dBB
- Explorer: https://explorer.sepolia.mantle.xyz/address/0xBe21FEa166213a5cdCf49a1964B3841eb5517dBB

This contract stores verifiable AI risk decision proof commitments for the Nexus Vector MVP.

