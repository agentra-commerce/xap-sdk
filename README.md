# XAP SDK

**Settlement objects for autonomous agent commerce.**

[![CI](https://github.com/agentralabs/xap-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/agentralabs/xap-sdk/actions)
[![PyPI](https://img.shields.io/pypi/v/xap-sdk)](https://pypi.org/project/xap-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/xap-sdk)](https://pypi.org/project/xap-sdk/)
[![Tests: 262 passing](https://img.shields.io/badge/Tests-262%20passing-brightgreen.svg)](#)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18944370.svg)](https://doi.org/10.5281/zenodo.18944370)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/agentralabs/xap-sdk/blob/main/LICENSE)
[![Patent Pending](https://img.shields.io/badge/Patent-Pending-blue.svg)](#)

XAP is the only protocol combining schema validation, cryptographic signatures, enforced state machines, idempotency, governed receipts, and replayable reasoning into one governed object model.

---

## Install

```bash
pip install xap-sdk
```

For MCP integration (Claude, Cursor, any MCP-compatible AI):

```bash
pip install xap-sdk[mcp]
```

---

## Quickstart: Two Agents, One Settlement, Full Provenance

```python
import asyncio
from xap import XAPClient

# Create two agents — sandbox uses fake money, no external services needed
provider = XAPClient.sandbox(balance=0)
consumer = XAPClient.sandbox(balance=100_000)  # $1,000.00
consumer.adapter.fund_agent(str(provider.agent_id), 0)
provider.adapter = consumer.adapter

# Provider registers a capability with SLA guarantees
provider_identity = provider.identity(
    display_name="SummarizeBot",
    capabilities=[{
        "name": "text_summarization",
        "version": "1.0.0",
        "pricing": {"model": "fixed", "amount_minor_units": 500, "currency": "USD", "per": "request"},
        "sla": {"max_latency_ms": 2000, "availability_bps": 9950},
    }],
)
consumer.discovery.register(provider_identity)

# Consumer discovers and negotiates
results = consumer.discovery.search(capability="text_summarization")
offer = consumer.negotiation.create_offer(
    responder=provider.agent_id,
    capability="text_summarization",
    amount_minor_units=500,
)
accepted = provider.negotiation.accept(offer)

# Settle with full decision provenance
async def settle():
    settlement = consumer.settlement.create_from_contract(
        accepted_contract=accepted,
        payees=[{"agent_id": str(provider.agent_id), "share_bps": 10000}],
    )
    locked = await consumer.settlement.lock(settlement)
    result = await consumer.settlement.verify_and_settle(
        settlement=locked,
        condition_results=[{
            "condition_id": "cond_0001",
            "type": "deterministic",
            "check": "output_delivered",
            "passed": True,
        }],
    )

    # Every decision is deterministically replayable
    assert consumer.receipts.verify_replay(result.verity_receipt)
    print(f"Settlement: {result.receipt['outcome']}")
    print(f"Replay verified: {result.verity_receipt['replay_hash']}")
    return result

asyncio.run(settle())
```

---

## The Verification Handshake

What separates XAP from every other agent protocol is Step 2 — trust verified before money moves:

```python
from xap import XAPClient
from xap.verify import verify_manifest

async def find_trusted_agent(capability: str, min_success_rate_bps: int = 9000):
    client = XAPClient.sandbox()

    # Step 1 — DECLARE: query the registry
    results = client.discovery.search(
        capability=capability,
        min_success_rate_bps=min_success_rate_bps,
        include_manifest=True,
    )

    for agent in results:
        # Step 2 — VERIFY: replay Verity receipts to confirm claimed track record
        manifest = agent["manifest"]
        verification = await verify_manifest(
            manifest=manifest,
            sample_receipts=3,
        )

        if verification.confirmed:
            print(f"Agent {agent['agent_id']} verified:")
            print(f"  Claimed:  {manifest['capabilities'][0]['attestation']['success_rate_bps'] / 100}%")
            print(f"  Verified: {verification.verified_rate_bps / 100}%")
            print(f"  Receipts replayed: {verification.receipts_checked}")

            # Step 3 — NEGOTIATE: enter negotiation with verified trust
            return client.negotiation.create_offer(
                responder=agent["agent_id"],
                capability=capability,
                amount_minor_units=1000,
            )

    return None
```

No other agent protocol has Step 2. Verification against real Verity receipts before a single dollar is committed.

---

## Three-Agent Split Settlement

```python
import asyncio
from xap import XAPClient

async def multi_agent_workflow():
    orchestrator = XAPClient.sandbox(balance=500_000)
    executor     = XAPClient.sandbox(balance=0)
    verifier     = XAPClient.sandbox(balance=0)

    executor.adapter = orchestrator.adapter
    verifier.adapter = orchestrator.adapter
    orchestrator.adapter.fund_agent(str(executor.agent_id), 0)
    orchestrator.adapter.fund_agent(str(verifier.agent_id), 0)

    settlement = orchestrator.settlement.create(
        payer_id=str(orchestrator.agent_id),
        payees=[
            {"agent_id": str(executor.agent_id),   "share_bps": 7000},  # 70%
            {"agent_id": str(verifier.agent_id),    "share_bps": 2000},  # 20%
            {"agent_id": str(orchestrator.agent_id),"share_bps": 1000},  # 10%
        ],
        amount_minor_units=10_000,  # $100.00
        currency="USD",
    )

    locked = await orchestrator.settlement.lock(settlement)
    result = await orchestrator.settlement.verify_and_settle(
        settlement=locked,
        condition_results=[{
            "condition_id": "cond_0001",
            "type": "probabilistic",
            "check": "quality_score",
            "score_bps": 9200,
            "threshold_bps": 8500,
            "passed": True,
        }],
    )

    print(f"Outcome: {result.receipt['outcome']}")
    print(f"Executor:     ${result.receipt['payouts'][str(executor.agent_id)] / 100:.2f}")
    print(f"Verifier:     ${result.receipt['payouts'][str(verifier.agent_id)] / 100:.2f}")

asyncio.run(multi_agent_workflow())
```

---

## What XAP Does

Every agent-to-agent economic interaction produces governed objects that are:

- **Schema-validated** — structured, machine-readable, JSON Schema Draft 2020-12
- **Cryptographically signed** — Ed25519, tamper-evident
- **State-transitioned** — explicit state machines, no implicit jumps
- **Idempotent** — safe retries, no duplicate effects
- **Receipted** — every settlement emits a governed `ExecutionReceipt`
- **Replayable** — every decision captured in a `VerityReceipt`, independently verifiable

---

## The Six Primitives

| # | Primitive | What It Does |
|---|---|---|
| 0 | `AgentManifest` | Signed, Verity-backed trust credential. How agents find and verify each other. |
| 1 | `AgentIdentity` | Permanent economic passport with append-only reputation. |
| 2 | `NegotiationContract` | Time-bound offer/counter/accept flow with conditional pricing. |
| 3 | `SettlementIntent` | Escrow instruction with declared release conditions and split rules. |
| 4 | `ExecutionReceipt` | Tamper-proof record of every economic event. |
| 5 | `VerityReceipt` | Deterministically replayable proof of why a decision was made. |

---

## The Stack

```
xap-protocol    — Open standard (MIT). The language agents speak.
verity-engine   — Open source truth engine (Rust, MIT). The Git of financial truth.
xap-sdk         — This package. Build XAP-native agents in Python.
Agentra Rail    — Commercial infrastructure. Production settlement at scale.
```

---

## MCP Integration

Connect XAP to Claude, Cursor, or any MCP-compatible AI assistant:

```bash
pip install xap-sdk[mcp]
python -m xap.mcp.setup  # Auto-configure for Claude Desktop
```

Or run the MCP server directly:

```bash
xap-mcp
```

This exposes XAP's full capability — discovery, negotiation, settlement, receipts, Verity replay — as MCP tools. Any AI that supports MCP can transact on XAP without writing code.

---

## Examples

| Example | What It Shows |
|---|---|
| [`two_agent_demo.py`](examples/two_agent_demo.py) | Full flow: discover, negotiate, settle, replay. The canonical starting point. |
| [`three_agent_split.py`](examples/three_agent_split.py) | Multi-party settlement with basis point splits. Atomic payment to multiple agents. |
| [`unknown_outcome.py`](examples/unknown_outcome.py) | When verification is ambiguous. Partial settlement and refund scenarios. |
| [`manifest_demo.py`](examples/manifest_demo.py) | Build a manifest, sign it, verify receipts, query the registry. |
| [`mcp_demo.py`](examples/mcp_demo.py) | XAP as MCP tools. Negotiate and settle from a Claude conversation. |

---

## Key Concepts

**Money is always integers.** `500` means $5.00 (minor units). No floating point, ever. This is not a convention — it is an invariant enforced at every layer.

**Shares are basis points.** `4000` means 40%. All shares in a settlement must sum to exactly `10000`. The settlement engine rejects anything else.

**Every decision is replayable.** The `VerityReceipt` captures inputs, rules, computation steps, and a replay hash. Any party can independently verify the outcome. Given the same inputs and rules, the same outcome is guaranteed.

**Sandbox mode is zero-config.** `XAPClient.sandbox()` gives you fake money, in-memory registry, and test adapter. No external services, no accounts, no configuration.

**Manifests are credentials, not claims.** An `AgentManifest` is signed with the agent's Ed25519 key and contains Verity receipt hashes from real past settlements. It is not "here is what I can do" — it is cryptographic proof of what has been done.

---

## Links

- [XAP Protocol Specification](https://github.com/agentralabs/xap-protocol)
- [Verity Truth Engine](https://github.com/agentralabs/verity-engine)
- [Agentra Rail — Production Infrastructure](https://www.agentralabs.tech)
- [Discord Community](https://discord.gg/agentralabs)

---

## Citation

```bibtex
@software{xap_sdk_2026,
  title  = {XAP SDK: Settlement objects for autonomous agent commerce},
  author = {Agentra Labs},
  year   = {2026},
  doi    = {10.5281/zenodo.18944370},
  url    = {https://github.com/agentralabs/xap-sdk}
}
```

---

## License

MIT
