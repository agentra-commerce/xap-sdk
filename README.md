# XAP SDK

**Settlement objects for autonomous agent commerce.**

XAP is the only protocol combining schema validation, cryptographic signatures, enforced state machines, idempotency, governed receipts, and replayable reasoning into one governed object model.

[![CI](https://github.com/agentralabs/xap-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/agentralabs/xap-sdk/actions)
[![PyPI](https://img.shields.io/pypi/v/xap-sdk)](https://pypi.org/project/xap-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/xap-sdk)](https://pypi.org/project/xap-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Install

```bash
pip install xap-sdk
```

## Quickstart: Two Agents, One Settlement, Full Provenance

```python
import asyncio
from xap import XAPClient

# Create two agents with sandbox (fake money, no external services)
provider = XAPClient.sandbox(balance=0)
consumer = XAPClient.sandbox(balance=100_000)  # $1,000.00
consumer.adapter.fund_agent(str(provider.agent_id), 0)
provider.adapter = consumer.adapter

# Provider registers a capability
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
            "condition_id": "cond_0001", "type": "deterministic",
            "check": "output_delivered", "passed": True,
        }],
    )

    # Verify the decision is deterministically replayable
    assert consumer.receipts.verify_replay(result.verity_receipt)
    print(f"Settlement: {result.receipt['outcome']}")
    print(f"Replay verified")
    return result

asyncio.run(settle())
```

## What XAP Does

XAP is a settlement object protocol. Every agent-to-agent economic interaction produces governed objects that are:

- **Schema-validated** — structured, machine-readable
- **Cryptographically signed** — Ed25519, tamper-evident
- **State-transitioned** — explicit state machines, no implicit jumps
- **Idempotent** — safe retries, no duplicate effects
- **Receipted** — every settlement emits a governed receipt
- **Replayable** — every decision can be independently verified

## The Stack

```
xap-protocol    — Open standard (MIT). The language agents speak.
verity-engine   — Open source truth engine (Rust). The Git of financial truth.
xap-sdk         — This package. Build with XAP in Python.
Agentra Rail    — Commercial infrastructure. The GitHub of agent settlement.
```

## MCP Integration

Connect XAP to Claude, Cursor, or any MCP-compatible AI:

```bash
pip install xap-sdk[mcp]
python -m xap.mcp.setup  # Auto-configure for Claude
```

Or run the server directly:

```bash
xap-mcp
```

## Examples

| Example | What it shows |
|---------|---------------|
| [Two-Agent Demo](examples/two_agent_demo.py) | Full flow: discover, negotiate, settle, replay |
| [Three-Agent Split](examples/three_agent_split.py) | Multi-party settlement with basis point splits |
| [Unknown Outcome](examples/unknown_outcome.py) | Partial settlement and refund scenarios |
| [MCP Demo](examples/mcp_demo.py) | MCP server tools in action |

## Key Concepts

**Money is always integers.** `500` means $5.00 (minor units). No floating point, ever.

**Shares are basis points.** `4000` means 40%. Shares must sum to exactly `10000`.

**Every decision is replayable.** The `VerityReceipt` captures inputs, rules, computation steps, and a replay hash. Any party can independently verify the outcome.

**Sandbox mode is zero-config.** `XAPClient.sandbox()` gives you fake money, in-memory registry, and test adapter. No external services needed.

## Links

- [XAP Protocol Specification](https://github.com/agentralabs/xap-protocol)
- [Verity Truth Engine](https://github.com/agentralabs/verity-engine)
- [Agentra Labs](https://agentralabs.tech)

## License

MIT
