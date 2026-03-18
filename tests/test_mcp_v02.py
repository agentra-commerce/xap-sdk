"""Tests for XAP v0.2 MCP tool updates."""

import json
import pytest

from xap import XAPClient, XAPSigner, AgentManifest
from xap.mcp.server import _tool_schemas, call_tool, get_base, _store_contract
import xap.mcp.server as mcp_server


@pytest.fixture(autouse=True)
def _reset_mcp():
    mcp_server._base = None
    mcp_server._contracts.clear()
    mcp_server._verity_receipts.clear()
    yield
    mcp_server._base = None
    mcp_server._contracts.clear()
    mcp_server._verity_receipts.clear()


class TestDiscoverAgentsV02:
    """xap_discover_agents updated for RegistryQuery."""

    def test_tool_schema_has_min_success_rate_bps(self):
        tools = {t.name: t for t in _tool_schemas()}
        schema = tools["xap_discover_agents"].inputSchema
        assert "min_success_rate_bps" in schema["properties"]

    def test_tool_schema_has_include_manifest(self):
        tools = {t.name: t for t in _tool_schemas()}
        schema = tools["xap_discover_agents"].inputSchema
        assert "include_manifest" in schema["properties"]

    def test_tool_schema_has_page_size(self):
        tools = {t.name: t for t in _tool_schemas()}
        schema = tools["xap_discover_agents"].inputSchema
        assert "page_size" in schema["properties"]

    def test_tool_schema_has_condition_type(self):
        tools = {t.name: t for t in _tool_schemas()}
        schema = tools["xap_discover_agents"].inputSchema
        assert "condition_type" in schema["properties"]

    def test_tool_schema_has_currency(self):
        tools = {t.name: t for t in _tool_schemas()}
        schema = tools["xap_discover_agents"].inputSchema
        assert "currency" in schema["properties"]

    @pytest.mark.asyncio
    async def test_discover_with_include_manifest(self):
        base = get_base()
        provider = XAPClient.sandbox(balance=0)
        provider.adapter = base.client.adapter
        identity = provider.identity(
            display_name="ManifestMCPBot",
            capabilities=[{
                "name": "code_review", "version": "1.0.0",
                "pricing": {"model": "fixed", "amount_minor_units": 500, "currency": "USD", "per": "request"},
                "sla": {"max_latency_ms": 2000, "availability_bps": 9900},
            }],
        )
        manifest = provider.manifest.build(
            capabilities=[{
                "name": "code_review", "version": "1.0.0",
                "attestation": {"total_settlements": 0, "success_rate_bps": 0, "window_days": 90, "receipt_hashes": []},
            }],
            economic_terms={"accepted_currencies": ["USD"], "accepted_condition_types": ["deterministic"],
                            "min_amount_minor": 100, "max_amount_minor": 50000},
        )
        base.client.discovery.register(identity, manifest=manifest)

        result = await call_tool("xap_discover_agents", {
            "capability": "code_review", "include_manifest": True,
        })
        data = json.loads(result[0].text)
        assert len(data["results"]) == 1
        assert "manifest" in data["results"][0]

    @pytest.mark.asyncio
    async def test_include_manifest_surfaces_receipt_hashes_available(self):
        base = get_base()
        provider = XAPClient.sandbox(balance=0)
        provider.adapter = base.client.adapter
        identity = provider.identity(
            display_name="HashBot",
            capabilities=[{
                "name": "analysis", "version": "1.0.0",
                "pricing": {"model": "fixed", "amount_minor_units": 500, "currency": "USD", "per": "request"},
                "sla": {"max_latency_ms": 2000, "availability_bps": 9900},
            }],
        )
        manifest = provider.manifest.build(
            capabilities=[{
                "name": "analysis", "version": "1.0.0",
                "attestation": {"total_settlements": 10, "success_rate_bps": 9000, "window_days": 90,
                                "receipt_hashes": [f"vrt_{'ab' * 32}", f"vrt_{'cd' * 32}"]},
            }],
            economic_terms={"accepted_currencies": ["USD"], "accepted_condition_types": ["deterministic"],
                            "min_amount_minor": 100, "max_amount_minor": 50000},
        )
        base.client.discovery.register(identity, manifest=manifest)
        result = await call_tool("xap_discover_agents", {
            "capability": "analysis", "include_manifest": True,
        })
        data = json.loads(result[0].text)
        assert data["results"][0]["receipt_hashes_available"] == 2

    @pytest.mark.asyncio
    async def test_legacy_min_reputation_still_works(self):
        base = get_base()
        result = await call_tool("xap_discover_agents", {
            "capability": "nonexistent", "min_reputation": 8000,
        })
        data = json.loads(result[0].text)
        assert "results" in data


