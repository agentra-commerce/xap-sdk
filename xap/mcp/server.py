"""
XAP MCP Server
==============
Model Context Protocol server for XAP agent commerce.

Allows any MCP-compatible AI (Claude, Cursor, etc.) to:
- Discover agents by capability
- Create negotiation offers
- Accept/reject/counter offers
- Execute settlements
- Verify receipts via replay
- Check balances

Run directly:
    python -m xap.mcp.server

Or configure in Claude Desktop / Claude Code:
    python -m xap.mcp.setup

Requires: pip install xap-sdk[mcp]
"""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from xap.integrations.base import XAPIntegrationBase

app = Server("xap-mcp")

_base: XAPIntegrationBase | None = None


def get_base() -> XAPIntegrationBase:
    """Get or create the XAP integration base (sandbox by default)."""
    global _base
    if _base is None:
        _base = XAPIntegrationBase.sandbox(balance=1_000_000)
    return _base


def _tool_schemas() -> list[Tool]:
    """Return the 6 XAP tool definitions."""
    return [
        Tool(
            name="xap_discover_agents",
            description="Search the XAP registry for agents with specific capabilities. Returns matching agents with IDs, capabilities, pricing, and reputation scores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "description": "The capability to search for (e.g., 'data_analysis', 'payment.process')",
                    },
                    "min_reputation": {
                        "type": "integer",
                        "description": "Minimum reputation in basis points (0-10000). Default 0.",
                        "default": 0,
                    },
                },
                "required": ["capability"],
            },
        ),
        Tool(
            name="xap_create_offer",
            description="Create a negotiation offer to an agent for a specific service. The offer includes amount, capability requested, and optional conditions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The agent ID to send the offer to",
                    },
                    "capability": {
                        "type": "string",
                        "description": "The capability being requested",
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Amount in minor units (e.g., 1000 = $10.00 USD)",
                    },
                    "currency": {
                        "type": "string",
                        "description": "ISO 4217 currency code. Default USD.",
                        "default": "USD",
                    },
                },
                "required": ["agent_id", "capability", "amount"],
            },
        ),
        Tool(
            name="xap_respond_to_offer",
            description="Accept, reject, or counter a negotiation offer. For counter-offers, provide new terms.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "The negotiation contract ID",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["accept", "reject", "counter"],
                        "description": "The response action",
                    },
                    "counter_amount": {
                        "type": "integer",
                        "description": "New amount for counter-offer (required if action is 'counter')",
                    },
                },
                "required": ["contract_id", "action"],
            },
        ),
        Tool(
            name="xap_settle",
            description="Execute a settlement from an accepted negotiation. Locks funds, verifies conditions, releases payment, and produces a cryptographically verifiable receipt.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "The accepted negotiation contract ID",
                    },
                    "payee_shares": {
                        "type": "array",
                        "description": "Optional split: array of {agent_id, share_bps}. Default: 100% to provider.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "agent_id": {"type": "string"},
                                "share_bps": {"type": "integer"},
                            },
                        },
                    },
                },
                "required": ["contract_id"],
            },
        ),
        Tool(
            name="xap_verify_receipt",
            description="Verify that a settlement receipt is deterministically replayable. Returns whether the replay hash matches the original execution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "receipt_id": {
                        "type": "string",
                        "description": "The verity receipt ID to verify",
                    },
                },
                "required": ["receipt_id"],
            },
        ),
        Tool(
            name="xap_check_balance",
            description="Check the current balance of an agent in the settlement adapter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "Agent ID to check. Default: current agent.",
                    },
                },
                "required": [],
            },
        ),
    ]


# Store contracts by negotiation_id for MCP tool lookup
_contracts: dict[str, dict] = {}
_verity_receipts: dict[str, dict] = {}


def _store_contract(contract: dict) -> None:
    """Store a contract for later retrieval by negotiation_id."""
    _contracts[contract["negotiation_id"]] = contract


def _get_contract(contract_id: str) -> dict:
    """Retrieve a stored contract by negotiation_id."""
    if contract_id not in _contracts:
        raise ValueError(f"Contract not found: {contract_id}")
    return _contracts[contract_id]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return _tool_schemas()


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    base = get_base()

    try:
        if name == "xap_discover_agents":
            result = base.discover(
                capability=arguments["capability"],
                min_reputation=arguments.get("min_reputation", 0),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "xap_create_offer":
            contract = base.create_offer(
                agent_id=arguments["agent_id"],
                capability=arguments["capability"],
                amount=arguments["amount"],
            )
            _store_contract(contract)
            return [TextContent(type="text", text=json.dumps({
                "negotiation_id": contract["negotiation_id"],
                "state": contract["state"],
                "amount": contract["pricing"]["amount_minor_units"],
                "currency": contract["pricing"]["currency"],
                "contract": contract,
            }, indent=2, default=str))]

        elif name == "xap_respond_to_offer":
            contract = _get_contract(arguments["contract_id"])
            action = arguments["action"]
            new_amount = arguments.get("counter_amount")
            result = base.respond_to_offer(contract, action, new_amount=new_amount)
            _store_contract(result)
            return [TextContent(type="text", text=json.dumps({
                "negotiation_id": result["negotiation_id"],
                "state": result["state"],
                "contract": result,
            }, indent=2, default=str))]

        elif name == "xap_settle":
            contract = _get_contract(arguments["contract_id"])
            payee_shares = arguments.get("payee_shares")
            result = await base.settle_async(contract, payee_shares=payee_shares)
            if "verity_receipt" in result:
                _verity_receipts[result["verity_id"]] = result["verity_receipt"]
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "xap_verify_receipt":
            receipt_id = arguments["receipt_id"]
            if receipt_id not in _verity_receipts:
                return [TextContent(type="text", text=json.dumps({
                    "error": f"Verity receipt not found: {receipt_id}",
                }))]
            valid = base.verify(_verity_receipts[receipt_id])
            return [TextContent(type="text", text=json.dumps({"verified": valid}))]

        elif name == "xap_check_balance":
            agent_id = arguments.get("agent_id") or None
            balance = base.check_balance(agent_id)
            return [TextContent(type="text", text=json.dumps({"balance": balance}))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    """Run the MCP server over stdio."""
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


def main_cli():
    """CLI entry point for xap-mcp command."""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    main_cli()
