#!/usr/bin/env node
/**
 * @agentra/xap-mcp — XAP MCP server launcher
 *
 * Tries three launch strategies in order:
 * 1. uvx (fastest — no Python install required)
 * 2. python -m xap.mcp.server (if xap-sdk already installed)
 * 3. pip install xap-sdk[mcp] then launch (fallback)
 */

const { execSync, spawn } = require("child_process");
const path = require("path");

function tryLaunch(command, args) {
  const proc = spawn(command, args, {
    stdio: "inherit",
    env: { ...process.env },
  });
  proc.on("error", () => {});
  return proc;
}

function commandExists(cmd) {
  try {
    execSync(`${cmd} --version`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

// Strategy 1: uvx (installs and runs in one step, no Python config needed)
if (commandExists("uvx")) {
  tryLaunch("uvx", ["--from", "xap-sdk[mcp]", "xap-mcp"]);
  process.exit(0);
}

// Strategy 2: xap-sdk already installed, run directly
try {
  execSync("python -c 'import xap.mcp'", { stdio: "ignore" });
  tryLaunch("python", ["-m", "xap.mcp.server"]);
  process.exit(0);
} catch {}

// Strategy 3: install via pip then launch
console.log("[xap-mcp] Installing xap-sdk[mcp] via pip...");
try {
  execSync("pip install xap-sdk[mcp] --quiet", { stdio: "inherit" });
  tryLaunch("python", ["-m", "xap.mcp.server"]);
  process.exit(0);
} catch {
  console.error(
    "[xap-mcp] Could not start the XAP MCP server.\n" +
    "Please install manually: pip install xap-sdk[mcp]\n" +
    "Then run: python -m xap.mcp.server\n" +
    "Docs: https://zexrail.com/docs/mcp"
  );
  process.exit(1);
}
