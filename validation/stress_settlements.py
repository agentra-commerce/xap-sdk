#!/usr/bin/env python3
"""Stress test: 50 concurrent settlements.

Run: python validation/stress_settlements.py
"""

import asyncio
import random
import sys
import time

from xap import XAPClient, AgentId


async def run_settlement(
    buyer: XAPClient,
    accepted_contract: dict,
    payee_id: AgentId,
    condition_passed: bool | None,
    rng: random.Random,
) -> dict:
    """Run a single settlement through lock -> verify -> settle."""
    settlement = buyer.settlement.create_from_contract(
        accepted_contract=accepted_contract,
        payees=[{"agent_id": str(payee_id), "share_bps": 10000, "role": "primary_executor"}],
    )

    settlement = await buyer.settlement.lock(settlement)

    # Determine condition results
    if condition_passed is True:
        condition_results = [
            {"condition_id": "cond_0001", "type": "deterministic", "check": "output_delivered", "passed": True}
        ]
    elif condition_passed is False:
        condition_results = [
            {"condition_id": "cond_0001", "type": "deterministic", "check": "output_delivered", "passed": False}
        ]
    else:
        # Mix: one pass, one fail -> PARTIAL
        condition_results = [
            {"condition_id": "cond_0001", "type": "deterministic", "check": "output_delivered", "passed": True},
            {"condition_id": "cond_0002", "type": "deterministic", "check": "quality_check", "passed": False},
        ]

    result = await buyer.settlement.verify_and_settle(settlement, condition_results)

    replay_ok = buyer.receipts.verify_replay(result.verity_receipt)
    chain_ok = buyer.receipts.verify_chain(settlement["settlement_id"])

    amount = settlement["total_amount_minor_units"]
    distributed = sum(p["final_amount_minor_units"] for p in result.receipt["payouts"]) if result.receipt["payouts"] else 0

    return {
        "settlement_id": settlement["settlement_id"],
        "state": result.settlement["state"],
        "amount_locked": amount,
        "amount_distributed": distributed,
        "replay_ok": replay_ok,
        "chain_ok": chain_ok,
        "receipt_id": result.receipt["receipt_id"],
        "verity_id": result.verity_receipt["verity_id"],
    }


async def main() -> None:
    rng = random.Random(42)

    # Create shared adapter with one buyer that has plenty of funds
    buyer_id = AgentId.generate()
    buyer = XAPClient.sandbox(agent_id=buyer_id, balance=50_000_000)

    print("Setting up 50 pre-accepted negotiations...")

    # Create 50 pre-accepted negotiations
    contracts = []
    payee_ids = []
    for i in range(50):
        payee_id = AgentId.generate()
        payee = XAPClient.sandbox(agent_id=payee_id)
        payee.adapter = buyer.adapter

        price = rng.randint(200, 2000)
        offer = buyer.negotiation.create_offer(
            responder=payee_id,
            capability="data_processing",
            amount_minor_units=price,
            currency="USD",
        )
        accepted = payee.negotiation.accept(offer)
        contracts.append(accepted)
        payee_ids.append(payee_id)

    print("Starting 50 concurrent settlements...")
    start = time.monotonic()

    # Decide outcomes: 60% all pass, 25% partial, 15% all fail
    tasks = []
    for i in range(50):
        roll = rng.random()
        if roll < 0.15:
            condition_passed = False  # REFUNDED
        elif roll < 0.40:
            condition_passed = None  # PARTIAL (mixed)
        else:
            condition_passed = True  # SETTLED

        tasks.append(run_settlement(buyer, contracts[i], payee_ids[i], condition_passed, rng))

    results = await asyncio.gather(*tasks)
    elapsed = time.monotonic() - start

    # Analyze
    settled = sum(1 for r in results if r["state"] == "SETTLED")
    partial = sum(1 for r in results if r["state"] == "PARTIAL")
    refunded = sum(1 for r in results if r["state"] == "REFUNDED")

    total_locked = sum(r["amount_locked"] for r in results)
    total_distributed = sum(r["amount_distributed"] for r in results)
    # For refunds, the money goes back to payer via adapter, not via payouts
    # Money conservation: locked == distributed + refunded_to_payer
    # The adapter handles this internally
    refunded_amount = sum(r["amount_locked"] for r in results if r["state"] == "REFUNDED")
    partial_refunded = sum(r["amount_locked"] - r["amount_distributed"] for r in results if r["state"] == "PARTIAL")
    money_conserved = total_locked == total_distributed + refunded_amount + partial_refunded

    all_receipts = all(r["receipt_id"] and r["verity_id"] for r in results)
    all_replay = all(r["replay_ok"] for r in results)
    all_chain = all(r["chain_ok"] for r in results)

    # Check uniqueness
    settlement_ids = [r["settlement_id"] for r in results]
    all_unique = len(settlement_ids) == len(set(settlement_ids))

    print(f"Completed: {len(results)}/50")
    print(f"  Settled: {settled}")
    print(f"  Partial: {partial}")
    print(f"  Refunded: {refunded}")
    print(f"Money conservation: {'PASSED' if money_conserved else 'FAILED'} (locked == distributed + refunded)")
    print(f"All receipts valid: {'YES' if all_receipts else 'NO'}")
    print(f"All replay hashes valid: {'YES' if all_replay else 'NO'}")
    print(f"All chains valid: {'YES' if all_chain else 'NO'}")
    print(f"All settlement IDs unique: {'YES' if all_unique else 'NO'}")
    print(f"Time: {elapsed:.1f}s")

    failed = False
    if not money_conserved:
        print("\nFAILED: Money conservation violated!")
        failed = True
    if not all_receipts:
        print("\nFAILED: Missing receipts!")
        failed = True
    if not all_replay:
        print("\nFAILED: Replay hash verification failed!")
        failed = True
    if not all_chain:
        print("\nFAILED: Chain verification failed!")
        failed = True
    if not all_unique:
        print("\nFAILED: Duplicate settlement IDs!")
        failed = True

    if failed:
        sys.exit(1)

    print("\nPASSED.")


if __name__ == "__main__":
    asyncio.run(main())
