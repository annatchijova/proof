"""
test_mcp_server.py — Tests for the L6 MCP server.

Tests that the MCP server exposes the correct tools and that tool
calls are routed correctly. We test the tool handlers directly
rather than over stdio to avoid subprocess complexity.
"""
import asyncio
import json

import pytest

from proof.mcp_server import _handle_call_tool as call_tool
from proof.mcp_server import _handle_list_tools as list_tools


class _MockParams:
    """Mock params object for call_tool."""
    def __init__(self, name, arguments=None):
        self.name = name
        self.arguments = arguments


@pytest.mark.asyncio
async def test_list_tools_returns_eight_tools():
    """Invariant: the MCP server exposes exactly eight tools.

    Mutation caught: if a tool were removed or renamed, the count
    or names would change.
    """
    result = await list_tools(ctx=None)
    tool_names = [t.name for t in result.tools]
    assert "verify_payment" in tool_names
    assert "verify_dispute" in tool_names
    assert "issue_receipt" in tool_names
    assert "compute_commitment_hash" in tool_names
    assert "register_commitment" in tool_names
    assert "get_onchain_commitment" in tool_names
    assert "register_onchain_receipt" in tool_names
    assert "get_onchain_receipt" in tool_names
    assert len(tool_names) == 8


@pytest.mark.asyncio
async def test_compute_commitment_hash_tool():
    """Invariant: the compute_commitment_hash tool returns a 64-char hash."""
    params = _MockParams("compute_commitment_hash", {
        "sender": "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z",
        "recipient": "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z",
        "asset_code": "XLM",
        "amount_stroops": 1000000000,
    })
    result = await call_tool(ctx=None, params=params)
    assert not result.is_error
    text = result.content[0].text
    data = json.loads(text)
    assert "commitment_hash" in data
    assert len(data["commitment_hash"]) == 64


@pytest.mark.asyncio
async def test_unknown_tool_returns_error():
    """Invariant: an unknown tool name returns an error result."""
    params = _MockParams("nonexistent_tool", {})
    result = await call_tool(ctx=None, params=params)
    assert result.is_error


@pytest.mark.asyncio
async def test_verify_payment_with_invalid_hash_returns_error():
    """Invariant: an invalid transaction hash returns an error result.

    Mutation caught: if the MCP server didn't validate, an invalid
    hash would reach the engine and produce a confusing error.
    """
    params = _MockParams("verify_payment", {
        "transaction_hash": "invalid",
        "network": "testnet",
    })
    result = await call_tool(ctx=None, params=params)
    assert result.is_error


@pytest.mark.asyncio
async def test_compute_commitment_hash_deterministic():
    """Invariant: same inputs produce the same commitment hash via MCP."""
    args = {
        "sender": "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z",
        "recipient": "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z",
        "asset_code": "USDC",
        "asset_issuer": "GBXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z",
        "amount_stroops": 5000000,
        "reference": "INV-184",
    }
    result_a = await call_tool(ctx=None, params=_MockParams("compute_commitment_hash", args))
    result_b = await call_tool(ctx=None, params=_MockParams("compute_commitment_hash", args))
    hash_a = json.loads(result_a.content[0].text)["commitment_hash"]
    hash_b = json.loads(result_b.content[0].text)["commitment_hash"]
    assert hash_a == hash_b
