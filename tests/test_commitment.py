"""
test_commitment.py — Tests for L4 commitments and receipts.

Each test states the invariant it defends and what mutation it would catch.
"""
import base64
import pytest

from proof.adjudicator import adjudicate_with_commitment, compute_verdict
from proof.claim import PaymentClaim
from proof.commitment import (
    COMMITMENT_KEY_PREFIX,
    CommitmentTerms,
    PaymentCommitment,
    Receipt,
    compute_commitment_hash,
    commitment_key,
)
from proof.commitment_extractor import (
    CommitmentExtractionError,
    extract_commitment,
)
from proof.evidence import (
    ABSTAIN,
    FAIL,
    NOT_VERIFIED,
    PASS,
    PaymentEvidence,
    PaymentOperation,
    VERIFIED,
)
from proof.engine import issue_receipt
from proof.evidence import EvidenceBundle

TX_HASH = "a" * 64
COMMIT_TX_HASH = "b" * 64
SENDER = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
RECIPIENT = "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
ISSUER = "GBXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"


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
    # If amount_stroops is overridden, propagate to the operation so the
    # evidence is internally consistent (as it would be in real extraction).
    op_overrides = {}
    if "amount_stroops" in overrides:
        op_overrides["amount_stroops"] = overrides["amount_stroops"]
    if "sender" in overrides:
        op_overrides["sender"] = overrides["sender"]
    if "recipient" in overrides:
        op_overrides["recipient"] = overrides["recipient"]
    if "asset_code" in overrides:
        op_overrides["asset_code"] = overrides["asset_code"]
    if "asset_issuer" in overrides:
        op_overrides["asset_issuer"] = overrides["asset_issuer"]
    op = _make_op(**op_overrides)
    defaults = dict(
        transaction_hash=TX_HASH,
        ledger=200,
        timestamp_unix=1700001000,
        successful=True,
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=1000000000,
        memo="INV-184",
        memo_type="text",
        operation_type="payment",
        operations=[op],
    )
    defaults.update(overrides)
    return PaymentEvidence(**defaults)


def _make_terms(**overrides) -> CommitmentTerms:
    defaults = dict(
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=1000000000,
        reference="INV-184",
    )
    defaults.update(overrides)
    return CommitmentTerms(**defaults)


def _make_commitment(**overrides) -> PaymentCommitment:
    terms = _make_terms()
    defaults = dict(
        commitment_tx_hash=COMMIT_TX_HASH,
        commitment_ledger=100,
        commitment_timestamp_unix=1700000000,
        reference="INV-184",
        committed_hash=terms.commitment_hash(),
        terms=terms,
    )
    defaults.update(overrides)
    return PaymentCommitment(**defaults)


class TestCommitmentTerms:
    def test_commitment_hash_is_deterministic(self):
        """Invariant: same terms produce the same commitment hash.

        Mutation caught: if any nondeterministic element entered the hash,
        two calls would differ.
        """
        terms = _make_terms()
        assert terms.commitment_hash() == terms.commitment_hash()

    def test_different_terms_produce_different_hashes(self):
        """Invariant: different terms produce different hashes.

        Mutation caught: if amount were ignored, changing it wouldn't
        change the hash.
        """
        a = _make_terms().commitment_hash()
        b = _make_terms(amount_stroops=999999999).commitment_hash()
        assert a != b

    def test_reference_affects_hash(self):
        """Invariant: reference is part of the commitment hash.

        Mutation caught: if reference were excluded, two commitments
        with different references would collide.
        """
        a = _make_terms(reference="INV-184").commitment_hash()
        b = _make_terms(reference="INV-999").commitment_hash()
        assert a != b

    def test_compute_commitment_hash_helper(self):
        """Invariant: the helper function produces the same hash as CommitmentTerms."""
        terms = _make_terms()
        helper_hash = compute_commitment_hash(
            sender=terms.sender,
            recipient=terms.recipient,
            asset_code=terms.asset_code,
            asset_issuer=terms.asset_issuer,
            amount_stroops=terms.amount_stroops,
            reference=terms.reference,
        )
        assert helper_hash == terms.commitment_hash()

    def test_commitment_key_format(self):
        """Invariant: commitment_key produces the correct manage_data key."""
        key = commitment_key("INV-184")
        assert key == f"{COMMITMENT_KEY_PREFIX}INV-184"

    def test_commitment_key_rejects_empty(self):
        """Invariant: empty reference is rejected."""
        with pytest.raises(ValueError):
            commitment_key("")


