"""
adjudicator.py — Compare a payment claim against ledger evidence.

Each proposition in the claim is checked independently against the evidence.
A proposition not present in the claim (None) is ABSTAIN-ed, not assumed true.
A proposition present and matching is PASS. A proposition present and not
matching is FAIL.

The verdict is:
  VERIFIED           — all applicable checks PASS
  NOT_VERIFIED       — at least one check FAIL
  INSUFFICIENT_EVIDENCE — the transaction could not be found or fetched

No float, no probability, no LLM. Pure deterministic comparison.
"""
from __future__ import annotations

from .claim import PaymentClaim
from .evidence import (
    ABSTAIN,
    FAIL,
    INSUFFICIENT_EVIDENCE,
    NOT_VERIFIED,
    PASS,
    CheckResult,
    PaymentEvidence,
    VERIFIED,
)


def _check(
    name: str,
    claim_value: object | None,
    evidence_value: object,
    detail_pass: str,
    detail_fail: str,
) -> CheckResult:
    """Check one proposition: claim_value vs evidence_value."""
    if claim_value is None:
        return CheckResult(
            name=name,
            status=ABSTAIN,
            expected=None,
            actual=str(evidence_value),
            detail=f"No {name} asserted in claim — not checked.",
        )
    if claim_value == evidence_value:
        return CheckResult(
            name=name,
            status=PASS,
            expected=str(claim_value),
            actual=str(evidence_value),
            detail=detail_pass,
        )
    return CheckResult(
        name=name,
        status=FAIL,
        expected=str(claim_value),
        actual=str(evidence_value),
        detail=detail_fail,
    )


def _check_asset(
    claim: PaymentClaim, evidence: PaymentEvidence
) -> CheckResult:
    """Check asset code and issuer together.

    For path payments, the evidence may have source_asset fields on the
    first operation. If the claim specifies an asset that matches the source
    asset but not the destination, we still FAIL — the claim should match
    the destination asset (what the recipient received).
    """
    if claim.asset_code is None:
        return CheckResult(
            name="asset_matches",
            status=ABSTAIN,
            expected=None,
            actual=f"{evidence.asset_code}:{evidence.asset_issuer or 'native'}",
            detail="No asset asserted in claim — not checked.",
        )

    claim_asset = claim.asset_code
    evidence_asset = evidence.asset_code

    # Also check issuer if the claim specifies one and the asset is not native.
    if claim.asset_issuer is not None and evidence.asset_issuer is not None:
        if claim_asset == evidence_asset and claim.asset_issuer == evidence.asset_issuer:
            return CheckResult(
                name="asset_matches",
                status=PASS,
                expected=f"{claim_asset}:{claim.asset_issuer}",
                actual=f"{evidence_asset}:{evidence.asset_issuer}",
                detail="Asset code and issuer match.",
            )
        return CheckResult(
            name="asset_matches",
            status=FAIL,
            expected=f"{claim_asset}:{claim.asset_issuer}",
            actual=f"{evidence_asset}:{evidence.asset_issuer}",
            detail="Asset code or issuer does not match.",
        )

    # Native asset (XLM) or issuer not specified in claim.
    if claim_asset == evidence_asset:
        return CheckResult(
            name="asset_matches",
            status=PASS,
            expected=claim_asset,
            actual=evidence_asset,
            detail="Asset code matches.",
        )
    return CheckResult(
        name="asset_matches",
        status=FAIL,
        expected=claim_asset,
        actual=evidence_asset,
        detail="Asset code does not match.",
    )


def _check_source_asset(
    claim: PaymentClaim, evidence: PaymentEvidence
) -> CheckResult:
    """Check source asset for path payments.

    Only applicable when the evidence has a source asset (path payments).
    If the claim doesn't specify a source asset, ABSTAIN. If the evidence
    doesn't have a source asset, ABSTAIN (not a path payment).
    """
    if not evidence.operations:
        return CheckResult(
            name="source_asset_matches",
            status=ABSTAIN,
            expected=None,
            actual=None,
            detail="No operations in evidence — not checked.",
        )

    first_op = evidence.operations[0]
    if first_op.source_asset_code is None:
        return CheckResult(
            name="source_asset_matches",
            status=ABSTAIN,
            expected=None,
            actual=None,
            detail="Not a path payment — no source asset in evidence.",
        )

    # The claim doesn't have a source_asset field yet (L3 doesn't add it
    # to PaymentClaim). This check is structural — it reports the source
    # asset for informational purposes. ABSTAIN until the claim can express
    # source asset expectations.
    return CheckResult(
        name="source_asset_matches",
        status=ABSTAIN,
        expected=None,
        actual=f"{first_op.source_asset_code}:{first_op.source_asset_issuer or 'native'}",
        detail="Source asset present in path payment — claim has no source asset assertion.",
    )


