"""In-memory test adapter for development and testing. No real money."""

from __future__ import annotations

from datetime import datetime, timezone

from xap.adapters.base import SettlementAdapter
from xap.errors import XAPAdapterError


class TestAdapter(SettlementAdapter):
    """In-memory adapter for development and testing. No real money."""

    def __init__(self) -> None:
        self._balances: dict[str, int] = {}
        self._payment_hold: dict[str, int] = {}
        self._transactions: list[dict] = []

    def fund_agent(self, agent_id: str, amount: int) -> None:
        """Give fake money to an agent for testing."""
        self._balances[agent_id] = self._balances.get(agent_id, 0) + amount
        self._transactions.append({
            "type": "fund",
            "agent_id": agent_id,
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def lock_funds(self, settlement: dict) -> dict:
        """Move funds from payer to payment hold."""
        payer = settlement["payer_agent"]
        amount = settlement["total_amount_minor_units"]
        stl_id = settlement["settlement_id"]

        if stl_id in self._payment_hold:
            raise XAPAdapterError(f"Funds already locked for settlement {stl_id}")

        balance = self._balances.get(payer, 0)
        if balance < amount:
            raise XAPAdapterError(
                f"Insufficient funds: {payer} has {balance}, needs {amount}"
            )

        self._balances[payer] -= amount
        self._payment_hold[stl_id] = amount
        self._transactions.append({
            "type": "lock",
            "settlement_id": stl_id,
            "payer": payer,
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {"status": "locked", "amount": amount}

    async def release_funds(self, settlement: dict, payouts: list[dict]) -> dict:
        """Release held funds to payees according to split."""
        stl_id = settlement["settlement_id"]

        if stl_id not in self._payment_hold:
            raise XAPAdapterError(f"No payment hold found for settlement {stl_id}")

        held = self._payment_hold[stl_id]
        total_payout = sum(p["amount_minor_units"] for p in payouts)

        if total_payout > held:
            raise XAPAdapterError(
                f"Payout total {total_payout} exceeds held amount {held}"
            )

        for payout in payouts:
            agent = payout["agent_id"]
            amt = payout["amount_minor_units"]
            self._balances[agent] = self._balances.get(agent, 0) + amt

        del self._payment_hold[stl_id]
        self._transactions.append({
            "type": "release",
            "settlement_id": stl_id,
            "payouts": payouts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        remainder = held - total_payout
        if remainder > 0:
            payer = settlement["payer_agent"]
            self._balances[payer] = self._balances.get(payer, 0) + remainder

        return {"status": "released", "total_released": total_payout}

    async def refund(self, settlement: dict, amount: int) -> dict:
        """Return held funds to payer."""
        stl_id = settlement["settlement_id"]
        payer = settlement["payer_agent"]

        if stl_id not in self._payment_hold:
            raise XAPAdapterError(f"No payment hold found for settlement {stl_id}")

        held = self._payment_hold[stl_id]
        if amount > held:
            raise XAPAdapterError(
                f"Refund amount {amount} exceeds held amount {held}"
            )

        self._payment_hold[stl_id] -= amount
        if self._payment_hold[stl_id] == 0:
            del self._payment_hold[stl_id]

        self._balances[payer] = self._balances.get(payer, 0) + amount
        self._transactions.append({
            "type": "refund",
            "settlement_id": stl_id,
            "payer": payer,
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {"status": "refunded", "amount": amount}

    def adapter_type(self) -> str:
        return "test"

    def default_finality(self) -> str:
        return "final"

    def balance(self, agent_id: str) -> int:
        """Get agent's current balance."""
        return self._balances.get(agent_id, 0)

    def transaction_log(self) -> list[dict]:
        """Get all transactions."""
        return list(self._transactions)