class TestCommitmentAdjudication:
    def test_commitment_match_passes(self):
        """Invariant: when payment matches commitment, commitment checks PASS.

        Mutation caught: if the hash check were removed, any payment
        would match any commitment.
        """
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        evidence = _make_evidence()
        commitment = _make_commitment()
        checks = adjudicate_with_commitment(claim, evidence, commitment)
        hash_check = next(c for c in checks if c.name == "commitment_hash_matches")
        assert hash_check.status == PASS

    def test_commitment_mismatch_fails(self):
        """Invariant: when payment doesn't match commitment, FAIL.

        Mutation caught: if the hash comparison were removed, a wrong
        payment would still verify.
        """
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        evidence = _make_evidence(amount_stroops=999999999)
        commitment = _make_commitment()  # hash for 1000000000 stroops
        checks = adjudicate_with_commitment(claim, evidence, commitment)
        hash_check = next(c for c in checks if c.name == "commitment_hash_matches")
        assert hash_check.status == FAIL

    def test_commitment_precedes_payment_passes(self):
        """Invariant: commitment registered before payment passes temporal check."""
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        evidence = _make_evidence(ledger=200)
        commitment = _make_commitment(commitment_ledger=100)
        checks = adjudicate_with_commitment(claim, evidence, commitment)
        temporal_check = next(c for c in checks if c.name == "commitment_precedes_payment")
        assert temporal_check.status == PASS

    def test_commitment_after_payment_fails(self):
        """Invariant: commitment registered after payment fails temporal check.

        Mutation caught: if temporal order weren't checked, someone could
        register a commitment after seeing the payment and claim it was
        pre-registered.
        """
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        evidence = _make_evidence(ledger=100)
        commitment = _make_commitment(commitment_ledger=200)
        checks = adjudicate_with_commitment(claim, evidence, commitment)
        temporal_check = next(c for c in checks if c.name == "commitment_precedes_payment")
        assert temporal_check.status == FAIL

    def test_no_commitment_abstains(self):
        """Invariant: no commitment produces ABSTAIN, not FAIL.

        Mutation caught: if missing commitment were treated as FAIL,
        every payment without a commitment would be NOT_VERIFIED.
        """
        claim = PaymentClaim(transaction_hash=TX_HASH)
        evidence = _make_evidence()
        checks = adjudicate_with_commitment(claim, evidence, None)
        exists_check = next(c for c in checks if c.name == "commitment_exists")
        assert exists_check.status == ABSTAIN
        hash_check = next(c for c in checks if c.name == "commitment_hash_matches")
        assert hash_check.status == ABSTAIN

    def test_commitment_mismatch_produces_not_verified(self):
        """Invariant: commitment mismatch makes the whole verdict NOT_VERIFIED."""
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        evidence = _make_evidence(amount_stroops=999999999)
        commitment = _make_commitment()
        checks = adjudicate_with_commitment(claim, evidence, commitment)
        verdict = compute_verdict(checks)
        assert verdict == NOT_VERIFIED

    def test_commitment_match_still_verifies(self):
        """Invariant: commitment match doesn't break VERIFIED."""
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        evidence = _make_evidence()
        commitment = _make_commitment()
        checks = adjudicate_with_commitment(claim, evidence, commitment)
        verdict = compute_verdict(checks)
        assert verdict == VERIFIED


