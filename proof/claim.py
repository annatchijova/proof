"""
claim.py — A payment claim is what someone asserts happened.

A claim is a set of propositions, each of which is independently verifiable
against the ledger. Fields left as None are propositions the claim does not
make — they are ABSTAIN-ed during adjudication, not assumed true.

Amounts are integer stroops (1 unit = 10^7 stroops). No float ever enters
the claim — this is a deterministic-core invariant.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Stellar public keys are 56 chars, start with G, base32-encoded.
_STELLAR_ADDRESS_RE = re.compile(r"^G[A-Z2-7]{55}$")
# Transaction hashes are 64 hex chars (SHA-256).
_TX_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

# Maximum amounts in stroops (Stellar uses signed 64-bit integers).
MAX_STROOPS = 2**63 - 1


def is_valid_stellar_address(addr: str) -> bool:
    """Check whether ``addr`` has the format of a Stellar public key (G...)."""
    if not isinstance(addr, str):
        return False
    return bool(_STELLAR_ADDRESS_RE.match(addr))


def is_valid_tx_hash(tx_hash: str) -> bool:
    """Check whether ``tx_hash`` has the format of a Stellar transaction hash."""
    if not isinstance(tx_hash, str):
        return False
    return bool(_TX_HASH_RE.match(tx_hash))


def validate_stellar_address(addr: str, field_name: str) -> str:
    """Validate a Stellar address or raise ValueError with the field name."""
    if not isinstance(addr, str) or not is_valid_stellar_address(addr):
        raise ValueError(f"{field_name} is not a valid Stellar address: {addr!r}")
    return addr


def validate_tx_hash(tx_hash: str) -> str:
    """Validate a transaction hash or raise ValueError."""
    if not isinstance(tx_hash, str) or not is_valid_tx_hash(tx_hash):
        raise ValueError(
            f"transaction_hash is not a valid 64-char hex hash: {tx_hash!r}"
        )
    return tx_hash


def validate_stroops(amount: int, field_name: str) -> int:
    """Validate an integer amount in stroops."""
    if not isinstance(amount, bool) and not isinstance(amount, int):
        raise ValueError(f"{field_name} must be an integer (stroops), got {type(amount).__name__}")
    if isinstance(amount, bool):
        raise ValueError(f"{field_name} must be an integer, not bool")
    if amount < 0:
        raise ValueError(f"{field_name} must be non-negative, got {amount}")
    if amount > MAX_STROOPS:
        raise ValueError(f"{field_name} exceeds maximum stroops ({MAX_STROOPS}), got {amount}")
    return amount


def validate_ledger_seq(seq: int, field_name: str) -> int:
    """Validate a Stellar ledger sequence number."""
    if not isinstance(seq, int) or isinstance(seq, bool):
        raise ValueError(f"{field_name} must be an integer, got {type(seq).__name__}")
    if seq < 0:
        raise ValueError(f"{field_name} must be non-negative, got {seq}")
    return seq


@dataclass(frozen=True)
class PaymentClaim:
    """What someone asserts happened.

    Every field is optional — a claim can be as specific as "100 USDC from
    Alice to Bob for invoice INV-184" or as vague as "a payment happened in
    this transaction." Fields left as None are not checked.
    """

    transaction_hash: str
    sender: str | None = None
    recipient: str | None = None
    asset_code: str | None = None
    asset_issuer: str | None = None
    amount_stroops: int | None = None
    reference: str | None = None
    ledger_min: int | None = None
    ledger_max: int | None = None
    commitment_tx_hash: str | None = None

    def __post_init__(self) -> None:
        validate_tx_hash(self.transaction_hash)
        if self.sender is not None:
            validate_stellar_address(self.sender, "sender")
        if self.recipient is not None:
            validate_stellar_address(self.recipient, "recipient")
        if self.asset_issuer is not None:
            validate_stellar_address(self.asset_issuer, "asset_issuer")
        if self.amount_stroops is not None:
            validate_stroops(self.amount_stroops, "amount_stroops")
        if self.ledger_min is not None:
            validate_ledger_seq(self.ledger_min, "ledger_min")
        if self.ledger_max is not None:
            validate_ledger_seq(self.ledger_max, "ledger_max")
        if (
            self.ledger_min is not None
            and self.ledger_max is not None
            and self.ledger_min > self.ledger_max
        ):
            raise ValueError(
                f"ledger_min ({self.ledger_min}) > ledger_max ({self.ledger_max})"
            )
        if self.commitment_tx_hash is not None:
            if not is_valid_tx_hash(self.commitment_tx_hash):
                raise ValueError(
                    f"commitment_tx_hash is not a valid 64-char hex hash: {self.commitment_tx_hash!r}"
                )

    def to_dict(self) -> dict:
        """Return a dict with only the non-None fields (for canonical serialization)."""
        result: dict = {"transaction_hash": self.transaction_hash}
        for field in (
            "sender",
            "recipient",
            "asset_code",
            "asset_issuer",
            "amount_stroops",
            "reference",
            "ledger_min",
            "ledger_max",
            "commitment_tx_hash",
        ):
            value = getattr(self, field)
            if value is not None:
                result[field] = value
        return result
