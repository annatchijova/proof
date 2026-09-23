#!/usr/bin/env python3
"""Demonstrate that mutating a sealed evidence field is detected.

This is a local, synthetic demo. It does not contact Stellar or require a
funded account; it exercises the same EvidenceBundle and independent verifier
used by the product.
"""

from __future__ import annotations

from copy import deepcopy

from proof.evidence import EvidenceBundle, PaymentEvidence, PaymentOperation
from proof.verifier import verify_bundle


TX_HASH = "a" * 64
SENDER = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
RECIPIENT = "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"


def build_demo_bundle() -> dict:
    operation = PaymentOperation(
        operation_type="payment",
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=1_000_000_000,
    )
    evidence = PaymentEvidence(
        transaction_hash=TX_HASH,
        ledger=12345,
        timestamp_unix=1_700_000_000,
        successful=True,
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=1_000_000_000,
        memo=None,
        memo_type="none",
        operation_type="payment",
        operations=[operation],
    )
    return EvidenceBundle.build(
        claim={"transaction_hash": TX_HASH},
        evidence=evidence.to_dict(),
        checks=[
            {
                "name": "transaction_exists",
                "status": "PASS",
                "expected": TX_HASH,
                "actual": TX_HASH,
                "detail": "found",
            },
            {
                "name": "transaction_successful",
                "status": "PASS",
                "expected": "success",
                "actual": "success",
                "detail": "ok",
            },
        ],
        verdict="VERIFIED",
        chain_of_custody={"network": "testnet", "source": "local-demo"},
    ).to_dict()


def main() -> None:
    valid_bundle = build_demo_bundle()
    valid_report = verify_bundle(valid_bundle)

    tampered_bundle = deepcopy(valid_bundle)
    tampered_bundle["evidence"]["amount_stroops"] = 2_000_000_000
    tampered_report = verify_bundle(tampered_bundle)

    print("PROOF tamper demo")
    print(f"valid bundle:    seal_ok={valid_report['seal_ok']}")
    print(
        "tampered amount: "
        f"seal_ok={tampered_report['seal_ok']} "
        f"issues={tampered_report['issues']}"
    )

    if not valid_report["seal_ok"] or tampered_report["seal_ok"]:
        raise SystemExit("tamper demo failed its expected outcomes")


if __name__ == "__main__":
    main()
