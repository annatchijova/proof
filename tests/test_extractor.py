"""
test_extractor.py — Tests for the L3 evidence extractor.

Tests multi-operation extraction, path payments with source/destination
assets, account_merge with amount from effects, and memo type classification.
"""
import pytest

from proof.extractor import (
    ExtractionError,
    extract_evidence,
    _classify_memo,
    _parse_asset,
)

TX_HASH = "a" * 64
SENDER = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
RECIPIENT = "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
ISSUER = "GBXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"


def _make_tx_data(**overrides) -> dict:
    defaults = {
        "hash": TX_HASH,
        "ledger": 12345,
        "created_at": "2024-01-01T00:00:00Z",
        "successful": True,
        "memo": "INV-184",
        "memo_type": "text",
    }
    defaults.update(overrides)
    return defaults


def _make_payment_op(**overrides) -> dict:
    defaults = {
        "type": "payment",
        "from": SENDER,
        "to": RECIPIENT,
        "asset_type": "native",
        "amount": "100.0000000",
    }
    defaults.update(overrides)
    return defaults


def _make_create_account_op(**overrides) -> dict:
    defaults = {
        "type": "create_account",
        "funder": SENDER,
        "account": RECIPIENT,
        "starting_balance": "50.0000000",
    }
    defaults.update(overrides)
    return defaults


def _make_path_payment_op(**overrides) -> dict:
    defaults = {
        "type": "path_payment_strict_receive",
        "from": SENDER,
        "to": RECIPIENT,
        "asset_type": "credit_alphanum4",
        "asset_code": "USDC",
        "asset_issuer": ISSUER,
        "amount": "100.0000000",
        "source_asset_type": "native",
        "source_amount": "99.5000000",
    }
    defaults.update(overrides)
    return defaults


def _make_account_merge_op(**overrides) -> dict:
    defaults = {
        "type": "account_merge",
        "account": SENDER,
        "into": RECIPIENT,
    }
    defaults.update(overrides)
    return defaults


def _make_account_debited_effect(**overrides) -> dict:
    defaults = {
        "type": "account_debited",
        "account": SENDER,
        "amount": "250.0000000",
        "asset_type": "native",
    }
    defaults.update(overrides)
    return defaults


class TestSinglePaymentExtraction:
    def test_payment_op_extracts_correctly(self):
        """Invariant: a simple payment op produces correct evidence."""
        tx = _make_tx_data()
        ops = [_make_payment_op()]
        evidence = extract_evidence(tx, ops)
        assert evidence.sender == SENDER
        assert evidence.recipient == RECIPIENT
        assert evidence.asset_code == "XLM"
        assert evidence.amount_stroops == 1000000000
        assert evidence.operation_type == "payment"
        assert len(evidence.operations) == 1

    def test_create_account_extracts_correctly(self):
        """Invariant: create_account produces XLM evidence with starting_balance."""
        tx = _make_tx_data()
        ops = [_make_create_account_op()]
        evidence = extract_evidence(tx, ops)
        assert evidence.asset_code == "XLM"
        assert evidence.amount_stroops == 500000000
        assert evidence.operation_type == "create_account"

    def test_non_native_asset_extracts_issuer(self):
        """Invariant: non-native assets include the issuer."""
        tx = _make_tx_data()
        ops = [_make_payment_op(
            asset_type="credit_alphanum4",
            asset_code="USDC",
            asset_issuer=ISSUER,
        )]
        evidence = extract_evidence(tx, ops)
        assert evidence.asset_code == "USDC"
        assert evidence.asset_issuer == ISSUER


class TestMultiOperationExtraction:
    def test_multiple_payment_ops_extracted(self):
        """Invariant: all payment-type operations are extracted, not just the first.

        Mutation caught: if the extractor only took the first payment op,
        the second would be missing from the operations list.
        """
        tx = _make_tx_data()
        ops = [
            _make_payment_op(amount="100.0000000"),
            _make_payment_op(amount="200.0000000"),
        ]
        evidence = extract_evidence(tx, ops)
        assert len(evidence.operations) == 2
        assert evidence.operations[0].amount_stroops == 1000000000
        assert evidence.operations[1].amount_stroops == 2000000000

    def test_mixed_operations(self):
        """Invariant: payment and non-payment ops are handled — only payments extracted."""
        tx = _make_tx_data()
        ops = [
            {"type": "set_options", "source_account": SENDER},
            _make_payment_op(amount="100.0000000"),
            {"type": "change_trust", "source_account": SENDER},
            _make_payment_op(amount="50.0000000"),
        ]
        evidence = extract_evidence(tx, ops)
        assert len(evidence.operations) == 2

    def test_top_level_fields_from_first_op(self):
        """Invariant: top-level fields are from the first payment op (backward compat).

        Mutation caught: if top-level fields came from a random op, they
        wouldn't match the first operation.
        """
        tx = _make_tx_data()
        ops = [
            _make_payment_op(amount="100.0000000"),
            _make_payment_op(amount="200.0000000"),
        ]
        evidence = extract_evidence(tx, ops)
        assert evidence.amount_stroops == 1000000000
        assert evidence.operations[1].amount_stroops == 2000000000


