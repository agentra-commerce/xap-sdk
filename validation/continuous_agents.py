#!/usr/bin/env python3
"""Two XAP agents transacting continuously.

Run: python validation/continuous_agents.py --rounds 1000
Logs every failure. Exits non-zero if any round fails.
"""

import argparse
import asyncio
import random
import sys
import time
import traceback

from xap import XAPClient, AgentId


async def run_round(
    round_num: int,
    total_rounds: int,
    buyer: XAPClient,
    worker: XAPClient,
    worker_id: AgentId,
    rng: random.Random,
    verbose: bool,
) -> dict:
    """Execute a single transaction round. Returns a result dict."""
    start = time.monotonic()

    # Randomize pricing per round
    price = rng.randint(100, 500)

    # Worker response: accept 75%, counter 20%, reject 5%
    roll = rng.random()
    if roll < 0.05:
        worker_action = "reject"
    elif roll < 0.25:
        worker_action = "counter"
    else:
        worker_action = "accept"

    # Create offer
    offer = buyer.negotiation.create_offer(
        responder=worker_id,
        capability="data_processing",
        amount_minor_units=price,
        currency="USD",
    )

    if worker_action == "reject":
        worker.negotiation.reject(offer, reason="Not interested this round")
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "round": round_num,
            "outcome": "REJECTED",
            "amount": None,
            "elapsed_ms": elapsed_ms,
            "replay_ok": None,
            "chain_ok": None,
        }

    if worker_action == "counter":
        counter_price = price + rng.randint(50, 200)
        counter = worker.negotiation.counter_offer(offer, new_amount=counter_price)
        accepted = buyer.negotiation.accept(counter)
        final_price = counter_price
    else:
        accepted = worker.negotiation.accept(offer)
        final_price = price

    # Decide payee split: 70% single, 30% multi-payee
    if rng.random() < 0.30:
        num_extra = rng.randint(1, 2)  # 2-3 payees total
        if num_extra == 1:
            payees = [
                {"agent_id": str(worker_id), "share_bps": 7000, "role": "primary_executor"},
                {"agent_id": str(AgentId.generate()), "share_bps": 3000, "role": "data_provider"},
            ]
        else:
            payees = [
                {"agent_id": str(worker_id), "share_bps": 5000, "role": "primary_executor"},
                {"agent_id": str(AgentId.generate()), "share_bps": 3000, "role": "data_provider"},
                {"agent_id": str(AgentId.generate()), "share_bps": 2000, "role": "verifier"},
            ]
    else:
        payees = [{"agent_id": str(worker_id), "share_bps": 10000, "role": "primary_executor"}]

    # Build conditions
    num_conditions = rng.randint(1, 3)
    conditions = []
    for i in range(num_conditions):
        ctype = rng.choice(["deterministic", "probabilistic"])
        cond = {
            "condition_id": f"cond_{i + 1:04d}",
            "type": ctype,
            "check": rng.choice(["output_delivered", "quality_score", "latency_check"]),
            "verifier": "engine",
            "required": True,
        }
        if ctype == "probabilistic":
            cond["operator"] = "gte"
            cond["threshold"] = 7000
        conditions.append(cond)

    settlement = buyer.settlement.create_from_contract(
        accepted_contract=accepted,
        payees=payees,
        conditions=conditions,
    )

    settlement = await buyer.settlement.lock(settlement)

    # Condition results: all pass 60%, some fail 25%, all fail 15%
    roll = rng.random()
    condition_results = []
    for cond in conditions:
        if roll < 0.15:
            passed = False
        elif roll < 0.40:
            passed = rng.choice([True, False])
        else:
            passed = True

        cr = {
            "condition_id": cond["condition_id"],
            "type": cond["type"],
            "check": cond["check"],
            "passed": passed,
            "verified_by": "engine",
        }
        if cond["type"] == "probabilistic":
            cr["confidence_bps"] = rng.randint(5000, 10000) if passed else rng.randint(1000, 4999)
        condition_results.append(cr)

    result = await buyer.settlement.verify_and_settle(settlement, condition_results)

    outcome = result.settlement["state"]
    amount_display = None
    if outcome in ("SETTLED", "PARTIAL"):
        amount_display = sum(p["final_amount_minor_units"] for p in result.receipt["payouts"])

    replay_ok = buyer.receipts.verify_replay(result.verity_receipt)
    chain_ok = buyer.receipts.verify_chain(settlement["settlement_id"])

    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "round": round_num,
        "outcome": outcome,
        "amount": amount_display,
        "elapsed_ms": elapsed_ms,
        "replay_ok": replay_ok,
        "chain_ok": chain_ok,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Continuous XAP agent transaction test")
    parser.add_argument("--rounds", type=int, default=100, help="Number of rounds (default: 100)")
    parser.add_argument("--verbose", action="store_true", help="Detailed output per round")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    buyer_id = AgentId.generate()
    worker_id = AgentId.generate()

    buyer = XAPClient.sandbox(agent_id=buyer_id, balance=10_000_000)
    worker = XAPClient.sandbox(agent_id=worker_id)
    worker.adapter = buyer.adapter

    # Register worker
    worker_identity = worker.identity(
        display_name="WorkerBot",
        capabilities=[{
            "name": "data_processing",
            "version": "1.0.0",
            "pricing": {"amount_minor_units": 300, "currency": "USD", "model": "fixed", "per": "request"},
            "sla": {"max_latency_ms": 2000, "availability_bps": 9900},
        }],
    )
    buyer.discovery.register(worker_identity)

    counters = {"SETTLED": 0, "PARTIAL": 0, "REFUNDED": 0, "REJECTED": 0, "NEGOTIATION_FAILED": 0}
    replay_verified = 0
    replay_total = 0
    chain_verified = 0
    chain_total = 0
    errors = []
    total_start = time.monotonic()

    for i in range(1, args.rounds + 1):
        try:
            res = await run_round(i, args.rounds, buyer, worker, worker_id, rng, args.verbose)
            outcome = res["outcome"]
            counters[outcome] = counters.get(outcome, 0) + 1

            if res["replay_ok"] is not None:
                replay_total += 1
                if res["replay_ok"]:
                    replay_verified += 1
            if res["chain_ok"] is not None:
                chain_total += 1
                if res["chain_ok"]:
                    chain_verified += 1

            if args.verbose or outcome == "REJECTED":
                amount_str = f"${res['amount'] / 100:.2f}" if res["amount"] is not None else "--"
                replay_str = f"replay={'OK' if res['replay_ok'] else 'FAIL'}" if res["replay_ok"] is not None else ""
                chain_str = f"chain={'OK' if res['chain_ok'] else 'FAIL'}" if res["chain_ok"] is not None else ""
                extra = f"  {replay_str}  {chain_str}" if replay_str else "  (negotiation rejected)"
                print(f"Round {i}/{args.rounds}: {outcome:<12} {amount_str:<8}{extra}  ({res['elapsed_ms']:.0f}ms)")
            elif i % max(1, args.rounds // 20) == 0:
                # Progress indicator every 5%
                print(f"Round {i}/{args.rounds}: {outcome:<12} ({res['elapsed_ms']:.0f}ms)")

        except Exception as e:
            errors.append({
                "round": i,
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            print(f"Round {i}/{args.rounds}: ERROR - {e}")

    total_time = time.monotonic() - total_start

    print(f"\n=== SUMMARY ===")
    print(f"Total rounds:    {args.rounds}")
    print(f"Settled:         {counters['SETTLED']}")
    print(f"Partial:         {counters['PARTIAL']}")
    print(f"Refunded:        {counters['REFUNDED']}")
    print(f"Rejected:        {counters['REJECTED']}")
    settled_total = counters["SETTLED"] + counters["PARTIAL"] + counters["REFUNDED"]
    print(f"Replay verified: {replay_verified}/{replay_total} ({100 * replay_verified // max(1, replay_total)}%)")
    print(f"Chain verified:  {chain_verified}/{chain_total} ({100 * chain_verified // max(1, chain_total)}%)")
    print(f"Errors:          {len(errors)}")
    print(f"Total time:      {total_time:.1f}s")
    print(f"Avg round:       {total_time / args.rounds * 1000:.1f}ms")

    if errors:
        print(f"\n=== ERRORS ===")
        for err in errors:
            print(f"\nRound {err['round']}: {err['error']}")
            print(err["traceback"])
        sys.exit(1)

    if replay_verified != replay_total or chain_verified != chain_total:
        print("\nFAILED: Not all replay/chain verifications passed.")
        sys.exit(1)

    print("\nPASSED: All rounds completed without errors.")


if __name__ == "__main__":
    asyncio.run(main())
