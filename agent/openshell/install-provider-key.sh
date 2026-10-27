#!/usr/bin/env bash
# Install a direct-adapter key without copying it into the repository.
# Usage: bash agent/openshell/install-provider-key.sh telegram|tavily KEY_FILE [sandbox]
export PATH="$HOME/.local/bin:$PATH"
if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1; fi
set -euo pipefail
if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "usage: $0 telegram|tavily KEY_FILE [sandbox]" >&2
  exit 2
fi
case "$1" in
  telegram) DEST=telegram-bot.key ;;
  tavily) DEST=tavily.key ;;
  *) echo "service must be telegram or tavily" >&2; exit 2 ;;
esac
KEY_FILE="$2"
SANDBOX="${3:-keeper}"
[ -f "$KEY_FILE" ] && [ ! -L "$KEY_FILE" ] && [ -s "$KEY_FILE" ] || {
  echo "key must be a nonempty regular, non-symlink file" >&2; exit 1;
}
[ "$(wc -c < "$KEY_FILE")" -le 4096 ] || { echo "key file is too large" >&2; exit 1; }
command -v nemohermes >/dev/null || { echo "nemohermes is required in WSL" >&2; exit 1; }
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
chmod 700 "$STAGE"
install -m 600 "$KEY_FILE" "$STAGE/$DEST.new"
cmp -s "$KEY_FILE" "$STAGE/$DEST.new" || { echo "staging copy differs" >&2; exit 1; }
nemohermes "$SANDBOX" exec -- mkdir -p /sandbox/keeper/secrets
nemohermes "$SANDBOX" exec -- chmod 700 /sandbox/keeper/secrets
nemohermes "$SANDBOX" upload "$STAGE/$DEST.new" /sandbox/keeper/secrets/
nemohermes "$SANDBOX" exec -- chmod 600 "/sandbox/keeper/secrets/$DEST.new"
nemohermes "$SANDBOX" exec -- mv -f "/sandbox/keeper/secrets/$DEST.new" "/sandbox/keeper/secrets/$DEST"
nemohermes "$SANDBOX" exec -- chmod 600 "/sandbox/keeper/secrets/$DEST"
echo "Installed $DEST in the sandbox secrets directory (contents hidden)."
