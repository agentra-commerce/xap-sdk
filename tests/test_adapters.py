"""Tests for xap.adapters — TestAdapter."""

import pytest
from xap.adapters import TestAdapter
from xap.errors import XAPAdapterError


@pytest.fixture
def adapter():
    return TestAdapter()


def _make_settlement(stl_id="stl_12345678", payer="agent_aabbccdd", amount=10000):
    return {
        "settlement_id": stl_id,
        "payer_agent": payer,
        "total_amount_minor_units": amount,
    }


class TestTestAdapter:
    @pytest.mark.asyncio
    async def test_fund_and_balance(self, adapter):
        adapter.fund_agent("agent_aabbccdd", 50000)
        assert adapter.balance("agent_aabbccdd") == 50000

    @pytest.mark.asyncio
    async def test_lock_funds(self, adapter):
        adapter.fund_agent("agent_aabbccdd", 50000)
        result = await adapter.lock_funds(_make_settlement())
        assert result["status"] == "locked"
        assert adapter.balance("agent_aabbccdd") == 40000

    @pytest.mark.asyncio
    async def test_lock_insufficient_funds(self, adapter):
        adapter.fund_agent("agent_aabbccdd", 5000)
        with pytest.raises(XAPAdapterError, match="Insufficient"):
            await adapter.lock_funds(_make_settlement())

    @pytest.mark.asyncio
    async def test_double_lock(self, adapter):
        adapter.fund_agent("agent_aabbccdd", 50000)
        await adapter.lock_funds(_make_settlement())
        with pytest.raises(XAPAdapterError, match="already locked"):
            await adapter.lock_funds(_make_settlement())

    @pytest.mark.asyncio
    async def test_release_funds(self, adapter):
        adapter.fund_agent("agent_aabbccdd", 50000)
        stl = _make_settlement()
        await adapter.lock_funds(stl)

        payouts = [
            {"agent_id": "agent_11111111", "amount_minor_units": 8000},
            {"agent_id": "agent_22222222", "amount_minor_units": 2000},
        ]
        result = await adapter.release_funds(stl, payouts)
        assert result["status"] == "released"
        assert adapter.balance("agent_11111111") == 8000
        assert adapter.balance("agent_22222222") == 2000

    @pytest.mark.asyncio
    async def test_release_no_payment_hold(self, adapter):
        with pytest.raises(XAPAdapterError, match="No payment hold"):
            await adapter.release_funds(_make_settlement(), [])

    @pytest.mark.asyncio
    async def test_refund(self, adapter):
        adapter.fund_agent("agent_aabbccdd", 50000)
        stl = _make_settlement()
        await adapter.lock_funds(stl)

        result = await adapter.refund(stl, 10000)
        assert result["status"] == "refunded"
        assert adapter.balance("agent_aabbccdd") == 50000  # fully restored

    @pytest.mark.asyncio
    async def test_refund_no_payment_hold(self, adapter):
        with pytest.raises(XAPAdapterError, match="No payment hold"):
            await adapter.refund(_make_settlement(), 5000)

    @pytest.mark.asyncio
    async def test_refund_exceeds_payment_hold(self, adapter):
        adapter.fund_agent("agent_aabbccdd", 50000)
        stl = _make_settlement()
        await adapter.lock_funds(stl)
        with pytest.raises(XAPAdapterError, match="exceeds"):
            await adapter.refund(stl, 20000)

    @pytest.mark.asyncio
    async def test_transaction_log(self, adapter):
        adapter.fund_agent("agent_aabbccdd", 50000)
        stl = _make_settlement()
        await adapter.lock_funds(stl)
        log = adapter.transaction_log()
        assert len(log) == 2
        assert log[0]["type"] == "fund"
        assert log[1]["type"] == "lock"

    def test_adapter_type(self, adapter):
        assert adapter.adapter_type() == "test"

    def test_default_finality(self, adapter):
        assert adapter.default_finality() == "final"

    @pytest.mark.asyncio
    async def test_partial_release_returns_remainder(self, adapter):
        adapter.fund_agent("agent_aabbccdd", 50000)
        stl = _make_settlement()
        await adapter.lock_funds(stl)
        payouts = [{"agent_id": "agent_11111111", "amount_minor_units": 7000}]
        await adapter.release_funds(stl, payouts)
        # 3000 remainder goes back to payer
        assert adapter.balance("agent_aabbccdd") == 43000  # 40000 + 3000
        assert adapter.balance("agent_11111111") == 7000
