#!/usr/bin/env bash
# update.sh — Pulls the latest video skills from their 8 upstream repos into skills/.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGING_DIR=$(mktemp -d -t video-editing-update-XXXXXX)
trap 'rm -rf "${STAGING_DIR}"' EXIT

# repo | path of the skill inside the repo | skill folder name here
SOURCES="
alchaincyf/huashu-motion|skills/huashu-motion|huashu-motion
rossark0/rossark-motion-skill|.|rossark-motion-skill
talsiach/take-one|.|take-one
NiazMorshed2007/reanimate|skills/reanimate|reanimate
shreyaskarnik/argo|skills/argo-guide|argo-guide
vincentsch/explainroo|skills/explainroo|explainroo
win4r/video-director|video-director|video-director
Leonxlnx/earshot|skills/earshot|earshot
Leonxlnx/earshot|skills/real-sound|real-sound
"

rm -rf "${PLUGIN_DIR}/skills" && mkdir -p "${PLUGIN_DIR}/skills"
: > "${PLUGIN_DIR}/UPSTREAM.md.tmp"
while IFS='|' read -r repo path name; do
    [ -z "$repo" ] && continue
    dir="${STAGING_DIR}/${repo//\//__}"
    [ -d "$dir" ] || { echo "Cloning ${repo}..."; git clone -q --depth 1 "https://github.com/${repo}.git" "$dir"; }
    # Skip demo videos/gifs (rossark: ~11 MB); the skill only reads the .swift sources.
    rsync -a --exclude .git --exclude .github --exclude '*.mp4' --exclude '*.gif' "${dir}/${path}/" "${PLUGIN_DIR}/skills/${name}/"
    [ -f "${PLUGIN_DIR}/skills/${name}/LICENSE" ] || cp "${dir}/LICENSE" "${PLUGIN_DIR}/skills/${name}/LICENSE"
    echo "| \`${name}\` | [${repo}](https://github.com/${repo}) | \`$(git -C "$dir" rev-parse --short HEAD)\` |" >> "${PLUGIN_DIR}/UPSTREAM.md.tmp"
done <<< "$SOURCES"

{ echo "| Skill | Upstream | Commit |"; echo "| :--- | :--- | :--- |"; cat "${PLUGIN_DIR}/UPSTREAM.md.tmp"; } > "${PLUGIN_DIR}/UPSTREAM.md"
rm "${PLUGIN_DIR}/UPSTREAM.md.tmp"

if command -v claude >/dev/null 2>&1; then
    claude plugin marketplace update video-editing >/dev/null 2>&1 || true
    claude plugin update video-editing@video-editing >/dev/null 2>&1 || true
fi
echo "Done. Skills refreshed:"; cat "${PLUGIN_DIR}/UPSTREAM.md"