class TestPathPaymentExtraction:
    def test_path_payment_extracts_source_and_dest(self):
        """Invariant: path payments extract both source and destination assets.

        Mutation caught: if source_asset were ignored, it would be None.
        """
        tx = _make_tx_data()
        ops = [_make_path_payment_op()]
        evidence = extract_evidence(tx, ops)
        assert evidence.operations[0].asset_code == "USDC"
        assert evidence.operations[0].asset_issuer == ISSUER
        assert evidence.operations[0].source_asset_code == "XLM"
        assert evidence.operations[0].source_asset_issuer is None
        assert evidence.operations[0].amount_stroops == 1000000000
        assert evidence.operations[0].source_amount_stroops == 995000000

    def test_path_payment_send_type(self):
        """Invariant: path_payment_strict_send is also supported."""
        tx = _make_tx_data()
        ops = [_make_path_payment_op(type="path_payment_strict_send")]
        evidence = extract_evidence(tx, ops)
        assert evidence.operations[0].operation_type == "path_payment_strict_send"

    def test_path_payment_with_non_native_source(self):
        """Invariant: source asset can be non-native too."""
        tx = _make_tx_data()
        ops = [_make_path_payment_op(
            source_asset_type="credit_alphanum4",
            source_asset_code="EURT",
            source_asset_issuer=ISSUER,
        )]
        evidence = extract_evidence(tx, ops)
        assert evidence.operations[0].source_asset_code == "EURT"
        assert evidence.operations[0].source_asset_issuer == ISSUER


class TestAccountMergeExtraction:
    def test_account_merge_with_effects(self):
        """Invariant: account_merge amount is extracted from effects.

        Mutation caught: if effects weren consulted, amount would be 0
        and extraction would fail.
        """
        tx = _make_tx_data()
        ops = [_make_account_merge_op()]
        effects = [_make_account_debited_effect(amount="250.0000000")]
        evidence = extract_evidence(tx, ops, effects)
        assert evidence.operations[0].amount_stroops == 2500000000
        assert evidence.operations[0].operation_type == "account_merge"

    def test_account_merge_without_effects_raises(self):
        """Invariant: account_merge without effects raises ExtractionError.

        Mutation caught: if the extractor silently set amount to 0, it
        would produce misleading evidence.
        """
        tx = _make_tx_data()
        ops = [_make_account_merge_op()]
        with pytest.raises(ExtractionError, match="account_merge amount not found"):
            extract_evidence(tx, ops, effects=[])

    def test_account_merge_uses_correct_effect(self):
        """Invariant: the debited effect for the sender is used, not any effect."""
        tx = _make_tx_data()
        ops = [_make_account_merge_op()]
        effects = [
            {"type": "account_debited", "account": RECIPIENT, "amount": "999.0000000"},
            _make_account_debited_effect(account=SENDER, amount="250.0000000"),
        ]
        evidence = extract_evidence(tx, ops, effects)
        assert evidence.operations[0].amount_stroops == 2500000000


class TestMemoClassification:
    def test_text_memo_classified(self):
        """Invariant: text memo produces memo_type='text'."""
        memo, memo_type = _classify_memo({"memo": "INV-184", "memo_type": "text"})
        assert memo == "INV-184"
        assert memo_type == "text"

    def test_none_memo_classified(self):
        """Invariant: no memo produces memo_type='none' and memo=None."""
        memo, memo_type = _classify_memo({"memo_type": "none"})
        assert memo is None
        assert memo_type == "none"

    def test_hash_memo_classified(self):
        """Invariant: hash memo produces memo_type='hash'."""
        memo, memo_type = _classify_memo({"memo": "abc123", "memo_type": "hash"})
        assert memo_type == "hash"

    def test_return_memo_classified(self):
        """Invariant: return memo produces memo_type='return'."""
        memo, memo_type = _classify_memo({"memo": "abc123", "memo_type": "return"})
        assert memo_type == "return"

    def test_unknown_memo_type_defaults_to_none(self):
        """Invariant: unknown memo type defaults to 'none'."""
        memo, memo_type = _classify_memo({"memo_type": "weird"})
        assert memo_type == "none"

    def test_memo_type_in_evidence(self):
        """Invariant: evidence includes memo_type field."""
        tx = _make_tx_data(memo="INV-184", memo_type="text")
        ops = [_make_payment_op()]
        evidence = extract_evidence(tx, ops)
        assert evidence.memo_type == "text"
        assert evidence.memo == "INV-184"

    def test_none_memo_in_evidence(self):
        """Invariant: evidence with no memo has memo_type='none'."""
        tx = _make_tx_data(memo=None, memo_type="none")
        ops = [_make_payment_op()]
        evidence = extract_evidence(tx, ops)
        assert evidence.memo_type == "none"
        assert evidence.memo is None


