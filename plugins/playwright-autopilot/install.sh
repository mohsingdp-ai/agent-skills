#!/usr/bin/env bash
# install.sh — Installs the Playwright Autopilot Claude Code plugin.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKETPLACE_NAME="playwright-autopilot"
PLUGIN_NAME="playwright-autopilot"

echo "=== Playwright Autopilot Claude Code Plugin Installer ==="

# Check for claude CLI
if command -v claude >/dev/null 2>&1; then
    echo "Found Claude Code CLI. Registering plugin marketplace..."
    claude plugin marketplace remove "$MARKETPLACE_NAME" >/dev/null 2>&1 || true
    claude plugin marketplace add "$PLUGIN_DIR" || true
    echo "Installing plugin ${PLUGIN_NAME}@${MARKETPLACE_NAME}..."
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
echo "Commands available:"
echo "  /pw-autopilot:loop             - Autonomous QA iteration loop"
echo "  /pw-autopilot:discover-backlog - Discover bugs, Jev score & backlog under epic"
echo "  /pw-autopilot:fix-verify       - Surgical fix & dual E2E/DevTools verification"
