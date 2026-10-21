#!/usr/bin/env bash
# Put Keeper's state back into a fresh sandbox from a rescue copy made with
# `docker cp` (see docs/phase2-memory-skills.md). Run after agent/deploy.sh:
#   bash agent/restore.sh [rescue-dir] [sandbox]
# Restores memory and the router log, the Token Factory key file, and every
# learned skill in the keeper category (re-pinned into SOUL.md).
export PATH="$HOME/.local/bin:$PATH"
if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1; fi
set -euo pipefail
RESCUE="${1:-$HOME/keeper-rescue}"
SANDBOX="${2:-keeper}"
nh() { nemohermes "$SANDBOX" "$@"; }
[ -d "$RESCUE/keeper" ] || { echo "no $RESCUE/keeper folder; nothing to restore" >&2; exit 1; }

# Stage on the Linux filesystem: uploads from /mnt/c arrive as zeros.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
SHIPPED=" keeper-learn-from-corrections keeper-memory "

echo "== memory, router log and drafts"
if [ -d "$RESCUE/keeper/data" ]; then
  cp -r "$RESCUE/keeper/data" "$STAGE/data"
  nh exec -- rm -rf /sandbox/keeper/data
  nh upload "$STAGE/data" /sandbox/keeper/
fi

echo "== Token Factory key file"
if [ -d "$RESCUE/keeper/secrets" ]; then
  cp -r "$RESCUE/keeper/secrets" "$STAGE/secrets"
  nh exec -- rm -rf /sandbox/keeper/secrets
  nh upload "$STAGE/secrets" /sandbox/keeper/
  nh exec -- chmod 700 /sandbox/keeper/secrets
  nh exec -- bash -c 'chmod 600 /sandbox/keeper/secrets/*'
fi

echo "== learned skills"
learned=()
if [ -d "$RESCUE/hermes/skills/keeper" ]; then
  for dir in "$RESCUE"/hermes/skills/keeper/*/; do
    name="$(basename "$dir")"
    case "$SHIPPED" in *" $name "*) continue ;; esac
    cp -r "${dir%/}" "$STAGE/$name"
    nh exec -- rm -rf "/sandbox/.hermes/skills/keeper/$name"
    nh upload "$STAGE/$name" /sandbox/.hermes/skills/keeper/
    learned+=("$name")
    echo "   $name"
  done
fi
for name in "${learned[@]}"; do
  nh exec -- /sandbox/keeper/bin/keeper skills pin "$name"
done

echo
echo "Restored. Check with:"
echo "  nemohermes $SANDBOX exec -- /sandbox/keeper/bin/keeper memory topics"
echo "  nemohermes $SANDBOX exec -- /sandbox/keeper/bin/keeper skills list"
