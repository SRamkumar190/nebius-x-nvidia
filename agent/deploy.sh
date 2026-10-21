#!/usr/bin/env bash
# Copy Keeper's code, skills and persona into the sandbox. Run in WSL from the repo root:
#   bash agent/deploy.sh [sandbox]
# Safe to rerun after every change.
# NemoClaw puts nemohermes and openshell in ~/.local/bin, and nemohermes runs
# on nvm's Node. Load both so this also works from `bash script.sh` in PowerShell.
export PATH="$HOME/.local/bin:$PATH"
if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1; fi
set -euo pipefail
for tool in nemohermes openshell; do
  command -v "$tool" >/dev/null || { echo "$tool not found. Run this from the Ubuntu (WSL) window where NemoClaw is installed." >&2; exit 1; }
done
SANDBOX="${1:-keeper}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
nh() { nemohermes "$SANDBOX" "$@"; }

# Stage everything on the Linux filesystem first. OpenShell's upload reads
# files under /mnt/c (the Windows drive) as all zero bytes, so nothing is
# uploaded straight from the repo checkout.
echo "== stage code, the keeper command and skills"
mkdir -p "$STAGE/app" "$STAGE/bin" "$STAGE/skills"
cp -r "$ROOT/router" "$ROOT/memory" "$ROOT/skills" "$STAGE/app/"
rm -rf "$STAGE/app/skills/hermes"
find "$STAGE/app" -name __pycache__ -prune -exec rm -rf {} +
cp "$ROOT/agent/bin/keeper" "$STAGE/bin/keeper"
chmod +x "$STAGE/bin/keeper"
cp -r "$ROOT"/skills/hermes/*/ "$STAGE/skills/"

# Upload copies a folder *into* the destination, so each folder goes to its
# parent. Replace Keeper's code and shipped skills, but leave data/ and any
# skills you approved alone.
echo "== upload code and the keeper command"
nh exec -- rm -rf /sandbox/keeper/app /sandbox/keeper/bin
nh exec -- mkdir -p /sandbox/keeper/data /sandbox/.hermes/skills/keeper
nh upload "$STAGE/app" /sandbox/keeper/
nh upload "$STAGE/bin" /sandbox/keeper/
nh exec -- chmod +x /sandbox/keeper/bin/keeper

echo "== install Keeper's skills"
for dir in "$STAGE"/skills/*/; do
  name="$(basename "$dir")"
  nh exec -- rm -rf "/sandbox/.hermes/skills/keeper/$name"
  nh upload "${dir%/}" /sandbox/.hermes/skills/keeper/
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
current = re.sub(r"\n*<!-- keeper:start -->.*?<!-- keeper:end -->\n*", "\n", current, flags=re.S).strip()
# Keeper goes first: the model takes its identity from the top of SOUL.md.
open(sys.argv[1], "w", encoding="utf-8").write(keeper.rstrip() + "\n\n" + current + "\n" if current else keeper)
PY
nh upload "$STAGE/SOUL.md" /sandbox/.hermes/

echo "== Hermes settings"
# Every skill write waits for /skills approve <id>.
nh exec -- hermes config set skills.write_approval true
# Let terminal commands see the Token Factory placeholder. Hermes strips
# key-like variables by default; the real key never enters the sandbox.
nh exec -- hermes config set terminal.env_passthrough '["TOKENFACTORY_API_KEY"]'
# /teach, /keep and /drop: typed by the user, run by Hermes without the model.
nh exec -- hermes config set quick_commands '{"teach": {"type": "exec", "command": "/sandbox/keeper/bin/keeper skills teach"}, "keep": {"type": "exec", "command": "/sandbox/keeper/bin/keeper skills keep"}, "drop": {"type": "exec", "command": "/sandbox/keeper/bin/keeper skills drop"}}'

echo "== check the deployed files"
nh exec -- /sandbox/keeper/bin/keeper skills list

echo
echo "Deployed. Restart Hermes so it picks up SOUL.md and the setting:"
echo "  nemohermes $SANDBOX stop && nemohermes $SANDBOX start"
