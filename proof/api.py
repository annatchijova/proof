"""
api.py — HTTP API for PROOF verification.

Exposes the deterministic core via a REST API so third parties can
verify payment claims without running the full pipeline locally.

Endpoints:
  POST /verify          — verify a single payment claim
  POST /verify/dispute  — verify a dispute between two claims
  POST /receipt         — issue a receipt from a verified bundle
  GET  /health          — health check

The API is a thin transport layer. All logic lives in the deterministic
core. The API never modifies verdicts, seals, or evidence.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .claim import PaymentClaim
from .engine import issue_receipt, verify_dispute, verify_payment

app = FastAPI(
    title="PROOF — Payment Evidence, Not Screenshots",
    description="Verify Stellar payment claims from the ledger, not from images.",
    version="0.4.0",
)


class VerifyRequest(BaseModel):
    """Request body for POST /verify."""
    transaction_hash: str = Field(..., description="64-char hex Stellar transaction hash")
    sender: str | None = Field(None, description="Expected sender address (G...)")
    recipient: str | None = Field(None, description="Expected recipient address (G...)")
    asset_code: str | None = Field(None, description="Expected asset code (e.g. USDC)")
    asset_issuer: str | None = Field(None, description="Expected asset issuer address")
    amount_stroops: int | None = Field(None, description="Expected amount in stroops (integer)")
    reference: str | None = Field(None, description="Expected reference/memo")
    ledger_min: int | None = Field(None, description="Minimum ledger sequence")
    ledger_max: int | None = Field(None, description="Maximum ledger sequence")
    commitment_tx_hash: str | None = Field(None, description="Transaction hash of an on-chain commitment")
    network: str = Field("testnet", description="Stellar network: testnet or mainnet")

    @field_validator("network")
    @classmethod
    def validate_network(cls, v: str) -> str:
        if v not in ("testnet", "mainnet"):
            raise ValueError("network must be 'testnet' or 'mainnet'")
        return v

    def to_claim(self) -> PaymentClaim:
        return PaymentClaim(
            transaction_hash=self.transaction_hash,
            sender=self.sender,
            recipient=self.recipient,
            asset_code=self.asset_code,
            asset_issuer=self.asset_issuer,
            amount_stroops=self.amount_stroops,
            reference=self.reference,
            ledger_min=self.ledger_min,
            ledger_max=self.ledger_max,
            commitment_tx_hash=self.commitment_tx_hash,
        )


class DisputeRequest(BaseModel):
    """Request body for POST /verify/dispute."""
    claim_a: VerifyRequest
    claim_b: VerifyRequest


class ReceiptRequest(BaseModel):
    """Request body for POST /receipt."""
    bundle: dict = Field(..., description="A verified evidence bundle")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/verify")
def verify(req: VerifyRequest) -> dict[str, Any]:
    """Verify a payment claim against the Stellar ledger.

    Returns a sealed evidence bundle with the verdict, checks, and SHA-256 seal.
    """
    try:
        claim = req.to_claim()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    bundle = verify_payment(claim, network=req.network)
    return bundle.to_dict()


@app.post("/verify/dispute")
def verify_dispute_endpoint(req: DisputeRequest) -> dict[str, Any]:
    """Verify a dispute between two contradictory payment claims.

    Each claim is verified independently, then the evidence sets are
    compared for contradictions.
    """
    try:
        claim_a = req.claim_a.to_claim()
        claim_b = req.claim_b.to_claim()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Use the network from claim_a (both claims should be on the same network).
    result = verify_dispute(claim_a, claim_b, network=req.claim_a.network)
    return result.to_dict()


@app.post("/receipt")
def receipt(req: ReceiptRequest) -> dict[str, Any]:
    """Issue a receipt from a verified evidence bundle.

    The receipt contains the transaction hash, verdict, and seal. It can
    be registered on-chain via a manage_data operation.
    """
    bundle_dict = req.bundle
    if not isinstance(bundle_dict, dict):
        raise HTTPException(status_code=400, detail="bundle must be a dict")

    required_fields = {"version", "claim", "evidence", "checks", "verdict", "seal"}
    missing = required_fields - set(bundle_dict.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"bundle missing fields: {missing}")

    from .evidence import EvidenceBundle

    bundle = EvidenceBundle(
        version=bundle_dict["version"],
        claim=bundle_dict["claim"],
        evidence=bundle_dict["evidence"],
        checks=bundle_dict["checks"],
        verdict=bundle_dict["verdict"],
        scope_notes=bundle_dict.get("scope_notes", []),
        seal=bundle_dict["seal"],
        chain_of_custody=bundle_dict.get("chain_of_custody", {}),
        commitment=bundle_dict.get("commitment"),
    )

    receipt_obj = issue_receipt(bundle)
    return receipt_obj.to_dict()
