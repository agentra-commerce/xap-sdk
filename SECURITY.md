# Security Policy — XAP SDK MCP Server

## Authentication

- **Sandbox mode** (`XAP_MODE=sandbox`): No credentials required. Uses local in-memory settlement engine. No external API calls.
- **Live mode** (`XAP_MODE=live`): Requires `XAP_API_KEY` environment variable. No default value — the server will not authenticate without an explicit key.

## Permissions Explained

### `env_vars` (read-only)
The server reads two environment variables:
- `XAP_MODE` — determines sandbox vs live operation
- `XAP_API_KEY` — authentication for live mode API calls
- `XAP_API_URL` — optional override for API endpoint

No environment variables are written or modified.

### `process_spawn`
Used **only** in the optional `setup.py` script to invoke `claude mcp add` for Claude Desktop configuration. The MCP server itself (`server.py`) does not spawn any processes during normal tool operation.

### `HTTP Network Access`
In live mode, the server makes HTTPS requests to a single endpoint:
- `https://api.zexrail.com/api/v1/*`

No other external endpoints are contacted. In sandbox mode, no network requests are made.

### `File System Read`
The server reads local schema files for validation. No file system writes occur during tool operation.

## Data Storage

Tool state (negotiation contracts, verity receipts) is stored in bounded in-memory caches:
- Maximum 1,000 entries per cache
- Automatic expiry after 1 hour (TTL)
- Entries are cleaned up on each tool call
- No data persists to disk
- No data is shared between sessions

## Dependency Security

All dependencies are pinned to versions that address known CVEs:
- `mcp >= 1.9` — addresses DNS rebinding (CVE-2025-66416), validation DoS (CVE-2025-53366), HTTP transport DoS (CVE-2025-53365)
- `pydantic >= 2.11` — addresses regex DoS (CVE-2024-3772)
- `jsonschema >= 4.23` — latest stable

## Reporting Vulnerabilities

Report security vulnerabilities to: security@zexrail.com

Please include:
- Description of the vulnerability
- Steps to reproduce
- Expected vs actual behavior
- Impact assessment

We aim to respond within 48 hours and patch critical vulnerabilities within 7 days.
