#!/bin/bash
# Run from xap-sdk/npm/ to publish to npm.
# Requires: npm login with @agentra org access.

set -e

echo "Publishing @agentra/xap-mcp..."
echo "Version: $(node -p "require('./package.json').version")"
echo ""

# Sanity checks
node scripts/check-python.js
echo ""

# Publish
npm publish --access public

echo ""
echo "Published. Verify at: https://www.npmjs.com/package/@agentra/xap-mcp"
echo "Users can now install with: npx -y @agentra/xap-mcp"
