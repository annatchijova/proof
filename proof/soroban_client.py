"""
soroban_client.py — Client for the PROOF Soroban registry contract.

This module wraps the stellar CLI to interact with the deployed Soroban
contract on Testnet. It is a thin transport layer — it does not modify
commitment hashes, seals, or verdicts. All logic lives in the
deterministic core.

The contract ID and source identity are configurable via environment
variables:
  PROOF_CONTRACT_ID  — the deployed contract ID (default: testnet)
  PROOF_STELLAR_SOURCE — the stellar CLI identity name (default: alice)
  PROOF_STELLAR_NETWORK — the stellar network (default: testnet)
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any

DEFAULT_CONTRACT_ID = "CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I"
DEFAULT_SOURCE = "alice"
DEFAULT_NETWORK = "testnet"


def _get_contract_id() -> str:
    return os.environ.get("PROOF_CONTRACT_ID", DEFAULT_CONTRACT_ID)


def _get_source() -> str:
    return os.environ.get("PROOF_STELLAR_SOURCE", DEFAULT_SOURCE)


def _get_network() -> str:
    return os.environ.get("PROOF_STELLAR_NETWORK", DEFAULT_NETWORK)


def _invoke(
    function: str,
    *args: str,
    send: bool = True,
    contract_id: str | None = None,
    source: str | None = None,
    network: str | None = None,
) -> str:
    """Invoke a contract function via the stellar CLI.

    Returns the stdout output as a string. Raises RuntimeError on failure.
    """
    cid = contract_id or _get_contract_id()
    src = source or _get_source()
    net = network or _get_network()

    cli_args = [
        "stellar",
        "contract",
        "invoke",
        "--source", src,
        "--network", net,
        "--id", cid,
    ]
    if send:
        cli_args.append("--send=yes")
    else:
        cli_args.append("--send=no")
    cli_args.append("--")
    cli_args.append(function)
    cli_args.extend(args)

    result = subprocess.run(
        cli_args,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise SorobanClientError(
            f"stellar CLI failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


class SorobanClientError(Exception):
    """Raised when the Soroban contract interaction fails."""


@dataclass(frozen=True)
class OnChainCommitment:
    """A commitment retrieved from the Soroban contract."""
    reference: str
    commitment_hash: str
    committer: str
    ledger: int
    timestamp: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OnChainCommitment":
        return cls(
            reference=d.get("reference", ""),
            commitment_hash=d.get("commitment_hash", ""),
            committer=d.get("committer", ""),
            ledger=int(d.get("ledger", 0)),
            timestamp=int(d.get("timestamp", 0)),
        )


@dataclass(frozen=True)
class OnChainReceipt:
    """A receipt retrieved from the Soroban contract."""
    transaction_hash: str
    seal: str
    verdict: str
    ledger: int
    timestamp: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OnChainReceipt":
        return cls(
            transaction_hash=d.get("transaction_hash", ""),
            seal=d.get("seal", ""),
            verdict=d.get("verdict", ""),
            ledger=int(d.get("ledger", 0)),
            timestamp=int(d.get("timestamp", 0)),
        )


def register_commitment(
    committer: str,
    reference: str,
    commitment_hash: str,
) -> OnChainCommitment:
    """Register a commitment on the Soroban contract.

    Args:
        committer: The address of the committer (must authorize).
        reference: The reference string (e.g. invoice number).
        commitment_hash: The SHA-256 commitment hash (hex string).

    Returns:
        The on-chain commitment record.
    """
    output = _invoke(
        "register_commitment",
        "--committer", committer,
        "--reference", reference,
        "--commitment_hash", commitment_hash,
    )
    if not output or output == "null":
        raise SorobanClientError("contract returned null for register_commitment")
    return OnChainCommitment.from_dict(json.loads(output))


def get_commitment(reference: str) -> OnChainCommitment | None:
    """Retrieve a commitment from the Soroban contract.

    Returns None if no commitment exists for the reference.
    """
    output = _invoke(
        "get_commitment",
        "--reference", reference,
        send=False,
    )
    if not output or output == "null":
        return None
    return OnChainCommitment.from_dict(json.loads(output))


def register_receipt(
    registrar: str,
    transaction_hash: str,
    seal: str,
    verdict: str,
) -> OnChainReceipt:
    """Register a receipt on the Soroban contract.

    Args:
        registrar: The address of the registrar (must authorize).
        transaction_hash: The verified transaction hash.
        seal: The SHA-256 seal of the evidence bundle (hex string).
        verdict: The verdict string (e.g. "VERIFIED").

    Returns:
        The on-chain receipt record.
    """
    output = _invoke(
        "register_receipt",
        "--registrar", registrar,
        "--transaction_hash", transaction_hash,
        "--seal", seal,
        "--verdict", verdict,
    )
    if not output or output == "null":
        raise SorobanClientError("contract returned null for register_receipt")
    return OnChainReceipt.from_dict(json.loads(output))


def get_receipt(transaction_hash: str) -> OnChainReceipt | None:
    """Retrieve a receipt from the Soroban contract.

    Returns None if no receipt exists for the transaction hash.
    """
    output = _invoke(
        "get_receipt",
        "--transaction_hash", transaction_hash,
        send=False,
    )
    if not output or output == "null":
        return None
    return OnChainReceipt.from_dict(json.loads(output))


def verify_temporal_order(reference: str, transaction_hash: str) -> int:
    """Verify temporal order on-chain.

    Returns:
        0: commitment does not exist
        1: receipt does not exist
        2: commitment was registered after or at the same ledger as the receipt
        3: commitment was registered before the receipt (success)
    """
    output = _invoke(
        "verify_temporal_order",
        "--reference", reference,
        "--transaction_hash", transaction_hash,
        send=False,
    )
    try:
        return int(output)
    except ValueError:
        raise SorobanClientError(f"unexpected temporal order result: {output!r}")


def list_commitments() -> list[str]:
    """List all commitment references on the contract."""
    output = _invoke("list_commitments", send=False)
    if not output or output == "null":
        return []
    return json.loads(output)


def list_receipts() -> list[str]:
    """List all receipt transaction hashes on the contract."""
    output = _invoke("list_receipts", send=False)
    if not output or output == "null":
        return []
    return json.loads(output)
