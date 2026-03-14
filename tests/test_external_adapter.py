"""Tests for external adapter interface."""

import pytest

from xap.adapters.external import ExternalSettlementAdapter


class MockExternalAdapter(ExternalSettlementAdapter):
    """Mock external adapter for testing the interface."""

    def provider_name(self) -> str:
        return "MockPay"

    def provider_url(self) -> str:
        return "https://mockpay.test"

    def supported_currencies(self) -> list[str]:
        return ["USD", "GBP"]

    def max_amount(self, currency: str) -> int:
        if currency == "USD":
            return 5_000_000
        return 1_000_000

    async def health_check(self) -> dict:
        return {"status": "healthy", "latency_ms": 12}

    async def lock_funds(self, settlement: dict) -> dict:
        return {"status": "locked", "trace": "mock_lock_001"}

    async def release_funds(self, settlement: dict, payouts: list[dict]) -> dict:
        return {"status": "released", "trace": "mock_release_001"}

    async def refund(self, settlement: dict, amount: int) -> dict:
        return {"status": "refunded", "amount": amount}

    def adapter_type(self) -> str:
        return "mock_pay"

    def default_finality(self) -> str:
        return "final"


class TestExternalAdapter:
    def test_external_adapter_metadata(self):
        """External adapter returns correct metadata."""
        adapter = MockExternalAdapter()
        meta = adapter.adapter_metadata()
        assert meta["provider"] == "MockPay"
        assert meta["url"] == "https://mockpay.test"
        assert meta["type"] == "mock_pay"
        assert meta["currencies"] == ["USD", "GBP"]
        assert meta["finality"] == "final"

    @pytest.mark.asyncio
    async def test_external_adapter_health_check(self):
        """Health check returns status."""
        adapter = MockExternalAdapter()
        health = await adapter.health_check()
        assert health["status"] == "healthy"

    def test_external_adapter_supported_currencies(self):
        """Supported currencies returns expected list."""
        adapter = MockExternalAdapter()
        assert "USD" in adapter.supported_currencies()
        assert "GBP" in adapter.supported_currencies()

    def test_external_adapter_max_amount(self):
        """Max amount varies by currency."""
        adapter = MockExternalAdapter()
        assert adapter.max_amount("USD") == 5_000_000
        assert adapter.max_amount("GBP") == 1_000_000

    @pytest.mark.asyncio
    async def test_external_adapter_lock_funds(self):
        """Lock funds works through external adapter."""
        adapter = MockExternalAdapter()
        result = await adapter.lock_funds({"settlement_id": "test_001"})
        assert result["status"] == "locked"

    @pytest.mark.asyncio
    async def test_external_adapter_release_funds(self):
        """Release funds works through external adapter."""
        adapter = MockExternalAdapter()
        result = await adapter.release_funds(
            {"settlement_id": "test_001"},
            [{"agent_id": "agent_1", "amount_minor_units": 500}],
        )
        assert result["status"] == "released"

    @pytest.mark.asyncio
    async def test_external_adapter_refund(self):
        """Refund works through external adapter."""
        adapter = MockExternalAdapter()
        result = await adapter.refund({"settlement_id": "test_001"}, 250)
        assert result["status"] == "refunded"
        assert result["amount"] == 250

    def test_external_adapter_is_settlement_adapter(self):
        """External adapter is a valid SettlementAdapter subclass."""
        from xap.adapters.base import SettlementAdapter
        adapter = MockExternalAdapter()
        assert isinstance(adapter, SettlementAdapter)
