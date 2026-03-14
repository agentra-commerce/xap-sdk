"""
Setup XAP MCP server for Claude Code or Claude Desktop.

Usage:
    python -m xap.mcp.setup          # Auto-detect Claude Code or Desktop
    python -m xap.mcp.setup --code    # Claude Code only
    python -m xap.mcp.setup --desktop # Claude Desktop only
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _claude_desktop_config_path() -> Path:
    """Return the path to claude_desktop_config.json."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "claude" / "claude_desktop_config.json"


def setup_claude_code() -> bool:
    """Configure XAP MCP server for Claude Code."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        print("Claude Code CLI not found. Skipping Claude Code setup.")
        return False

    try:
        subprocess.run(
            ["claude", "mcp", "add", "xap-mcp", "--", sys.executable, "-m", "xap.mcp.server"],
            check=True,
            capture_output=True,
            text=True,
        )
        print("Configured XAP MCP server for Claude Code.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to configure Claude Code: {e.stderr}")
        return False


def setup_claude_desktop() -> bool:
    """Configure XAP MCP server for Claude Desktop."""
    config_path = _claude_desktop_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config: dict = {}
    if config_path.exists():
        config = json.loads(config_path.read_text())

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["xap-mcp"] = {
        "command": sys.executable,
        "args": ["-m", "xap.mcp.server"],
        "env": {
            "XAP_MODE": "sandbox",
        },
    }

    config_path.write_text(json.dumps(config, indent=2))
    print(f"Configured XAP MCP server for Claude Desktop at {config_path}")
    return True


def main():
    """Auto-detect and configure Claude Code and/or Claude Desktop."""
    import argparse

    parser = argparse.ArgumentParser(description="Setup XAP MCP server")
    parser.add_argument("--code", action="store_true", help="Configure for Claude Code only")
    parser.add_argument("--desktop", action="store_true", help="Configure for Claude Desktop only")
    args = parser.parse_args()

    if not args.code and not args.desktop:
        args.code = True
        args.desktop = True

    success = False
    if args.code:
        success = setup_claude_code() or success
    if args.desktop:
        success = setup_claude_desktop() or success

    if not success:
        print("No configuration was applied.")
        sys.exit(1)


if __name__ == "__main__":
    main()
