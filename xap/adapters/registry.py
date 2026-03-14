"""
Adapter registry for discovering and selecting settlement adapters.

Allows runtime registration of adapters so the settlement engine
can select the right adapter based on currency, amount, or preference.
"""

from __future__ import annotations

from xap.adapters.base import SettlementAdapter


class AdapterRegistry:
    """Registry of available settlement adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, SettlementAdapter] = {}

    def register(self, adapter: SettlementAdapter) -> None:
        """Register an adapter by its type name."""
        self._adapters[adapter.adapter_type()] = adapter

    def get(self, adapter_type: str) -> SettlementAdapter:
        """Get adapter by type. Raises if not found."""
        if adapter_type not in self._adapters:
            raise ValueError(f"No adapter registered for type: {adapter_type}")
        return self._adapters[adapter_type]

    def list(self) -> list[dict]:
        """List all registered adapters with metadata."""
        result = []
        for adapter in self._adapters.values():
            if hasattr(adapter, "adapter_metadata"):
                meta = adapter.adapter_metadata()
            else:
                meta = {"type": adapter.adapter_type(), "finality": adapter.default_finality()}
            result.append(meta)
        return result

    def find_for_currency(self, currency: str) -> list[SettlementAdapter]:
        """Find adapters that support a given currency."""
        result = []
        for adapter in self._adapters.values():
            if hasattr(adapter, "supported_currencies"):
                if currency in adapter.supported_currencies():
                    result.append(adapter)
            else:
                result.append(adapter)  # Legacy adapters assumed to support all
        return result
