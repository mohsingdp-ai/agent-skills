#!/usr/bin/env bash
# update.sh — Pulls the latest skills from upstream humanlayer/skills and refreshes this plugin.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_REPO="https://github.com/humanlayer/skills.git"
MARKETPLACE_NAME="humanlayer"
PLUGIN_NAME="humanlayer"

echo "=================================================="
echo "   HumanLayer Claude Code Upstream Updater        "
echo "=================================================="

# 1. Create temporary directory and clone upstream
STAGING_DIR=$(mktemp -d -t humanlayer-skills-update-XXXXXX)
trap 'rm -rf "${STAGING_DIR}"' EXIT

echo "Cloning latest upstream repository..."
git clone --depth 1 "$UPSTREAM_REPO" "$STAGING_DIR"

# 2. Sync unified skills from upstream plugins
echo "Syncing skills..."
mkdir -p "${PLUGIN_DIR}/skills"
rm -rf "${PLUGIN_DIR}/skills"/*

for plugin_dir in "${STAGING_DIR}/plugins/"*; do
    if [ -d "${plugin_dir}" ]; then
        skill_name=$(basename "${plugin_dir}")
        if [ -d "${plugin_dir}/skills/${skill_name}" ]; then
            cp -a "${plugin_dir}/skills/${skill_name}" "${PLUGIN_DIR}/skills/"
            if [ -f "${plugin_dir}/.claude-plugin/plugin.json" ]; then
                cp -a "${plugin_dir}/.claude-plugin/plugin.json" "${PLUGIN_DIR}/skills/${skill_name}/plugin.json"
            fi
        fi
    fi
done

# 3. Copy licenses and upstream docs
for doc in LICENSE; do
    if [ -f "${STAGING_DIR}/${doc}" ]; then
        cp -a "${STAGING_DIR}/${doc}" "${PLUGIN_DIR}/${doc}"
    fi
done
if [ -f "${STAGING_DIR}/README.md" ]; then
    cp -a "${STAGING_DIR}/README.md" "${PLUGIN_DIR}/UPSTREAM_README.md"
fi

# 4. Refresh in Claude Code
if command -v claude >/dev/null 2>&1; then
    echo "Refreshing plugin in Claude Code..."
    claude plugin uninstall "${PLUGIN_NAME}@${MARKETPLACE_NAME}" --scope user >/dev/null 2>&1 || true
    claude plugin marketplace remove "$MARKETPLACE_NAME" >/dev/null 2>&1 || true
    claude plugin marketplace add "$PLUGIN_DIR" >/dev/null 2>&1 || true
    claude plugin install "${PLUGIN_NAME}@${MARKETPLACE_NAME}" --scope user >/dev/null 2>&1 || true
    echo "✓ Re-installed ${PLUGIN_NAME}@${MARKETPLACE_NAME} in Claude Code."
fi

echo "Update complete! Successfully refreshed HumanLayer skills."
