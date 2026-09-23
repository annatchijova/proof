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
        """Fetch a transaction by hash.

        Returns None if the transaction is genuinely not found (HTTP 404).
        Raises StellarFetchError for network errors, TLS errors, timeouts,
        or server errors (HTTP 5xx). This distinguishes "doesn't exist"
        from "couldn't fetch" — the engine produces different messages.
        """
        try:
            response = self._server.transactions().transaction(tx_hash).call()
            return dict(response)
        except Exception as exc:
            # The Stellar SDK raises NotFoundError (or similar) for 404.
            # We check the exception name to distinguish 404 from network errors.
            exc_name = type(exc).__name__
            if exc_name in ("NotFoundError", "NotFoundErrorError"):
                return None
            # Check for HTTP 404 in the exception string as a fallback.
            exc_str = str(exc).lower()
            if "404" in exc_str or "not found" in exc_str:
                return None
            # Everything else is a network/server error — re-raise.
            raise StellarFetchError(
                f"failed to fetch transaction {tx_hash}: {exc}"
            ) from exc

    def fetch_operations(self, tx_hash: str) -> list[dict[str, Any]]:
        """Fetch all operations for a transaction.

        Returns an empty list if the operations cannot be fetched.
        Raises StellarFetchError for network errors.
        """
        try:
            response = self._server.operations().for_transaction(tx_hash).call()
            records = response.get("_embedded", {}).get("records", [])
            return [dict(r) for r in records]
        except Exception as exc:
            exc_name = type(exc).__name__
            if exc_name in ("NotFoundError", "NotFoundErrorError"):
                return []
            exc_str = str(exc).lower()
            if "404" in exc_str or "not found" in exc_str:
                return []
            raise StellarFetchError(
                f"failed to fetch operations for {tx_hash}: {exc}"
            ) from exc

    def fetch_effects(self, tx_hash: str) -> list[dict[str, Any]]:
        """Fetch all effects for a transaction.

        Effects are needed for account_merge operations, where the
        transferred amount is not in the operation itself but in the
        account_debited effect.

        Returns an empty list if the effects cannot be fetched.
        Raises StellarFetchError for network errors.
        """
        try:
            response = self._server.effects().for_transaction(tx_hash).call()
            records = response.get("_embedded", {}).get("records", [])
            return [dict(r) for r in records]
        except Exception as exc:
            exc_name = type(exc).__name__
            if exc_name in ("NotFoundError", "NotFoundErrorError"):
                return []
            exc_str = str(exc).lower()
            if "404" in exc_str or "not found" in exc_str:
                return []
            raise StellarFetchError(
                f"failed to fetch effects for {tx_hash}: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._server.close()


class StellarFetchError(Exception):
    """Raised when a Horizon fetch fails due to network/server errors.

    This is distinct from a transaction not being found (which returns
    None). Network errors should not be silently treated as "not found"
    because they produce misleading INSUFFICIENT_EVIDENCE verdicts.
    """


def amount_to_stroops(amount_str: str) -> int:
    """Convert a Stellar decimal amount string to integer stroops.

    Stellar Horizon returns amounts as decimal strings like "100.0000000".
    We use Decimal for exact conversion — no float ever enters the path.

    Fails closed if the amount has fractional stroops (more than 7 decimal
    places). A well-formed Horizon response never produces fractional
    stroops, but a malformed or adversarial response could. We reject
    rather than truncate — silent truncation would produce a wrong amount
    in the sealed evidence.
    """
    if not isinstance(amount_str, str):
        raise ValueError(f"amount must be a string, got {type(amount_str).__name__}")
    decimal = Decimal(amount_str)
    stroops_decimal = decimal * STROOPS_PER_UNIT
    if stroops_decimal != int(stroops_decimal):
        raise ValueError(
            f"amount has fractional stroops (more than 7 decimal places): {amount_str!r}"
        )
    return int(stroops_decimal)


def iso_to_unix(iso_timestamp: str) -> int:
    """Convert an ISO 8601 timestamp to Unix epoch seconds (integer)."""
    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    return int(dt.timestamp())
