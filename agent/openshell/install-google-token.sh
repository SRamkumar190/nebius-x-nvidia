#!/usr/bin/env bash
# Run in Ubuntu/WSL with a token created by scripts/google_oauth.py on Windows.
# Usage: bash agent/openshell/install-google-token.sh TOKEN_JSON [sandbox]
export PATH="$HOME/.local/bin:$PATH"
if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1; fi
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 TOKEN_JSON [sandbox]" >&2
  exit 2
fi
TOKEN="$1"
SANDBOX="${2:-keeper}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$TOKEN" ] && [ ! -L "$TOKEN" ] || { echo "token must be a regular, non-symlink file" >&2; exit 1; }
command -v nemohermes >/dev/null || { echo "nemohermes not found in this WSL environment" >&2; exit 1; }
python3 "$ROOT/scripts/validate_google_token.py" "$TOKEN"

# OpenShell uploads from /mnt/c can arrive as zero bytes. Stage on the Linux
# filesystem, verify the copy, and keep both the directory and file private.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
chmod 700 "$STAGE"
install -m 600 "$TOKEN" "$STAGE/google-token.json.new"
cmp -s "$TOKEN" "$STAGE/google-token.json.new" || { echo "token staging copy differs" >&2; exit 1; }
nemohermes "$SANDBOX" exec -- mkdir -p /sandbox/keeper/secrets
nemohermes "$SANDBOX" exec -- chmod 700 /sandbox/keeper/secrets
nemohermes "$SANDBOX" upload "$STAGE/google-token.json.new" /sandbox/keeper/secrets/
nemohermes "$SANDBOX" exec -- chmod 600 /sandbox/keeper/secrets/google-token.json.new
nemohermes "$SANDBOX" exec -- mv -f /sandbox/keeper/secrets/google-token.json.new /sandbox/keeper/secrets/google-token.json
nemohermes "$SANDBOX" exec -- chmod 600 /sandbox/keeper/secrets/google-token.json
echo "Google token installed at /sandbox/keeper/secrets/google-token.json (contents hidden)."
