"""
extractor.py — Reconstruct payment evidence from Stellar transaction data.

This is the boundary where external data (from Horizon) becomes internal
evidence. Every field from Horizon is validated before it enters a
PaymentEvidence. If the transaction or its operations don't contain a
recognizable payment, extraction fails — we never guess.
"""
from __future__ import annotations

from typing import Any

from .claim import is_valid_stellar_address, validate_tx_hash
from .evidence import PaymentEvidence
from .stellar_client import amount_to_stroops, iso_to_unix

# Operation types that represent a payment transfer.
PAYMENT_OPERATION_TYPES = frozenset({
    "payment",
    "create_account",
    "path_payment_strict_receive",
    "path_payment_strict_send",
    "account_merge",
})


class ExtractionError(Exception):
    """Raised when evidence cannot be extracted from the transaction data."""


def _extract_from_payment_op(op: dict[str, Any]) -> tuple[str, str, str, str | None, int]:
    """Extract sender, recipient, asset_code, asset_issuer, amount_stroops from a payment op."""
    sender = op.get("from", "")
    recipient = op.get("to", "")
    if not is_valid_stellar_address(sender):
        raise ExtractionError(f"invalid sender address in operation: {sender!r}")
    if not is_valid_stellar_address(recipient):
        raise ExtractionError(f"invalid recipient address in operation: {recipient!r}")

    asset_type = op.get("asset_type", "")
    if asset_type == "native":
        asset_code = "XLM"
        asset_issuer = None
    else:
        asset_code = op.get("asset_code", "")
        asset_issuer = op.get("asset_issuer", "")
        if not asset_code:
            raise ExtractionError("non-native asset missing asset_code")
        if not is_valid_stellar_address(asset_issuer):
            raise ExtractionError(f"invalid asset_issuer: {asset_issuer!r}")

    amount_str = op.get("amount", "")
    if not amount_str:
        raise ExtractionError("payment operation missing amount")
    amount_stroops = amount_to_stroops(amount_str)

    return sender, recipient, asset_code, asset_issuer, amount_stroops


def _extract_from_create_account_op(op: dict[str, Any]) -> tuple[str, str, str, str | None, int]:
    """Extract from a create_account operation (funds a new account with XLM)."""
    sender = op.get("funder", "")
    recipient = op.get("account", "")
    if not is_valid_stellar_address(sender):
        raise ExtractionError(f"invalid funder address: {sender!r}")
    if not is_valid_stellar_address(recipient):
        raise ExtractionError(f"invalid account address: {recipient!r}")

    amount_str = op.get("starting_balance", "")
    if not amount_str:
        raise ExtractionError("create_account missing starting_balance")
    amount_stroops = amount_to_stroops(amount_str)

    return sender, recipient, "XLM", None, amount_stroops


def _extract_from_account_merge_op(op: dict[str, Any]) -> tuple[str, str, str, str | None, int]:
    """Extract from an account_merge operation.

    Account merge transfers the entire balance. The Horizon API does not
    report the amount in the operation itself — it must be looked up from
    the effects. For L1, we set amount_stroops to 0 and note the limitation.
    """
    sender = op.get("account", "")
    recipient = op.get("into", "")
    if not is_valid_stellar_address(sender):
        raise ExtractionError(f"invalid account address in merge: {sender!r}")
    if not is_valid_stellar_address(recipient):
        raise ExtractionError(f"invalid destination in merge: {recipient!r}")

    # Account merge amount is not in the operation — would need effects lookup.
    # For L1, we flag this as a known limitation.
    return sender, recipient, "XLM", None, 0


def extract_evidence(
    tx_data: dict[str, Any],
    operations: list[dict[str, Any]],
) -> PaymentEvidence:
    """Extract payment evidence from a Stellar transaction and its operations.

    Raises ExtractionError if the transaction doesn't contain a recognizable
    payment operation, or if any field is malformed.
    """
    tx_hash = tx_data.get("hash", "")
    validate_tx_hash(tx_hash)

    ledger = tx_data.get("ledger")
    if not isinstance(ledger, int) or isinstance(ledger, bool):
        raise ExtractionError(f"invalid ledger value: {ledger!r}")

    created_at = tx_data.get("created_at", "")
    if not isinstance(created_at, str) or not created_at:
        raise ExtractionError("missing or invalid created_at timestamp")
    timestamp_unix = iso_to_unix(created_at)

    successful = tx_data.get("successful", False)
    if not isinstance(successful, bool):
        raise ExtractionError(f"successful field is not bool: {successful!r}")

    memo = tx_data.get("memo")
    if memo is not None and not isinstance(memo, str):
        memo = str(memo)

    # Find the first payment-type operation.
    payment_op: dict[str, Any] | None = None
    op_type = ""
    for op in operations:
        op_type = op.get("type", "")
        if op_type in PAYMENT_OPERATION_TYPES:
            payment_op = op
            break

    if payment_op is None:
        raise ExtractionError(
            f"no payment-type operation found in {len(operations)} operations"
        )

    if op_type == "payment":
        sender, recipient, asset_code, asset_issuer, amount_stroops = (
            _extract_from_payment_op(payment_op)
        )
    elif op_type == "create_account":
        sender, recipient, asset_code, asset_issuer, amount_stroops = (
            _extract_from_create_account_op(payment_op)
        )
    elif op_type == "account_merge":
        sender, recipient, asset_code, asset_issuer, amount_stroops = (
            _extract_from_account_merge_op(payment_op)
        )
    elif op_type in ("path_payment_strict_receive", "path_payment_strict_send"):
        sender, recipient, asset_code, asset_issuer, amount_stroops = (
            _extract_from_payment_op(payment_op)
        )
    else:
        raise ExtractionError(f"unsupported operation type: {op_type}")

    return PaymentEvidence(
        transaction_hash=tx_hash,
        ledger=ledger,
        timestamp_unix=timestamp_unix,
        successful=successful,
        sender=sender,
        recipient=recipient,
        asset_code=asset_code,
        asset_issuer=asset_issuer,
        amount_stroops=amount_stroops,
        memo=memo,
        operation_type=op_type,
    )
