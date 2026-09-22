#!/usr/bin/env bash
# install.sh — Installs the Firecrawl Claude Code plugin and optional standalone skills.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="firecrawl"

echo "=== Firecrawl Claude Code Plugin Installer ==="

# Check for claude CLI
if command -v claude >/dev/null 2>&1; then
    echo "Found Claude Code CLI. Registering plugin marketplace..."
    claude plugin marketplace add "$PLUGIN_DIR" || true
    echo "Installing plugin ${PLUGIN_NAME}@${PLUGIN_NAME}..."
    claude plugin install "${PLUGIN_NAME}@${PLUGIN_NAME}" || true
    echo "✓ Plugin registered and installed in Claude Code."
else
    echo "Claude Code CLI ('claude') not found in PATH."
    echo "To register later when Claude Code is available:"
    echo "  claude plugin marketplace add $PLUGIN_DIR"
    echo "  claude plugin install ${PLUGIN_NAME}@${PLUGIN_NAME}"
fi


echo ""
echo "Installation complete!"
echo "Invoke skills as firecrawl:<skill-name> (e.g. firecrawl:scrape, firecrawl:search, firecrawl:build)"