class TestVerifyManifestTool:
    """New xap_verify_manifest tool."""

    def test_tool_exists_in_list(self):
        names = [t.name for t in _tool_schemas()]
        assert "xap_verify_manifest" in names

    def test_tool_schema_requires_manifest(self):
        tools = {t.name: t for t in _tool_schemas()}
        schema = tools["xap_verify_manifest"].inputSchema
        assert "manifest" in schema["required"]

    @pytest.mark.asyncio
    async def test_verify_valid_manifest(self):
        get_base()
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=[{
                "name": "code_review", "version": "1.0.0",
                "attestation": {"total_settlements": 847, "success_rate_bps": 9430,
                                "window_days": 90, "receipt_hashes": []},
            }],
            economic_terms={"accepted_currencies": ["USD"], "accepted_condition_types": ["deterministic"],
                            "min_amount_minor": 100, "max_amount_minor": 50000},
        )
        result = await call_tool("xap_verify_manifest", {"manifest": manifest})
        data = json.loads(result[0].text)
        assert data["verified"] is True
        assert "TRUST" in data["recommendation"]
        assert data["signature_valid"] is True
        assert data["claimed_success_rate"] == "94.3%"

    @pytest.mark.asyncio
    async def test_verify_tampered_manifest(self):
        get_base()
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=[{
                "name": "test", "version": "1.0.0",
                "attestation": {"total_settlements": 0, "success_rate_bps": 0,
                                "window_days": 90, "receipt_hashes": []},
            }],
            economic_terms={"accepted_currencies": ["USD"], "accepted_condition_types": ["deterministic"],
                            "min_amount_minor": 100, "max_amount_minor": 50000},
        )
        manifest["agent_id"] = "deadbeef"
        result = await call_tool("xap_verify_manifest", {"manifest": manifest})
        data = json.loads(result[0].text)
        assert data["verified"] is False
        assert "DO_NOT_TRUST" in data["recommendation"]

    @pytest.mark.asyncio
    async def test_verify_expired_manifest(self):
        get_base()
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=[{
                "name": "test", "version": "1.0.0",
                "attestation": {"total_settlements": 0, "success_rate_bps": 0,
                                "window_days": 90, "receipt_hashes": []},
            }],
            economic_terms={"accepted_currencies": ["USD"], "accepted_condition_types": ["deterministic"],
                            "min_amount_minor": 100, "max_amount_minor": 50000},
        )
        manifest["expires_at"] = "2020-01-01T00:00:00Z"
        result = await call_tool("xap_verify_manifest", {"manifest": manifest})
        data = json.loads(result[0].text)
        assert data["verified"] is False
        assert data["not_expired"] is False


class TestMCPServerToolCount:
    def test_server_exposes_7_tools(self):
        tools = _tool_schemas()
        assert len(tools) == 7

    def test_all_expected_tools_present(self):
        names = {t.name for t in _tool_schemas()}
        expected = {
            "xap_discover_agents", "xap_verify_manifest",
            "xap_create_offer", "xap_respond_to_offer",
            "xap_settle", "xap_verify_receipt", "xap_check_balance",
        }
        assert names == expected
