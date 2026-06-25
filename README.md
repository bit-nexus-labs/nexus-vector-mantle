# Nexus Vector

**Nexus Vector** is a hackathon MVP of a **Verifiable AI Risk Agent** for crypto trading decisions.

It connects an off-chain AI risk decision layer with an on-chain proof registry on a Mantle-compatible EVM network.

> This repository contains a clean public release. Development history is maintained in a private working repository active since May 19, 2026.

The goal is not to store private trading data on-chain.
The goal is to prove that a specific AI risk decision existed in an unchanged form at a specific moment.

---

## Project Links

* BUIDL page: https://dorahacks.io/buidl/45033
* Live dashboard: https://bit-nexus-labs.github.io/nexus-vector-mantle/frontend/
* Demo video: https://youtu.be/_6e-r6gE4xE
* Mantle Sepolia contract: https://explorer.sepolia.mantle.xyz/address/0xBe21FEa166213a5cdCf49a1964B3841eb5517dBB

---

## What Nexus Vector Does

Nexus Vector turns an off-chain trading or risk decision into a verifiable proof flow:

1. The trading/risk engine produces a structured decision JSON.
2. The proof layer converts that decision into a deterministic SHA-256 hash.
3. The hash can be registered on-chain through the Mantle proof registry contract.
4. A dashboard can later verify whether the decision JSON still matches the registered proof.

In short:

```
AI decision JSON -> deterministic hash -> Mantle proof registry -> dashboard verification
```

Nexus Vector is presented as a **risk-first AI trading decision layer**, not as a profit-only trading bot.

The MVP demonstrates that an automated trading agent can produce structured, auditable decision records for both profitable and defensive outcomes:

* blocked unsafe entries;
* controlled stop-loss exits;
* protected breakeven exits;
* flat-market capital preservation;
* verified take-profit execution.

---

## Why It Matters

Most trading bots only show the final result: profit, loss, or open position.

Nexus Vector focuses on something deeper:

* What did the agent decide?
* Why did it decide that?
* Which safety layers were active?
* Can that decision be verified later?
* Can the proof survive outside the local machine?

This makes Nexus Vector useful not only as a trading assistant, but as a verifiable risk-control agent.

The long-term vision is a **Proof-of-Strategy Oracle**: an infrastructure layer where AI agents can build trust through verifiable behavior, risk discipline, and transparent decision records rather than marketing claims.

---

## Hackathon MVP Scope

This repository contains the clean public release of the Nexus Vector hackathon MVP:

* Python trading/risk core prototype
* Sample verifiable AI risk decision JSON files
* Deterministic SHA-256 decision proof generator
* Mantle-compatible proof registry smart contract
* Mantle Sepolia deployment reference
* Interactive frontend dashboard
* Verification flow documentation
* Runtime architecture overview
* Telegram monitoring snapshots
* Public demo cases covering blocked entries, controlled losses, protected exits, flat liquidation, and verified take-profit execution
* Public safety policy and exchange scope notes

---

## Repository Structure

```
contracts/
  NexusVectorProofRegistry.sol
  README.md

proofs/
  decision_hasher.py
  decision.proof.sample.json

samples/
  decision.sample.json

docs/
  ARCHITECTURE.md
  STRATEGY_ROADMAP_PUBLIC.md
  VERIFICATION_FLOW.md
  demo/
    CASE_ENTRY_TOO_CLOSE_20260612.md
    CASE_CLOSED_SL_20260611.md
    CASE_PROTECTED_SL_20260612.md
    CASE_CLOSED_FLAT_20260612.md
    CASE_CLOSED_TP_20260612.md
    decision_*.json
    xrp_closed_flat_20260612.png
    xrp_closed_tp_20260612.png
    VIDEO_SCRIPT_20260612.md

frontend/
  index.html
  assets/
    nexus-vector-logo.png
    telegram/

main.py
mexc_client.py
market_structure_analysis.py
bot_interface.py
database.py
config.py
run_bot.bat
```

---

## Sample Proof Flow

A sample AI risk decision is stored in:

```
samples/decision.sample.json
```

The proof generator creates a deterministic hash:

```bash
python proofs/decision_hasher.py
```

Example generated hash:

```
0x909597939927a3979cc6841dee5c81038db2f9898814a63f9670445fa48a4224
```

The generated proof file is stored in:

```
proofs/decision.proof.sample.json
```

---

## Mantle Proof Registry

The Mantle-compatible proof registry contract is located at:

