"""
dispute.py — Dispute resolution between contradictory payment claims.

A dispute arises when two parties make contradictory claims about the same
payment. PROOF does not adjudicate who is right in a human sense — it
determines what the ledger can establish about each claim and whether they
are mutually consistent.

Dispute outcomes:
  - CLAIM_A_VERIFIED: claim A is verified, claim B is not
  - CLAIM_B_VERIFIED: claim B is verified, claim A is not
  - BOTH_VERIFIED: both claims are verified (they are not contradictory
    in what the ledger can establish)
  - NEITHER_VERIFIED: neither claim is verified
  - CONTRADICTION: both claims reference the same transaction but assert
    contradictory facts that the ledger cannot support simultaneously
  - INSUFFICIENT_EVIDENCE: at least one claim could not be checked

No float, no probability, no LLM. Pure deterministic comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .canonicalize import seal
from .claim import PaymentClaim
from .evidence import (
    ABSTAIN,
    FAIL,
    INSUFFICIENT_EVIDENCE,
    NOT_VERIFIED,
    PASS,
    CheckResult,
    EvidenceBundle,
    PaymentEvidence,
    VERIFIED,
)

# Dispute verdicts.
CLAIM_A_VERIFIED = "CLAIM_A_VERIFIED"
CLAIM_B_VERIFIED = "CLAIM_B_VERIFIED"
BOTH_VERIFIED = "BOTH_VERIFIED"
NEITHER_VERIFIED = "NEITHER_VERIFIED"
CONTRADICTION = "CONTRADICTION"


@dataclass(frozen=True)
class DisputeResult:
    """The result of adjudicating a dispute between two claims.

    Each claim is verified independently. The dispute verdict describes
    the relationship between the two verification results.
    """

    claim_a_verdict: str
    claim_b_verdict: str
    dispute_verdict: str
    claim_a_checks: list[dict]
    claim_b_checks: list[dict]
    contradiction_checks: list[dict]
    detail: str

    def to_dict(self) -> dict:
        return {
            "claim_a_verdict": self.claim_a_verdict,
            "claim_b_verdict": self.claim_b_verdict,
            "dispute_verdict": self.dispute_verdict,
            "claim_a_checks": self.claim_a_checks,
            "claim_b_checks": self.claim_b_checks,
            "contradiction_checks": self.contradiction_checks,
            "detail": self.detail,
        }


def _check_field_contradiction(
    field_name: str,
    evidence_a: PaymentEvidence,
    evidence_b: PaymentEvidence,
) -> CheckResult | None:
    """Check if a specific field contradicts between two evidence sets.

    Only checks fields that should be identical if both claims refer to the
    same transaction. Returns None if the field is not applicable.
    """
    # Only check if both evidences refer to the same transaction.
    if evidence_a.transaction_hash != evidence_b.transaction_hash:
        return None

    val_a = getattr(evidence_a, field_name, None)
    val_b = getattr(evidence_b, field_name, None)

    if val_a == val_b:
        return None  # No contradiction.

    return CheckResult(
        name=f"contradiction_{field_name}",
        status=FAIL,
        expected=str(val_a),
        actual=str(val_b),
        detail=f"Field {field_name!r} differs between evidence sets: "
               f"{val_a!r} vs {val_b!r}.",
    )


def find_contradictions(
    evidence_a: PaymentEvidence,
    evidence_b: PaymentEvidence,
) -> list[CheckResult]:
    """Find contradictions between two evidence sets.

    If both evidences refer to the same transaction, all fields should
    be identical (they come from the same ledger data). If they differ,
    something is wrong — either the evidence was tampered with or the
    two claims reference different transactions that were confused.

    If the evidences refer to different transactions, we check whether
    the claims are semantically contradictory (e.g., both claim to be
    "the payment for invoice INV-184" but reference different txs).
    """
    checks: list[CheckResult] = []

    same_tx = evidence_a.transaction_hash == evidence_b.transaction_hash

    if same_tx:
        # Same transaction — all fields must match. If they don't,
        # the evidence reconstruction is inconsistent.
        for field_name in (
            "ledger",
            "timestamp_unix",
            "successful",
            "sender",
            "recipient",
            "asset_code",
            "asset_issuer",
            "amount_stroops",
            "memo",
            "memo_type",
        ):
            result = _check_field_contradiction(field_name, evidence_a, evidence_b)
            if result is not None:
                checks.append(result)

        # Check the operations list — if both evidences come from the
        # same transaction, the operations must be identical. A different
        # operations list (e.g., a removed operation) would not be caught
        # by the top-level field checks above.
        ops_a = [op.to_dict() for op in evidence_a.operations]
        ops_b = [op.to_dict() for op in evidence_b.operations]
        if ops_a != ops_b:
            checks.append(
                CheckResult(
                    name="contradiction_operations",
                    status=FAIL,
                    expected=f"{len(ops_a)} operations",
                    actual=f"{len(ops_b)} operations",
                    detail="Operations list differs between evidence sets. "
                           "The evidence reconstruction is inconsistent.",
                )
            )

        if not checks:
            checks.append(
                CheckResult(
                    name="same_transaction_consistent",
                    status=PASS,
                    expected=evidence_a.transaction_hash,
                    actual=evidence_b.transaction_hash,
                    detail="Both evidence sets refer to the same transaction and are consistent.",
                )
            )
    else:
        # Different transactions — check for semantic contradictions.
        # If both claims reference the same reference/memo but different
        # transactions, that's a potential dispute about which payment
        # satisfies the obligation.
        checks.append(
            CheckResult(
                name="different_transactions",
                status=PASS,
                expected=evidence_a.transaction_hash,
                actual=evidence_b.transaction_hash,
                detail="Claims reference different transactions.",
            )
        )

        # Check if the references/memos collide.
        memo_a = evidence_a.memo if evidence_a.memo_type == "text" else None
        memo_b = evidence_b.memo if evidence_b.memo_type == "text" else None
        if (
            memo_a is not None
            and memo_b is not None
            and memo_a == memo_b
        ):
            checks.append(
                CheckResult(
                    name="same_reference_different_tx",
                    status=FAIL,
                    expected=memo_a,
                    actual=memo_b,
                    detail=f"Both claims reference {memo_a!r} but point to different transactions. "
                           f"Only one can satisfy the obligation.",
                )
            )

    return checks


def adjudicate_dispute(
    claim_a: PaymentClaim,
    evidence_a: PaymentEvidence | None,
    claim_b: PaymentClaim,
    evidence_b: PaymentEvidence | None,
) -> DisputeResult:
    """Adjudicate a dispute between two claims.

    Each claim is verified independently against its evidence. Then the
    evidence sets are compared for contradictions.

    Args:
        claim_a: The first claim.
        evidence_a: The evidence for claim A (None if not found).
        claim_b: The second claim.
        evidence_b: The evidence for claim B (None if not found).

    Returns:
        A DisputeResult with the verdicts and contradiction checks.
    """
    from .adjudicator import adjudicate, compute_verdict

    # Verify claim A.
    if evidence_a is None:
        verdict_a = INSUFFICIENT_EVIDENCE
        checks_a: list[CheckResult] = [
            CheckResult(
                name="transaction_exists",
                status=FAIL,
                expected=claim_a.transaction_hash,
                actual=None,
                detail="Transaction not found for claim A.",
            )
        ]
    else:
        checks_a = adjudicate(claim_a, evidence_a)
        verdict_a = compute_verdict(checks_a)

    # Verify claim B.
    if evidence_b is None:
        verdict_b = INSUFFICIENT_EVIDENCE
        checks_b: list[CheckResult] = [
            CheckResult(
                name="transaction_exists",
                status=FAIL,
                expected=claim_b.transaction_hash,
                actual=None,
                detail="Transaction not found for claim B.",
            )
        ]
    else:
        checks_b = adjudicate(claim_b, evidence_b)
        verdict_b = compute_verdict(checks_b)

    # Find contradictions.
    contradiction_checks: list[CheckResult] = []
    if evidence_a is not None and evidence_b is not None:
        contradiction_checks = find_contradictions(evidence_a, evidence_b)

    # Determine dispute verdict.
    has_contradiction = any(c.status == FAIL for c in contradiction_checks)

    if has_contradiction:
        dispute_verdict = CONTRADICTION
        detail = "The evidence sets contain contradictions."
    elif verdict_a == VERIFIED and verdict_b == VERIFIED:
        dispute_verdict = BOTH_VERIFIED
        detail = "Both claims are verified against the ledger."
    elif verdict_a == VERIFIED and verdict_b != VERIFIED:
        dispute_verdict = CLAIM_A_VERIFIED
        detail = "Claim A is verified; claim B is not."
    elif verdict_b == VERIFIED and verdict_a != VERIFIED:
        dispute_verdict = CLAIM_B_VERIFIED
        detail = "Claim B is verified; claim A is not."
    else:
        dispute_verdict = NEITHER_VERIFIED
        detail = "Neither claim is verified against the ledger."

    return DisputeResult(
        claim_a_verdict=verdict_a,
        claim_b_verdict=verdict_b,
        dispute_verdict=dispute_verdict,
        claim_a_checks=[c.to_dict() for c in checks_a],
        claim_b_checks=[c.to_dict() for c in checks_b],
        contradiction_checks=[c.to_dict() for c in contradiction_checks],
        detail=detail,
    )
