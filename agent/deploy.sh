#!/usr/bin/env bash
# Copy Keeper's code, skills and persona into the sandbox. Run in WSL from the repo root:
#   bash agent/deploy.sh [sandbox]
# Safe to rerun after every change.
set -euo pipefail
SANDBOX="${1:-keeper}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
nh() { nemohermes "$SANDBOX" "$@"; }

echo "== stage code"
mkdir -p "$STAGE/app"
cp -r "$ROOT/router" "$ROOT/memory" "$ROOT/skills" "$STAGE/app/"
rm -rf "$STAGE/app/skills/hermes"
find "$STAGE/app" -name __pycache__ -prune -exec rm -rf {} +

echo "== upload code and the keeper command"
nh exec -- mkdir -p /sandbox/keeper/app /sandbox/keeper/bin /sandbox/keeper/data /sandbox/.hermes/skills/keeper
nh upload "$STAGE/app/" /sandbox/keeper/app/
nh upload "$ROOT/agent/bin/keeper" /sandbox/keeper/bin/
nh exec -- chmod +x /sandbox/keeper/bin/keeper

echo "== install Keeper's skills"
for dir in "$ROOT"/skills/hermes/*/; do
  name="$(basename "$dir")"
  nh upload "$dir" "/sandbox/.hermes/skills/keeper/$name/"
  echo "   $name"
done

echo "== merge the Keeper section into SOUL.md"
mkdir -p "$HOME/keeper-backups"
if nh download /sandbox/.hermes/SOUL.md "$STAGE/" >/dev/null 2>&1 && [ -f "$STAGE/SOUL.md" ]; then
  cp "$STAGE/SOUL.md" "$HOME/keeper-backups/SOUL.md.$(date +%Y%m%d-%H%M%S)"
else
  : > "$STAGE/SOUL.md"
fi
python3 - "$STAGE/SOUL.md" "$ROOT/agent/SOUL.md" <<'PY'
import re, sys
current, keeper = (open(p, encoding="utf-8").read() for p in sys.argv[1:3])
current = re.sub(r"\n*<!-- keeper:start -->.*?<!-- keeper:end -->\n*", "\n", current, flags=re.S).rstrip()
open(sys.argv[1], "w", encoding="utf-8").write((current + "\n\n" if current else "") + keeper)
PY
nh upload "$STAGE/SOUL.md" /sandbox/.hermes/

echo "== Hermes settings"
# Every skill write waits for /skills approve <id>.
nh exec -- hermes config set skills.write_approval true
# Let terminal commands see the Token Factory placeholder. Hermes strips
# key-like variables by default; the real key never enters the sandbox.
nh exec -- hermes config set terminal.env_passthrough '["TOKENFACTORY_API_KEY"]'

echo
echo "Deployed. Restart Hermes so it picks up SOUL.md and the setting:"
echo "  nemohermes $SANDBOX stop && nemohermes $SANDBOX start"
