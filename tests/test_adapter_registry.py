"""Tests for adapter registry."""

import pytest

from xap.adapters.registry import AdapterRegistry
from xap.adapters.test_adapter import TestAdapter
from xap.adapters.external import ExternalSettlementAdapter


class FakeExternalAdapter(ExternalSettlementAdapter):
    """A fake external adapter for testing."""

    def provider_name(self) -> str:
        return "FakeCard"

    def provider_url(self) -> str:
        return "https://fakecard.test"

    def supported_currencies(self) -> list[str]:
        return ["USD", "EUR"]

    def max_amount(self, currency: str) -> int:
        return 10_000_000

    async def health_check(self) -> dict:
        return {"status": "ok"}

    async def lock_funds(self, settlement: dict) -> dict:
        return {"status": "locked"}

    async def release_funds(self, settlement: dict, payouts: list[dict]) -> dict:
        return {"status": "released"}

    async def refund(self, settlement: dict, amount: int) -> dict:
        return {"status": "refunded"}

    def adapter_type(self) -> str:
        return "fake_card"

    def default_finality(self) -> str:
        return "final"


class TestAdapterRegistry:
    def test_register_and_get(self):
        """Register adapter, retrieve by type."""
        registry = AdapterRegistry()
        adapter = TestAdapter()
        registry.register(adapter)
        assert registry.get("test") is adapter

    def test_get_unknown_raises(self):
        """Getting unregistered adapter raises ValueError."""
        registry = AdapterRegistry()
        with pytest.raises(ValueError, match="No adapter registered"):
            registry.get("nonexistent")

    def test_list_adapters(self):
        """List returns metadata for all registered adapters."""
        registry = AdapterRegistry()
        registry.register(TestAdapter())
        registry.register(FakeExternalAdapter())
        adapters = registry.list()
        assert len(adapters) == 2
        types = {a["type"] for a in adapters}
        assert "test" in types
        assert "fake_card" in types

    def test_list_external_adapter_metadata(self):
        """External adapter includes full metadata in listing."""
        registry = AdapterRegistry()
        registry.register(FakeExternalAdapter())
        adapters = registry.list()
        meta = adapters[0]
        assert meta["provider"] == "FakeCard"
        assert meta["url"] == "https://fakecard.test"
        assert "USD" in meta["currencies"]
        assert "EUR" in meta["currencies"]

    def test_find_for_currency(self):
        """Find adapters that support USD."""
        registry = AdapterRegistry()
        registry.register(TestAdapter())  # Legacy — no supported_currencies
        registry.register(FakeExternalAdapter())  # Supports USD, EUR
        usd_adapters = registry.find_for_currency("USD")
        assert len(usd_adapters) == 2  # Both: legacy assumed to support all

    def test_find_for_currency_filters(self):
        """Find adapters filters by supported currencies."""
        registry = AdapterRegistry()
        registry.register(FakeExternalAdapter())  # USD, EUR only
        gbp_adapters = registry.find_for_currency("GBP")
        assert len(gbp_adapters) == 0

    def test_register_overwrites(self):
        """Registering same adapter type overwrites previous."""
        registry = AdapterRegistry()
        adapter1 = TestAdapter()
        adapter2 = TestAdapter()
        registry.register(adapter1)
        registry.register(adapter2)
        assert registry.get("test") is adapter2
