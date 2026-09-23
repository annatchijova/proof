"""
test_dispute.py — Tests for L5 dispute resolution.

Each test states the invariant it defends and what mutation it would catch.
"""
from proof.claim import PaymentClaim
from proof.dispute import (
    BOTH_VERIFIED,
    CLAIM_A_VERIFIED,
    CLAIM_B_VERIFIED,
    CONTRADICTION,
    NEITHER_VERIFIED,
    DisputeResult,
    adjudicate_dispute,
    find_contradictions,
)
from proof.evidence import (
    FAIL,
    PASS,
    PaymentEvidence,
    PaymentOperation,
    VERIFIED,
)

TX_HASH_A = "a" * 64
TX_HASH_B = "b" * 64
SENDER = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
RECIPIENT = "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"


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


def _make_evidence(tx_hash=TX_HASH_A, **overrides) -> PaymentEvidence:
    op = _make_op()
    defaults = dict(
        transaction_hash=tx_hash,
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


def _make_claim(tx_hash=TX_HASH_A, **overrides) -> PaymentClaim:
    defaults = dict(
        transaction_hash=tx_hash,
        sender=SENDER,
        recipient=RECIPIENT,
        asset_code="XLM",
        amount_stroops=1000000000,
        reference="INV-184",
    )
    defaults.update(overrides)
    return PaymentClaim(**defaults)


class TestFindContradictions:
    def test_same_tx_consistent(self):
        """Invariant: same tx, same fields → no contradiction.

        Mutation caught: if the consistency check flagged identical
        evidence as contradictory, every dispute would be a contradiction.
        """
        ev_a = _make_evidence()
        ev_b = _make_evidence()
        checks = find_contradictions(ev_a, ev_b)
        fail_checks = [c for c in checks if c.status == FAIL]
        assert fail_checks == []
        assert any(c.name == "same_transaction_consistent" and c.status == PASS for c in checks)

    def test_same_tx_different_amount_is_contradiction(self):
        """Invariant: same tx but different amount → contradiction.

        Mutation caught: if field comparison were removed, tampered
        evidence wouldn't be detected.
        """
        ev_a = _make_evidence(amount_stroops=1000000000)
        ev_b = _make_evidence(amount_stroops=999999999)
        checks = find_contradictions(ev_a, ev_b)
        amount_check = next(c for c in checks if c.name == "contradiction_amount_stroops")
        assert amount_check.status == FAIL

    def test_same_tx_different_recipient_is_contradiction(self):
        """Invariant: same tx but different recipient → contradiction."""
        ev_a = _make_evidence(recipient=RECIPIENT)
        ev_b = _make_evidence(recipient=SENDER)
        checks = find_contradictions(ev_a, ev_b)
        recipient_check = next(c for c in checks if c.name == "contradiction_recipient")
        assert recipient_check.status == FAIL

    def test_different_tx_no_field_contradiction(self):
        """Invariant: different txs → no field-level contradiction check.

        Mutation caught: if field checks ran across different txs, they
        would flag normal differences as contradictions.
        """
        ev_a = _make_evidence(tx_hash=TX_HASH_A)
        ev_b = _make_evidence(tx_hash=TX_HASH_B, amount_stroops=999999999)
        checks = find_contradictions(ev_a, ev_b)
        # No contradiction_amount_stroops check should exist.
        assert not any(c.name == "contradiction_amount_stroops" for c in checks)
        assert any(c.name == "different_transactions" for c in checks)

    def test_same_reference_different_tx_is_contradiction(self):
        """Invariant: same reference but different tx → contradiction.

        Mutation caught: if reference collision weren't checked, two
        payments claiming to satisfy the same invoice would both verify.
        """
        ev_a = _make_evidence(tx_hash=TX_HASH_A, memo="INV-184")
        ev_b = _make_evidence(tx_hash=TX_HASH_B, memo="INV-184")
        checks = find_contradictions(ev_a, ev_b)
        ref_check = next(c for c in checks if c.name == "same_reference_different_tx")
        assert ref_check.status == FAIL

    def test_different_reference_different_tx_no_contradiction(self):
        """Invariant: different references and different txs → no contradiction."""
        ev_a = _make_evidence(tx_hash=TX_HASH_A, memo="INV-184")
        ev_b = _make_evidence(tx_hash=TX_HASH_B, memo="INV-999")
        checks = find_contradictions(ev_a, ev_b)
        assert not any(c.name == "same_reference_different_tx" for c in checks)


class TestAdjudicateDispute:
    def test_both_verified_same_tx(self):
        """Invariant: both claims verify against the same tx → BOTH_VERIFIED."""
        claim_a = _make_claim()
        claim_b = _make_claim()
        ev = _make_evidence()
        result = adjudicate_dispute(claim_a, ev, claim_b, ev)
        assert result.dispute_verdict == BOTH_VERIFIED
        assert result.claim_a_verdict == VERIFIED
        assert result.claim_b_verdict == VERIFIED

    def test_claim_a_verified_claim_b_not(self):
        """Invariant: A verifies, B doesn't → CLAIM_A_VERIFIED.

        Mutation caught: if the dispute verdict ignored individual
        verdicts, it wouldn't distinguish A-wins from B-wins.
        """
        claim_a = _make_claim()
        claim_b = _make_claim(recipient=SENDER)  # wrong recipient
        ev = _make_evidence()
        result = adjudicate_dispute(claim_a, ev, claim_b, ev)
        assert result.dispute_verdict == CLAIM_A_VERIFIED
        assert result.claim_a_verdict == VERIFIED

    def test_claim_b_verified_claim_a_not(self):
        """Invariant: B verifies, A doesn't → CLAIM_B_VERIFIED."""
        claim_a = _make_claim(recipient=SENDER)  # wrong recipient
        claim_b = _make_claim()
        ev = _make_evidence()
        result = adjudicate_dispute(claim_a, ev, claim_b, ev)
        assert result.dispute_verdict == CLAIM_B_VERIFIED
        assert result.claim_b_verdict == VERIFIED

    def test_neither_verified(self):
        """Invariant: neither claim verifies → NEITHER_VERIFIED."""
        claim_a = _make_claim(recipient=SENDER)
        claim_b = _make_claim(recipient=SENDER)
        ev = _make_evidence()
        result = adjudicate_dispute(claim_a, ev, claim_b, ev)
        assert result.dispute_verdict == NEITHER_VERIFIED

    def test_contradiction_dominates(self):
        """Invariant: contradiction takes precedence over individual verdicts.

        Mutation caught: if contradiction didn't dominate, a tampered
        evidence set would produce BOTH_VERIFIED instead of CONTRADICTION.
        """
        claim_a = _make_claim()
        claim_b = _make_claim()
        ev_a = _make_evidence(amount_stroops=1000000000)
        ev_b = _make_evidence(amount_stroops=999999999)
        result = adjudicate_dispute(claim_a, ev_a, claim_b, ev_b)
        assert result.dispute_verdict == CONTRADICTION

    def test_insufficient_evidence_for_claim_a(self):
        """Invariant: missing evidence for A → A gets INSUFFICIENT_EVIDENCE."""
        from proof.evidence import INSUFFICIENT_EVIDENCE
        claim_a = _make_claim()
        claim_b = _make_claim()
        ev_b = _make_evidence()
        result = adjudicate_dispute(claim_a, None, claim_b, ev_b)
        assert result.claim_a_verdict == INSUFFICIENT_EVIDENCE
        assert result.claim_b_verdict == VERIFIED
        assert result.dispute_verdict == CLAIM_B_VERIFIED

    def test_insufficient_evidence_for_both(self):
        """Invariant: missing evidence for both → NEITHER_VERIFIED."""
        from proof.evidence import INSUFFICIENT_EVIDENCE
        claim_a = _make_claim()
        claim_b = _make_claim(tx_hash=TX_HASH_B)
        result = adjudicate_dispute(claim_a, None, claim_b, None)
        assert result.claim_a_verdict == INSUFFICIENT_EVIDENCE
        assert result.claim_b_verdict == INSUFFICIENT_EVIDENCE
        assert result.dispute_verdict == NEITHER_VERIFIED

    def test_dispute_result_to_dict(self):
        """Invariant: DisputeResult serializes to dict correctly."""
        claim_a = _make_claim()
        claim_b = _make_claim()
        ev = _make_evidence()
        result = adjudicate_dispute(claim_a, ev, claim_b, ev)
        d = result.to_dict()
        assert "claim_a_verdict" in d
        assert "claim_b_verdict" in d
        assert "dispute_verdict" in d
        assert "contradiction_checks" in d
        assert "detail" in d

    def test_same_reference_different_tx_produces_contradiction(self):
        """Invariant: two txs with same reference → CONTRADICTION.

        This is the key L5 scenario: Alice claims tx A pays for INV-184,
        Bob claims tx B pays for INV-184. Both can't be right.
        """
        claim_a = _make_claim(tx_hash=TX_HASH_A, reference="INV-184")
        claim_b = _make_claim(tx_hash=TX_HASH_B, reference="INV-184")
        ev_a = _make_evidence(tx_hash=TX_HASH_A, memo="INV-184")
        ev_b = _make_evidence(tx_hash=TX_HASH_B, memo="INV-184")
        result = adjudicate_dispute(claim_a, ev_a, claim_b, ev_b)
        assert result.dispute_verdict == CONTRADICTION
