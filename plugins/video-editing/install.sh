#!/usr/bin/env bash
# install.sh — Installs the video-editing Claude Code plugin.
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
claude plugin marketplace add "$PLUGIN_DIR"
claude plugin install video-editing@video-editing
echo "Invoke skills as video-editing:<skill-name> (e.g. video-editing:take-one)."
