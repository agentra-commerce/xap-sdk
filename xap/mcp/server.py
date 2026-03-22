"""XAP MCP Server — Model Context Protocol server for XAP agent commerce."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import OrderedDict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from xap.integrations.base import XAPIntegrationBase

logger = logging.getLogger(__name__)

XAP_MODE    = os.environ.get("XAP_MODE", "sandbox")    # "sandbox" or "live"
XAP_API_KEY = os.environ.get("XAP_API_KEY", "")         # required for live
XAP_API_URL = os.environ.get("XAP_API_URL",             # override for local dev
                "https://api.zexrail.com")


class BoundedCache:
    """Bounded cache with TTL expiry to prevent unbounded memory growth."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def set(self, key: str, value: object) -> None:
        self._cleanup()
        if key in self._cache:
            del self._cache[key]
        elif len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
        self._cache[key] = (time.time(), value)

    def get(self, key: str) -> object | None:
        self._cleanup()
        if key in self._cache:
            return self._cache[key][1]
        return None

    def __contains__(self, key: str) -> bool:
        self._cleanup()
        return key in self._cache

    def __getitem__(self, key: str) -> object:
        self._cleanup()
        if key in self._cache:
            return self._cache[key][1]
        raise KeyError(key)

    def __setitem__(self, key: str, value: object) -> None:
        self.set(key, value)

    def _cleanup(self) -> None:
        now = time.time()
        expired = [k for k, (t, _) in self._cache.items() if now - t > self._ttl]
        for k in expired:
            del self._cache[k]

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        self._cleanup()
        return len(self._cache)


app = Server("xap-mcp")
_base: XAPIntegrationBase | None = None

def get_base() -> XAPIntegrationBase:
    global _base
    if _base is None:
        _base = XAPIntegrationBase.sandbox(balance=1_000_000)
    return _base

def _tool_schemas() -> list[Tool]:
    """Return the 8 XAP tool definitions."""
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
            description="Verify an agent's trust credential (AgentManifest) by cryptographically replaying Verity receipts. Returns: signature validity, expiry status, TSA-anchored count, policy-verified count, attested condition count, and a TRUST/VERIFY_MANUALLY/DO_NOT_TRUST recommendation.",
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
        Tool(
            name="xap_verify_workflow",
            description="Verify the complete causal chain of a multi-agent workflow. Checks that every receipt in the workflow is valid, replayed correctly, and causally linked.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "The workflow ID (wf_[8 hex]) from any receipt in the chain",
                    },
                },
                "required": ["workflow_id"],
            },
        ),
    ]


# Store contracts by negotiation_id for MCP tool lookup (bounded to prevent memory leaks)
_contracts: BoundedCache = BoundedCache(max_size=1000, ttl_seconds=3600)
_verity_receipts: BoundedCache = BoundedCache(max_size=1000, ttl_seconds=3600)

def _store_contract(contract: dict) -> None:
    _contracts.set(contract["negotiation_id"], contract)

def _get_contract(contract_id: str) -> dict:
    contract = _contracts.get(contract_id)
    if contract is None:
        raise KeyError(f"Contract not found: {contract_id}")
    return contract


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
            from xap.verify import verify_manifest, verify_manifest_full
            manifest = arguments["manifest"]
            v = verify_manifest(manifest)
            att = manifest.get("capabilities", [{}])[0].get("attestation", {})

            # Attempt full verification with gap fields if basic checks pass
            tsa_anchored = 0
            policy_verified = 0
            attested_conditions = 0
            receipts_replayed = 0
            replay_confirmed = 0
            full_recommendation = None
            full_warnings = []

            if v.valid:
                try:
                    mv = await verify_manifest_full(manifest, sample_receipts=3)
                    tsa_anchored = mv.tsa_anchored_count
                    policy_verified = mv.policy_verified_count
                    attested_conditions = mv.attested_conditions
                    receipts_replayed = mv.receipts_checked
                    replay_confirmed = mv.replay_confirmed
                    if mv.receipts_checked > 0:
                        full_recommendation = mv.recommendation
                    full_warnings = mv.warnings
                except (ConnectionError, TimeoutError, ValueError, KeyError, AttributeError, TypeError) as ve:
                    logger.debug("Full manifest verification skipped: %s(%s)", type(ve).__name__, ve)

            verdict = {
                "verified": v.valid, "schema_valid": v.schema_valid,
                "signature_valid": v.signature_valid, "not_expired": v.not_expired,
                "claimed_success_rate": f"{att.get('success_rate_bps', 0) / 100:.1f}%",
                "total_settlements": att.get("total_settlements", 0),
                "receipts_replayed": receipts_replayed,
                "replay_confirmed": replay_confirmed,
                "tsa_anchored": tsa_anchored,
                "policy_verified": policy_verified,
                "attested_conditions": attested_conditions,
                "errors": v.errors,
                "warnings": full_warnings,
                "recommendation": full_recommendation or (
                    "TRUST — valid" if v.valid else "DO_NOT_TRUST — verification failed"
                ),
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
                _verity_receipts.set(result["verity_id"], result["verity_receipt"])
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "xap_verify_receipt":
            rid = arguments["receipt_id"]
            receipt = _verity_receipts.get(rid)
            if receipt is None:
                return [TextContent(type="text", text=json.dumps({"error": f"Verity receipt not found: {rid}"}))]
            return [TextContent(type="text", text=json.dumps({"verified": base.verify(receipt)}))]

        elif name == "xap_check_balance":
            return [TextContent(type="text", text=json.dumps(
                {"balance": base.check_balance(arguments.get("agent_id"))}))]

        elif name == "xap_verify_workflow":
            from xap.clients.workflow import WorkflowClient
            wf_client = WorkflowClient()
            try:
                result = await wf_client.verify_workflow(arguments["workflow_id"])
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except (ConnectionError, TimeoutError) as e:
                return [TextContent(type="text", text=json.dumps({"error": f"Network error: {e}"}))]
            except (ValueError, KeyError) as e:
                return [TextContent(type="text", text=json.dumps({"error": f"Invalid workflow data: {e}"}))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        logger.error("Tool error in %s: %s(%s)", name, type(e).__name__, e)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    except (ConnectionError, TimeoutError, OSError) as e:
        logger.error("Network error in %s: %s(%s)", name, type(e).__name__, e)
        return [TextContent(type="text", text=json.dumps({"error": f"Service unavailable: {e}"}))]


async def main():
    print(f"[xap-mcp] Mode: {XAP_MODE}", file=sys.stderr)
    if XAP_MODE == "live" and not XAP_API_KEY:
        print("[xap-mcp] Warning: XAP_MODE=live but XAP_API_KEY not set", file=sys.stderr)
        print("[xap-mcp] Get your API key at https://zexrail.com/login", file=sys.stderr)
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

def main_cli():
    import asyncio
    asyncio.run(main())

if __name__ == "__main__":
    main_cli()
