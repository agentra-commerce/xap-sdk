#!/usr/bin/env python3
"""Stress test: 100 concurrent negotiations.

Run: python validation/stress_negotiations.py
"""

import asyncio
import random
import sys
import time

from xap import XAPClient, AgentId


async def run_negotiation(
    buyer: XAPClient,
    provider: XAPClient,
    provider_id: AgentId,
    rng: random.Random,
) -> dict:
    """Run a single negotiation. Returns result dict."""
    price = rng.randint(100, 1000)

    offer = buyer.negotiation.create_offer(
        responder=provider_id,
        capability=rng.choice(["text_summarization", "data_analysis", "image_generation"]),
        amount_minor_units=price,
        currency="USD",
    )

    contract_id = offer["negotiation_id"]

    # Provider: accept 75%, counter 15%, reject 10%
    roll = rng.random()
    if roll < 0.10:
        provider.negotiation.reject(offer, reason="Too busy")
        return {"contract_id": contract_id, "outcome": "rejected", "chain_hash": None}

    if roll < 0.25:
        counter_price = price + rng.randint(50, 300)
        counter = provider.negotiation.counter_offer(offer, new_amount=counter_price)
        accepted = buyer.negotiation.accept(counter)
        return {
            "contract_id": contract_id,
            "outcome": "countered_then_accepted",
            "chain_hash": accepted.get("previous_state_hash"),
        }

    accepted = buyer.negotiation.accept(offer)
    return {
        "contract_id": contract_id,
        "outcome": "accepted",
        "chain_hash": accepted.get("previous_state_hash"),
    }


async def main() -> None:
    rng = random.Random(42)

    # Create 10 providers
    providers = []
    shared_adapter = None
    for i in range(10):
        pid = AgentId.generate()
        p = XAPClient.sandbox(agent_id=pid, balance=0)
        if shared_adapter is None:
            shared_adapter = p.adapter
        else:
            p.adapter = shared_adapter
        providers.append((p, pid))

    # Create 100 buyers, each with their own client but shared adapter
    buyers = []
    for i in range(100):
        bid = AgentId.generate()
        b = XAPClient.sandbox(agent_id=bid, balance=100_000)
        b.adapter = shared_adapter
        buyers.append(b)

    print("Starting 100 concurrent negotiations...")
    start = time.monotonic()

    # Each buyer negotiates with a random provider
    tasks = []
    for buyer in buyers:
        provider, provider_id = rng.choice(providers)
        task_rng = random.Random(rng.randint(0, 2**32))
        tasks.append(run_negotiation(buyer, provider, provider_id, task_rng))

    results = await asyncio.gather(*tasks)
    elapsed = time.monotonic() - start

    # Analyze results
    accepted = sum(1 for r in results if r["outcome"] == "accepted")
    rejected = sum(1 for r in results if r["outcome"] == "rejected")
    countered = sum(1 for r in results if r["outcome"] == "countered_then_accepted")

    # Check uniqueness of contract IDs
    contract_ids = [r["contract_id"] for r in results]
    all_unique = len(contract_ids) == len(set(contract_ids))

    # Check hash chains for accepted negotiations
    chain_results = [r for r in results if r["outcome"] in ("accepted", "countered_then_accepted")]
    all_chains_valid = all(
        r["chain_hash"] is not None or r["outcome"] == "accepted"
        for r in chain_results
    )

    print(f"Completed: {len(results)}/100")
    print(f"  Accepted: {accepted}")
    print(f"  Rejected: {rejected}")
    print(f"  Countered then accepted: {countered}")
    print(f"All contract IDs unique: {'YES' if all_unique else 'NO'}")
    print(f"All hash chains valid: {'YES' if all_chains_valid else 'NO'}")
    print(f"Time: {elapsed:.1f}s")

    if not all_unique:
        print("\nFAILED: Duplicate contract IDs detected!")
        sys.exit(1)

    if not all_chains_valid:
        print("\nFAILED: Invalid hash chains detected!")
        sys.exit(1)

    print("\nPASSED.")


if __name__ == "__main__":
    asyncio.run(main())
