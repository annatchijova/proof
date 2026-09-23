"""
evidence.py — What the ledger actually shows, plus the sealed bundle.

PaymentEvidence is the deterministic reconstruction of a Stellar transaction's
payment-relevant facts. It contains no float — amounts are integer stroops.

CheckResult is one proposition checked against the evidence.

EvidenceBundle is the sealed output: the claim, the evidence, the checks,
the verdict, and the SHA-256 seal. Chain-of-custody metadata lives outside
the seal so a verifier can confirm the result without trusting the prose.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .canonicalize import CANONICALIZE_VERSION, seal

# Verdicts — three states, not two. INSUFFICIENT_EVIDENCE is not the same as
# NOT_VERIFIED: the former means we could not even look, the latter means we
# looked and the claim does not hold.
VERIFIED = "VERIFIED"
NOT_VERIFIED = "NOT_VERIFIED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

# Check statuses — three states per honest-degradation.
PASS = "PASS"
FAIL = "FAIL"
ABSTAIN = "ABSTAIN"

# Scope notes — always included. These are the things PROOF does NOT prove.
# They are not checks; they are boundaries on what the evidence can establish.
SCOPE_NOTES = [
    "Payment execution does not establish legal satisfaction of any underlying debt.",
    "Transaction existence does not establish delivery of goods or services.",
    "Wallet signature does not establish human identity.",
]


@dataclass(frozen=True)
class PaymentOperation:
    """One payment-type operation within a transaction.

    For path payments, source_asset_* fields describe what the sender spent
    and asset_* fields describe what the recipient received.
    """

    operation_type: str
    sender: str
    recipient: str
    asset_code: str
    asset_issuer: str | None
    amount_stroops: int
    source_asset_code: str | None = None
    source_asset_issuer: str | None = None
    source_amount_stroops: int | None = None

    def to_dict(self) -> dict:
        result: dict = {
            "operation_type": self.operation_type,
            "sender": self.sender,
            "recipient": self.recipient,
            "asset_code": self.asset_code,
            "asset_issuer": self.asset_issuer,
            "amount_stroops": self.amount_stroops,
        }
        if self.source_asset_code is not None:
            result["source_asset_code"] = self.source_asset_code
        if self.source_asset_issuer is not None:
            result["source_asset_issuer"] = self.source_asset_issuer
        if self.source_amount_stroops is not None:
            result["source_amount_stroops"] = self.source_amount_stroops
        return result


@dataclass(frozen=True)
class PaymentEvidence:
    """What the Stellar ledger shows for a given transaction.

    A transaction may contain multiple payment-type operations. Each is
    represented as a PaymentOperation in the operations list. The top-level
    fields (sender, recipient, etc.) are convenience aliases for the first
    payment operation, preserving backward compatibility with L1/L2 callers.
    """

    transaction_hash: str
    ledger: int
    timestamp_unix: int
    successful: bool
    sender: str
    recipient: str
    asset_code: str
    asset_issuer: str | None
    amount_stroops: int
    memo: str | None
    memo_type: str
    operation_type: str
    operations: list[PaymentOperation] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a dict for canonical serialization."""
        result: dict = {
            "transaction_hash": self.transaction_hash,
            "ledger": self.ledger,
            "timestamp_unix": self.timestamp_unix,
            "successful": self.successful,
            "sender": self.sender,
            "recipient": self.recipient,
            "asset_code": self.asset_code,
            "asset_issuer": self.asset_issuer,
            "amount_stroops": self.amount_stroops,
            "memo": self.memo,
            "memo_type": self.memo_type,
            "operation_type": self.operation_type,
            "operations": [op.to_dict() for op in self.operations],
        }
        return result


@dataclass(frozen=True)
class CheckResult:
    """One proposition checked against the evidence."""

    name: str
    status: str  # PASS, FAIL, ABSTAIN
    expected: str | None
    actual: str | None
    detail: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "expected": self.expected,
            "actual": self.actual,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class EvidenceBundle:
    """The sealed output of PROOF.

    The sealed_payload contains everything that goes into the SHA-256 hash.
    The seal is computed over canonical(sealed_payload).
    The chain_of_custody is metadata stored beside the seal, not inside it.

    L4: if a commitment was verified, it is included in the sealed payload
    so the commitment is part of the tamper-evident record.
    """

    version: str
    claim: dict
    evidence: dict
    checks: list[dict]
    verdict: str
    scope_notes: list[str]
    seal: str
    chain_of_custody: dict
    commitment: dict | None = None

    @classmethod
    def build(
        cls,
        claim: dict,
        evidence: dict,
        checks: list[dict],
        verdict: str,
        chain_of_custody: dict,
        commitment: dict | None = None,
    ) -> "EvidenceBundle":
        """Construct a bundle, computing the seal over the sealed payload."""
        sealed_payload: dict = {
            "version": CANONICALIZE_VERSION,
            "claim": claim,
            "evidence": evidence,
            "checks": checks,
            "verdict": verdict,
            "scope_notes": list(SCOPE_NOTES),
        }
        if commitment is not None:
            sealed_payload["commitment"] = commitment
        digest = seal(sealed_payload)
        return cls(
            version=CANONICALIZE_VERSION,
            claim=claim,
            evidence=evidence,
            checks=checks,
            verdict=verdict,
            scope_notes=list(SCOPE_NOTES),
            seal=digest,
            chain_of_custody=chain_of_custody,
            commitment=commitment,
        )

    def to_dict(self) -> dict:
        """Full dict representation including seal and chain of custody."""
        result: dict = {
            "version": self.version,
            "claim": self.claim,
            "evidence": self.evidence,
            "checks": self.checks,
            "verdict": self.verdict,
            "scope_notes": self.scope_notes,
            "seal": self.seal,
            "chain_of_custody": self.chain_of_custody,
        }
        if self.commitment is not None:
            result["commitment"] = self.commitment
        return result

    @property
    def sealed_payload(self) -> dict:
        """The portion that was sealed — used by the verifier."""
        result: dict = {
            "version": self.version,
            "claim": self.claim,
            "evidence": self.evidence,
            "checks": self.checks,
            "verdict": self.verdict,
            "scope_notes": self.scope_notes,
        }
        if self.commitment is not None:
            result["commitment"] = self.commitment
        return result
