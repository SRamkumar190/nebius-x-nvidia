# Telegram delivery and Tavily search

## Telegram bot and gateway

Create a disposable bot through @BotFather. In the WSL host with NemoClaw, run `bash agent/openshell/setup-telegram.sh keeper`. It prompts privately for the bot token and for a numeric allowed Telegram user ID, then adds the Telegram channel, rebuilds the sandbox, and applies the Telegram policy preset. The setup follows [NemoClaw's host-side channel process](https://docs.nvidia.com/nemoclaw/user-guide/hermes/network-policy/integration-policy-examples); do not edit the generated gateway configuration inside the sandbox. Send `/start` to the bot from the allowed account. This repository has no live bot credential, so setup cannot run until the operator supplies one.

The Keeper product adapter sends directly through the Telegram Bot API using a private token file. Install a separate mode-600 copy from a key file outside the checkout: `bash agent/openshell/install-provider-key.sh telegram /path/outside/repo/telegram-bot.key keeper`. Construct `LiveTelegram.from_token_file(Path("/sandbox/keeper/secrets/telegram-bot.key"), Path("/sandbox/keeper/data/keeper.db"))`. The same bot token may be used by Hermes gateway for inbound conversations and Keeper for outbound `sendMessage`; only the gateway polls updates. Deploy Keeper code again after a NemoClaw rebuild if the rebuilt image lacks it.

`send_message(recipient_reference, text, idempotency_key=...)` expects the destination chat ID (or a supported `@username`). It writes a `notification_records` row before making a request. Successful delivery stores Telegram's message ID, UTC delivery time, and `delivered` status. Replaying the same key and payload returns that saved ID without another call. Reusing a key for another recipient or text raises `IdempotencyConflict`. Telegram has no Bot API send idempotency parameter, so a timeout, transport failure, 5xx, or malformed success leaves the row `pending` with an uncertainty note; a repeat call stops for operator reconciliation instead of risking a duplicate. A confirmed 429 uses `retry_after` and bounded retries; after exhaustion it logs `failed`, allowing a later call with the same key. Rejected requests also log `failed`. The adapter does not log the message body or token.

## Tavily search

Put a Tavily key in a private file outside the checkout, then run `bash agent/openshell/install-provider-key.sh tavily /path/outside/repo/tavily.key keeper`. Apply the `tavily` network preset to the sandbox with `nemohermes keeper policy add tavily --yes`; [NemoClaw documents this preset](https://docs.nvidia.com/nemoclaw/user-guide/hermes/network-policy/integration-policy-examples). Construct `LiveTavily.from_key_file(Path("/sandbox/keeper/secrets/tavily.key"))`.

`search(query, limit=5)` makes one `POST /search` call with an 8-second transport timeout, basic depth, no generated answer, and no raw page content. It accepts 1–20 results and truncates an oversized provider response to the requested limit. It returns URL, title, up to 1,000 characters of snippet, and source host. Empty or malformed provider data raises an adapter error; 401/403 is an auth error, 429 a rate limit, and timeout/5xx an unavailable provider. A timeout is not silently treated as an empty search.

For a fully offline demo, `load_fakes(Path("demo/fixtures/adapter_responses.json"))` returns `FakeTavily` as the fourth adapter. The exact query `software internship 2027` returns the synthetic `careers.example.test` internship hit in fixture order. Unknown queries return `()`. The URL, organization, and email examples are intentionally fictional.

```python
from pathlib import Path
from keeper_core.fakes import load_fakes

_, _, _, tavily, _ = load_fakes(Path("demo/fixtures/adapter_responses.json"))
print(tavily.search("software internship 2027", limit=1)[0].title)
# Software Engineering Intern
```

Run `python3 -m unittest tests.test_tavily_live tests.test_adapters` to exercise live-adapter behavior against a deterministic transport and the checked-in fake responses without spending Tavily credits or contacting Telegram.
