"""
test_boundary.py — Tests for input validation at the boundary.

Every input from outside is untrusted until validated. These tests check
that malformed inputs are rejected at the boundary, not deep inside.
"""
import pytest

from proof.claim import (
    PaymentClaim,
    is_valid_stellar_address,
    is_valid_tx_hash,
    validate_stroops,
)

TX_HASH = "a" * 64
VALID_ADDR = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"


class TestTxHashValidation:
    def test_valid_hash_accepted(self):
        """Invariant: a 64-char hex string is a valid tx hash."""
        assert is_valid_tx_hash("a" * 64)
        assert is_valid_tx_hash("0123456789abcdef" * 4)

    def test_short_hash_rejected(self):
        """Mutation caught: if length weren checked, short strings would pass."""
        assert not is_valid_tx_hash("a" * 63)

    def test_non_hex_rejected(self):
        """Mutation caught: if chars weren't validated, non-hex would pass."""
        assert not is_valid_tx_hash("g" * 64)

    def test_uppercase_hex_rejected(self):
        """Stellar hashes are lowercase. Mutation: if case weren't checked."""
        assert not is_valid_tx_hash("A" * 64)

    def test_empty_rejected(self):
        assert not is_valid_tx_hash("")

    def test_none_rejected(self):
        assert not is_valid_tx_hash(None)  # type: ignore

    def test_claim_rejects_invalid_hash(self):
        with pytest.raises(ValueError, match="transaction_hash"):
            PaymentClaim(transaction_hash="invalid")


class TestAddressValidation:
    def test_valid_address_accepted(self):
        assert is_valid_stellar_address(VALID_ADDR)

    def test_wrong_prefix_rejected(self):
        """Mutation caught: if prefix weren't checked, S... addresses would pass."""
        assert not is_valid_stellar_address("S" + VALID_ADDR[1:])

    def test_short_address_rejected(self):
        assert not is_valid_stellar_address("GABC")

    def test_empty_rejected(self):
        assert not is_valid_stellar_address("")

    def test_lowercase_rejected(self):
        """Stellar addresses are uppercase base32. Mutation: case not checked."""
        assert not is_valid_stellar_address("g" + VALID_ADDR[1:])

    def test_claim_rejects_invalid_sender(self):
        with pytest.raises(ValueError, match="sender"):
            PaymentClaim(transaction_hash=TX_HASH, sender="invalid")

    def test_claim_rejects_invalid_recipient(self):
        with pytest.raises(ValueError, match="recipient"):
            PaymentClaim(transaction_hash=TX_HASH, recipient="invalid")


class TestAmountValidation:
    def test_valid_stroops_accepted(self):
        assert validate_stroops(1000000000, "amount") == 1000000000

    def test_zero_accepted(self):
        assert validate_stroops(0, "amount") == 0

    def test_negative_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            validate_stroops(-1, "amount")

    def test_bool_rejected(self):
        """Mutation caught: if bool weren't checked before int, True would pass as 1."""
        with pytest.raises(ValueError, match="bool"):
            validate_stroops(True, "amount")

    def test_float_rejected(self):
        """Mutation caught: if float were allowed, it would enter the decision path."""
        with pytest.raises(ValueError, match="integer"):
            validate_stroops(1.0, "amount")  # type: ignore

    def test_exceeds_max_rejected(self):
        with pytest.raises(ValueError, match="maximum"):
            validate_stroops(2**63, "amount")

    def test_claim_rejects_float_amount(self):
        with pytest.raises(ValueError):
            PaymentClaim(transaction_hash=TX_HASH, amount_stroops=1.5)  # type: ignore


class TestLedgerValidation:
    def test_valid_ledger_accepted(self):
        claim = PaymentClaim(transaction_hash=TX_HASH, ledger_min=100, ledger_max=200)
        assert claim.ledger_min == 100
        assert claim.ledger_max == 200

    def test_negative_ledger_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            PaymentClaim(transaction_hash=TX_HASH, ledger_min=-1)

    def test_min_greater_than_max_rejected(self):
        with pytest.raises(ValueError, match="ledger_min.*ledger_max"):
            PaymentClaim(transaction_hash=TX_HASH, ledger_min=200, ledger_max=100)
