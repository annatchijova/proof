"""
test_stellar_client.py — Tests for the Stellar client boundary behavior.

F2: fetch_transaction must distinguish "not found" (returns None) from
"network error" (raises StellarFetchError). Swallowing all exceptions as
"not found" produces misleading INSUFFICIENT_EVIDENCE verdicts.
"""
import pytest
from unittest.mock import MagicMock, patch

from proof.stellar_client import StellarClient, StellarFetchError


class TestFetchTransactionErrorHandling:
    """F2: distinguish not-found from network-error."""

    def test_not_found_returns_none(self):
        """Invariant: a 404 returns None, not an exception.

        The SDK raises NotFoundError for 404s. We catch it and return
        None so the engine can produce a "not found" message.
        """
        client = StellarClient(network="testnet")

        # Mock the server to raise a NotFoundError-like exception.
        mock_call = MagicMock(side_effect=Exception("404 not found"))
        with patch.object(client._server.transactions(), "transaction", return_value=MagicMock(call=mock_call)):
            # The mock chain is complex; instead, patch fetch_transaction's
            # internal call path more directly.
            pass

        # Simpler approach: patch the _server attribute.
        mock_server = MagicMock()
        mock_server.transactions.return_value.transaction.return_value.call.side_effect = Exception("404 not found")
        client._server = mock_server

        result = client.fetch_transaction("a" * 64)
        assert result is None

    def test_network_error_raises_stellar_fetch_error(self):
        """Invariant: a network error raises StellarFetchError, not None.

        Mutation caught: if we swallowed all exceptions as None, a
        network error would be indistinguishable from "not found".
        """
        client = StellarClient(network="testnet")

        mock_server = MagicMock()
        mock_server.transactions.return_value.transaction.return_value.call.side_effect = Exception("Connection timeout")
        client._server = mock_server

        with pytest.raises(StellarFetchError, match="failed to fetch transaction"):
            client.fetch_transaction("a" * 64)

    def test_fetch_operations_network_error_raises(self):
        """Invariant: fetch_operations also raises StellarFetchError on network error."""
        client = StellarClient(network="testnet")

        mock_server = MagicMock()
        mock_server.operations.return_value.for_transaction.return_value.call.side_effect = Exception("Connection refused")
        client._server = mock_server

        with pytest.raises(StellarFetchError, match="failed to fetch operations"):
            client.fetch_operations("a" * 64)

    def test_fetch_effects_network_error_raises(self):
        """Invariant: fetch_effects also raises StellarFetchError on network error."""
        client = StellarClient(network="testnet")

        mock_server = MagicMock()
        mock_server.effects.return_value.for_transaction.return_value.call.side_effect = Exception("TLS error")
        client._server = mock_server

        with pytest.raises(StellarFetchError, match="failed to fetch effects"):
            client.fetch_effects("a" * 64)
