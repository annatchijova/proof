"""
engine.py — The PROOF engine: claim + transaction -> sealed evidence bundle.

This is the main entry point. It ties together the Stellar client, the
extractor, the adjudicator, and the sealer into one deterministic pipeline:

    PaymentClaim
        |
        v
    Stellar Horizon (fetch tx + operations)
        |
        v
    Extractor (reconstruct payment evidence)
        |
        v
    Adjudicator (compare claim vs evidence)
        |
        v
    EvidenceBundle (sealed with SHA-256)

If anything fails — transaction not found, extraction error, network error —
the engine returns INSUFFICIENT_EVIDENCE, never VERIFIED. Fail closed.
"""
from __future__ import annotations

import time
from typing import Any

from .adjudicator import adjudicate, compute_verdict
from .claim import PaymentClaim
from .evidence import (
    INSUFFICIENT_EVIDENCE,
    EvidenceBundle,
    PaymentEvidence,
)
from .extractor import ExtractionError, extract_evidence
from .stellar_client import StellarClient

VERSION = "0.1.0"


def verify_payment(
    claim: PaymentClaim,
    network: str = "testnet",
) -> EvidenceBundle:
    """Verify a payment claim against the Stellar ledger.

    Args:
        claim: The payment claim to verify.
        network: "testnet" or "mainnet".

    Returns:
        An EvidenceBundle with the verdict, checks, and SHA-256 seal.
    """
    fetched_at = int(time.time())

    client = StellarClient(network=network)
    try:
        tx_data = client.fetch_transaction(claim.transaction_hash)
        if tx_data is None:
            return _insufficient_evidence_bundle(
                claim,
                reason="Transaction not found on the ledger.",
                network=network,
                fetched_at=fetched_at,
            )

        operations = client.fetch_operations(claim.transaction_hash)
        if not operations:
            return _insufficient_evidence_bundle(
                claim,
                reason="No operations found for this transaction.",
                network=network,
                fetched_at=fetched_at,
            )

        try:
            evidence = extract_evidence(tx_data, operations)
        except ExtractionError as exc:
            return _insufficient_evidence_bundle(
                claim,
                reason=f"Evidence extraction failed: {exc}",
                network=network,
                fetched_at=fetched_at,
            )

        checks = adjudicate(claim, evidence)
        verdict = compute_verdict(checks)

        chain_of_custody = {
            "network": network,
            "horizon_url": client.horizon_url,
            "fetched_at": fetched_at,
            "tool_version": VERSION,
            "transaction_hash": claim.transaction_hash,
        }

        return EvidenceBundle.build(
            claim=claim.to_dict(),
            evidence=evidence.to_dict(),
            checks=[c.to_dict() for c in checks],
            verdict=verdict,
            chain_of_custody=chain_of_custody,
        )
    finally:
        client.close()


def _insufficient_evidence_bundle(
    claim: PaymentClaim,
    reason: str,
    network: str,
    fetched_at: int,
) -> EvidenceBundle:
    """Build an INSUFFICIENT_EVIDENCE bundle when we can't verify."""
    chain_of_custody = {
        "network": network,
        "fetched_at": fetched_at,
        "tool_version": VERSION,
        "transaction_hash": claim.transaction_hash,
        "reason": reason,
    }

    return EvidenceBundle.build(
        claim=claim.to_dict(),
        evidence={},
        checks=[
            {
                "name": "transaction_exists",
                "status": "FAIL",
                "expected": claim.transaction_hash,
                "actual": None,
                "detail": reason,
            }
        ],
        verdict=INSUFFICIENT_EVIDENCE,
        chain_of_custody=chain_of_custody,
    )