```
contracts/NexusVectorProofRegistry.sol
```

It stores:

* decision hash;
* decision id;
* agent name;
* optional metadata URI;
* submitter address;
* chain id;
* timestamp.

It does **not** store:

* API keys;
* exchange credentials;
* Telegram tokens;
* wallet private keys;
* private balances;
* runtime databases;
* raw trading logs.

---

## Mantle Deployment

The Nexus Vector proof registry contract has been deployed to Mantle Sepolia.

* Network: Mantle Sepolia
* Chain ID: 5003
* Contract: NexusVectorProofRegistry
* Contract address: `0xBe21FEa166213a5cdCf49a1964B3841eb5517dBB`
* Explorer: https://explorer.sepolia.mantle.xyz/address/0xBe21FEa166213a5cdCf49a1964B3841eb5517dBB

This contract stores verifiable AI risk decision proof commitments for the Nexus Vector MVP.

---

## Frontend Dashboard

The interactive dashboard is located at:

```
frontend/index.html
```

Live dashboard:

```
https://bit-nexus-labs.github.io/nexus-vector-mantle/frontend/
```

The dashboard shows:

* project overview and risk-first positioning;
* verification flow from decision JSON to deterministic proof hash;
* runtime architecture and safety controls;
* Telegram monitoring snapshots;
* public demo cases with decision JSON viewer;
* proof matrix and verification metadata;
* Mantle Sepolia deployment reference.

To run the dashboard locally from the repository root:

```bash
python -m http.server 8000
```

Then open:

```
http://localhost:8000/frontend/
```

---

## Demo Video

The demo presentation is submitted separately and is not stored in this repository as a video file.

Demo video:

```
https://youtu.be/_6e-r6gE4xE
```

The video script is stored at:

```
docs/demo/VIDEO_SCRIPT_20260612.md
```

---

## Verifiable Decision Cases

Each public decision record follows the same verification path:

1. `decision_*.json`
2. Canonical JSON serialization
3. SHA-256 decision hash
4. Proof-ready decision record
5. Mantle Proof Registry contract

The proof layer is designed to verify the decision record. It does not expose exchange credentials, private Telegram data, balances, or raw runtime logs.

### Entry blocked

* Event: `ENTRY_TOO_CLOSE`
* Decision: `BLOCK_ENTRY`
* Result: `0 USDT at risk`
* Case: [Markdown](docs/demo/CASE_ENTRY_TOO_CLOSE_20260612.md)
* Decision record: [JSON](docs/demo/decision_entry_too_close_20260612.json)
* Proof hash: `0x66388c31f1528c8157ebda04acd2d36d0bf3e4aa69395d9dabdf73ebb05ca025`

### Controlled stop-loss

* Event: `CLOSED_SL`
* Decision: `EXIT_POSITION`
* Result: `-0.37%`
* Case: [Markdown](docs/demo/CASE_CLOSED_SL_20260611.md)
* Decision record: [JSON](docs/demo/decision_closed_sl_20260611.json)
* Proof hash: `0x0a3f55e319bbd76f0fb8caa213ff5e0106b1f054cd975a35b952c390ef549a78`

### Protected SL exit

* Event: `PROTECTED_SL_EXIT`
* Decision: `EXIT_POSITION`
* Result: `+0.11%`
* Case: [Markdown](docs/demo/CASE_PROTECTED_SL_20260612.md)
* Decision record: [JSON](docs/demo/decision_protected_sl_20260612.json)
* Proof hash: `0x6a9f6d62c2a0cac5a618085aaea51132779c1402e07869511f29034a757144ed`

### Flat liquidation

* Event: `CLOSED_FLAT`
* Decision: `EXIT_POSITION`
* Result: `-0.01%`
* Case: [Markdown](docs/demo/CASE_CLOSED_FLAT_20260612.md)
* Decision record: [JSON](docs/demo/decision_closed_flat_20260612.json)
* Chart: [PNG](docs/demo/xrp_closed_flat_20260612.png)
* Proof hash: `0xfd97a117bc486c743b1d1ad90376bf7ca381a1d1814d6b0d0482f7b11842497a`

### Verified take-profit

* Event: `CLOSED_TP`
* Decision: `EXIT_POSITION`
* Result: `+0.70%`
* Case: [Markdown](docs/demo/CASE_CLOSED_TP_20260612.md)
* Decision record: [JSON](docs/demo/decision_closed_tp_20260612.json)
* Chart: [PNG](docs/demo/xrp_closed_tp_20260612.png)
* Proof hash: `0xa3cb4a674a237518820f728631cab25d0051f57665ef1b4fd23e67d0ed75f971`

