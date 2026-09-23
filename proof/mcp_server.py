"""
mcp_server.py — MCP (Model Context Protocol) server for PROOF.

Exposes PROOF's verification capabilities as MCP tools so AI agents
can verify Stellar payment claims without running the full pipeline.

Tools:
  verify_payment           — verify a single payment claim
  verify_dispute            — verify a dispute between two claims
  issue_receipt             — issue a receipt from a verified bundle
  compute_commitment_hash   — compute a commitment hash from payment terms
  register_commitment       — register a commitment on the Soroban contract
  get_onchain_commitment    — retrieve a commitment from the Soroban contract
  register_onchain_receipt  — register a receipt on the Soroban contract
  get_onchain_receipt       — retrieve a receipt from the Soroban contract

The MCP server is a thin transport layer. All logic lives in the
deterministic core. The server never modifies verdicts, seals, or evidence.

Run with:
  python -m proof.mcp_server
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)

from .claim import PaymentClaim
from .commitment import compute_commitment_hash
from .engine import issue_receipt, verify_dispute, verify_payment
from .evidence import EvidenceBundle


def _tool_definitions() -> list[Tool]:
    """Return the tool definitions PROOF exposes via MCP."""
    return [
        Tool(
            name="verify_payment",
            description=(
                "Verify a Stellar payment claim against the ledger. Returns a "
                "sealed evidence bundle with the verdict (VERIFIED, NOT_VERIFIED, "
                "or INSUFFICIENT_EVIDENCE), checks, and SHA-256 seal."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "transaction_hash": {
                        "type": "string",
                        "description": "64-char hex Stellar transaction hash",
                    },
                    "sender": {"type": "string", "description": "Expected sender address (G...)"},
                    "recipient": {"type": "string", "description": "Expected recipient address (G...)"},
                    "asset_code": {"type": "string", "description": "Expected asset code (e.g. USDC)"},
                    "asset_issuer": {"type": "string", "description": "Expected asset issuer address"},
                    "amount_stroops": {"type": "integer", "description": "Expected amount in stroops"},
                    "reference": {"type": "string", "description": "Expected reference/memo"},
                    "ledger_min": {"type": "integer", "description": "Minimum ledger sequence"},
                    "ledger_max": {"type": "integer", "description": "Maximum ledger sequence"},
                    "commitment_tx_hash": {"type": "string", "description": "Transaction hash of an on-chain commitment"},
                    "network": {
                        "type": "string",
                        "enum": ["testnet", "mainnet"],
                        "default": "testnet",
                        "description": "Stellar network",
                    },
                },
                "required": ["transaction_hash"],
            },
        ),
        Tool(
            name="verify_dispute",
            description=(
                "Verify a dispute between two contradictory payment claims. "
                "Each claim is verified independently, then the evidence sets "
                "are compared for contradictions. Returns a DisputeResult."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "claim_a": {
                        "type": "object",
                        "description": "First payment claim",
                        "properties": {
                            "transaction_hash": {"type": "string"},
                            "sender": {"type": "string"},
                            "recipient": {"type": "string"},
                            "asset_code": {"type": "string"},
                            "asset_issuer": {"type": "string"},
                            "amount_stroops": {"type": "integer"},
                            "reference": {"type": "string"},
                            "ledger_min": {"type": "integer"},
                            "ledger_max": {"type": "integer"},
                            "commitment_tx_hash": {"type": "string"},
                        },
                        "required": ["transaction_hash"],
                    },
                    "claim_b": {
                        "type": "object",
                        "description": "Second payment claim",
                        "properties": {
                            "transaction_hash": {"type": "string"},
                            "sender": {"type": "string"},
                            "recipient": {"type": "string"},
                            "asset_code": {"type": "string"},
                            "asset_issuer": {"type": "string"},
                            "amount_stroops": {"type": "integer"},
                            "reference": {"type": "string"},
                            "ledger_min": {"type": "integer"},
                            "ledger_max": {"type": "integer"},
                            "commitment_tx_hash": {"type": "string"},
                        },
                        "required": ["transaction_hash"],
                    },
                    "network": {
                        "type": "string",
                        "enum": ["testnet", "mainnet"],
                        "default": "testnet",
                    },
                },
                "required": ["claim_a", "claim_b"],
            },
        ),
        Tool(
            name="issue_receipt",
            description=(
                "Issue a receipt from a verified evidence bundle. The receipt "
                "contains the transaction hash, verdict, and seal. It can be "
                "registered on-chain via a manage_data operation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "bundle": {
                        "type": "object",
                        "description": "A verified evidence bundle (dict)",
                    },
                },
                "required": ["bundle"],
            },
        ),
        Tool(
            name="compute_commitment_hash",
            description=(
                "Compute a commitment hash from payment terms. This is the "
                "hash that would be registered on-chain (via the Soroban "
                "contract or manage_data) before the payment occurs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sender": {"type": "string", "description": "Sender address (G...)"},
                    "recipient": {"type": "string", "description": "Recipient address (G...)"},
                    "asset_code": {"type": "string", "description": "Asset code (e.g. USDC)"},
                    "asset_issuer": {"type": "string", "description": "Asset issuer address"},
                    "amount_stroops": {"type": "integer", "description": "Amount in stroops"},
                    "reference": {"type": "string", "description": "Reference (e.g. invoice number)"},
                },
                "required": ["sender", "recipient", "asset_code", "amount_stroops"],
            },
        ),
        Tool(
            name="register_commitment",
            description=(
                "Register a commitment on the PROOF Soroban contract on Testnet. "
                "The commitment hash is computed from the payment terms and "
                "registered on-chain. The commitment is immutable — it cannot "
                "be overwritten. Requires the stellar CLI to be installed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "committer": {"type": "string", "description": "Stellar address of the committer (G...)"},
                    "reference": {"type": "string", "description": "Reference string (e.g. invoice number)"},
                    "sender": {"type": "string", "description": "Expected sender address (G...)"},
                    "recipient": {"type": "string", "description": "Expected recipient address (G...)"},
                    "asset_code": {"type": "string", "description": "Asset code (e.g. XLM, USDC)"},
                    "asset_issuer": {"type": "string", "description": "Asset issuer address (omit for XLM)"},
                    "amount_stroops": {"type": "integer", "description": "Amount in stroops"},
                },
                "required": ["committer", "reference", "sender", "recipient", "asset_code", "amount_stroops"],
            },
        ),
        Tool(
            name="get_onchain_commitment",
            description=(
                "Retrieve a commitment from the PROOF Soroban contract by reference. "
                "Returns the commitment hash, committer, ledger, and timestamp."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {"type": "string", "description": "The commitment reference (e.g. invoice number)"},
                },
                "required": ["reference"],
            },
        ),
        Tool(
            name="register_onchain_receipt",
            description=(
                "Register a receipt on the PROOF Soroban contract after verification. "
                "The receipt contains the transaction hash, seal, and verdict. "
                "Requires the stellar CLI to be installed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "bundle": {
                        "type": "object",
                        "description": "A verified evidence bundle (dict)",
                    },
                },
                "required": ["bundle"],
            },
        ),
        Tool(
            name="get_onchain_receipt",
            description=(
                "Retrieve a receipt from the PROOF Soroban contract by transaction hash. "
                "Returns the seal, verdict, ledger, and timestamp."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "transaction_hash": {"type": "string", "description": "64-char hex transaction hash"},
                },
                "required": ["transaction_hash"],
            },
        ),
    ]


def _build_claim(params: dict[str, Any]) -> PaymentClaim:
    """Build a PaymentClaim from tool parameters."""
    return PaymentClaim(
        transaction_hash=params["transaction_hash"],
        sender=params.get("sender"),
        recipient=params.get("recipient"),
        asset_code=params.get("asset_code"),
        asset_issuer=params.get("asset_issuer"),
        amount_stroops=params.get("amount_stroops"),
        reference=params.get("reference"),
        ledger_min=params.get("ledger_min"),
        ledger_max=params.get("ledger_max"),
        commitment_tx_hash=params.get("commitment_tx_hash"),
    )


async def _handle_list_tools(ctx, params=None) -> ListToolsResult:
    """Handle the list_tools request."""
    return ListToolsResult(tools=_tool_definitions())


async def _handle_call_tool(ctx, params) -> CallToolResult:
    """Handle a tool call."""
    name = params.name
    arguments = params.arguments or {}

    try:
        if name == "verify_payment":
            claim = _build_claim(arguments)
            network = arguments.get("network", "testnet")
            bundle = verify_payment(claim, network=network)
            result = bundle.to_dict()

        elif name == "verify_dispute":
            claim_a = _build_claim(arguments["claim_a"])
            claim_b = _build_claim(arguments["claim_b"])
            network = arguments.get("network", "testnet")
            result = verify_dispute(claim_a, claim_b, network=network).to_dict()

        elif name == "issue_receipt":
            bundle_dict = arguments["bundle"]
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
            result = receipt_obj.to_dict()

        elif name == "compute_commitment_hash":
            result = {
                "commitment_hash": compute_commitment_hash(
                    sender=arguments["sender"],
                    recipient=arguments["recipient"],
                    asset_code=arguments["asset_code"],
                    asset_issuer=arguments.get("asset_issuer"),
                    amount_stroops=arguments["amount_stroops"],
                    reference=arguments.get("reference"),
                )
            }

        elif name == "register_commitment":
            from .commitment import CommitmentTerms
            from .soroban_client import register_commitment as _reg_commit

            terms = CommitmentTerms(
                sender=arguments["sender"],
                recipient=arguments["recipient"],
                asset_code=arguments["asset_code"],
                asset_issuer=arguments.get("asset_issuer"),
                amount_stroops=arguments["amount_stroops"],
                reference=arguments["reference"],
            )
            commitment_hash = terms.commitment_hash()
            on_chain = _reg_commit(
                committer=arguments["committer"],
                reference=arguments["reference"],
                commitment_hash=commitment_hash,
            )
            result = {
                "status": "committed",
                "commitment_hash": commitment_hash,
                "on_chain": {
                    "reference": on_chain.reference,
                    "commitment_hash": on_chain.commitment_hash,
                    "committer": on_chain.committer,
                    "ledger": on_chain.ledger,
                    "timestamp": on_chain.timestamp,
                },
            }

        elif name == "get_onchain_commitment":
            from .soroban_client import get_commitment as _get_commit

            on_chain = _get_commit(arguments["reference"])
            if on_chain is None:
                result = {"status": "not_found", "reference": arguments["reference"]}
            else:
                result = {
                    "reference": on_chain.reference,
                    "commitment_hash": on_chain.commitment_hash,
                    "committer": on_chain.committer,
                    "ledger": on_chain.ledger,
                    "timestamp": on_chain.timestamp,
                }

        elif name == "register_onchain_receipt":
            from .soroban_client import register_receipt as _reg_receipt
            import os

            bundle_dict = arguments["bundle"]
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
            tx_hash = bundle_dict.get("claim", {}).get("transaction_hash", "")
            registrar = os.environ.get("PROOF_STELLAR_SOURCE", "alice")
            on_chain = _reg_receipt(
                registrar=registrar,
                transaction_hash=tx_hash,
                seal=bundle.seal,
                verdict=bundle.verdict,
            )
            result = {
                "status": "registered",
                "on_chain": {
                    "transaction_hash": on_chain.transaction_hash,
                    "seal": on_chain.seal,
                    "verdict": on_chain.verdict,
                    "ledger": on_chain.ledger,
                    "timestamp": on_chain.timestamp,
                },
            }

        elif name == "get_onchain_receipt":
            from .soroban_client import get_receipt as _get_receipt

            on_chain = _get_receipt(arguments["transaction_hash"])
            if on_chain is None:
                result = {"status": "not_found", "transaction_hash": arguments["transaction_hash"]}
            else:
                result = {
                    "transaction_hash": on_chain.transaction_hash,
                    "seal": on_chain.seal,
                    "verdict": on_chain.verdict,
                    "ledger": on_chain.ledger,
                    "timestamp": on_chain.timestamp,
                }

        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                is_error=True,
            )

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))],
        )
    except Exception as exc:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {exc}")],
            is_error=True,
        )


# Expose handlers for testing.
list_tools = _handle_list_tools
call_tool = _handle_call_tool


def create_server() -> Server:
    """Create and return the MCP server instance."""
    return Server(
        "proof",
        version="0.4.0",
        on_list_tools=_handle_list_tools,
        on_call_tool=_handle_call_tool,
    )


async def main() -> None:
    """Run the MCP server over stdio."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
