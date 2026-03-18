"""XAP MCP Server — Model Context Protocol server for XAP agent commerce."""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from xap.integrations.base import XAPIntegrationBase

app = Server("xap-mcp")
_base: XAPIntegrationBase | None = None

def get_base() -> XAPIntegrationBase:
    global _base
    if _base is None:
        _base = XAPIntegrationBase.sandbox(balance=1_000_000)
    return _base

def _tool_schemas() -> list[Tool]:
    """Return the 7 XAP tool definitions."""
    return [
        Tool(
            name="xap_discover_agents",
            description="Search the XAP registry for agents by capability. Returns agents ranked by composite score with Verity-backed attestation data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "description": "The capability to search for (e.g., 'code_review', 'text_summarization')",
                    },
                    "min_success_rate_bps": {
                        "type": "integer",
                        "description": "Minimum success rate in basis points (0-10000). 9000 = 90%. Default 0.",
                        "default": 0,
                    },
                    "max_price_minor": {
                        "type": "integer",
                        "description": "Maximum price in minor units (e.g., 1000 = $10.00 USD). No limit if omitted.",
                    },
                    "currency": {
                        "type": "string",
                        "description": "ISO 4217 currency code filter. Default: USD.",
                        "default": "USD",
                    },
                    "condition_type": {
                        "type": "string",
                        "enum": ["deterministic", "probabilistic", "human_approval"],
                        "description": "Filter by accepted condition type.",
                    },
                    "include_manifest": {
                        "type": "boolean",
                        "description": "Include full AgentManifest in results. Default false.",
                        "default": False,
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of results to return (1-100). Default 10.",
                        "default": 10,
                    },
                },
                "required": ["capability"],
            },
        ),
        Tool(
            name="xap_verify_manifest",
            description="Verify an agent's manifest (Ed25519 signature + expiry). Call after xap_discover_agents, before xap_create_offer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "manifest": {
                        "type": "object",
                        "description": "The agent manifest object (from xap_discover_agents with include_manifest=true)",
                    },
                },
                "required": ["manifest"],
            },
        ),
        Tool(
            name="xap_create_offer",
            description="Create a negotiation offer to an agent for a specific capability.",
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
            description="Accept, reject, or counter a negotiation offer.",
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
                        "description": "New amount for counter-offer (if action is 'counter')",
                    },
                },
                "required": ["contract_id", "action"],
            },
        ),
        Tool(
            name="xap_settle",
            description="Execute settlement from accepted negotiation. Locks funds, verifies, releases.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "The accepted negotiation contract ID",
                    },
                    "payee_shares": {
                        "type": "array",
                        "description": "Optional split: [{agent_id, share_bps}]. Default: 100% to provider.",
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
            description="Verify that a settlement receipt is deterministically replayable.",
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
            description="Check an agent's balance in the settlement adapter.",
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
_contracts: dict[str, dict] = {}; _verity_receipts: dict[str, dict] = {}

def _store_contract(contract: dict) -> None:
    _contracts[contract["negotiation_id"]] = contract

def _get_contract(contract_id: str) -> dict:
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
            include_mf = arguments.get("include_manifest", False)
            result = base.discover(
                capability=arguments["capability"],
                min_success_rate_bps=arguments.get("min_success_rate_bps", 0),
                max_price_minor=arguments.get("max_price_minor"),
                currency=arguments.get("currency"),
                condition_type=arguments.get("condition_type"),
                include_manifest=include_mf,
                page_size=arguments.get("page_size", 10),
                min_reputation=arguments.get("min_reputation", 0),
            )
            if include_mf and isinstance(result, dict):
                for r in result.get("results", []):
                    if m := r.get("manifest"):
                        att = m.get("capabilities", [{}])[0].get("attestation", {})
                        r["receipt_hashes_available"] = len(att.get("receipt_hashes", []))
                        r["verification_endpoint"] = att.get("verification_endpoint")
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "xap_verify_manifest":
            from xap.verify import verify_manifest
            manifest = arguments["manifest"]
            v = verify_manifest(manifest)
            att = manifest.get("capabilities", [{}])[0].get("attestation", {})
            verdict = {
                "verified": v.valid, "schema_valid": v.schema_valid,
                "signature_valid": v.signature_valid, "not_expired": v.not_expired,
                "claimed_success_rate": f"{att.get('success_rate_bps', 0) / 100:.1f}%",
                "total_settlements": att.get("total_settlements", 0),
                "errors": v.errors,
                "recommendation": "TRUST — valid" if v.valid else "DO_NOT_TRUST — verification failed",
            }
            return [TextContent(type="text", text=json.dumps(verdict, indent=2))]

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
            result = base.respond_to_offer(contract, arguments["action"], new_amount=arguments.get("counter_amount"))
            _store_contract(result)
            return [TextContent(type="text", text=json.dumps(
                {"negotiation_id": result["negotiation_id"], "state": result["state"], "contract": result},
                indent=2, default=str))]

        elif name == "xap_settle":
            contract = _get_contract(arguments["contract_id"])
            result = await base.settle_async(contract, payee_shares=arguments.get("payee_shares"))
            if "verity_receipt" in result:
                _verity_receipts[result["verity_id"]] = result["verity_receipt"]
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "xap_verify_receipt":
            rid = arguments["receipt_id"]
            if rid not in _verity_receipts:
                return [TextContent(type="text", text=json.dumps({"error": f"Verity receipt not found: {rid}"}))]
            return [TextContent(type="text", text=json.dumps({"verified": base.verify(_verity_receipts[rid])}))]

        elif name == "xap_check_balance":
            return [TextContent(type="text", text=json.dumps(
                {"balance": base.check_balance(arguments.get("agent_id"))}))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

def main_cli():
    import asyncio
    asyncio.run(main())

if __name__ == "__main__":
    main_cli()
