# Keeper

Keeper is an always-on personal assistant for students, built for the Personal AI track of the Nebius x NVIDIA Global AI Hackathon. It reads a demo inbox and calendar, keeps an eye out for internships and hackathons, and reports back over Telegram. When you correct it, it writes the correction down as a skill so it doesn't make the same mistake twice.

It runs as a Hermes agent inside NVIDIA OpenShell, set up with NemoClaw. Inference goes to Nemotron 3 models (Nano, Super and Ultra) on Nebius Token Factory.

## Status

- **Phase 1, feasibility:** done. The verdict was go; see [docs/phase1-report.md](docs/phase1-report.md).
- **Phase 2, the working assistant:** in progress. Items 1 to 3 are done: repo scaffold, model router, and memory and skills ([item 3 report](docs/phase2-item3-report.md)). Next are inbox and calendar triage, the opportunity radar, and the OpenShell network policy.

## Layout

| Folder | What goes in it |
| --- | --- |
| `agent/` | Hermes configuration for the `keeper` sandbox (persona, config) |
| `router/` | Picks Nano, Super or Ultra per task and logs every call to SQLite |
| `skills/` | Keeper's skills as markdown: built-in triage and radar, plus skills learned from corrections |
| `memory/` | Long-term memory store (markdown files on the sandbox's persistent volume) |
| `dashboard/` | Phase 3 view of model usage, latency and cost |
| `demo/` | Demo script and sample data. Never real inbox content. |
| `docs/` | Setup steps, phase reports |
| `scripts/` | Developer utilities, including the phase 1 Token Factory probe |

## Setup

1. Install NemoClaw with the Hermes agent and connect it to Token Factory by following [docs/phase1-nemoclaw.md](docs/phase1-nemoclaw.md).
2. For local development, copy `.env.example` to `.env` and fill in your keys. Inside the sandbox, the OpenShell gateway holds the keys instead.

## Feedback

[NOTES_FEEDBACK.md](NOTES_FEEDBACK.md) logs everything that broke or was confusing in Token Factory, NemoClaw, OpenShell, Hermes and Nemotron while building this.

## License

MIT. See [LICENSE](LICENSE).
