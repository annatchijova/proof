"""
test_verifier.py — Tests for the independent bundle verifier.

Each test states the invariant it defends and what mutation it would catch.
"""
from proof.canonicalize import CANONICALIZE_VERSION
from proof.claim import PaymentClaim
from proof.evidence import CheckResult, EvidenceBundle, PaymentEvidence, PaymentOperation
from proof.verifier import verify_bundle

TX_HASH = "a" * 64
SENDER = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
RECIPIENT = "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"


def _make_bundle(verdict="VERIFIED", checks=None, evidence=None) -> dict:
    """Build a valid bundle dict for testing."""
    if evidence is None:
        op = PaymentOperation(
            operation_type="payment",
            sender=SENDER,
            recipient=RECIPIENT,
            asset_code="XLM",
            asset_issuer=None,
            amount_stroops=1000000000,
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
            memo=None,
            memo_type="none",
            operation_type="payment",
            operations=[op],
        ).to_dict()

    if checks is None:
        checks = [
            CheckResult("transaction_exists", "PASS", TX_HASH, TX_HASH, "found").to_dict(),
            CheckResult("transaction_successful", "PASS", "success", "success", "ok").to_dict(),
        ]

    claim = PaymentClaim(transaction_hash=TX_HASH).to_dict()
    bundle = EvidenceBundle.build(
        claim=claim,
        evidence=evidence,
        checks=checks,
        verdict=verdict,
        chain_of_custody={"network": "testnet"},
    )
    return bundle.to_dict()


def test_valid_bundle_verifies():
    """Invariant: a correctly sealed bundle passes verification.

    Mutation caught: if the verifier recomputed the seal wrong, a valid
    bundle would fail.
    """
    bundle = _make_bundle()
    report = verify_bundle(bundle)
    assert report["seal_ok"] is True
    assert report["version_ok"] is True
    assert report["verdict_consistent"] is True
    assert report["issues"] == []


def test_tampered_seal_detected():
    """Invariant: a modified seal is detected.

    Mutation caught: if the verifier didn't compare seals, a tampered seal
    would pass.
    """
    bundle = _make_bundle()
    bundle["seal"] = "0" * 64
    report = verify_bundle(bundle)
    assert report["seal_ok"] is False
    assert len(report["issues"]) > 0


def test_tampered_evidence_detected():
    """Invariant: modifying the evidence after sealing breaks the seal.

    Mutation caught: if the seal didn't cover the evidence, changing it
    wouldn't be detected.
    """
    bundle = _make_bundle()
    bundle["evidence"]["amount_stroops"] = 999
    report = verify_bundle(bundle)
    assert report["seal_ok"] is False


def test_tampered_verdict_detected():
    """Invariant: modifying the verdict after sealing breaks the seal.

    Mutation caught: if the seal didn't cover the verdict, changing it
    wouldn't be detected.
    """
    bundle = _make_bundle(verdict="VERIFIED")
    bundle["verdict"] = "NOT_VERIFIED"
    report = verify_bundle(bundle)
    assert report["seal_ok"] is False


def test_tampered_checks_detected():
    """Invariant: modifying the checks after sealing breaks the seal.

    Mutation caught: if the seal didn't cover the checks, changing them
    wouldn't be detected.
    """
    bundle = _make_bundle()
    bundle["checks"][0]["status"] = "FAIL"
    report = verify_bundle(bundle)
    assert report["seal_ok"] is False


def test_inconsistent_verdict_detected():
    """Invariant: a verdict inconsistent with checks is flagged.

    Mutation caught: if the verifier didn't check verdict consistency,
    a NOT_VERIFIED with no FAIL checks would pass.
    """
    bundle = _make_bundle(verdict="NOT_VERIFIED")
    report = verify_bundle(bundle)
    assert report["verdict_consistent"] is False


def test_insufficient_evidence_with_failed_lookup_is_consistent():
    """Invariant: inability to obtain evidence remains distinct from mismatch."""
    bundle = _make_bundle(
        verdict="INSUFFICIENT_EVIDENCE",
        checks=[{
            "name": "transaction_exists",
            "status": "FAIL",
            "expected": TX_HASH,
            "actual": None,
            "detail": "not found",
        }],
    )
    report = verify_bundle(bundle)
    assert report["seal_ok"] is True
    assert report["verdict_consistent"] is True


def test_unknown_verdict_is_rejected():
    """Invariant: a valid seal cannot introduce a fourth verdict state."""
    bundle = _make_bundle(verdict="BOGUS")
    report = verify_bundle(bundle)
    assert report["seal_ok"] is True
    assert report["verdict_consistent"] is False
    assert any("unknown verdict" in issue for issue in report["issues"])


def test_chain_of_custody_outside_seal():
    """Invariant: modifying chain_of_custody does NOT break the seal.

    Mutation caught: if the chain of custody were inside the seal, changing
    it (e.g., updating fetched_at) would break verification.
    """
    bundle = _make_bundle()
    original_seal = bundle["seal"]
    bundle["chain_of_custody"]["fetched_at"] = 9999999999
    report = verify_bundle(bundle)
    assert report["seal_ok"] is True
