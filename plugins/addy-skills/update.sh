#!/usr/bin/env bash
# update.sh — Pulls the latest skills from upstream addyosmani/agent-skills and refreshes this plugin.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_FILE="${PLUGIN_DIR}/.claude-plugin/plugin.json"
MARKETPLACE_FILE="${PLUGIN_DIR}/.claude-plugin/marketplace.json"
UPSTREAM_REPO="https://github.com/addyosmani/agent-skills.git"

echo "=================================================="
echo "   Addy Skills Claude Code Upstream Updater       "
echo "=================================================="

# 1. Check current plugin version
CURRENT_VERSION="unknown"
if [ -f "$MANIFEST_FILE" ]; then
    CURRENT_VERSION=$(node -e "try { console.log(require('${MANIFEST_FILE}').version); } catch(e){ console.log('unknown'); }")
fi
echo "Current plugin version: ${CURRENT_VERSION}"

# 2. Check latest release tag from upstream
echo "Checking latest upstream release on GitHub..."
LATEST_TAG=$(git ls-remote --tags --refs "$UPSTREAM_REPO" | awk -F'/' '{print $3}' | sort -V | tail -n 1 || echo "")

if [ -z "$LATEST_TAG" ]; then
    LATEST_TAG="main"
fi
echo "Latest upstream ref: ${LATEST_TAG}"

if [ "$CURRENT_VERSION" = "$LATEST_TAG" ] && [ "${1:-}" != "--force" ]; then
    echo "✓ Plugin is already at latest version (${CURRENT_VERSION})."
    echo "  (To force re-sync anyway, run: ./update.sh --force)"
    exit 0
fi

echo ""
echo "Updating plugin from version ${CURRENT_VERSION} -> ${LATEST_TAG}..."

# 3. Create temporary directory and clone upstream
STAGING_DIR=$(mktemp -d -t addy-skills-update-XXXXXX)
trap 'rm -rf "${STAGING_DIR}"' EXIT

echo "Cloning latest upstream repository..."
git clone --depth 1 --branch "${LATEST_TAG}" "$UPSTREAM_REPO" "$STAGING_DIR" 2>/dev/null || git clone --depth 1 "$UPSTREAM_REPO" "$STAGING_DIR"

UPSTREAM_VERSION=$(node -e "try { console.log(require('${STAGING_DIR}/plugin.json').version); } catch(e){ console.log('${LATEST_TAG}'); }")

# 4. Sync directories
echo "Syncing skills..."
mkdir -p "${PLUGIN_DIR}/skills"
rm -rf "${PLUGIN_DIR}/skills"/*
cp -a "${STAGING_DIR}/skills/"* "${PLUGIN_DIR}/skills/"

echo "Syncing commands..."
mkdir -p "${PLUGIN_DIR}/commands" "${PLUGIN_DIR}/.claude/commands"
rm -rf "${PLUGIN_DIR}/commands"/* "${PLUGIN_DIR}/.claude/commands"/*
cp -a "${STAGING_DIR}/commands/"* "${PLUGIN_DIR}/commands/" 2>/dev/null || true
cp -a "${STAGING_DIR}/.claude/commands/"* "${PLUGIN_DIR}/.claude/commands/" 2>/dev/null || true

echo "Syncing agents, hooks, references, docs, evals..."
for dir in agents hooks references docs evals scripts; do
    if [ -d "${STAGING_DIR}/${dir}" ]; then
        mkdir -p "${PLUGIN_DIR}/${dir}"
        rm -rf "${PLUGIN_DIR}/${dir}"/*
        cp -a "${STAGING_DIR}/${dir}/"* "${PLUGIN_DIR}/${dir}/" 2>/dev/null || true
    fi
done

for doc in AGENTS.md CONTRIBUTING.md LICENSE; do
    if [ -f "${STAGING_DIR}/${doc}" ]; then
        cp -a "${STAGING_DIR}/${doc}" "${PLUGIN_DIR}/${doc}"
    fi
done

# 5. Transform command references from agent-skills: to addy-skills:
echo "Transforming namespace references (agent-skills -> addy-skills)..."
if [ -d "${PLUGIN_DIR}/.claude/commands" ]; then
    find "${PLUGIN_DIR}/.claude/commands" -type f -name "*.md" -exec sed -i 's/agent-skills:/addy-skills:/g' {} +
fi

if [ -f "${PLUGIN_DIR}/hooks/session-start.sh" ]; then
    sed -i 's/agent-skills:/addy-skills:/g' "${PLUGIN_DIR}/hooks/session-start.sh"
    sed -i 's/agent-skills loaded/addy-skills loaded/g' "${PLUGIN_DIR}/hooks/session-start.sh"
fi

# 6. Update manifests
node -e "
const fs = require('fs');
const pJsonPath = '${MANIFEST_FILE}';
if (fs.existsSync(pJsonPath)) {
    const pj = JSON.parse(fs.readFileSync(pJsonPath, 'utf8'));
    pj.version = '${UPSTREAM_VERSION}';
    fs.writeFileSync(pJsonPath, JSON.stringify(pj, null, 2) + '\n');
}
const mJsonPath = '${MARKETPLACE_FILE}';
if (fs.existsSync(mJsonPath)) {
    const mj = JSON.parse(fs.readFileSync(mJsonPath, 'utf8'));
    fs.writeFileSync(mJsonPath, JSON.stringify(mj, null, 2) + '\n');
}
const rootPjPath = '${PLUGIN_DIR}/plugin.json';
if (fs.existsSync(rootPjPath)) {
    const rpj = JSON.parse(fs.readFileSync(rootPjPath, 'utf8'));
    rpj.name = 'addy-skills';
    rpj.version = '${UPSTREAM_VERSION}';
    fs.writeFileSync(rootPjPath, JSON.stringify(rpj, null, 2) + '\n');
}
"

# 7. Refresh in Claude Code
if command -v claude >/dev/null 2>&1; then
    echo "Refreshing plugin in Claude Code..."
    claude plugin uninstall addy-skills@addy-skills --scope user >/dev/null 2>&1 || true
    claude plugin marketplace remove addy-skills >/dev/null 2>&1 || true
    claude plugin marketplace add "$PLUGIN_DIR" >/dev/null 2>&1 || true
    claude plugin install addy-skills@addy-skills --scope user >/dev/null 2>&1 || true
    echo "✓ Re-installed addy-skills@addy-skills (${UPSTREAM_VERSION}) in Claude Code."
fi

echo "Update complete! Successfully updated to version ${UPSTREAM_VERSION}."
