"""Tests for XAP MCP server tool definitions and execution."""

import json
import pytest

from xap import XAPClient
from xap.mcp.server import (
    _tool_schemas,
    call_tool,
    get_base,
    _contracts,
    _verity_receipts,
    _store_contract,
    _base,
)
import xap.mcp.server as mcp_server


@pytest.fixture(autouse=True)
def _reset_mcp_state():
    """Reset MCP server state between tests."""
    mcp_server._base = None
    _contracts.clear()
    _verity_receipts.clear()
    yield
    mcp_server._base = None
    _contracts.clear()
    _verity_receipts.clear()


def _setup_provider():
    """Create a base with a registered provider and return (base, provider)."""
    base = get_base()
    provider = XAPClient.sandbox(balance=0)
    provider.adapter = base.client.adapter
    provider_identity = provider.identity(
        display_name="MCPTestBot",
        capabilities=[{
            "name": "text_summarization",
            "version": "1.0.0",
            "pricing": {"model": "fixed", "amount_minor_units": 500, "currency": "USD", "per": "request"},
            "sla": {"max_latency_ms": 2000, "availability_bps": 9900},
        }],
    )
    base.client.discovery.register(provider_identity)
    provider.discovery._registry = base.client.discovery._registry
    return base, provider


def test_mcp_server_lists_6_tools():
    """Server exposes exactly 6 tools."""
    tools = _tool_schemas()
    assert len(tools) == 6


def test_mcp_tool_names():
    """All 6 expected tool names are present."""
    tools = _tool_schemas()
    names = {t.name for t in tools}
    expected = {
        "xap_discover_agents",
        "xap_create_offer",
        "xap_respond_to_offer",
        "xap_settle",
        "xap_verify_receipt",
        "xap_check_balance",
    }
    assert names == expected


def test_mcp_tools_have_input_schemas():
    """Each tool has an inputSchema with type 'object'."""
    tools = _tool_schemas()
    for tool in tools:
        assert tool.inputSchema["type"] == "object"
        assert "properties" in tool.inputSchema


@pytest.mark.asyncio
async def test_mcp_discover_agents():
    """xap_discover_agents returns results."""
    _setup_provider()
    result = await call_tool("xap_discover_agents", {"capability": "text_summarization"})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert len(data["results"]) == 1
    assert data["results"][0]["display_name"] == "MCPTestBot"


@pytest.mark.asyncio
async def test_mcp_discover_no_results():
    """xap_discover_agents returns empty for unknown capability."""
    get_base()
    result = await call_tool("xap_discover_agents", {"capability": "nonexistent"})
    data = json.loads(result[0].text)
    assert len(data["results"]) == 0


@pytest.mark.asyncio
async def test_mcp_create_offer():
    """xap_create_offer creates a valid contract."""
    base, provider = _setup_provider()
    result = await call_tool("xap_create_offer", {
        "agent_id": str(provider.agent_id),
        "capability": "text_summarization",
        "amount": 500,
    })
    data = json.loads(result[0].text)
    assert data["state"] == "OFFER"
    assert data["amount"] == 500
    assert "negotiation_id" in data


@pytest.mark.asyncio
async def test_mcp_respond_to_offer_accept():
    """xap_respond_to_offer can accept an offer."""
    base, provider = _setup_provider()
    # Create offer
    offer_result = await call_tool("xap_create_offer", {
        "agent_id": str(provider.agent_id),
        "capability": "text_summarization",
        "amount": 500,
    })
    offer_data = json.loads(offer_result[0].text)
    contract_id = offer_data["negotiation_id"]

    # Accept
    result = await call_tool("xap_respond_to_offer", {
        "contract_id": contract_id,
        "action": "accept",
    })
    data = json.loads(result[0].text)
    assert data["state"] == "ACCEPT"


@pytest.mark.asyncio
async def test_mcp_respond_to_offer_counter():
    """xap_respond_to_offer can counter with new amount."""
    base, provider = _setup_provider()
    offer_result = await call_tool("xap_create_offer", {
        "agent_id": str(provider.agent_id),
        "capability": "text_summarization",
        "amount": 500,
    })
    offer_data = json.loads(offer_result[0].text)

    result = await call_tool("xap_respond_to_offer", {
        "contract_id": offer_data["negotiation_id"],
        "action": "counter",
        "counter_amount": 700,
    })
    data = json.loads(result[0].text)
    assert data["state"] == "COUNTER"


@pytest.mark.asyncio
async def test_mcp_check_balance():
    """xap_check_balance returns balance."""
    get_base()
    result = await call_tool("xap_check_balance", {})
    data = json.loads(result[0].text)
    assert data["balance"] == 1_000_000


@pytest.mark.asyncio
async def test_mcp_full_flow():
    """discover -> offer -> accept -> settle -> verify via MCP tools."""
    base, provider = _setup_provider()

    # Discover
    disc_result = await call_tool("xap_discover_agents", {"capability": "text_summarization"})
    disc_data = json.loads(disc_result[0].text)
    assert len(disc_data["results"]) >= 1

    # Create offer
    offer_result = await call_tool("xap_create_offer", {
        "agent_id": str(provider.agent_id),
        "capability": "text_summarization",
        "amount": 500,
    })
    offer_data = json.loads(offer_result[0].text)
    contract_id = offer_data["negotiation_id"]

    # Accept (provider side — need to accept via provider client, then store)
    contract = _contracts[contract_id]
    accepted = provider.negotiation.accept(contract)
    _store_contract(accepted)

    # Settle
    settle_result = await call_tool("xap_settle", {"contract_id": contract_id})
    settle_data = json.loads(settle_result[0].text)
    assert settle_data["outcome"] == "SETTLED"
    assert settle_data["replay_verified"] is True
    assert settle_data["total_paid"] == 500

    # Check balance after settlement
    bal_result = await call_tool("xap_check_balance", {})
    bal_data = json.loads(bal_result[0].text)
    assert bal_data["balance"] == 1_000_000 - 500


@pytest.mark.asyncio
async def test_mcp_invalid_tool():
    """Unknown tool returns error, not crash."""
    get_base()
    result = await call_tool("nonexistent_tool", {})
    data = json.loads(result[0].text)
    assert "error" in data


@pytest.mark.asyncio
async def test_mcp_invalid_contract_id():
    """Invalid contract_id returns error."""
    get_base()
    result = await call_tool("xap_respond_to_offer", {
        "contract_id": "invalid_id",
        "action": "accept",
    })
    data = json.loads(result[0].text)
    assert "error" in data


@pytest.mark.asyncio
async def test_mcp_invalid_receipt_id():
    """Invalid receipt_id returns error."""
    get_base()
    result = await call_tool("xap_verify_receipt", {"receipt_id": "invalid_id"})
    data = json.loads(result[0].text)
    assert "error" in data