def _check_ledger_window(
    claim: PaymentClaim, evidence: PaymentEvidence
) -> CheckResult:
    """Check that the transaction ledger falls within the claimed window."""
    if claim.ledger_min is None and claim.ledger_max is None:
        return CheckResult(
            name="ledger_within_window",
            status=ABSTAIN,
            expected=None,
            actual=str(evidence.ledger),
            detail="No ledger window asserted in claim — not checked.",
        )

    lo = claim.ledger_min if claim.ledger_min is not None else 0
    hi = claim.ledger_max if claim.ledger_max is not None else float("inf")

    if lo <= evidence.ledger <= hi:
        return CheckResult(
            name="ledger_within_window",
            status=PASS,
            expected=f"[{lo}, {hi if hi != float('inf') else 'unbounded'}]",
            actual=str(evidence.ledger),
            detail="Transaction ledger is within the claimed window.",
        )
    return CheckResult(
        name="ledger_within_window",
        status=FAIL,
        expected=f"[{lo}, {hi if hi != float('inf') else 'unbounded'}]",
        actual=str(evidence.ledger),
        detail="Transaction ledger is outside the claimed window.",
    )


def adjudicate(
    claim: PaymentClaim, evidence: PaymentEvidence
) -> list[CheckResult]:
    """Run all applicable checks of the claim against the evidence."""
    checks: list[CheckResult] = []

    # 1. Transaction exists — if we got here, it was found.
    checks.append(
        CheckResult(
            name="transaction_exists",
            status=PASS,
            expected=claim.transaction_hash,
            actual=evidence.transaction_hash,
            detail=f"Transaction found on ledger {evidence.ledger}.",
        )
    )

    # 2. Transaction successful.
    if evidence.successful:
        checks.append(
            CheckResult(
                name="transaction_successful",
                status=PASS,
                expected="success",
                actual="success",
                detail="Transaction succeeded on ledger.",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="transaction_successful",
                status=FAIL,
                expected="success",
                actual="failed",
                detail="Transaction failed on ledger — no effect was applied.",
            )
        )

    # 3. Sender matches.
    checks.append(
        _check(
            "sender_matches",
            claim.sender,
            evidence.sender,
            "Sender matches the claimed address.",
            "Sender does not match the claimed address.",
        )
    )

    # 4. Recipient matches.
    checks.append(
        _check(
            "recipient_matches",
            claim.recipient,
            evidence.recipient,
            "Recipient matches the claimed address.",
            "Recipient does not match the claimed address.",
        )
    )

    # 5. Asset matches.
    checks.append(_check_asset(claim, evidence))

    # 5b. Source asset (path payments) — informational, ABSTAIN for now.
    checks.append(_check_source_asset(claim, evidence))

    # 6. Amount matches.
    checks.append(
        _check(
            "amount_matches",
            claim.amount_stroops,
            evidence.amount_stroops,
            "Amount matches the claimed value.",
            "Amount does not match the claimed value.",
        )
    )

    # 7. Ledger within window.
    checks.append(_check_ledger_window(claim, evidence))

    # 8. Reference/memo matches.
    # Only compare against the memo when the memo type is "text". Hash and
    # return memos are binary and don't have a string representation that
    # a claim's reference field would match meaningfully.
    if evidence.memo_type == "text":
        checks.append(
            _check(
                "reference_matches",
                claim.reference,
                evidence.memo,
                "Reference/memo matches the claimed value.",
                "Reference/memo does not match the claimed value.",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="reference_matches",
                status=ABSTAIN,
                expected=claim.reference,
                actual=f"memo_type={evidence.memo_type}",
                detail=f"Memo type is {evidence.memo_type!r}, not 'text' — reference not checked.",
            )
        )

    return checks


def compute_verdict(checks: list[CheckResult]) -> str:
    """Compute the overall verdict from the check results.

    FAIL dominates: any FAIL means NOT_VERIFIED.
    If no FAIL and at least one PASS, VERIFIED.
    If all ABSTAIN (no PASS, no FAIL), that means the claim was empty —
    we still return VERIFIED because the transaction exists and is the one
    claimed, even if no specific propositions were asserted.
    """
    has_fail = any(c.status == FAIL for c in checks)
    if has_fail:
        return NOT_VERIFIED
    return VERIFIED