---

## Real Demo Case: CLOSED_FLAT

The repository includes a real capital-preservation case:

```
docs/demo/CASE_CLOSED_FLAT_20260612.md
docs/demo/decision_closed_flat_20260612.json
docs/demo/xrp_closed_flat_20260612.png
```

In this case, Nexus Vector entered a valid XRP/USDT setup, monitored the trade, activated Breathing Room once, and then closed the position almost flat when the market failed to confirm continuation.

Result:

```
Entry: 1.1445
Exit: 1.1444
PnL: -0.0026 USDT
Result: -0.01%
```

Final exchange state after exit:

```
XRP free: 0.00
XRP used/locked: 0.00
XRP total: 0.00
BUY orders: 0
SELL orders: 0
Open orders: none
```

This is the key behavior Nexus Vector demonstrates:

```
No continuation -> extend observation once -> no confirmation -> exit near breakeven
```

That makes the case useful for a verifiable proof layer because the agent chose capital preservation instead of passively waiting for take-profit or stop-loss.

---

## Exchange Scope

Current execution adapter:

* MEXC Spot

The proof layer is exchange-agnostic. Future exchange adapters can be added through the same abstraction layer without changing the decision-proof format.

Possible future roadmap:

* MEXC adapter: current live MVP validation;
* Bybit adapter: possible future Mantle-aligned execution route;
* other CEX adapters: possible through the same adapter abstraction.

No claim is made that the current MVP executes on Bybit or Binance. The current tested execution venue is MEXC Spot.

---

## Security and Public Safety

Runtime and secret files are excluded from Git:

* local databases;
* `.env` files;
* logs;
* terminal output;
* cache files;
* virtual environments;
* frontend build folders;
* raw runtime screenshots;
* video files.

Never commit:

* real API keys;
* Telegram bot tokens;
* wallet private keys;
* seed phrases;
* exchange credentials;
* production runtime databases.

Public demo files follow these rules:

* exchange order IDs are redacted;
* API keys are not included;
* database files are not included;
* runtime logs are not included;
* private strategy internals are not published;
* Telegram screenshots are redacted and translated for public presentation.

The public repository is designed for review, demonstration, and proof verification.
It is **not** intended to be used as a live trading deployment without private configuration, additional safety review, and exchange-specific operational controls.

---

## Current MVP Status

Completed:

* Clean public submission repository
* Python trading/risk core prototype
* Sample verifiable decision JSON files
* SHA-256 proof generator
* Mantle-compatible proof registry contract
* Mantle Sepolia deployment
* Interactive frontend dashboard
* GitHub Pages live demo
* Verification flow documentation
* Runtime architecture overview
* Public demo case studies
* Telegram monitoring snapshots
* Demo presentation video prepared outside the repository
* DoraHacks BUIDL submission

Submission notes:

* The repository does not include private runtime databases, API keys, wallet keys, logs, terminal output, or video files.
* The demo video is submitted separately as the working demonstration / project presentation.
* The proof registry contract is deployed on Mantle Sepolia and linked in this README.

---

## Positioning

**Nexus Vector = Verifiable AI Risk Agent**

It is designed to answer one question:

> Can we prove that an AI trading/risk decision was made according to a specific rule set before or at the moment of execution?

For the hackathon MVP, the answer is:

```
Yes: decision JSON -> deterministic hash -> Mantle proof registry -> dashboard verification
```

Nexus Vector is a first step toward a future **Proof-of-Strategy Oracle**: an infrastructure layer where AI agents can build trust through verifiable behavior, transparent decision records, and disciplined risk management.

---

## Roadmap

Potential future development directions:

* deeper strategy registry;
* public proof explorer;
* agent reputation layer;
* multi-timeframe decision audit;
* extended risk scoring;
* additional exchange adapters;
* safer copy-trading verification;
* improved operational controls for production trading;
* stronger Telegram command authorization and runtime hardening;
* automated deployment and verification tooling for Mantle-compatible networks.

---

## Disclaimer

Nexus Vector is an experimental hackathon MVP.

It does not provide financial advice.
It does not guarantee profit.
It should not be used for live trading without independent review, proper risk controls, private configuration, and operational safeguards.

The project focuses on verifiability, transparency, and risk-aware decision records for AI-assisted trading systems.
