"""
commitment_extractor.py — Reconstruct payment commitments from the ledger.

A commitment is registered on-chain via a manage_data operation with a key
prefixed by "PROOF:COMMIT:" and a value containing the commitment hash.

This module reconstructs a PaymentCommitment from a transaction that
contains such a manage_data operation. It validates every field from the
Horizon response — no guessing.
"""
from __future__ import annotations

from typing import Any

from .claim import is_valid_stellar_address, validate_tx_hash
from .commitment import (
    COMMITMENT_KEY_PREFIX,
    CommitmentTerms,
    PaymentCommitment,
)
from .stellar_client import iso_to_unix


class CommitmentExtractionError(Exception):
    """Raised when a commitment cannot be extracted from the transaction data."""


def _decode_manage_data_value(value: Any) -> str:
    """Decode the value of a manage_data operation.

    Horizon returns the value as a base64-encoded string. We decode it
    to get the commitment hash (a 64-char hex string).
    """
    import base64

    if not isinstance(value, str):
        raise CommitmentExtractionError(
            f"manage_data value must be a string, got {type(value).__name__}"
        )
    try:
        decoded_bytes = base64.b64decode(value)
        decoded = decoded_bytes.decode("utf-8")
    except Exception as exc:
        raise CommitmentExtractionError(
            f"failed to decode manage_data value: {exc}"
        ) from exc
    if len(decoded) != 64:
        raise CommitmentExtractionError(
            f"commitment hash must be 64 chars, got {len(decoded)}: {decoded!r}"
        )
    return decoded


def _find_commitment_op(operations: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the first manage_data operation with a PROOF:COMMIT: key."""
    for op in operations:
        if op.get("type") != "manage_data":
            continue
        name = op.get("name", "")
        if isinstance(name, str) and name.startswith(COMMITMENT_KEY_PREFIX):
            return op
    return None


def extract_commitment(
    tx_data: dict[str, Any],
    operations: list[dict[str, Any]],
) -> PaymentCommitment:
    """Extract a payment commitment from a transaction's manage_data operations.

    Raises CommitmentExtractionError if no commitment is found or if any
    field is malformed.
    """
    tx_hash = tx_data.get("hash", "")
    validate_tx_hash(tx_hash)

    ledger = tx_data.get("ledger")
    if not isinstance(ledger, int) or isinstance(ledger, bool):
        raise CommitmentExtractionError(f"invalid ledger value: {ledger!r}")

    created_at = tx_data.get("created_at", "")
    if not isinstance(created_at, str) or not created_at:
        raise CommitmentExtractionError("missing or invalid created_at timestamp")
    timestamp_unix = iso_to_unix(created_at)

    successful = tx_data.get("successful", False)
    if not isinstance(successful, bool):
        raise CommitmentExtractionError(f"successful field is not bool: {successful!r}")

    if not successful:
        raise CommitmentExtractionError(
            "commitment transaction failed on ledger — commitment not applied"
        )

    commitment_op = _find_commitment_op(operations)
    if commitment_op is None:
        raise CommitmentExtractionError(
            f"no manage_data operation with key prefix {COMMITMENT_KEY_PREFIX!r} found"
        )

    key = commitment_op.get("name", "")
    if not isinstance(key, str) or not key.startswith(COMMITMENT_KEY_PREFIX):
        raise CommitmentExtractionError(f"invalid commitment key: {key!r}")

    reference = key[len(COMMITMENT_KEY_PREFIX):]
    if not reference:
        raise CommitmentExtractionError("commitment key has empty reference")

    value = commitment_op.get("value")
    committed_hash = _decode_manage_data_value(value)

    # The source account of the manage_data operation is the committer.
    source = commitment_op.get("source_account", "")
    if source and not is_valid_stellar_address(source):
        raise CommitmentExtractionError(f"invalid source_account: {source!r}")

    return PaymentCommitment(
        commitment_tx_hash=tx_hash,
        commitment_ledger=ledger,
        commitment_timestamp_unix=timestamp_unix,
        reference=reference,
        committed_hash=committed_hash,
        terms=None,  # Terms are not stored on-chain; they are reconstructed off-chain.
    )
