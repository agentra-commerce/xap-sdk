# MCP Registry PR Content
# Submit to: github.com/modelcontextprotocol/servers
# Add to: README.md under the appropriate category

## Entry to add under "Finance & Commerce" or "Developer Tools":

### XAP — Agent Settlement Protocol

Enable AI assistants to discover agents, negotiate terms, execute conditional
settlements, and verify cryptographic receipts using the XAP open protocol.

**Install:**
```json
{
  "mcpServers": {
    "xap": {
      "command": "npx",
      "args": ["-y", "@agenticamem/xap-mcp"]
    }
  }
}
```

**Tools (7):** `xap_discover_agents`, `xap_verify_manifest`,
`xap_create_offer`, `xap_respond_to_offer`, `xap_settle`,
`xap_verify_receipt`, `xap_check_balance`

**Sandbox:** Works with no account (fake money, no real effects).
Set `XAP_MODE=sandbox` in env.

**Links:**
- npm: [@agenticamem/xap-mcp](https://npmjs.com/package/@agenticamem/xap-mcp)
- PyPI: [xap-sdk](https://pypi.org/project/xap-sdk/)
- Protocol: [xap-protocol.org](https://xap-protocol.org)
- Docs: [zexrail.com/docs/mcp](https://zexrail.com/docs/mcp)
- GitHub: [agentra-commerce/xap-sdk](https://github.com/agentra-commerce/xap-sdk)
