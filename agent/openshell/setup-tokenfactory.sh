#!/usr/bin/env bash
# One-time setup, run in WSL from the repo root:
#   bash agent/openshell/setup-tokenfactory.sh [sandbox]
# Gives Keeper's router direct access to all three Nemotron models. The
# sandbox's inference.local route rewrites every request to one model.
# NemoClaw puts nemohermes and openshell in ~/.local/bin, and nemohermes runs
# on nvm's Node. Load both so this also works from `bash script.sh` in PowerShell.
export PATH="$HOME/.local/bin:$PATH"
if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1; fi
set -euo pipefail
for tool in nemohermes openshell; do
  command -v "$tool" >/dev/null || { echo "$tool not found. Run this from the Ubuntu (WSL) window where NemoClaw is installed." >&2; exit 1; }
done
SANDBOX="${1:-keeper}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROFILE="$HERE/tokenfactory-keeper-v1.yaml"
PROVIDER=keeper-tokenfactory

echo "== 1/4 check and import the provider profile"
openshell provider profile lint -f "$PROFILE"
openshell provider profile import -f "$PROFILE" || echo "   (import failed; if it says the profile already exists, that's fine)"

echo "== 2/4 create the provider from your Token Factory key"
if openshell provider list 2>/dev/null | grep -q "$PROVIDER"; then
  echo "   $PROVIDER already exists, skipping"
else
  if [ -z "${TOKENFACTORY_API_KEY:-}" ]; then
    read -rsp "   Token Factory API key (input hidden): " TOKENFACTORY_API_KEY; echo
  fi
  export TOKENFACTORY_API_KEY
  openshell provider create --name "$PROVIDER" --type tokenfactory-keeper-v1 --from-existing
  unset TOKENFACTORY_API_KEY
fi

echo "== 3/4 attach it to sandbox '$SANDBOX'"
openshell sandbox provider attach "$SANDBOX" "$PROVIDER"

echo "== 4/4 allow Token Factory in the sandbox network policy"
nemohermes "$SANDBOX" policy add --from-file "$HERE/policies/keeper-tokenfactory.yaml" --yes

echo
echo "Done. Restart the sandbox so new processes get the key placeholder:"
echo "  nemohermes $SANDBOX stop && nemohermes $SANDBOX start"
