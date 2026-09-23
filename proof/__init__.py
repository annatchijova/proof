"""
PROOF — Payment Evidence, Not Screenshots.

Verify Stellar payment claims from the ledger, not from images.
"""
from .claim import PaymentClaim
from .commitment import CommitmentTerms, PaymentCommitment, Receipt, compute_commitment_hash
from .evidence import (
    ABSTAIN,
    CheckResult,
    EvidenceBundle,
    FAIL,
    INSUFFICIENT_EVIDENCE,
    NOT_VERIFIED,
    PASS,
    PaymentEvidence,
    PaymentOperation,
    VERIFIED,
)
from .engine import issue_receipt, verify_payment

__version__ = "0.3.0"

__all__ = [
    "PaymentClaim",
    "PaymentEvidence",
    "PaymentOperation",
    "CheckResult",
    "EvidenceBundle",
    "CommitmentTerms",
    "PaymentCommitment",
    "Receipt",
    "compute_commitment_hash",
    "verify_payment",
    "issue_receipt",
    "VERIFIED",
    "NOT_VERIFIED",
    "INSUFFICIENT_EVIDENCE",
    "PASS",
    "FAIL",
    "ABSTAIN",
]
