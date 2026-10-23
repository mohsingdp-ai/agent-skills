#!/bin/sh
# Self-check for snap.sh on a throwaway repo: sh bin/snap.test.sh
set -eu
SNAP="$(cd "$(dirname "$0")" && pwd)/snap.sh"
repo=$(mktemp -d)
trap 'rm -rf "$repo"' EXIT
cd "$repo"
fail() { echo "FAIL: $1" >&2; exit 1; }

git init -q . && git config user.name t && git config user.email t@t
echo a >a.txt; echo b >b.txt; echo ig.log >.gitignore
git add -A && git commit -qm init
echo c >c.txt; echo ig >ig.log; head -c 11000000 /dev/zero >big.bin
echo staged >>a.txt && git add a.txt # a staged change must survive untouched
index_before=$(git ls-files -s | git hash-object --stdin)

before=$(sh "$SNAP" snap refs/prompt-changes/t/1)
git cat-file -e "$before:c.txt" || fail "untracked file not in snapshot"
git cat-file -e "$before:ig.log" 2>/dev/null && fail "ignored file in snapshot"
git cat-file -e "$before:big.bin" 2>/dev/null && fail "big new file in snapshot"

# the "prompt": edit, delete, create, touch ignored + big files
echo changed >>a.txt; rm b.txt; mkdir d; echo n >d/new.txt; echo c2 >c.txt
echo ig2 >ig.log; echo grew >>big.bin

undo=$(sh "$SNAP" restore "$before" refs/prompt-changes/t/undo)
[ "$(cat a.txt)" = "$(printf 'a\nstaged')" ] || fail "a.txt not restored"
[ "$(cat b.txt)" = b ] || fail "b.txt not brought back"
[ ! -e d/new.txt ] || fail "new file not removed"
[ "$(cat c.txt)" = c ] || fail "untracked c.txt not restored"
[ "$(cat ig.log)" = ig2 ] || fail "ignored file touched"
[ "$(tail -c 5 big.bin)" = grew ] || fail "big file touched"
[ "$(git ls-files -s | git hash-object --stdin)" = "$index_before" ] || fail "real index changed"

sh "$SNAP" restore "$undo" refs/prompt-changes/t/undo >/dev/null
[ "$(tail -n1 a.txt)" = changed ] && [ ! -e b.txt ] && [ "$(cat d/new.txt)" = n ] || fail "undo did not bring the prompt's changes back"

GIT_COMMITTER_DATE="2000-01-01T00:00:00" sh "$SNAP" snap refs/prompt-changes/old/1 >/dev/null
sh "$SNAP" prune 7
git show-ref -q refs/prompt-changes/old/1 && fail "old snapshot not pruned"
git show-ref -q refs/prompt-changes/t/1 || fail "fresh snapshot pruned"
echo "snap.sh: all checks passed"
