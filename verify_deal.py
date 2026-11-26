"""Verify a DealProof deal file: recompute deal_hash over the canonical terms JSON."""
import hashlib
import json
import sys


def canonical_hash(terms: dict) -> str:
    canonical = json.dumps(terms, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python verify_deal.py <deal file>")
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        deal = json.load(f)
    terms = deal.get("terms")
    stored = deal.get("deal_hash")
    if not isinstance(terms, dict) or not stored:
        print("TAMPERED")
        return 1
    if canonical_hash(terms) == stored:
        print("OK")
        return 0
    print("TAMPERED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