class TestCommitmentExtractor:
    def _make_commit_tx_data(self, key="PROOF:COMMIT:INV-184", value=None):
        if value is None:
            terms = _make_terms()
            value = base64.b64encode(terms.commitment_hash().encode("utf-8")).decode("utf-8")
        return {
            "hash": COMMIT_TX_HASH,
            "ledger": 100,
            "created_at": "2024-01-01T00:00:00Z",
            "successful": True,
        }

    def _make_manage_data_op(self, key="PROOF:COMMIT:INV-184", value=None):
        if value is None:
            terms = _make_terms()
            value = base64.b64encode(terms.commitment_hash().encode("utf-8")).decode("utf-8")
        return {
            "type": "manage_data",
            "name": key,
            "value": value,
            "source_account": SENDER,
        }

    def test_extract_commitment_success(self):
        """Invariant: a valid manage_data commitment is extracted correctly."""
        tx = self._make_commit_tx_data()
        ops = [self._make_manage_data_op()]
        commitment = extract_commitment(tx, ops)
        assert commitment.commitment_tx_hash == COMMIT_TX_HASH
        assert commitment.reference == "INV-184"
        assert commitment.commitment_ledger == 100
        assert len(commitment.committed_hash) == 64

    def test_extract_fails_on_failed_tx(self):
        """Invariant: a failed commitment transaction raises.

        Mutation caught: if success weren't checked, a failed tx would
        produce a commitment that was never applied.
        """
        tx = self._make_commit_tx_data()
        tx["successful"] = False
        ops = [self._make_manage_data_op()]
        with pytest.raises(CommitmentExtractionError, match="failed"):
            extract_commitment(tx, ops)

    def test_extract_fails_without_commitment_op(self):
        """Invariant: no manage_data with PROOF prefix raises."""
        tx = self._make_commit_tx_data()
        ops = [{"type": "payment", "from": SENDER, "to": RECIPIENT, "amount": "1.0", "asset_type": "native"}]
        with pytest.raises(CommitmentExtractionError, match="no manage_data"):
            extract_commitment(tx, ops)

    def test_extract_fails_on_invalid_hash(self):
        """Invariant: a value that's not a 64-char hex hash raises."""
        tx = self._make_commit_tx_data()
        ops = [self._make_manage_data_op(
            value=base64.b64encode(b"short").decode("utf-8")
        )]
        with pytest.raises(CommitmentExtractionError, match="64 chars"):
            extract_commitment(tx, ops)

    def test_extract_fails_on_empty_reference(self):
        """Invariant: a commitment key with empty reference raises."""
        tx = self._make_commit_tx_data()
        ops = [self._make_manage_data_op(key="PROOF:COMMIT:")]
        with pytest.raises(CommitmentExtractionError, match="empty reference"):
            extract_commitment(tx, ops)


class TestReceipt:
    def test_receipt_creation(self):
        """Invariant: a receipt can be created from a bundle."""
        op = _make_op()
        evidence = PaymentEvidence(
            transaction_hash=TX_HASH, ledger=1, timestamp_unix=1,
            successful=True, sender=SENDER, recipient=RECIPIENT,
            asset_code="XLM", asset_issuer=None, amount_stroops=1000000000,
            memo=None, memo_type="none", operation_type="payment",
            operations=[op],
        )
        claim = PaymentClaim(transaction_hash=TX_HASH)
        bundle = EvidenceBundle.build(
            claim=claim.to_dict(),
            evidence=evidence.to_dict(),
            checks=[],
            verdict=VERIFIED,
            chain_of_custody={},
        )
        receipt = issue_receipt(bundle)
        assert receipt.transaction_hash == TX_HASH
        assert receipt.verdict == VERIFIED
        assert receipt.seal == bundle.seal

    def test_receipt_manage_data_key(self):
        """Invariant: the manage_data key has the correct format."""
        receipt = Receipt(
            transaction_hash=TX_HASH,
            verdict=VERIFIED,
            seal="a" * 64,
            issued_at=1700000000,
        )
        assert receipt.manage_data_key == "PROOF:RECEIPT:" + TX_HASH

    def test_receipt_manage_data_value(self):
        """Invariant: the manage_data value is the seal."""
        receipt = Receipt(
            transaction_hash=TX_HASH,
            verdict=VERIFIED,
            seal="a" * 64,
            issued_at=1700000000,
        )
        assert receipt.manage_data_value == "a" * 64

    def test_receipt_rejects_invalid_tx_hash(self):
        """Invariant: invalid tx hash is rejected."""
        with pytest.raises(ValueError):
            Receipt(
                transaction_hash="invalid",
                verdict=VERIFIED,
                seal="a" * 64,
                issued_at=1700000000,
            )

    def test_receipt_rejects_invalid_seal(self):
        """Invariant: invalid seal length is rejected."""
        with pytest.raises(ValueError):
            Receipt(
                transaction_hash=TX_HASH,
                verdict=VERIFIED,
                seal="short",
                issued_at=1700000000,
            )


