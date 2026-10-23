#!/bin/sh
# Hidden git snapshots of the whole working tree (tracked + untracked, never
# ignored files), kept under refs/prompt-changes/. The real index is untouched.
#   snap.sh snap [ref]           print a commit of the tree now; store it at ref
#   snap.sh restore <commit> <undo-ref>
#                                snapshot now to undo-ref (printed), then make the
#                                tree match <commit>: changed files written back,
#                                files created since removed
#   snap.sh prune <days>         drop snapshots older than <days>
set -eu
MAX_NEW_KB=10240 # new files over 10 MB are left out of snapshots and never touched

cd "$(git rev-parse --show-toplevel)"
export GIT_AUTHOR_NAME=prompt-changes GIT_AUTHOR_EMAIL=prompt-changes@localhost
export GIT_COMMITTER_NAME=prompt-changes GIT_COMMITTER_EMAIL=prompt-changes@localhost
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

snap() { # snap [ref] -> commit
  # seed from the real index so unchanged files are recognised by stat, not rehashed
  cp "$(git rev-parse --git-path index)" "$tmp/idx" 2>/dev/null || :
  printf '.\0' >"$tmp/spec"
  git ls-files -z --others --exclude-standard |
    xargs -0 -r sh -c 'find "$@" -prune -type f -size +'"$MAX_NEW_KB"'k -print0' sh |
    xargs -0 -r printf ':(exclude,literal)%s\0' >>"$tmp/spec"
  GIT_INDEX_FILE="$tmp/idx" git add -A --pathspec-from-file="$tmp/spec" --pathspec-file-nul
  commit=$(git commit-tree "$(GIT_INDEX_FILE="$tmp/idx" git write-tree)" -m snapshot)
  if [ -n "${1:-}" ]; then git update-ref "$1" "$commit"; fi
  rm -f "$tmp/idx"
  echo "$commit"
}

case $1 in
snap) snap "${2:-}" ;;
restore)
  target=$2
  now=$(snap "$3")
  # created since: remove
  git diff --name-only -z --no-renames --diff-filter=A "$target" "$now" | xargs -0 -r rm -f --
  # changed since: write back. A "deleted" path still on disk was only left out
  # of the snapshot (big or newly ignored), so it is kept, not overwritten.
  { git diff --name-only -z --no-renames --diff-filter=MT "$target" "$now"
    git diff --name-only -z --no-renames --diff-filter=D "$target" "$now" |
      xargs -0 -r sh -c 'for f; do [ -e "$f" ] || [ -L "$f" ] || printf "%s\0" "$f"; done' sh
  } >"$tmp/back"
  GIT_INDEX_FILE="$tmp/idx" git read-tree "$target"
  GIT_INDEX_FILE="$tmp/idx" git checkout-index -f -z --stdin <"$tmp/back"
  echo "$now"
  ;;
prune)
  cutoff=$(($(date +%s) - $2 * 86400))
  git for-each-ref --format='%(committerdate:unix) %(refname)' refs/prompt-changes/ |
    while read -r when ref; do [ "$when" -lt "$cutoff" ] && echo "delete $ref"; done |
    git update-ref --stdin
  ;;
*) echo "unknown command: $1" >&2; exit 2 ;;
esac
