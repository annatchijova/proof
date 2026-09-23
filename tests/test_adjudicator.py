"""
test_adjudicator.py — Tests for the claim vs evidence adjudication.

Each test states the invariant it defends and what mutation it would catch.
"""
from proof.adjudicator import adjudicate, compute_verdict
from proof.claim import PaymentClaim
from proof.evidence import (
    ABSTAIN,
    FAIL,
    NOT_VERIFIED,
    PASS,
    PaymentEvidence,
    PaymentOperation,
    VERIFIED,
)

# Valid Stellar addresses for testing.
SENDER = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
RECIPIENT = "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
TX_HASH = "a" * 64


def _make_op(**overrides) -> PaymentOperation:
    defaults = dict(
        operation_type="payment",
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=1000000000,
    )
    defaults.update(overrides)
    return PaymentOperation(**defaults)


def _make_evidence(**overrides) -> PaymentEvidence:
    op = _make_op()
    defaults = dict(
        transaction_hash=TX_HASH,
        ledger=12345,
        timestamp_unix=1700000000,
        successful=True,
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=1000000000,  # 100 XLM
        memo="INV-184",
        memo_type="text",
        operation_type="payment",
        operations=[op],
    )
    defaults.update(overrides)
    return PaymentEvidence(**defaults)


def _make_claim(**overrides) -> PaymentClaim:
    defaults = dict(
        transaction_hash=TX_HASH,
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        amount_stroops=1000000000,
        reference="INV-184",
    )
    defaults.update(overrides)
    return PaymentClaim(**defaults)


def test_all_match_verifies():
    """Invariant: when all claim propositions match the evidence, verdict is VERIFIED.

    Mutation caught: if compute_verdict ignored PASS checks, a fully matching
    claim would not verify.
    """
    claim = _make_claim()
    evidence = _make_evidence()
    checks = adjudicate(claim, evidence)
    verdict = compute_verdict(checks)
    assert verdict == VERIFIED
    # ledger_within_window is ABSTAIN (no window in claim), not PASS.
    assert not any(c.status == FAIL for c in checks)


def test_recipient_mismatch_not_verified():
    """Invariant: a mismatched recipient produces NOT_VERIFIED.

    Mutation caught: if the recipient check were removed, a wrong recipient
    would still verify.
    """
    wrong_recipient = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2A"
    claim = _make_claim(recipient=wrong_recipient)
    evidence = _make_evidence()
    checks = adjudicate(claim, evidence)
    verdict = compute_verdict(checks)
    assert verdict == NOT_VERIFIED
    recipient_check = next(c for c in checks if c.name == "recipient_matches")
    assert recipient_check.status == FAIL


def test_amount_mismatch_not_verified():
    """Invariant: a mismatched amount produces NOT_VERIFIED.

    Mutation caught: if the amount check compared as float, rounding could
    make a wrong amount pass.
    """
    claim = _make_claim(amount_stroops=999999999)
    evidence = _make_evidence()
    checks = adjudicate(claim, evidence)
    verdict = compute_verdict(checks)
    assert verdict == NOT_VERIFIED
    amount_check = next(c for c in checks if c.name == "amount_matches")
    assert amount_check.status == FAIL


def test_failed_transaction_not_verified():
    """Invariant: a failed transaction always produces NOT_VERIFIED.

    Mutation caught: if the successful check were removed, a failed tx
    would verify.
    """
    claim = _make_claim()
    evidence = _make_evidence(successful=False)
    checks = adjudicate(claim, evidence)
    verdict = compute_verdict(checks)
    assert verdict == NOT_VERIFIED
    success_check = next(c for c in checks if c.name == "transaction_successful")
    assert success_check.status == FAIL


def test_abstain_for_unspecified_fields():
    """Invariant: fields not in the claim are ABSTAIN, not PASS or FAIL.

    Mutation caught: if None fields were treated as PASS, an empty claim
    would verify without checking anything.
    """
    claim = PaymentClaim(transaction_hash=TX_HASH)
    evidence = _make_evidence()
    checks = adjudicate(claim, evidence)
    sender_check = next(c for c in checks if c.name == "sender_matches")
    assert sender_check.status == ABSTAIN
    amount_check = next(c for c in checks if c.name == "amount_matches")
    assert amount_check.status == ABSTAIN


def test_empty_claim_still_verifies():
    """Invariant: a claim with only the tx hash still verifies if the tx exists.

    This is correct: the claim is "this transaction is a payment" — and it is.
    The scope notes remind the user what PROOF does NOT prove.
    """
    claim = PaymentClaim(transaction_hash=TX_HASH)
    evidence = _make_evidence()
    checks = adjudicate(claim, evidence)
    verdict = compute_verdict(checks)
    assert verdict == VERIFIED


def test_ledger_window_pass():
    """Invariant: ledger within the claimed window passes.

    Mutation caught: if the window check used float comparison, boundary
    issues could arise.
    """
    claim = _make_claim(ledger_min=12340, ledger_max=12350)
    evidence = _make_evidence(ledger=12345)
    checks = adjudicate(claim, evidence)
    window_check = next(c for c in checks if c.name == "ledger_within_window")
    assert window_check.status == PASS


def test_ledger_window_fail():
    """Invariant: ledger outside the claimed window fails.

    Mutation caught: if the window check were inverted, an out-of-window
    tx would pass.
    """
    claim = _make_claim(ledger_min=12340, ledger_max=12350)
    evidence = _make_evidence(ledger=12399)
    checks = adjudicate(claim, evidence)
    window_check = next(c for c in checks if c.name == "ledger_within_window")
    assert window_check.status == FAIL


def test_reference_mismatch_not_verified():
    """Invariant: a mismatched memo/reference produces NOT_VERIFIED.

    Mutation caught: if the reference check were removed, a payment with
    the wrong memo would verify.
    """
    claim = _make_claim(reference="INV-999")
    evidence = _make_evidence(memo="INV-184")
    checks = adjudicate(claim, evidence)
    verdict = compute_verdict(checks)
    assert verdict == NOT_VERIFIED
    ref_check = next(c for c in checks if c.name == "reference_matches")
    assert ref_check.status == FAIL


def test_asset_with_issuer_match():
    """Invariant: asset code + issuer must both match for non-native assets.

    Mutation caught: if issuer were ignored, USDC from issuer A would match
    USDC from issuer B.
    """
    issuer = "GBXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
    claim = _make_claim(asset_code="USDC", asset_issuer=issuer)
    evidence = _make_evidence(asset_code="USDC", asset_issuer=issuer)
    checks = adjudicate(claim, evidence)
    asset_check = next(c for c in checks if c.name == "asset_matches")
    assert asset_check.status == PASS


def test_asset_issuer_mismatch():
    """Invariant: same asset code but different issuer fails.

    Mutation caught: if issuer comparison were removed, wrong-issuer USDC
    would pass.
    """
    issuer_a = "GBXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
    issuer_b = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
    claim = _make_claim(asset_code="USDC", asset_issuer=issuer_a)
    evidence = _make_evidence(asset_code="USDC", asset_issuer=issuer_b)
    checks = adjudicate(claim, evidence)
    asset_check = next(c for c in checks if c.name == "asset_matches")
    assert asset_check.status == FAIL