class TestCommitmentInBundle:
    def test_bundle_with_commitment_includes_it(self):
        """Invariant: a bundle with a commitment includes it in to_dict."""
        op = _make_op()
        evidence = PaymentEvidence(
            transaction_hash=TX_HASH, ledger=200, timestamp_unix=1700001000,
            successful=True, sender=SENDER, recipient=RECIPIENT,
            asset_code="XLM", asset_issuer=None, amount_stroops=1000000000,
            memo="INV-184", memo_type="text", operation_type="payment",
            operations=[op],
        )
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        commitment = _make_commitment()
        bundle = EvidenceBundle.build(
            claim=claim.to_dict(),
            evidence=evidence.to_dict(),
            checks=[],
            verdict=VERIFIED,
            chain_of_custody={},
            commitment=commitment.to_dict(),
        )
        d = bundle.to_dict()
        assert "commitment" in d
        assert d["commitment"]["reference"] == "INV-184"

    def test_bundle_without_commitment_omits_it(self):
        """Invariant: a bundle without a commitment doesn't include the field."""
        op = _make_op()
        evidence = PaymentEvidence(
            transaction_hash=TX_HASH, ledger=1, timestamp_unix=1,
            successful=True, sender=SENDER, recipient=RECIPIENT,
            asset_code="XLM", asset_issuer=None, amount_stroops=1,
            memo=None, memo_type="none", operation_type="payment",
            operations=[op],
        )
        claim = PaymentClaim(transaction_hash=TX_HASH)
        bundle = EvidenceBundle.build(
            claim=claim.to_dict(),
            evidence=evidence.to_dict(),
            checks=[],
            verdict=VERIFIED,
            chain_of_custody={},
        )
        d = bundle.to_dict()
        assert "commitment" not in d

    def test_commitment_is_in_sealed_payload(self):
        """Invariant: commitment is part of the sealed payload.

        Mutation caught: if commitment were outside the seal, modifying it
        wouldn't break verification.
        """
        op = _make_op()
        evidence = PaymentEvidence(
            transaction_hash=TX_HASH, ledger=200, timestamp_unix=1700001000,
            successful=True, sender=SENDER, recipient=RECIPIENT,
            asset_code="XLM", asset_issuer=None, amount_stroops=1000000000,
            memo="INV-184", memo_type="text", operation_type="payment",
            operations=[op],
        )
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        commitment = _make_commitment()
        bundle = EvidenceBundle.build(
            claim=claim.to_dict(),
            evidence=evidence.to_dict(),
            checks=[],
            verdict=VERIFIED,
            chain_of_custody={},
            commitment=commitment.to_dict(),
        )
        sealed = bundle.sealed_payload
        assert "commitment" in sealed

    def test_tampering_commitment_breaks_seal(self):
        """Invariant: modifying the commitment after sealing breaks the seal."""
        from proof.verifier import verify_bundle

        op = _make_op()
        evidence = PaymentEvidence(
            transaction_hash=TX_HASH, ledger=200, timestamp_unix=1700001000,
            successful=True, sender=SENDER, recipient=RECIPIENT,
            asset_code="XLM", asset_issuer=None, amount_stroops=1000000000,
            memo="INV-184", memo_type="text", operation_type="payment",
            operations=[op],
        )
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        commitment = _make_commitment()
        bundle = EvidenceBundle.build(
            claim=claim.to_dict(),
            evidence=evidence.to_dict(),
            checks=[],
            verdict=VERIFIED,
            chain_of_custody={},
            commitment=commitment.to_dict(),
        )
        d = bundle.to_dict()
        d["commitment"]["reference"] = "TAMPERED"
        report = verify_bundle(d)
        assert report["seal_ok"] is False


