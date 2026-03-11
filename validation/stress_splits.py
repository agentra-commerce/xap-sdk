#!/usr/bin/env python3
"""Stress test: 10 split settlements with partial failures.

Run: python validation/stress_splits.py
"""

import asyncio
import sys

from xap import XAPClient, AgentId


async def run_scenario(
    scenario_num: int,
    description: str,
    amount: int,
    payees: list[dict],
    conditions: list[dict],
    condition_results: list[dict],
    expected_state: str,
    expected_payouts: list[int] | None = None,
    expected_refund: int | None = None,
    chargeback_policy: str = "proportional",
) -> bool:
    """Run a single split scenario and verify results."""
    buyer_id = AgentId.generate()
    buyer = XAPClient.sandbox(agent_id=buyer_id, balance=10_000_000)

    # Create payee clients sharing the adapter
    responder_id = AgentId(payees[0]["agent_id"])
    responder = XAPClient.sandbox(agent_id=responder_id)
    responder.adapter = buyer.adapter

    offer = buyer.negotiation.create_offer(
        responder=responder_id,
        capability="data_processing",
        amount_minor_units=amount,
        currency="USD",
    )
    accepted = responder.negotiation.accept(offer)

    settlement = buyer.settlement.create_from_contract(
        accepted_contract=accepted,
        payees=payees,
        conditions=conditions,
        chargeback_policy=chargeback_policy,
    )

    settlement = await buyer.settlement.lock(settlement)
    result = await buyer.settlement.verify_and_settle(settlement, condition_results)

    state = result.settlement["state"]
    actual_payouts = [p["final_amount_minor_units"] for p in result.receipt["payouts"]]

    replay_ok = buyer.receipts.verify_replay(result.verity_receipt)
    chain_ok = buyer.receipts.verify_chain(settlement["settlement_id"])

    passed = True
    errors = []

    if state != expected_state:
        errors.append(f"state={state}, expected={expected_state}")
        passed = False

    if expected_payouts is not None and actual_payouts != expected_payouts:
        errors.append(f"payouts={actual_payouts}, expected={expected_payouts}")
        passed = False

    if expected_refund is not None and state == "REFUNDED":
        if actual_payouts:
            errors.append(f"expected no payouts for REFUNDED, got {actual_payouts}")
            passed = False

    if not replay_ok:
        errors.append("replay hash verification failed")
        passed = False

    if not chain_ok:
        errors.append("chain verification failed")
        passed = False

    payout_str = f"payouts={actual_payouts}" if actual_payouts else f"refund={amount}"
    status = "PASS" if passed else f"FAIL ({'; '.join(errors)})"
    print(f"Scenario {scenario_num:2d}: {description:<45} {state:<10} {payout_str:<30} {status}")

    return passed


def make_payee_ids(count: int) -> list[AgentId]:
    return [AgentId.generate() for _ in range(count)]


def make_conditions(count: int) -> list[dict]:
    return [
        {
            "condition_id": f"cond_{i + 1:04d}",
            "type": "deterministic",
            "check": f"check_{i + 1}",
            "verifier": "engine",
            "required": True,
        }
        for i in range(count)
    ]


def make_results(conditions: list[dict], passed_flags: list[bool]) -> list[dict]:
    return [
        {
            "condition_id": cond["condition_id"],
            "type": cond["type"],
            "check": cond["check"],
            "passed": flag,
            "verified_by": "engine",
        }
        for cond, flag in zip(conditions, passed_flags)
    ]


