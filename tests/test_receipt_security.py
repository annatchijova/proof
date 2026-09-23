"""Receipt issuance must not bless an unverified bundle."""

import pytest
from fastapi import HTTPException

from proof.api import ReceiptRequest, receipt
from proof.claim import PaymentClaim
from proof.commitment import Receipt
from proof.evidence import EvidenceBundle, VERIFIED
from proof.engine import issue_receipt


TX_HASH = "a" * 64


def _bundle() -> dict:
    return EvidenceBundle.build(
        claim=PaymentClaim(transaction_hash=TX_HASH).to_dict(),
        evidence={},
        checks=[],
        verdict=VERIFIED,
        chain_of_custody={"network": "testnet"},
    ).to_dict()


def test_receipt_endpoint_rejects_forged_seal():
    """A caller cannot turn a claimed VERIFIED verdict into a receipt."""
    bundle = _bundle()
    bundle["seal"] = "a" * 64

    with pytest.raises(HTTPException) as exc_info:
        receipt(ReceiptRequest(bundle=bundle))

    assert exc_info.value.status_code == 400
    assert "independently verifiable" in str(exc_info.value.detail)


def test_issue_receipt_accepts_only_an_independently_verified_bundle():
    bundle = EvidenceBundle(**_bundle())
    result = issue_receipt(bundle)
    assert isinstance(result, Receipt)
    assert result.verdict == VERIFIED
