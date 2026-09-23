"""
extractor.py — Reconstruct payment evidence from Stellar transaction data.

This is the boundary where external data (from Horizon) becomes internal
evidence. Every field from Horizon is validated before it enters a
PaymentEvidence. If the transaction or its operations don't contain a
recognizable payment, extraction fails — we never guess.

L3: supports multi-operation transactions, path payments with source
and destination assets, account_merge with amount from effects, and
memo type classification.
"""
from __future__ import annotations

from typing import Any

from .claim import is_valid_stellar_address, validate_tx_hash
from .evidence import PaymentEvidence, PaymentOperation
from .stellar_client import amount_to_stroops, iso_to_unix

# Operation types that represent a payment transfer.
PAYMENT_OPERATION_TYPES = frozenset({
    "payment",
    "create_account",
    "path_payment_strict_receive",
    "path_payment_strict_send",
    "account_merge",
})

# Memo types recognized by Stellar.
MEMO_TYPES = frozenset({"text", "hash", "return", "none"})


class ExtractionError(Exception):
    """Raised when evidence cannot be extracted from the transaction data."""


def _parse_asset(op: dict[str, Any], prefix: str = "") -> tuple[str, str | None]:
    """Extract asset_code and asset_issuer from an operation dict.

    With prefix="" reads the destination asset fields (asset_type, asset_code,
    asset_issuer). With prefix="source_" reads the source asset fields
    (source_asset_type, source_asset_code, source_asset_issuer).
    """
    asset_type = op.get(f"{prefix}asset_type", "")
    if asset_type == "native":
        return "XLM", None
    asset_code = op.get(f"{prefix}asset_code", "")
    asset_issuer = op.get(f"{prefix}asset_issuer", "")
    if not asset_code:
        raise ExtractionError(f"non-native {prefix}asset missing asset_code")
    if not is_valid_stellar_address(asset_issuer):
        raise ExtractionError(f"invalid {prefix}asset_issuer: {asset_issuer!r}")
    return asset_code, asset_issuer


def _extract_payment_op(op: dict[str, Any]) -> PaymentOperation:
    """Extract a PaymentOperation from a payment-type operation."""
    sender = op.get("from", "")
    recipient = op.get("to", "")
    if not is_valid_stellar_address(sender):
        raise ExtractionError(f"invalid sender address in operation: {sender!r}")
    if not is_valid_stellar_address(recipient):
        raise ExtractionError(f"invalid recipient address in operation: {recipient!r}")

    asset_code, asset_issuer = _parse_asset(op)

    amount_str = op.get("amount", "")
    if not amount_str:
        raise ExtractionError("payment operation missing amount")
    amount_stroops = amount_to_stroops(amount_str)

    return PaymentOperation(
        operation_type="payment",
        sender=sender,
        recipient=recipient,
        asset_code=asset_code,
        asset_issuer=asset_issuer,
        amount_stroops=amount_stroops,
    )


def _extract_create_account_op(op: dict[str, Any]) -> PaymentOperation:
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

    return PaymentOperation(
        operation_type="create_account",
        sender=sender,
        recipient=recipient,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=amount_stroops,
    )


def _extract_account_merge_op(op: dict[str, Any], effects: list[dict[str, Any]]) -> PaymentOperation:
    """Extract from an account_merge operation.

    Account merge transfers the entire balance. The amount is not in the
    operation itself — we look it up from the effects, where the account
    debit effect carries the amount.
    """
    sender = op.get("account", "")
    recipient = op.get("into", "")
    if not is_valid_stellar_address(sender):
        raise ExtractionError(f"invalid account address in merge: {sender!r}")
    if not is_valid_stellar_address(recipient):
        raise ExtractionError(f"invalid destination in merge: {recipient!r}")

    # Find the account_debited effect for the sender — that's the amount.
    amount_stroops = 0
    for effect in effects:
        if (
            effect.get("type") == "account_debited"
            and effect.get("account") == sender
        ):
            amount_str = effect.get("amount", "")
            if amount_str:
                amount_stroops = amount_to_stroops(amount_str)
            break

    if amount_stroops == 0:
        raise ExtractionError(
            "account_merge amount not found in effects — cannot determine transfer value"
        )

    return PaymentOperation(
        operation_type="account_merge",
        sender=sender,
        recipient=recipient,
        asset_code="XLM",
        asset_issuer=None,
        amount_stroops=amount_stroops,
    )


