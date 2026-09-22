#!/usr/bin/env bash
# install.sh — Installs the Addy Skills Claude Code plugin.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="addy-skills"

echo "=== Addy Skills Claude Code Plugin Installer ==="

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
echo "Invoke skills as addy-skills:<skill-name> (e.g. addy-skills:code-review-and-quality, addy-skills:test-driven-development)"
echo "Or use slash commands (e.g. /spec, /plan, /build, /test, /review, /code-simplify, /ship, /constraints, /webperf)"
