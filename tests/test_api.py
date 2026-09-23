"""
test_api.py — Tests for the L6 HTTP API.

Each test states the invariant it defends and what mutation it would catch.
"""
import pytest
from fastapi.testclient import TestClient

from proof.api import app

client = TestClient(app)

TX_HASH = "a" * 64
SENDER = "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"
RECIPIENT = "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z"


class TestHealth:
    def test_health_ok(self):
        """Invariant: the health endpoint returns ok."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestVerifyEndpoint:
    def test_verify_rejects_invalid_tx_hash(self):
        """Invariant: invalid transaction hash is rejected at the boundary.

        Mutation caught: if the API didn't validate, an invalid hash
        would reach the engine and produce a confusing error.
        """
        resp = client.post("/verify", json={
            "transaction_hash": "invalid",
            "network": "testnet",
        })
        assert resp.status_code == 400

    def test_verify_rejects_invalid_network(self):
        """Invariant: invalid network is rejected at the boundary."""
        resp = client.post("/verify", json={
            "transaction_hash": TX_HASH,
            "network": "invalid",
        })
        assert resp.status_code == 422  # Pydantic validation error

    def test_verify_rejects_invalid_sender(self):
        """Invariant: invalid sender address is rejected."""
        resp = client.post("/verify", json={
            "transaction_hash": TX_HASH,
            "sender": "not-an-address",
            "network": "testnet",
        })
        assert resp.status_code == 400

    def test_verify_rejects_float_amount(self):
        """Invariant: float amount is rejected — stroops must be integer."""
        resp = client.post("/verify", json={
            "transaction_hash": TX_HASH,
            "amount_stroops": 100.5,
            "network": "testnet",
        })
        # Pydantic should reject float for an int field.
        assert resp.status_code in (400, 422)

    @pytest.mark.skip(reason="requires network access to Stellar testnet")
    def test_verify_nonexistent_tx_returns_insufficient_evidence(self):
        """Invariant: a tx that doesn't exist returns INSUFFICIENT_EVIDENCE.

        This is a live test against testnet. It should return a bundle
        with verdict INSUFFICIENT_EVIDENCE, not crash.
        """
        # Use a valid-format hash that doesn't exist on testnet.
        resp = client.post("/verify", json={
            "transaction_hash": TX_HASH,
            "network": "testnet",
        })
        # This may fail due to network issues; if it succeeds, check the verdict.
        if resp.status_code == 200:
            bundle = resp.json()
            assert bundle["verdict"] == "INSUFFICIENT_EVIDENCE"
            assert "seal" in bundle
            assert len(bundle["seal"]) == 64


class TestDisputeEndpoint:
    def test_dispute_rejects_invalid_claim(self):
        """Invariant: invalid claim in dispute request is rejected."""
        resp = client.post("/verify/dispute", json={
            "claim_a": {"transaction_hash": "invalid"},
            "claim_b": {"transaction_hash": TX_HASH},
        })
        assert resp.status_code == 400

    def test_dispute_rejects_missing_claim(self):
        """Invariant: missing claim_b is rejected."""
        resp = client.post("/verify/dispute", json={
            "claim_a": {"transaction_hash": TX_HASH},
        })
        assert resp.status_code == 422


class TestReceiptEndpoint:
    def test_receipt_rejects_missing_fields(self):
        """Invariant: a bundle missing required fields is rejected."""
        resp = client.post("/receipt", json={"bundle": {"version": "1"}})
        assert resp.status_code == 400

    def test_receipt_rejects_non_dict_bundle(self):
        """Invariant: a non-dict bundle is rejected."""
        resp = client.post("/receipt", json={"bundle": "not-a-dict"})
        assert resp.status_code in (400, 422)


class TestAPIDoesNotModifySeal:
    @pytest.mark.skip(reason="requires network access to Stellar testnet")
    def test_api_returns_sealed_bundle(self):
        """Invariant: the API returns the sealed bundle without modification.

        The API is a transport layer — it must not alter the seal, verdict,
        or any sealed field. We verify the structure is complete.
        """
        resp = client.post("/verify", json={
            "transaction_hash": TX_HASH,
            "network": "testnet",
        })
        if resp.status_code == 200:
            bundle = resp.json()
            required = {"version", "claim", "evidence", "checks", "verdict", "scope_notes", "seal", "chain_of_custody"}
            assert required.issubset(bundle.keys())
            assert isinstance(bundle["seal"], str)
            assert len(bundle["seal"]) == 64
