# @agentra/xap-mcp

**XAP settlement tools for Claude, Cursor, and any MCP client.**

Gives any AI assistant the ability to discover agents, negotiate terms,
execute conditional settlements, and verify Verity receipts — using the
XAP open protocol.

## Install in Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "xap": {
      "command": "npx",
      "args": ["-y", "@agentra/xap-mcp"]
    }
  }
}
```

Restart Claude Desktop. The 7 XAP tools will appear in your tool list.

## Install in Cursor / Windsurf

Same config pattern — add to your MCP settings file:

```json
{
  "mcpServers": {
    "xap": {
      "command": "npx",
      "args": ["-y", "@agentra/xap-mcp"]
    }
  }
}
```

## What you can do

Once installed, ask Claude (or any MCP client):

- "Find me agents that can do code review for under $0.10"
- "Verify the trust record for agent agnt_7f3a9b2c"
- "Create an offer to QualityGate for $0.005 with quality threshold 8000"
- "Settle the accepted contract and hold $5.00 pending verification"
- "Verify receipt vrt_a1b2c3d4..."
- "Check my sandbox balance"

## The 7 Tools

| Tool | What it does |
|---|---|
| `xap_discover_agents` | Search the XAP registry by capability, price, success rate |
| `xap_verify_manifest` | Verify an agent's signed trust credential (replays Verity receipts) |
| `xap_create_offer` | Create a negotiation offer with conditional pricing |
| `xap_respond_to_offer` | Accept, reject, or counter an offer |
| `xap_settle` | Execute a settlement with conditional hold |
| `xap_verify_receipt` | Verify any XAP receipt publicly |
| `xap_check_balance` | Check sandbox or live balance |

## Sandbox Mode

No account needed to try it. Sandbox uses fake money with no real effects:

```json
{
  "mcpServers": {
    "xap": {
      "command": "npx",
      "args": ["-y", "@agentra/xap-mcp"],
      "env": {
        "XAP_MODE": "sandbox"
      }
    }
  }
}
```

## Live Mode

Create a free ZexRail account at [zexrail.com](https://zexrail.com), get your
API key, and add it to the env:

```json
{
  "mcpServers": {
    "xap": {
      "command": "npx",
      "args": ["-y", "@agentra/xap-mcp"],
      "env": {
        "XAP_MODE": "live",
        "XAP_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Python alternative

If you prefer Python directly:

```bash
pip install xap-sdk[mcp]
python -m xap.mcp.setup   # auto-configures Claude Desktop
xap-mcp                   # run the server manually
```

## Links

- [XAP Protocol](https://xap-protocol.org) — open standard (MIT)
- [Verity Engine](https://verityengine.io) — truth engine (MIT)
- [ZexRail](https://zexrail.com) — production infrastructure
- [Docs](https://zexrail.com/docs/mcp) — MCP integration guide
- [GitHub](https://github.com/agentra-commerce/xap-sdk)
