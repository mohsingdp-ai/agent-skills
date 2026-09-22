#!/usr/bin/env bash
# install.sh — Installs the HumanLayer Claude Code plugins.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKETPLACE_NAME="humanlayer"
PLUGIN_NAME="humanlayer"

echo "=== HumanLayer Claude Code Plugin Installer ==="

# Check for claude CLI
if command -v claude >/dev/null 2>&1; then
    echo "Found Claude Code CLI. Registering plugin marketplace..."
    claude plugin marketplace remove "$MARKETPLACE_NAME" >/dev/null 2>&1 || true
    claude plugin marketplace add "$PLUGIN_DIR" || true
    echo "Installing unified plugin ${PLUGIN_NAME}@${MARKETPLACE_NAME}..."
    claude plugin install "${PLUGIN_NAME}@${MARKETPLACE_NAME}" || true
    echo "✓ Plugin registered and installed in Claude Code."
else
    echo "Claude Code CLI ('claude') not found in PATH."
    echo "To register later when Claude Code is available:"
    echo "  claude plugin marketplace add $PLUGIN_DIR"
    echo "  claude plugin install ${PLUGIN_NAME}@${MARKETPLACE_NAME}"
fi

echo ""
echo "Installation complete!"
echo "Invoke skills as humanlayer:<skill-name> (e.g. humanlayer:show-me, humanlayer:visual-pr, humanlayer:improve-claude-md)"
echo "Or use slash commands: /show-me, /visual-pr, /improve-claude-md, /narrow-react-prop-types, /build-iterated-agentic-loop, /design-control-loop"
