"""
engine.py — The PROOF engine: claim + transaction -> sealed evidence bundle.

This is the main entry point. It ties together the Stellar client, the
extractor, the adjudicator, and the sealer into one deterministic pipeline:

    PaymentClaim
        |
        v
    Stellar Horizon (fetch tx + operations + effects)
        |
        v
    Extractor (reconstruct payment evidence)
        |
        v
    [Optional] Commitment fetch + extraction
        |
        v
    Adjudicator (compare claim vs evidence, optionally vs commitment)
        |
        v
    EvidenceBundle (sealed with SHA-256)
        |
        v
    [Optional] Receipt issuance

If anything fails — transaction not found, extraction error, network error —
the engine returns INSUFFICIENT_EVIDENCE, never VERIFIED. Fail closed.
"""
from __future__ import annotations

import time
from typing import Any

from .adjudicator import adjudicate, adjudicate_with_commitment, compute_verdict
from .claim import PaymentClaim
from .commitment import PaymentCommitment, Receipt
from .commitment_extractor import CommitmentExtractionError, extract_commitment
from .dispute import DisputeResult, adjudicate_dispute
from .evidence import (
    INSUFFICIENT_EVIDENCE,
    EvidenceBundle,
    PaymentEvidence,
)
from .extractor import ExtractionError, extract_evidence
from .stellar_client import StellarClient

VERSION = "0.4.0"


def verify_payment(
    claim: PaymentClaim,
    network: str = "testnet",
) -> EvidenceBundle:
    """Verify a payment claim against the Stellar ledger.

    Args:
        claim: The payment claim to verify. If claim.commitment_tx_hash is
            set, the engine will also fetch and verify the commitment.
        network: "testnet" or "mainnet".

    Returns:
        An EvidenceBundle with the verdict, checks, and SHA-256 seal.
        If a commitment was verified, the bundle also includes commitment
        data and a receipt.
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

        # Fetch effects for account_merge amount lookup.
        effects = client.fetch_effects(claim.transaction_hash)

        try:
            evidence = extract_evidence(tx_data, operations, effects)
        except ExtractionError as exc:
            return _insufficient_evidence_bundle(
                claim,
                reason=f"Evidence extraction failed: {exc}",
                network=network,
                fetched_at=fetched_at,
            )

        # Optionally fetch and verify a commitment.
        commitment: PaymentCommitment | None = None
        if claim.commitment_tx_hash is not None:
            commitment_tx_data = client.fetch_transaction(claim.commitment_tx_hash)
            if commitment_tx_data is None:
                # Commitment not found — fail the commitment check but
                # continue with the payment verification.
                commitment = None
            else:
                commitment_ops = client.fetch_operations(claim.commitment_tx_hash)
                try:
                    commitment = extract_commitment(commitment_tx_data, commitment_ops)
                except CommitmentExtractionError:
                    commitment = None

        checks = adjudicate_with_commitment(claim, evidence, commitment)
        verdict = compute_verdict(checks)

        chain_of_custody: dict[str, Any] = {
            "network": network,
            "horizon_url": client.horizon_url,
            "fetched_at": fetched_at,
            "tool_version": VERSION,
            "transaction_hash": claim.transaction_hash,
        }
        if commitment is not None:
            chain_of_custody["commitment_tx_hash"] = commitment.commitment_tx_hash

        bundle = EvidenceBundle.build(
            claim=claim.to_dict(),
            evidence=evidence.to_dict(),
            checks=[c.to_dict() for c in checks],
            verdict=verdict,
            chain_of_custody=chain_of_custody,
            commitment=commitment.to_dict() if commitment is not None else None,
        )

        return bundle
    finally:
        client.close()


def issue_receipt(bundle: EvidenceBundle) -> Receipt:
    """Issue a receipt for a verified payment.

    The receipt contains the transaction hash, the verdict, and the seal
    of the evidence bundle. It can be registered on-chain via a manage_data
    operation with key=PROOF:RECEIPT:<tx_hash> and value=seal.
    """
    return Receipt(
        transaction_hash=bundle.claim.get("transaction_hash", ""),
        verdict=bundle.verdict,
        seal=bundle.seal,
        issued_at=int(time.time()),
    )


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


def _fetch_evidence_for_claim(
    client: StellarClient,
    tx_hash: str,
) -> PaymentEvidence | None:
    """Fetch and extract evidence for a single transaction.

    Returns None if the transaction is not found or extraction fails.
    """
    tx_data = client.fetch_transaction(tx_hash)
    if tx_data is None:
        return None
    operations = client.fetch_operations(tx_hash)
    if not operations:
        return None
    effects = client.fetch_effects(tx_hash)
    try:
        return extract_evidence(tx_data, operations, effects)
    except ExtractionError:
        return None


def verify_dispute(
    claim_a: PaymentClaim,
    claim_b: PaymentClaim,
    network: str = "testnet",
) -> DisputeResult:
    """Verify a dispute between two contradictory payment claims.

    Each claim is verified independently against the ledger. Then the
    evidence sets are compared for contradictions.

    Args:
        claim_a: The first claim (e.g., "I paid Bob 100 USDC").
        claim_b: The second claim (e.g., "I never received anything from Alice").
        network: "testnet" or "mainnet".

    Returns:
        A DisputeResult with the verdicts for each claim and the dispute verdict.
    """
    client = StellarClient(network=network)
    try:
        evidence_a = _fetch_evidence_for_claim(client, claim_a.transaction_hash)
        evidence_b = _fetch_evidence_for_claim(client, claim_b.transaction_hash)
    finally:
        client.close()

    return adjudicate_dispute(claim_a, evidence_a, claim_b, evidence_b)
