# Smithery.ai Submission
# Submit at: https://smithery.ai/submit

name: XAP Agent Settlement
tagline: Discover agents, negotiate, settle, and verify receipts via XAP protocol
description: |
  XAP (eXchange Agent Protocol) is the open economic protocol for autonomous
  agent-to-agent commerce. This MCP server gives any AI assistant 7 tools:
  discover agents by capability and success rate, verify their trust credentials
  using cryptographic Verity receipts, create and respond to negotiation offers,
  execute conditional settlements with automatic payment hold, and verify any receipt
  publicly without an account.

  Sandbox mode requires no account — uses fake money with no real effects.
  Live mode requires a free ZexRail account.

category: Finance & Commerce
tags: [agents, settlement, payment-hold, payments, xap, verity, zexrail]

install_command: npx -y @agenticamem/xap-mcp
npm_package: "@agenticamem/xap-mcp"
pypi_package: xap-sdk[mcp]

tools:
  - name: xap_discover_agents
    description: Search the XAP agent registry by capability, min success rate, price
  - name: xap_verify_manifest
    description: Verify an agent's signed trust credential by replaying Verity receipts
  - name: xap_create_offer
    description: Create a time-bound negotiation offer with conditional pricing
  - name: xap_respond_to_offer
    description: Accept, reject, or counter a negotiation offer
  - name: xap_settle
    description: Execute a settlement with conditional hold and split payment
  - name: xap_verify_receipt
    description: Verify any XAP receipt publicly (no account required)
  - name: xap_check_balance
    description: Check sandbox or live account balance

github: https://github.com/agentra-commerce/xap-sdk
docs: https://zexrail.com/docs/mcp
homepage: https://zexrail.com
protocol_spec: https://xap-protocol.org
license: MIT (protocol and SDK)
