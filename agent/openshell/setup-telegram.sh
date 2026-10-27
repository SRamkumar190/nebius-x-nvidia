#!/usr/bin/env bash
# Run in the WSL host with NemoClaw installed. The token is read without echo.
# Usage: bash agent/openshell/setup-telegram.sh [sandbox]
export PATH="$HOME/.local/bin:$PATH"
if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1; fi
set -euo pipefail
SANDBOX="${1:-keeper}"
command -v nemohermes >/dev/null || { echo "nemohermes is required in WSL" >&2; exit 1; }
read -rsp "Telegram BotFather token: " TELEGRAM_BOT_TOKEN
echo
read -rp "Allowed Telegram user ID: " TELEGRAM_ALLOWED_IDS
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [[ ! "$TELEGRAM_ALLOWED_IDS" =~ ^[0-9]+$ ]]; then
  echo "A bot token and numeric user ID are required" >&2
  exit 1
fi
export TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_IDS
export TELEGRAM_REQUIRE_MENTION=1
NEMOCLAW_NON_INTERACTIVE=1 nemohermes "$SANDBOX" channels add telegram
unset TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_IDS
nemohermes "$SANDBOX" rebuild
nemohermes "$SANDBOX" policy add telegram --yes
echo "Telegram channel and gateway configured for $SANDBOX. Send /start to the bot and check the gateway."
