"""
External adapter interface for third-party payment tools.

Any external payment service can implement this interface to become
an XAP settlement adapter. This enables the ecosystem to grow
without requiring changes to the XAP SDK.

Example:
    class AgentCardAdapter(ExternalSettlementAdapter):
        async def lock_funds(self, settlement):
            card = agentcard.create_card(amount=settlement['amount'])
            return {'status': 'locked', 'card_id': card.id}

        async def release_funds(self, settlement, payouts):
            ...

        async def refund(self, settlement, amount=None):
            ...
"""

from __future__ import annotations

from abc import abstractmethod

from xap.adapters.base import SettlementAdapter


class ExternalSettlementAdapter(SettlementAdapter):
    """Base class for external/third-party settlement adapters.

    Extends SettlementAdapter with:
    - Provider metadata for registry
    - Health check endpoint
    - Webhook handler registration
    """

    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name (e.g., 'AgentCard', 'Wise', 'Circle')."""
        ...

    @abstractmethod
    def provider_url(self) -> str:
        """Provider website URL."""
        ...

    @abstractmethod
    def supported_currencies(self) -> list[str]:
        """List of ISO 4217 currency codes this adapter supports."""
        ...

    @abstractmethod
    def max_amount(self, currency: str) -> int:
        """Maximum settlement amount in minor units for a currency."""
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        """Check adapter connectivity and readiness."""
        ...

    def adapter_metadata(self) -> dict:
        """Returns metadata for registry/discovery."""
        return {
            "provider": self.provider_name(),
            "url": self.provider_url(),
            "type": self.adapter_type(),
            "currencies": self.supported_currencies(),
            "finality": self.default_finality(),
        }
