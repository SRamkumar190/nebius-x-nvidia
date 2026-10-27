# agent

Keeper runs on the Hermes agent inside NVIDIA OpenShell, set up with NemoClaw. This folder has no custom agent loop. Instead it holds what gets layered onto Hermes in the `keeper` sandbox.

| File | What it does |
| --- | --- |
| `SOUL.md` | Keeper's persona and hard rules. `deploy.sh` puts it at the top of `/sandbox/.hermes/runtime/SOUL.md` (the one Hermes reads), `/sandbox/.hermes/SOUL.md` and `/sandbox/SOUL.md` (merge code in `skills/soul.py`) |
| `bin/keeper` | Keeper's command inside the sandbox (`keeper memory`, `keeper skills`, `keeper router`) |
| `deploy.sh` | Copies code, skills and persona into the sandbox, turns on Hermes's skill write-approval gate and adds the `/teach`, `/keep` and `/drop` quick commands. Rerun it after changes. |
| `restore.sh` | Puts memory, the router log, the key file and learned skills back into a re-created sandbox |
| `openshell/tokenfactory-keeper-v1.yaml` | OpenShell provider profile that gives the router all three Nemotron models without putting the key in the sandbox |
| `openshell/policies/keeper-tokenfactory.yaml` | Network policy preset that opens Token Factory to Keeper's Python only |
| `openshell/setup-tokenfactory.sh` | One-time setup: import the profile, create and attach the provider, apply the policy |
| `openshell/install-google-token.sh` | Install the demo Google OAuth token from WSL into the private sandbox secrets directory |

Steps and proof checks are in `docs/phase2-memory-skills.md`. Install and sandbox setup are in `docs/phase1-nemoclaw.md`; Google authorization is in `docs/google-authorization.md`.