def _extract_path_payment_op(op: dict[str, Any]) -> PaymentOperation:
    """Extract from a path_payment_strict_receive or path_payment_strict_send op.

    Path payments involve two assets: the source (what the sender spends)
    and the destination (what the recipient receives). We extract both.
    """
    sender = op.get("from", "")
    recipient = op.get("to", "")
    if not is_valid_stellar_address(sender):
        raise ExtractionError(f"invalid sender in path payment: {sender!r}")
    if not is_valid_stellar_address(recipient):
        raise ExtractionError(f"invalid recipient in path payment: {recipient!r}")

    # Destination asset (what the recipient receives).
    dest_code, dest_issuer = _parse_asset(op)

    # Source asset (what the sender spends).
    source_code, source_issuer = _parse_asset(op, prefix="source_")

    # Destination amount.
    dest_amount_str = op.get("amount", "")
    if not dest_amount_str:
        raise ExtractionError("path payment missing destination amount")
    dest_amount_stroops = amount_to_stroops(dest_amount_str)

    # Source amount.
    source_amount_str = op.get("source_amount", "")
    source_amount_stroops: int | None = None
    if source_amount_str:
        source_amount_stroops = amount_to_stroops(source_amount_str)

    op_type = op.get("type", "path_payment")

    return PaymentOperation(
        operation_type=op_type,
        sender=sender,
        recipient=recipient,
        asset_code=dest_code,
        asset_issuer=dest_issuer,
        amount_stroops=dest_amount_stroops,
        source_asset_code=source_code,
        source_asset_issuer=source_issuer,
        source_amount_stroops=source_amount_stroops,
    )


def _classify_memo(tx_data: dict[str, Any]) -> tuple[str | None, str]:
    """Classify the memo from transaction data.

    Returns (memo_value, memo_type). memo_type is one of:
    "text", "hash", "return", "none". memo_value is the string form
    (for text) or None if no memo.
    """
    memo_type = tx_data.get("memo_type", "none")
    if memo_type is None:
        memo_type = "none"
    if not isinstance(memo_type, str):
        memo_type = "none"
    if memo_type not in MEMO_TYPES:
        memo_type = "none"

    memo = tx_data.get("memo")
    if memo is not None and not isinstance(memo, str):
        memo = str(memo)
    if memo_type == "none":
        memo = None

    return memo, memo_type


def extract_evidence(
    tx_data: dict[str, Any],
    operations: list[dict[str, Any]],
    effects: list[dict[str, Any]] | None = None,
) -> PaymentEvidence:
    """Extract payment evidence from a Stellar transaction and its operations.

    Raises ExtractionError if the transaction doesn't contain a recognizable
    payment operation, or if any field is malformed.

    L3: extracts ALL payment-type operations, not just the first. Path
    payments include source and destination assets. Account merge amount
    is looked up from effects.
    """
    if effects is None:
        effects = []

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

    memo, memo_type = _classify_memo(tx_data)

    # Extract all payment-type operations.
    payment_ops: list[PaymentOperation] = []
    for op in operations:
        op_type = op.get("type", "")
        if op_type not in PAYMENT_OPERATION_TYPES:
            continue
        if op_type == "payment":
            payment_ops.append(_extract_payment_op(op))
        elif op_type == "create_account":
            payment_ops.append(_extract_create_account_op(op))
        elif op_type == "account_merge":
            payment_ops.append(_extract_account_merge_op(op, effects))
        elif op_type in ("path_payment_strict_receive", "path_payment_strict_send"):
            payment_ops.append(_extract_path_payment_op(op))
        else:
            raise ExtractionError(f"unsupported operation type: {op_type}")

    if not payment_ops:
        raise ExtractionError(
            f"no payment-type operation found in {len(operations)} operations"
        )

    # Top-level fields are from the first payment operation (backward compat).
    first = payment_ops[0]

    return PaymentEvidence(
        transaction_hash=tx_hash,
        ledger=ledger,
        timestamp_unix=timestamp_unix,
        successful=successful,
        sender=first.sender,
        recipient=first.recipient,
        asset_code=first.asset_code,
        asset_issuer=first.asset_issuer,
        amount_stroops=first.amount_stroops,
        memo=memo,
        memo_type=memo_type,
        operation_type=first.operation_type,
        operations=payment_ops,
    )