class TestMemoTypeAdjudication:
    """Test that reference matching respects memo_type."""

    def test_reference_checked_for_text_memo(self):
        """Invariant: reference is checked when memo_type is 'text'."""
        from proof.adjudicator import adjudicate
        from proof.claim import PaymentClaim
        from proof.evidence import PaymentEvidence, PaymentOperation

        op = PaymentOperation("payment", SENDER, RECIPIENT, "XLM", None, 1000000000)
        evidence = PaymentEvidence(
            transaction_hash=TX_HASH, ledger=1, timestamp_unix=1,
            successful=True, sender=SENDER, recipient=RECIPIENT,
            asset_code="XLM", asset_issuer=None, amount_stroops=1000000000,
            memo="INV-184", memo_type="text", operation_type="payment",
            operations=[op],
        )
        claim = PaymentClaim(transaction_hash=TX_HASH, reference="INV-184")
        checks = adjudicate(claim, evidence)
        ref_check = next(c for c in checks if c.name == "reference_matches")
        assert ref_check.status == "PASS"

    def test_reference_abstained_for_hash_memo(self):
        """Invariant: reference is ABSTAIN when memo_type is not 'text'.

        Mutation caught: if reference were checked against a hash memo,
        a text claim would never match a binary hash.
        """
        from proof.adjudicator import adjudicate
        from proof.claim import PaymentClaim
        from proof.evidence import PaymentEvidence, PaymentOperation

        op = PaymentOperation("payment", SENDER, RECIPIENT, "XLM", None, 1000000000)
        evidence = PaymentEvidence(
            transaction_hash=TX_HASH, ledger=1, timestamp_unix=1,
            successful=True, sender=SENDER, recipient=RECIPIENT,
            asset_code="XLM", asset_issuer=None, amount_stroops=1000000000,
            memo="abcdef", memo_type="hash", operation_type="payment",
            operations=[op],
        )
        claim = PaymentClaim(transaction_hash=TX_HASH, reference="INV-184")
        checks = adjudicate(claim, evidence)
        ref_check = next(c for c in checks if c.name == "reference_matches")
        assert ref_check.status == "ABSTAIN"


class TestSourceAssetAdjudication:
    """Test that source_asset check is ABSTAIN (informational for now)."""

    def test_source_asset_abstain_for_regular_payment(self):
        """Invariant: source_asset is ABSTAIN for non-path payments."""
        from proof.adjudicator import adjudicate
        from proof.claim import PaymentClaim
        from proof.evidence import PaymentEvidence, PaymentOperation

        op = PaymentOperation("payment", SENDER, RECIPIENT, "XLM", None, 1000000000)
        evidence = PaymentEvidence(
            transaction_hash=TX_HASH, ledger=1, timestamp_unix=1,
            successful=True, sender=SENDER, recipient=RECIPIENT,
            asset_code="XLM", asset_issuer=None, amount_stroops=1000000000,
            memo=None, memo_type="none", operation_type="payment",
            operations=[op],
        )
        claim = PaymentClaim(transaction_hash=TX_HASH)
        checks = adjudicate(claim, evidence)
        source_check = next(c for c in checks if c.name == "source_asset_matches")
        assert source_check.status == "ABSTAIN"

    def test_source_asset_abstain_for_path_payment(self):
        """Invariant: source_asset is ABSTAIN for path payments (claim has no source asset)."""
        from proof.adjudicator import adjudicate
        from proof.claim import PaymentClaim
        from proof.evidence import PaymentEvidence, PaymentOperation

        op = PaymentOperation(
            "path_payment_strict_receive", SENDER, RECIPIENT,
            "USDC", ISSUER, 1000000000,
            source_asset_code="XLM", source_asset_issuer=None,
            source_amount_stroops=995000000,
        )
        evidence = PaymentEvidence(
            transaction_hash=TX_HASH, ledger=1, timestamp_unix=1,
            successful=True, sender=SENDER, recipient=RECIPIENT,
            asset_code="USDC", asset_issuer=ISSUER, amount_stroops=1000000000,
            memo=None, memo_type="none", operation_type="path_payment_strict_receive",
            operations=[op],
        )
        claim = PaymentClaim(transaction_hash=TX_HASH)
        checks = adjudicate(claim, evidence)
        source_check = next(c for c in checks if c.name == "source_asset_matches")
        assert source_check.status == "ABSTAIN"
        # The actual field should show the source asset for informational purposes.
        assert "XLM" in (source_check.actual or "")
