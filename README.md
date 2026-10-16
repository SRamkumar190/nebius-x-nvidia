# Keeper

Personal AI track entry for the Nebius x NVIDIA Global AI Hackathon. Keeper is an always-on assistant meant to run as a Hermes agent inside NVIDIA OpenShell (via NemoClaw), with Nebius Token Factory doing inference.

Phase 1 (feasibility) is done. The verdict is go: see `docs/phase1-report.md`. Install and test steps are in `docs/phase1-nemoclaw.md`, and build notes for the feedback submission are in `NOTES_FEEDBACK.md`.

## Phase 1: Token Factory probe

`test_tokenfactory.py` lists the Token Factory catalog, then sends each Nemotron model one plain chat call and one call with a `get_weather` tool. It prints latency, token counts, and whether a real `tool_calls` entry came back.

PowerShell:

```powershell
py -m pip install -r requirements.txt
$env:TOKENFACTORY_API_KEY = "your-key"
py test_tokenfactory.py
```

Exit code is 0 only when every model answered and returned a tool call.

Optional overrides:

| Variable | Default |
| --- | --- |
| `KEEPER_MODELS` | the three Nemotron 3 ids in `keeper_probe/config.py`, comma separated |
| `TOKENFACTORY_BASE_URL` | `https://api.tokenfactory.us-central1.nebius.com/v1/` |
| `KEEPER_MAX_TOKENS` | `1024` (reasoning models can burn tokens thinking before they answer) |
| `KEEPER_TIMEOUT_S` | `120` |

If a model id isn't in the catalog, the script skips it and prints the closest ids that are. A case mismatch gets corrected automatically.

If the tool line says the call "came back as TEXT in content", the model tried to call the tool but the server returned it as plain text. An agent loop would need to parse that text itself.
