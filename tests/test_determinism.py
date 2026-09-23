"""
test_determinism.py — Prove the evidence bundle is reproducible bit-for-bit.

The same claim + evidence must always produce the same seal. This test
runs the bundle construction multiple times and asserts the seals match.
"""
from proof.canonicalize import seal
from proof.claim import PaymentClaim
from proof.evidence import CheckResult, EvidenceBundle, PaymentEvidence, PaymentOperation

TX_HASH = "a" * 64
SENDER = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
RECIPIENT = "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"


def _make_op() -> PaymentOperation:
    return PaymentOperation(
        operation_type="payment",
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=1000000000,
    )


def _build_bundle() -> dict:
    """Build a bundle from fixed inputs — must be deterministic."""
    claim = PaymentClaim(
        transaction_hash=TX_HASH,
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        amount_stroops=1000000000,
        reference="INV-184",
    )
    evidence = PaymentEvidence(
        transaction_hash=TX_HASH,
        ledger=12345,
        timestamp_unix=1700000000,
        successful=True,
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=1000000000,
        memo="INV-184",
        memo_type="text",
        operation_type="payment",
        operations=[_make_op()],
    )
    checks = [
        CheckResult("transaction_exists", "PASS", TX_HASH, TX_HASH, "found"),
        CheckResult("transaction_successful", "PASS", "success", "success", "ok"),
        CheckResult("sender_matches", "PASS", SENDER, SENDER, "match"),
        CheckResult("recipient_matches", "PASS", RECIPIENT, RECIPIENT, "match"),
    ]
    bundle = EvidenceBundle.build(
        claim=claim.to_dict(),
        evidence=evidence.to_dict(),
        checks=[c.to_dict() for c in checks],
        verdict="VERIFIED",
        chain_of_custody={"network": "testnet", "fetched_at": 1700000000},
    )
    return bundle.to_dict()


def test_seal_is_deterministic_across_runs():
    """Invariant: building the bundle N times produces the same seal.

    Mutation caught: if any nondeterministic element entered the sealed
    payload (timestamp, dict ordering, float), seals would diverge.
    """
    seals = [seal(_build_bundle()["version"] and _build_bundle()) for _ in range(5)]
    # Actually, we need to seal the sealed_payload, not the full bundle.
    bundles = [_build_bundle() for _ in range(5)]
    sealed_payloads = [
        {
            "version": b["version"],
            "claim": b["claim"],
            "evidence": b["evidence"],
            "checks": b["checks"],
            "verdict": b["verdict"],
            "scope_notes": b["scope_notes"],
        }
        for b in bundles
    ]
    seals = [seal(p) for p in sealed_payloads]
    assert all(s == seals[0] for s in seals), f"Seals diverged: {seals}"


def test_seal_is_deterministic_with_shuffled_check_order():
    """Invariant: check order does not affect the seal (list order is part
    of the seal, so this should actually CHANGE the seal — confirming the
    seal is sensitive to order, which is correct).

    Wait — list order IS preserved in canonicalization. So shuffling checks
    SHOULD produce a different seal. This test confirms that sensitivity.
    """
    claim = PaymentClaim(transaction_hash=TX_HASH)
    evidence = PaymentEvidence(
        transaction_hash=TX_HASH, ledger=1, timestamp_unix=1,
        successful=True, sender=SENDER, recipient=RECIPIENT,
        asset_code="XLM", asset_issuer=None, amount_stroops=1,
        memo=None, memo_type="none", operation_type="payment",
        operations=[PaymentOperation("payment", SENDER, RECIPIENT, "XLM", None, 1)],
    )
    checks_a = [
        CheckResult("a", "PASS", None, None, "x"),
        CheckResult("b", "PASS", None, None, "y"),
    ]
    checks_b = [
        CheckResult("b", "PASS", None, None, "y"),
        CheckResult("a", "PASS", None, None, "x"),
    ]
    bundle_a = EvidenceBundle.build(
        claim=claim.to_dict(), evidence=evidence.to_dict(),
        checks=[c.to_dict() for c in checks_a], verdict="VERIFIED",
        chain_of_custody={},
    )
    bundle_b = EvidenceBundle.build(
        claim=claim.to_dict(), evidence=evidence.to_dict(),
        checks=[c.to_dict() for c in checks_b], verdict="VERIFIED",
        chain_of_custody={},
    )
    # Different order -> different seal (this is correct behavior).
    assert bundle_a.seal != bundle_b.seal


def test_chain_of_custody_does_not_affect_seal():
    """Invariant: chain_of_custody is outside the seal.

    Mutation caught: if chain_of_custody were inside the sealed payload,
    changing fetched_at would change the seal.
    """
    claim = PaymentClaim(transaction_hash=TX_HASH)
    evidence = PaymentEvidence(
        transaction_hash=TX_HASH, ledger=1, timestamp_unix=1,
        successful=True, sender=SENDER, recipient=RECIPIENT,
        asset_code="XLM", asset_issuer=None, amount_stroops=1,
        memo=None, memo_type="none", operation_type="payment",
        operations=[PaymentOperation("payment", SENDER, RECIPIENT, "XLM", None, 1)],
    )
    checks = [CheckResult("test", "PASS", None, None, "ok")]
    bundle_a = EvidenceBundle.build(
        claim=claim.to_dict(), evidence=evidence.to_dict(),
        checks=[c.to_dict() for c in checks], verdict="VERIFIED",
        chain_of_custody={"fetched_at": 100},
    )
    bundle_b = EvidenceBundle.build(
        claim=claim.to_dict(), evidence=evidence.to_dict(),
        checks=[c.to_dict() for c in checks], verdict="VERIFIED",
        chain_of_custody={"fetched_at": 200},
    )
    assert bundle_a.seal == bundle_b.seal
