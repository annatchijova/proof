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
class PaymentEvidence:
    """What the Stellar ledger shows for a given transaction."""

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
    operation_type: str

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
            "operation_type": self.operation_type,
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
    """

    version: str
    claim: dict
    evidence: dict
    checks: list[dict]
    verdict: str
    scope_notes: list[str]
    seal: str
    chain_of_custody: dict

    @classmethod
    def build(
        cls,
        claim: dict,
        evidence: dict,
        checks: list[dict],
        verdict: str,
        chain_of_custody: dict,
    ) -> "EvidenceBundle":
        """Construct a bundle, computing the seal over the sealed payload."""
        sealed_payload = {
            "version": CANONICALIZE_VERSION,
            "claim": claim,
            "evidence": evidence,
            "checks": checks,
            "verdict": verdict,
            "scope_notes": list(SCOPE_NOTES),
        }
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
        )

    def to_dict(self) -> dict:
        """Full dict representation including seal and chain of custody."""
        return {
            "version": self.version,
            "claim": self.claim,
            "evidence": self.evidence,
            "checks": self.checks,
            "verdict": self.verdict,
            "scope_notes": self.scope_notes,
            "seal": self.seal,
            "chain_of_custody": self.chain_of_custody,
        }

    @property
    def sealed_payload(self) -> dict:
        """The portion that was sealed — used by the verifier."""
        return {
            "version": self.version,
            "claim": self.claim,
            "evidence": self.evidence,
            "checks": self.checks,
            "verdict": self.verdict,
            "scope_notes": self.scope_notes,
        }