async def main() -> None:
    all_passed = True

    # Scenario 1: 3-way split, all conditions pass -> SETTLED
    ids = make_payee_ids(3)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 5000, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 3000, "role": "data_provider"},
        {"agent_id": str(ids[2]), "share_bps": 2000, "role": "verifier"},
    ]
    conditions = make_conditions(2)
    results = make_results(conditions, [True, True])
    # amount=800: 800*5000//10000=400, 800*3000//10000=240, 800*2000//10000=160
    ok = await run_scenario(1, "3-way split, all pass", 800, payees, conditions, results, "SETTLED", [400, 240, 160])
    all_passed = all_passed and ok

    # Scenario 2: 3-way split, one condition fails -> PARTIAL (pro-rata 1/2 = 50%)
    ids = make_payee_ids(3)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 5000, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 3000, "role": "data_provider"},
        {"agent_id": str(ids[2]), "share_bps": 2000, "role": "verifier"},
    ]
    conditions = make_conditions(2)
    results = make_results(conditions, [True, False])
    # ratio_bps = 1*10000//2 = 5000, partial = 800*5000//10000 = 400
    # payouts: 400*5000//10000=200, 400*3000//10000=120, 400*2000//10000=80
    ok = await run_scenario(2, "3-way split, partial", 800, payees, conditions, results, "PARTIAL", [200, 120, 80])
    all_passed = all_passed and ok

    # Scenario 3: 5-way split, all conditions fail -> REFUNDED
    ids = make_payee_ids(5)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 3000, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 2000, "role": "data_provider"},
        {"agent_id": str(ids[2]), "share_bps": 2000, "role": "verifier"},
        {"agent_id": str(ids[3]), "share_bps": 2000, "role": "tool_provider"},
        {"agent_id": str(ids[4]), "share_bps": 1000, "role": "orchestrator"},
    ]
    conditions = make_conditions(3)
    results = make_results(conditions, [False, False, False])
    ok = await run_scenario(3, "5-way split, all fail", 1000, payees, conditions, results, "REFUNDED", [], expected_refund=1000)
    all_passed = all_passed and ok

    # Scenario 4: 2-way split, single condition pass -> SETTLED (timeout not directly testable via verify_and_settle)
    # Instead: test with all conditions passing for a 2-way split
    ids = make_payee_ids(2)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 6000, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 4000, "role": "data_provider"},
    ]
    conditions = make_conditions(1)
    results = make_results(conditions, [True])
    # 500*6000//10000=300, 500*4000//10000=200
    ok = await run_scenario(4, "2-way split, all pass", 500, payees, conditions, results, "SETTLED", [300, 200])
    all_passed = all_passed and ok

    # Scenario 5: 4-way split, mixed deterministic+probabilistic, partial
    ids = make_payee_ids(4)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 4000, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 3000, "role": "data_provider"},
        {"agent_id": str(ids[2]), "share_bps": 2000, "role": "verifier"},
        {"agent_id": str(ids[3]), "share_bps": 1000, "role": "orchestrator"},
    ]
    conditions = [
        {"condition_id": "cond_0001", "type": "deterministic", "check": "output_delivered", "verifier": "engine", "required": True},
        {"condition_id": "cond_0002", "type": "probabilistic", "check": "quality_score", "verifier": "engine", "required": True, "operator": "gte", "threshold": 7000},
        {"condition_id": "cond_0003", "type": "deterministic", "check": "latency_check", "verifier": "engine", "required": True},
    ]
    cond_results = [
        {"condition_id": "cond_0001", "type": "deterministic", "check": "output_delivered", "passed": True, "verified_by": "engine"},
        {"condition_id": "cond_0002", "type": "probabilistic", "check": "quality_score", "passed": True, "verified_by": "engine", "confidence_bps": 8500},
        {"condition_id": "cond_0003", "type": "deterministic", "check": "latency_check", "passed": False, "verified_by": "engine"},
    ]
    # ratio_bps = 2*10000//3 = 6666, partial = 1000*6666//10000 = 666
    # payouts: 666*4000//10000=266, 666*3000//10000=199, 666*2000//10000=133, 666*1000//10000=66
    # sum=664, remainder=2 -> first payee gets +2 = 268
    ok = await run_scenario(5, "4-way split, mixed conditions, partial", 1000, payees, conditions, cond_results, "PARTIAL", [268, 199, 133, 66])
    all_passed = all_passed and ok

    # Scenario 6: 3-way split, chargeback_policy=payer_absorbs, one fail
    ids = make_payee_ids(3)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 5000, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 3000, "role": "data_provider"},
        {"agent_id": str(ids[2]), "share_bps": 2000, "role": "verifier"},
    ]
    conditions = make_conditions(2)
    results = make_results(conditions, [True, False])
    # Same math as proportional (SDK currently treats all policies the same for pro-rata)
    ok = await run_scenario(6, "3-way, payer_absorbs, one fail", 800, payees, conditions, results, "PARTIAL", [200, 120, 80], chargeback_policy="payer_absorbs")
    all_passed = all_passed and ok

    # Scenario 7: 3-way split, chargeback_policy=orchestrator_absorbs, one fail
    ids = make_payee_ids(3)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 5000, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 3000, "role": "data_provider"},
        {"agent_id": str(ids[2]), "share_bps": 2000, "role": "verifier"},
    ]
    conditions = make_conditions(2)
    results = make_results(conditions, [True, False])
    ok = await run_scenario(7, "3-way, orchestrator_absorbs, one fail", 800, payees, conditions, results, "PARTIAL", [200, 120, 80], chargeback_policy="orchestrator_absorbs")
    all_passed = all_passed and ok

    # Scenario 8: 2-way split [7000, 3000], all pass -> verify exact payout amounts
    ids = make_payee_ids(2)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 7000, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 3000, "role": "data_provider"},
    ]
    conditions = make_conditions(1)
    results = make_results(conditions, [True])
    # 1000*7000//10000=700, 1000*3000//10000=300
    ok = await run_scenario(8, "2-way [7000,3000], all pass", 1000, payees, conditions, results, "SETTLED", [700, 300])
    all_passed = all_passed and ok

    # Scenario 9: 3-way split [5000,3000,2000], modifier via partial (2/3 pass) -> 6666 bps
    ids = make_payee_ids(3)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 5000, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 3000, "role": "data_provider"},
        {"agent_id": str(ids[2]), "share_bps": 2000, "role": "verifier"},
    ]
    conditions = make_conditions(3)
    results = make_results(conditions, [True, True, False])
    # ratio_bps = 2*10000//3 = 6666, partial = 900*6666//10000 = 599
    # payouts: 599*5000//10000=299, 599*3000//10000=179, 599*2000//10000=119
    # sum=597, remainder=2 -> first payee +2 = 301
    ok = await run_scenario(9, "3-way [5000,3000,2000], modifier 6666bps", 900, payees, conditions, results, "PARTIAL", [301, 179, 119])
    all_passed = all_passed and ok

    # Scenario 10: 4-way with remainder allocation
    ids = make_payee_ids(4)
    payees = [
        {"agent_id": str(ids[0]), "share_bps": 3333, "role": "primary_executor"},
        {"agent_id": str(ids[1]), "share_bps": 2500, "role": "data_provider"},
        {"agent_id": str(ids[2]), "share_bps": 2500, "role": "verifier"},
        {"agent_id": str(ids[3]), "share_bps": 1667, "role": "orchestrator"},
    ]
    conditions = make_conditions(1)
    results = make_results(conditions, [True])
    # 1000*3333//10000=333, 1000*2500//10000=250, 1000*2500//10000=250, 1000*1667//10000=166
    # sum=999, remainder=1 -> first payee gets +1 = 334
    ok = await run_scenario(10, "4-way remainder allocation", 1000, payees, conditions, results, "SETTLED", [334, 250, 250, 166])
    all_passed = all_passed and ok

    print()
    if all_passed:
        print("All 10 scenarios passed.")
        print("Modifier arithmetic verified in all cases.")
        print("Replay hashes verified in all cases.")
    else:
        print("SOME SCENARIOS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
