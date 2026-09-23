"""
commitment.py — Payment commitments registered on-chain.

A commitment is a pre-registered expectation of a payment. Before the
payment happens, someone registers a hash of the expected payment terms
on the Stellar ledger. When the payment later occurs, PROOF can verify
not just that the payment happened, but that it matches what was
committed.

The commitment hash is SHA-256(canonical(commitment_terms)). The terms
include: sender, recipient, asset_code, asset_issuer, amount_stroops,
reference.

PROOF supports two on-chain commitment mechanisms:

1. Soroban contract (PRIMARY): the proof-registry contract provides
   require_auth(), enforced immutability (panic on overwrite), and
   on-chain temporal order verification. This is the recommended path.

2. manage_data (FALLBACK): native Stellar manage_data operations store
   the commitment hash as a key-value pair. This works on all Stellar
   accounts without Soroban, but lacks auth enforcement, immutability,
   and temporal order verification.

The commitment hash computation (CommitmentTerms.commitment_hash) is
identical for both mechanisms. The difference is only in the transport.

A receipt is the inverse: after PROOF verifies a payment, it can issue
a receipt (the seal of the evidence bundle) that can be registered
on-chain as proof that verification occurred.

No float, no LLM, no probability. Pure deterministic hashing.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonicalize import seal
from .claim import (
    is_valid_stellar_address,
    validate_stellar_address,
    validate_stroops,
    validate_tx_hash,
)

# Prefix for manage_data keys that store PROOF commitments.
COMMITMENT_KEY_PREFIX = "PROOF:COMMIT:"

# Prefix for manage_data keys that store PROOF receipts.
RECEIPT_KEY_PREFIX = "PROOF:RECEIPT:"


@dataclass(frozen=True)
class CommitmentTerms:
    """The terms of a payment commitment.

    These are the fields that get hashed into the commitment. All fields
    are required — a commitment is a complete specification of the
    expected payment. Unlike a claim (which can be partial), a commitment
    must be specific.
    """

    sender: str
    recipient: str
    asset_code: str
    asset_issuer: str | None
    amount_stroops: int
    reference: str | None = None

    def __post_init__(self) -> None:
        validate_stellar_address(self.sender, "sender")
        validate_stellar_address(self.recipient, "recipient")
        if self.asset_issuer is not None:
            validate_stellar_address(self.asset_issuer, "asset_issuer")
        if not isinstance(self.asset_code, str) or not self.asset_code:
            raise ValueError(f"asset_code must be a non-empty string, got {self.asset_code!r}")
        validate_stroops(self.amount_stroops, "amount_stroops")
        if self.reference is not None and not isinstance(self.reference, str):
            raise ValueError(f"reference must be a string or None, got {type(self.reference).__name__}")

    def to_dict(self) -> dict:
        result: dict = {
            "sender": self.sender,
            "recipient": self.recipient,
            "asset_code": self.asset_code,
            "asset_issuer": self.asset_issuer,
            "amount_stroops": self.amount_stroops,
        }
        if self.reference is not None:
            result["reference"] = self.reference
        return result

    def commitment_hash(self) -> str:
        """Compute the SHA-256 commitment hash over the canonical terms."""
        return seal(self.to_dict())


@dataclass(frozen=True)
class PaymentCommitment:
    """A commitment that was registered on-chain.

    This is what PROOF reconstructs from the ledger when it fetches a
    commitment transaction. The commitment_tx_hash identifies the
    transaction that registered the commitment. The committed_hash is
    the hash stored in the manage_data entry. The terms are what the
    commitment claims to commit to (extracted from the manage_data key
    or from a separate structured source).
    """

    commitment_tx_hash: str
    commitment_ledger: int
    commitment_timestamp_unix: int
    reference: str
    committed_hash: str
    terms: CommitmentTerms | None

    def __post_init__(self) -> None:
        validate_tx_hash(self.commitment_tx_hash)
        if not isinstance(self.commitment_ledger, int) or isinstance(self.commitment_ledger, bool):
            raise ValueError(f"commitment_ledger must be int, got {type(self.commitment_ledger).__name__}")
        if self.commitment_ledger < 0:
            raise ValueError(f"commitment_ledger must be non-negative, got {self.commitment_ledger}")
        if not isinstance(self.commitment_timestamp_unix, int) or isinstance(self.commitment_timestamp_unix, bool):
            raise ValueError(
                f"commitment_timestamp_unix must be int, got {type(self.commitment_timestamp_unix).__name__}"
            )
        if not isinstance(self.reference, str) or not self.reference:
            raise ValueError(f"reference must be a non-empty string, got {self.reference!r}")
        if not isinstance(self.committed_hash, str) or len(self.committed_hash) != 64:
            raise ValueError(
                f"committed_hash must be a 64-char hex string, got {self.committed_hash!r}"
            )

    def to_dict(self) -> dict:
        result: dict = {
            "commitment_tx_hash": self.commitment_tx_hash,
            "commitment_ledger": self.commitment_ledger,
            "commitment_timestamp_unix": self.commitment_timestamp_unix,
            "reference": self.reference,
            "committed_hash": self.committed_hash,
        }
        if self.terms is not None:
            result["terms"] = self.terms.to_dict()
            result["terms_hash"] = self.terms.commitment_hash()
            result["hash_matches"] = self.terms.commitment_hash() == self.committed_hash
        return result


@dataclass(frozen=True)
class Receipt:
    """A receipt issued by PROOF after verifying a payment.

    The receipt is the seal of the evidence bundle. It can be registered
    on-chain via a manage_data operation with key=PROOF:RECEIPT:<tx_hash>
    and value=seal. This creates an on-chain record that PROOF verified
    the payment at a specific time.
    """

    transaction_hash: str
    verdict: str
    seal: str
    issued_at: int

    def __post_init__(self) -> None:
        validate_tx_hash(self.transaction_hash)
        if not isinstance(self.verdict, str) or not self.verdict:
            raise ValueError(f"verdict must be a non-empty string, got {self.verdict!r}")
        if not isinstance(self.seal, str) or len(self.seal) != 64:
            raise ValueError(f"seal must be a 64-char hex string, got {self.seal!r}")
        if not isinstance(self.issued_at, int) or isinstance(self.issued_at, bool):
            raise ValueError(f"issued_at must be int, got {type(self.issued_at).__name__}")

    def to_dict(self) -> dict:
        return {
            "transaction_hash": self.transaction_hash,
            "verdict": self.verdict,
            "seal": self.seal,
            "issued_at": self.issued_at,
        }

    @property
    def manage_data_key(self) -> str:
        """The manage_data key for registering this receipt on-chain."""
        return f"{RECEIPT_KEY_PREFIX}{self.transaction_hash}"

    @property
    def manage_data_value(self) -> str:
        """The manage_data value for registering this receipt on-chain."""
        return self.seal


def compute_commitment_hash(
    sender: str,
    recipient: str,
    asset_code: str,
    asset_issuer: str | None,
    amount_stroops: int,
    reference: str | None = None,
) -> str:
    """Compute a commitment hash from payment terms.

    This is the function a committer would call before registering the
    commitment on-chain. The resulting hash is stored as a manage_data
    value.
    """
    terms = CommitmentTerms(
        sender=sender,
        recipient=recipient,
        asset_code=asset_code,
        asset_issuer=asset_issuer,
        amount_stroops=amount_stroops,
        reference=reference,
    )
    return terms.commitment_hash()


def commitment_key(reference: str) -> str:
    """Build the manage_data key for a commitment with the given reference."""
    if not isinstance(reference, str) or not reference:
        raise ValueError(f"reference must be a non-empty string, got {reference!r}")
    return f"{COMMITMENT_KEY_PREFIX}{reference}"
