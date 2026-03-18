"""Shared logic for framework integrations."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from xap.client import XAPClient
from xap.types import AgentId

if TYPE_CHECKING:
    pass


class XAPIntegrationBase:
    """Shared logic for framework integrations.

    Both LangChain and CrewAI integrations delegate to this class
    for the actual XAP operations.
    """

    def __init__(self, client: XAPClient) -> None:
        self.client = client

    @classmethod
    def sandbox(cls, balance: int = 1_000_000) -> XAPIntegrationBase:
        """Create integration with a sandbox client."""
        client = XAPClient.sandbox(balance=balance)
        return cls(client)

    def discover(
        self,
        capability: str,
        min_success_rate_bps: int = 0,
        max_price_minor: int | None = None,
        currency: str | None = None,
        condition_type: str | None = None,
        include_manifest: bool = False,
        page_size: int = 20,
        # Legacy parameter — mapped to min_success_rate_bps for backwards compat
        min_reputation: int = 0,
        max_price: int | None = None,
    ) -> dict:
        """Search the XAP registry using RegistryQuery (XAP v0.2)."""
        effective_min_rate = max(min_success_rate_bps, min_reputation)
        effective_max_price = max_price_minor or max_price

        kwargs: dict = {"capability": capability, "limit": page_size}
        if effective_min_rate:
            kwargs["min_reputation_bps"] = effective_min_rate
        if effective_max_price is not None:
            kwargs["max_price_minor_units"] = effective_max_price
        if include_manifest:
            kwargs["include_manifest"] = True
        return self.client.discovery.search(**kwargs)

    def create_offer(
        self,
        agent_id: str,
        capability: str,
        amount: int,
        conditions: list[dict] | None = None,
    ) -> dict:
        """Create a negotiation offer to an agent."""
        return self.client.negotiation.create_offer(
            responder=AgentId(agent_id),
            capability=capability,
            amount_minor_units=amount,
            currency="USD",
            conditions=conditions,
        )

    def accept_offer(self, contract: dict) -> dict:
        """Accept a negotiation offer."""
        return self.client.negotiation.accept(contract)

    def reject_offer(self, contract: dict, reason: str | None = None) -> dict:
        """Reject a negotiation offer."""
        return self.client.negotiation.reject(contract, reason=reason)

    def counter_offer(self, contract: dict, new_amount: int | None = None) -> dict:
        """Counter a negotiation offer with new terms."""
        return self.client.negotiation.counter_offer(contract, new_amount=new_amount)

    def respond_to_offer(
        self,
        contract: dict,
        action: str,
        new_amount: int | None = None,
        reason: str | None = None,
    ) -> dict:
        """Accept, reject, or counter a negotiation offer."""
        if action == "accept":
            return self.accept_offer(contract)
        elif action == "reject":
            return self.reject_offer(contract, reason=reason)
        elif action == "counter":
            return self.counter_offer(contract, new_amount=new_amount)
        else:
            raise ValueError(f"Invalid action: {action}. Must be 'accept', 'reject', or 'counter'.")

    async def settle_async(
        self,
        contract: dict,
        payee_shares: list[dict] | None = None,
        condition_results: list[dict] | None = None,
    ) -> dict:
        """Execute a full settlement from an accepted contract (async)."""
        if contract.get("state") != "ACCEPT":
            raise ValueError("Contract must be in ACCEPT state to settle.")

        # Default: 100% to the provider (from_agent in an accepted contract)
        if payee_shares is None:
            provider = contract.get("from_agent")
            payee_shares = [{"agent_id": provider, "share_bps": 10000, "role": "primary_executor"}]

        settlement = self.client.settlement.create_from_contract(
            accepted_contract=contract,
            payees=payee_shares,
        )

        settlement = await self.client.settlement.lock(settlement)

        if condition_results is None:
            condition_results = [
                {"condition_id": "cond_0001", "type": "deterministic", "check": "output_delivered", "passed": True}
            ]

        result = await self.client.settlement.verify_and_settle(settlement, condition_results)

        replay_ok = self.client.receipts.verify_replay(result.verity_receipt)

        return {
            "settlement_id": result.settlement["settlement_id"],
            "outcome": result.settlement["state"],
            "receipt_id": result.receipt["receipt_id"],
            "verity_id": result.verity_receipt["verity_id"],
            "replay_verified": replay_ok,
            "payouts": result.receipt["payouts"],
            "total_paid": sum(p["final_amount_minor_units"] for p in result.receipt["payouts"]),
        }

    def settle(
        self,
        contract: dict,
        payee_shares: list[dict] | None = None,
        condition_results: list[dict] | None = None,
    ) -> dict:
        """Execute a full settlement from an accepted contract (sync wrapper)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.settle_async(contract, payee_shares, condition_results),
                )
                return future.result()
        else:
            return asyncio.run(self.settle_async(contract, payee_shares, condition_results))

    def verify(self, verity_receipt: dict) -> bool:
        """Verify that a settlement receipt is deterministically replayable."""
        return self.client.receipts.verify_replay(verity_receipt)

    def check_balance(self, agent_id: str | None = None) -> int:
        """Check an agent's current balance."""
        if agent_id is None:
            agent_id = str(self.client.agent_id)
        return self.client.adapter.balance(agent_id)

    def _format_result(self, data: dict | list | bool | int) -> str:
        """Format a result as JSON string for tool output."""
        if isinstance(data, bool):
            return json.dumps({"result": data})
        if isinstance(data, int):
            return json.dumps({"balance": data})
        return json.dumps(data, indent=2, default=str)
