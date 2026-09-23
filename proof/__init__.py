"""
PROOF — Payment Evidence, Not Screenshots.

Verify Stellar payment claims from the ledger, not from images.
"""
from .claim import PaymentClaim
from .commitment import CommitmentTerms, PaymentCommitment, Receipt, compute_commitment_hash
from .dispute import (
    BOTH_VERIFIED,
    CLAIM_A_VERIFIED,
    CLAIM_B_VERIFIED,
    CONTRADICTION,
    DisputeResult,
    NEITHER_VERIFIED,
    adjudicate_dispute,
    find_contradictions,
)
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
from .engine import issue_receipt, verify_dispute, verify_payment

__version__ = "0.4.0"
__all__ = [
    "PaymentClaim",
    "PaymentEvidence",
    "PaymentOperation",
    "CheckResult",
    "EvidenceBundle",
    "CommitmentTerms",
    "PaymentCommitment",
    "Receipt",
    "DisputeResult",
    "compute_commitment_hash",
    "verify_payment",
    "verify_dispute",
    "issue_receipt",
    "adjudicate_dispute",
    "find_contradictions",
    "VERIFIED",
    "NOT_VERIFIED",
    "INSUFFICIENT_EVIDENCE",
    "CLAIM_A_VERIFIED",
    "CLAIM_B_VERIFIED",
    "BOTH_VERIFIED",
    "NEITHER_VERIFIED",
    "CONTRADICTION",
    "PASS",
    "FAIL",
    "ABSTAIN",
]
