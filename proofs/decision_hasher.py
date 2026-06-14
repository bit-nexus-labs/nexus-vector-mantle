import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DECISION_PATH = ROOT_DIR / "samples" / "decision.sample.json"
DEFAULT_PROOF_PATH = ROOT_DIR / "proofs" / "decision.proof.sample.json"


def canonical_json(data: dict) -> str:
    """
    Returns deterministic JSON representation.
    Same decision data = same hash.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    decision_path = DEFAULT_DECISION_PATH
    proof_path = DEFAULT_PROOF_PATH

    with decision_path.open("r", encoding="utf-8-sig") as f:
        decision = json.load(f)

    canonical_payload = canonical_json(decision)
    decision_hash = sha256_hex(canonical_payload)

    proof = {
        "agent": decision.get("agent", "Nexus Vector"),
        "agent_type": decision.get("agent_type", "Verifiable AI Risk Agent"),
        "decision_id": decision.get("decision_id"),
        "source_file": str(decision_path.relative_to(ROOT_DIR)).replace("\\", "/"),
        "proof_type": "SHA256_DECISION_COMMITMENT",
        "hash_algorithm": "SHA-256",
        "decision_hash": "0x" + decision_hash,
        "network_target": "Mantle",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "note": "This hash can be anchored on Mantle to prove that the AI risk decision existed unchanged at proof time."
    }

    proof_path.parent.mkdir(parents=True, exist_ok=True)

    with proof_path.open("w", encoding="utf-8") as f:
        json.dump(proof, f, indent=2, ensure_ascii=False)

    print("Nexus Vector proof generated")
    print(f"Decision: {decision_path}")
    print(f"Proof:    {proof_path}")
    print(f"Hash:     0x{decision_hash}")


if __name__ == "__main__":
    main()

