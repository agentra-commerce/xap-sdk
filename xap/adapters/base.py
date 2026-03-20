"""Settlement adapter abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SettlementAdapter(ABC):
    """Abstract base for settlement adapters (Stripe, USDC, Test, etc.)."""

    @abstractmethod
    async def lock_funds(self, settlement: dict) -> dict:
        """Lock funds in a payment hold. Returns lock result."""

    @abstractmethod
    async def release_funds(self, settlement: dict, payouts: list[dict]) -> dict:
        """Release held funds to payees. Returns release result."""

    @abstractmethod
    async def refund(self, settlement: dict, amount: int) -> dict:
        """Return held funds to payer. Returns refund result."""

    @abstractmethod
    def adapter_type(self) -> str:
        """Adapter identifier string."""

    @abstractmethod
    def default_finality(self) -> str:
        """Default finality class for this adapter."""
