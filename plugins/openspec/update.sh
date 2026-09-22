#!/usr/bin/env bash
# update.sh — Pulls the latest OpenSpec templates from @fission-ai/openspec and refreshes this plugin.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_FILE="${PLUGIN_DIR}/.claude-plugin/plugin.json"
TARGET_TAG="${1:-latest}"

echo "=================================================="
echo "   OpenSpec Claude Code Plugin Upstream Updater   "
echo "=================================================="

# 1. Check current plugin version
CURRENT_VERSION="unknown"
if [ -f "$MANIFEST_FILE" ]; then
    CURRENT_VERSION=$(node -e "try { console.log(require('${MANIFEST_FILE}').version); } catch(e){ console.log('unknown'); }")
fi
echo "Current plugin version: ${CURRENT_VERSION}"

# 2. Resolve target OpenSpec version from npm
echo "Checking latest upstream @fission-ai/openspec version on npm..."
LATEST_VERSION=$(npm view "@fission-ai/openspec@${TARGET_TAG}" version 2>/dev/null || echo "")

if [ -z "$LATEST_VERSION" ]; then
    echo "⚠️ Could not resolve version for @fission-ai/openspec@${TARGET_TAG} from npm. Falling back to npx query..."
    LATEST_VERSION=$(npx --yes @fission-ai/openspec@latest --version 2>/dev/null | tail -n 1 || echo "")
fi

if [ -z "$LATEST_VERSION" ]; then
    echo "❌ Error: Failed to resolve upstream OpenSpec version. Please check internet connection."
    exit 1
fi

echo "Latest upstream version: ${LATEST_VERSION}"

if [ "$CURRENT_VERSION" = "$LATEST_VERSION" ] && [ "${2:-}" != "--force" ]; then
    echo "✓ Plugin is already at the latest OpenSpec version (${CURRENT_VERSION})."
    echo "  (To force re-generation anyway, run: ./update.sh latest --force)"
    exit 0
fi

echo ""
echo "Updating plugin from version ${CURRENT_VERSION} -> ${LATEST_VERSION}..."

# 3. Create a temporary workspace for openspec init
STAGING_DIR=$(mktemp -d -t openspec-update-XXXXXX)
trap 'rm -rf "${STAGING_DIR}"' EXIT

echo "Generating Claude Code templates using npx @fission-ai/openspec@${LATEST_VERSION}..."
npx --yes "@fission-ai/openspec@${LATEST_VERSION}" init "${STAGING_DIR}" --tools claude --force --no-animation

# 4. Validate output
if [ ! -d "${STAGING_DIR}/.claude/skills" ] || [ ! -d "${STAGING_DIR}/.claude/commands" ]; then
    echo "❌ Error: Expected .claude/skills or .claude/commands not found in generated output."
    exit 1
fi

# 5. Sync skills
echo "Syncing skills..."
mkdir -p "${PLUGIN_DIR}/skills"
# Remove existing skills
find "${PLUGIN_DIR}/skills" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
# Copy new skills
cp -a "${STAGING_DIR}/.claude/skills/"* "${PLUGIN_DIR}/skills/"
if [ -d "${PLUGIN_DIR}/templates/skills" ]; then
    cp -a "${PLUGIN_DIR}/templates/skills/"* "${PLUGIN_DIR}/skills/"
fi

# Create short alias symlinks in skills/
cd "${PLUGIN_DIR}/skills"
for skill_dir in openspec-*; do
    if [ -d "$skill_dir" ]; then
        short_name="${skill_dir#openspec-}"
        # If suffix is -change or -specs, simplify further if helpful
        case "$short_name" in
            apply-change) alias_name="apply" ;;
            archive-change) alias_name="archive" ;;
            bulk-archive-change) alias_name="bulk-archive" ;;
            continue-change) alias_name="continue" ;;
            new-change) alias_name="new" ;;
            sync-specs) alias_name="sync" ;;
            update-change) alias_name="update" ;;
            verify-change) alias_name="verify" ;;
            *) alias_name="$short_name" ;;
        esac
        ln -sf "$skill_dir" "$alias_name"
    fi
done

# 6. Sync commands
echo "Syncing slash commands..."
mkdir -p "${PLUGIN_DIR}/commands/opsx"
find "${PLUGIN_DIR}/commands/opsx" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
cp -a "${STAGING_DIR}/.claude/commands/opsx/"* "${PLUGIN_DIR}/commands/opsx/"
if [ -d "${PLUGIN_DIR}/templates/commands/opsx" ]; then
    cp -a "${PLUGIN_DIR}/templates/commands/opsx/"* "${PLUGIN_DIR}/commands/opsx/"
fi

# 7. Update version in plugin.json
if [ -f "$MANIFEST_FILE" ]; then
    node -e "
        const fs = require('fs');
        const pkg = JSON.parse(fs.readFileSync('${MANIFEST_FILE}', 'utf8'));
        pkg.version = '${LATEST_VERSION}';
        fs.writeFileSync('${MANIFEST_FILE}', JSON.stringify(pkg, null, 2) + '\n');
    "
fi

# 8. Refresh Claude Code plugin registration if claude CLI is available
if command -v claude >/dev/null 2>&1; then
    echo "Refreshing plugin in Claude Code..."
    claude plugin marketplace add "${PLUGIN_DIR}" >/dev/null 2>&1 || true
fi

echo ""
echo "=================================================="
echo "✓ OpenSpec plugin successfully updated to v${LATEST_VERSION}!"
echo "  - Skills:   $(find "${PLUGIN_DIR}/skills" -mindepth 1 -maxdepth 1 -type d | wc -l) skills synced"
echo "  - Commands: $(find "${PLUGIN_DIR}/commands/opsx" -type f | wc -l) commands synced"
echo "=================================================="
