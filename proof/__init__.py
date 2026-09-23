"""
PROOF — Payment Evidence, Not Screenshots.

Verify Stellar payment claims from the ledger, not from images.
"""
from .claim import PaymentClaim
from .evidence import (
    ABSTAIN,
    CheckResult,
    EvidenceBundle,
    FAIL,
    INSUFFICIENT_EVIDENCE,
    NOT_VERIFIED,
    PASS,
    PaymentEvidence,
    VERIFIED,
)
from .engine import verify_payment

__version__ = "0.1.0"

__all__ = [
    "PaymentClaim",
    "PaymentEvidence",
    "CheckResult",
    "EvidenceBundle",
    "verify_payment",
    "VERIFIED",
    "NOT_VERIFIED",
    "INSUFFICIENT_EVIDENCE",
    "PASS",
    "FAIL",
    "ABSTAIN",
]