class TestClaimCommitmentField:
    def test_claim_accepts_commitment_tx_hash(self):
        """Invariant: PaymentClaim accepts commitment_tx_hash."""
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        assert claim.commitment_tx_hash == COMMIT_TX_HASH

    def test_claim_rejects_invalid_commitment_tx_hash(self):
        """Invariant: invalid commitment_tx_hash is rejected at the boundary."""
        with pytest.raises(ValueError, match="commitment_tx_hash"):
            PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash="invalid")

    def test_claim_to_dict_includes_commitment_tx_hash(self):
        """Invariant: to_dict includes commitment_tx_hash when set."""
        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        d = claim.to_dict()
        assert "commitment_tx_hash" in d
        assert d["commitment_tx_hash"] == COMMIT_TX_HASH

    def test_claim_to_dict_omits_commitment_tx_hash_when_none(self):
        """Invariant: to_dict omits commitment_tx_hash when not set."""
        claim = PaymentClaim(transaction_hash=TX_HASH)
        d = claim.to_dict()
        assert "commitment_tx_hash" not in d


class TestCommitmentHashMultiOperation:
    """F4: commitment hash check must try all operations, not just the first.

    A commitment could be for ANY operation in a multi-operation transaction.
    Before the fix, only the first operation was checked, producing false
    negatives for commitments on the second or third operation.
    """

    def test_commitment_matches_second_operation(self):
        """Invariant: a commitment matching the second operation PASSES.

        Mutation caught: if we only checked the first operation, this
        would FAIL even though the payment actually matches the commitment.
        """
        from proof.adjudicator import adjudicate_with_commitment

        # First operation: 1000000000 stroops (the default).
        op1 = _make_op()
        # Second operation: 5000000 stroops (the commitment is for this).
        op2 = _make_op(amount_stroops=5000000)

        evidence = PaymentEvidence(
            transaction_hash=TX_HASH,
            ledger=200,
            timestamp_unix=1700001000,
            successful=True,
            sender=SENDER,
            recipient=RECIPIENT,
            asset_code="XLM",
            asset_issuer=None,
            amount_stroops=1000000000,  # top-level from first op
            memo="INV-184",
            memo_type="text",
            operation_type="payment",
            operations=[op1, op2],
        )

        # Commitment terms for the SECOND operation's amount.
        terms = CommitmentTerms(
            sender=SENDER,
            recipient=RECIPIENT,
            asset_code="XLM",
            asset_issuer=None,
            amount_stroops=5000000,
            reference="INV-184",
        )
        commitment = PaymentCommitment(
            commitment_tx_hash=COMMIT_TX_HASH,
            commitment_ledger=100,
            commitment_timestamp_unix=1700000000,
            reference="INV-184",
            committed_hash=terms.commitment_hash(),
            terms=terms,
        )

        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        checks = adjudicate_with_commitment(claim, evidence, commitment)
        hash_check = next(c for c in checks if c.name == "commitment_hash_matches")
        assert hash_check.status == PASS

    def test_commitment_no_operation_matches_fails(self):
        """Invariant: if no operation matches, the check FAILS."""
        from proof.adjudicator import adjudicate_with_commitment

        op1 = _make_op(amount_stroops=1000000000)
        op2 = _make_op(amount_stroops=2000000000)

        evidence = PaymentEvidence(
            transaction_hash=TX_HASH,
            ledger=200,
            timestamp_unix=1700001000,
            successful=True,
            sender=SENDER,
            recipient=RECIPIENT,
            asset_code="XLM",
            asset_issuer=None,
            amount_stroops=1000000000,
            memo="INV-184",
            memo_type="text",
            operation_type="payment",
            operations=[op1, op2],
        )

        # Commitment for an amount that doesn't match any operation.
        terms = CommitmentTerms(
            sender=SENDER,
            recipient=RECIPIENT,
            asset_code="XLM",
            asset_issuer=None,
            amount_stroops=999999999,
            reference="INV-184",
        )
        commitment = PaymentCommitment(
            commitment_tx_hash=COMMIT_TX_HASH,
            commitment_ledger=100,
            commitment_timestamp_unix=1700000000,
            reference="INV-184",
            committed_hash=terms.commitment_hash(),
            terms=terms,
        )

        claim = PaymentClaim(transaction_hash=TX_HASH, commitment_tx_hash=COMMIT_TX_HASH)
        checks = adjudicate_with_commitment(claim, evidence, commitment)
        hash_check = next(c for c in checks if c.name == "commitment_hash_matches")
        assert hash_check.status == FAIL
