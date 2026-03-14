"""
MCP Server Demo
===============
Demonstrates the XAP MCP server tools.

This example shows how the MCP server tools work by calling them directly.
In practice, these tools are invoked by MCP clients like Claude or Cursor.

To run the actual MCP server:
    python -m xap.mcp.server

To configure for Claude Code:
    python -m xap.mcp.setup --code

To configure for Claude Desktop:
    python -m xap.mcp.setup --desktop
"""

import asyncio
import json

from xap import XAPClient
from xap.mcp.server import call_tool, get_base, _store_contract, _contracts


async def main():
    # Setup: register a provider agent
    base = get_base()
    provider = XAPClient.sandbox(balance=0)
    provider.adapter = base.client.adapter
    provider_identity = provider.identity(
        display_name="DataAnalyzerBot",
        capabilities=[{
            "name": "data_analysis",
            "version": "1.0.0",
            "pricing": {"model": "fixed", "amount_minor_units": 1000, "currency": "USD", "per": "request"},
            "sla": {"max_latency_ms": 5000, "availability_bps": 9900},
        }],
    )
    base.client.discovery.register(provider_identity)
    provider.discovery._registry = base.client.discovery._registry

    print("=== XAP MCP Server Demo ===\n")

    # 1. Discover agents
    print("1. Discovering agents with 'data_analysis' capability...")
    result = await call_tool("xap_discover_agents", {"capability": "data_analysis"})
    data = json.loads(result[0].text)
    print(f"   Found {len(data['results'])} agent(s): {data['results'][0]['display_name']}")

    # 2. Create offer
    print("\n2. Creating offer for $10.00...")
    result = await call_tool("xap_create_offer", {
        "agent_id": str(provider.agent_id),
        "capability": "data_analysis",
        "amount": 1000,
    })
    offer = json.loads(result[0].text)
    contract_id = offer["negotiation_id"]
    print(f"   Offer created: {contract_id} (state: {offer['state']})")

    # 3. Accept offer (provider side)
    print("\n3. Provider accepts the offer...")
    contract = _contracts[contract_id]
    accepted = provider.negotiation.accept(contract)
    _store_contract(accepted)
    print(f"   Contract state: {accepted['state']}")

    # 4. Settle
    print("\n4. Settling payment...")
    result = await call_tool("xap_settle", {"contract_id": contract_id})
    settlement = json.loads(result[0].text)
    print(f"   Outcome: {settlement['outcome']}")
    print(f"   Receipt: {settlement['receipt_id']}")
    print(f"   Replay verified: {settlement['replay_verified']}")
    print(f"   Total paid: ${settlement['total_paid'] / 100:.2f}")

    # 5. Check balance
    print("\n5. Checking balance...")
    result = await call_tool("xap_check_balance", {})
    balance = json.loads(result[0].text)
    print(f"   Balance: ${balance['balance'] / 100:.2f}")

    print("\n=== Demo complete ===")


if __name__ == "__main__":
    asyncio.run(main())
