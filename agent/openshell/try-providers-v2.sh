#!/usr/bin/env bash
# Try OpenShell's providers_v2_enabled gateway setting, which may be what makes
# OpenShell swap the TOKENFACTORY_API_KEY placeholder for the real key. If the
# smoke test still fails, the setting is removed again.
#   bash agent/openshell/try-providers-v2.sh [sandbox]
export PATH="$HOME/.local/bin:$PATH"
if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1; fi
set -uo pipefail
SANDBOX="${1:-keeper}"

echo "== turn on providers_v2_enabled"
openshell settings set --global --key providers_v2_enabled --value true || exit 1
nemohermes "$SANDBOX" stop && nemohermes "$SANDBOX" start

echo "== smoke test from inside the sandbox"
if nemohermes "$SANDBOX" exec -- /sandbox/keeper/bin/keeper router smoke; then
  echo
  echo "WORKS: OpenShell now swaps in the key. Keeping the setting."
else
  echo
  echo "Still failing. Removing the setting again."
  openshell settings delete --global --key providers_v2_enabled
  nemohermes "$SANDBOX" stop && nemohermes "$SANDBOX" start
  exit 1
fi
