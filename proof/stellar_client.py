"""
stellar_client.py — Thin wrapper over the Stellar Horizon API.

Fetches a transaction and its operations from a Stellar Horizon server.
Supports both testnet and mainnet. This module is the trust boundary where
external data enters PROOF — everything returned here is untrusted until
the extractor validates it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from stellar_sdk import Server

# Horizon endpoints for both networks.
HORIZON_URLS = {
    "testnet": "https://horizon-testnet.stellar.org",
    "mainnet": "https://horizon.stellar.org",
}

# Stellar network passphrases.
NETWORK_PASSPHRASES = {
    "testnet": "Test SDF Network ; September 2015",
    "mainnet": "Public Global Stellar Network ; September 2015",
}

# One stroop = 10^-7 units. Stellar amounts are signed 64-bit integers.
STROOPS_PER_UNIT = 10**7


class StellarClient:
    """Fetches transaction and operation data from a Stellar Horizon server."""

    def __init__(self, network: str = "testnet") -> None:
        if network not in HORIZON_URLS:
            raise ValueError(
                f"network must be 'testnet' or 'mainnet', got {network!r}"
            )
        self.network = network
        self.horizon_url = HORIZON_URLS[network]
        self.network_passphrase = NETWORK_PASSPHRASES[network]
        self._server = Server(horizon_url=self.horizon_url)

    def fetch_transaction(self, tx_hash: str) -> dict[str, Any] | None:
        """Fetch a transaction by hash. Returns None if not found."""
        try:
            response = self._server.transactions().transaction(tx_hash).call()
            return dict(response)
        except Exception:
            return None

    def fetch_operations(self, tx_hash: str) -> list[dict[str, Any]]:
        """Fetch all operations for a transaction."""
        try:
            response = self._server.operations().for_transaction(tx_hash).call()
            records = response.get("_embedded", {}).get("records", [])
            return [dict(r) for r in records]
        except Exception:
            return []

    def fetch_effects(self, tx_hash: str) -> list[dict[str, Any]]:
        """Fetch all effects for a transaction.

        Effects are needed for account_merge operations, where the
        transferred amount is not in the operation itself but in the
        account_debited effect.
        """
        try:
            response = self._server.effects().for_transaction(tx_hash).call()
            records = response.get("_embedded", {}).get("records", [])
            return [dict(r) for r in records]
        except Exception:
            return []

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._server.close()


def amount_to_stroops(amount_str: str) -> int:
    """Convert a Stellar decimal amount string to integer stroops.

    Stellar Horizon returns amounts as decimal strings like "100.0000000".
    We use Decimal for exact conversion — no float ever enters the path.
    """
    if not isinstance(amount_str, str):
        raise ValueError(f"amount must be a string, got {type(amount_str).__name__}")
    decimal = Decimal(amount_str)
    stroops = int(decimal * STROOPS_PER_UNIT)
    return stroops


def iso_to_unix(iso_timestamp: str) -> int:
    """Convert an ISO 8601 timestamp to Unix epoch seconds (integer)."""
    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    return int(dt.timestamp())
