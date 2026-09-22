#!/usr/bin/env bash
# install.sh — Installs the Playwright Test Agents plugin in Claude Code.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="playwright"

echo "=== Playwright Test Agents Plugin Installer ==="

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
echo "Invoke skills as playwright:<skill-name> (e.g. playwright:planner, playwright:autofix)"
echo "Or use slash commands (e.g. /pw:init, /pw:plan, /pw:autofix). Run /pw:init in each project first."
