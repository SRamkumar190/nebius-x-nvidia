# agent

Keeper runs on the Hermes agent inside NVIDIA OpenShell, set up with NemoClaw. This folder has no custom agent loop. Instead it holds what gets layered onto Hermes in the `keeper` sandbox.

| File | What it does |
| --- | --- |
| `SOUL.md` | Keeper's persona and hard rules, merged into `/sandbox/.hermes/SOUL.md` between `keeper:start` and `keeper:end` markers |
| `bin/keeper` | Keeper's command inside the sandbox (`keeper memory`, `keeper skills`, `keeper router`) |
| `deploy.sh` | Copies code, skills and persona into the sandbox and turns on Hermes's skill write-approval gate. Rerun it after changes. |
| `openshell/tokenfactory-keeper-v1.yaml` | OpenShell provider profile that gives the router all three Nemotron models without putting the key in the sandbox |
| `openshell/policies/keeper-tokenfactory.yaml` | Network policy preset that opens Token Factory to Keeper's Python only |
| `openshell/setup-tokenfactory.sh` | One-time setup: import the profile, create and attach the provider, apply the policy |

Steps and proof checks are in `docs/phase2-memory-skills.md`. Install and sandbox setup are in `docs/phase1-nemoclaw.md`.
