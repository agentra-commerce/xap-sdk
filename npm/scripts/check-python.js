/**
 * Runs after npm install.
 * Checks if Python or uvx is available and prints setup guidance.
 * Non-fatal — never blocks the install.
 */

const { execSync } = require("child_process");

const hasPython = (() => {
  for (const cmd of ["python3", "python"]) {
    try { execSync(`${cmd} --version`, { stdio: "ignore" }); return true; }
    catch {}
  }
  return false;
})();

const hasUvx = (() => {
  try { execSync("uvx --version", { stdio: "ignore" }); return true; }
  catch { return false; }
})();

if (hasUvx) {
  console.log("\n✓ xap-mcp ready (uvx detected — no further setup needed)");
} else if (hasPython) {
  console.log("\n✓ xap-mcp ready (Python detected)");
  console.log("  The server will install xap-sdk[mcp] on first run.");
} else {
  console.log("\n⚠  xap-mcp: Python not found.");
  console.log("  Install Python from https://python.org");
  console.log("  Or install uv (faster): https://docs.astral.sh/uv/");
  console.log("  Then run: npx @agentra/xap-mcp");
}

console.log("\n  Docs: https://zexrail.com/docs/mcp");
console.log("  GitHub: https://github.com/agentra-commerce/xap-sdk\n");
