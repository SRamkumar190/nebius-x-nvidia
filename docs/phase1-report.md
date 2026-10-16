# Phase 1 report: feasibility

Dates: October 12 to 16, 2026.

Verdict: **go.** NemoClaw + Hermes + Nebius Token Factory works end to end on Windows 11 / WSL2. We don't need the custom agent loop fallback.

## What we tested

| Check | Result |
| --- | --- |
| Token Factory chat, called directly (`test_tokenfactory.py`) | Nano, Super and Ultra all answer |
| Token Factory tool calling, called directly | All three return a structured `tool_calls` entry with `finish_reason=tool_calls` and valid JSON arguments |
| NemoClaw onboarding against Token Factory | `Inference smoke passed` and `Inference route set` for `compatible-endpoint` / `nvidia/nemotron-3-super-120b-a12b` |
| Agent running in the sandbox | `Hermes Agent: running`, Hermes 0.21.3, API health `ok` |
| Agent answers a message | Yes, through `nemohermes launch keeper` and through `connect` then `hermes` |
| Tool call through Hermes inside OpenShell | Yes. Super called the memory tool, and the codeword showed up in `/sandbox/.hermes/memories/` when checked with `grep` |
| Memory across a restart | Yes. After `nemohermes keeper stop` and `start`, the file still had the codeword, and a new session answered `PELICAN-7342` |

## Did Nemotron tool calling work through NemoClaw?

Yes. Two separate pieces of evidence:

1. Onboarding only finishes after NemoClaw's provider check passes against the endpoint, and NVIDIA's docs say that check includes a structured tool call.
2. The memory test was a real tool call. Nemotron 3 Super, running inside the sandbox, called Hermes's memory tool. The request went out through `inference.local` and the OpenShell gateway to Token Factory, and the tool's write reached disk. A model that only claimed to save would have left the file empty.

## Current setup

- Sandbox `keeper`, Hermes 0.21.3, NemoClaw installed from the `lkg` channel.
- Inference: provider `compatible-endpoint`, base URL `https://api.tokenfactory.us-central1.nebius.com/v1`, model `nvidia/nemotron-3-super-120b-a12b`. Hermes auto-detected a 131.1K context window.
- The API key is stored with the OpenShell gateway. The sandbox only sees a placeholder.
- Policy tier is Balanced (npm, pypi, huggingface, brew-balanced). There's no web search, no messaging channels and no resource profile yet.
- Hermes reports 25 tools and 54 skills built in.

## Things to carry into phase 2

- **Hermes's built-in memory is small.** MEMORY.md holds about 2,200 characters and USER.md about 1,375, according to the Hermes memory docs for the pinned release. That's fine for a few preferences. It won't hold anything like inbox history or task lists, so Keeper will need its own storage for those.
- **Hermes loads memory when a session starts.** A fact saved mid-session only shows up in the next one. Telegram and dashboard sessions have to be reset with `/new`, and an open issue on Hermes 0.21.3 ([NemoClaw #12547](https://github.com/NVIDIA/NemoClaw/issues/12547)) says they don't reset on their own.
- **The port 8642 problem may come back.** After a reboot, a leftover `openshell` process can hold the port again. The fix: run `sudo ss -ltnp 'sport = :8642'`, kill the `openshell` PID it shows, then run `nemohermes keeper recover`.
- **WSL is short on resources.** Onboarding warned that the container runtime is under-provisioned. Builds and rebuilds will be slow unless `.wslconfig` gives WSL more memory.
- **Only stop/start has been tested.** We haven't tested `rebuild` or `destroy`. Run `nemohermes backup-all` before either.
- **Super is the right default model.** Nano spent about 250 reasoning tokens on a one-sentence reply in the direct probe and wasn't faster. Ultra is worth trying later for harder tasks, using `nemohermes inference set --provider compatible-endpoint --model nvidia/Nemotron-3-Ultra-550b-a55b --sandbox keeper`.
- **Adding integrations later needs network policy presets**, added with `nemohermes keeper policy add`:
  - Gmail and Telegram have presets in the list.
  - Tavily has a preset too, and web search can also be turned on during onboarding.

## Fallback (not needed)

If NemoClaw stops working before the deadline, the fallback from the original plan still applies: a small Python agent loop using the `openai` client against Token Factory, with our own tool dispatch and a memory file, run inside an OpenShell sandbox. `keeper_probe/` already has the client setup and a working tool-call round trip to build from.
