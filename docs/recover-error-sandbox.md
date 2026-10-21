# Recovering a sandbox stuck in `Phase: Error`

On 2026-10-21, Docker Desktop crashed during a routine `nemohermes keeper stop && start` ("vpnkit-bridge handshake failed"). The sandbox container exited, and OpenShell 0.0.116 marked the sandbox `Error`. In that version, `Error` can't be undone:

- `start` is refused: "sandbox must be Stopped to start"
- `stop` is refused: "sandbox must be Ready to stop"
- `recover` can't help either, and a Hermes `rebuild` needs a running sandbox to back up

The only way back is to back up with Docker, re-create the sandbox and restore. Everything below runs in Ubuntu (WSL) from the repo folder, unless marked PowerShell.

## 1. Get Docker healthy

- Start Docker Desktop and wait for "Engine running". If it shows a vpnkit or engine error, click **Quit**. **Never** use "Reset to factory defaults" or "Clean / Purge data": both delete the sandbox and its storage.
- Run `wsl --shutdown` in PowerShell, then restart Docker Desktop. If that doesn't help, restart Windows.
- `docker info > /dev/null && echo docker-ok` must print `docker-ok`.

## 2. Back up straight from the container

This works even while the container is stopped.

```bash
CID=$(docker ps -aq --filter "label=openshell.ai/sandbox-name=keeper")
mkdir -p ~/keeper-rescue/hermes
docker cp $CID:/sandbox/keeper ~/keeper-rescue/
docker cp $CID:/sandbox/.hermes/skills ~/keeper-rescue/hermes/
docker cp $CID:/sandbox/.hermes/state.db ~/keeper-rescue/hermes/
docker cp $CID:/sandbox/SOUL.md ~/keeper-rescue/
cp -r ~/keeper-rescue /mnt/c/Users/sidis/keeper-rescue
```

The backup contains the Token Factory key file, so keep it out of the repo folder.

## 3. If NemoClaw commands hang on a lock

If you see "Timed out waiting for the sandbox mutation lock … (owner PID N)", first check that `ps -p N` shows no process. Then move the stale lock files aside:

```bash
for f in $(grep -rls N ~/.nemoclaw/state 2>/dev/null | grep -i lock); do mv "$f" "$f.stale"; done
```

## 4. Re-create and restore

```bash
nemohermes keeper destroy
export NEMOCLAW_NO_EXPRESS=1
nemohermes onboard --name keeper
bash agent/openshell/setup-tokenfactory.sh
bash agent/deploy.sh
bash agent/restore.sh
nemohermes keeper stop && nemohermes keeper start
```

Use the same onboarding answers as in `docs/phase1-nemoclaw.md`: Other OpenAI-compatible endpoint, the Token Factory URL, `nvidia/nemotron-3-super-120b-a12b`, no web search, no messaging, no resource profile, and the Balanced presets.

`setup-tokenfactory.sh` skips the profile and provider, which already exist on the gateway. It only attaches the provider to the new sandbox and re-adds the network preset.

`restore.sh` puts back the memory, the router log, the key file and the learned skills, and re-pins each skill's rule into SOUL.md. Chat history (`state.db`) isn't restored.

## 5. Check

```bash
nemohermes keeper exec -- /sandbox/keeper/bin/keeper router smoke
nemohermes keeper exec -- /sandbox/keeper/bin/keeper memory topics
nemohermes keeper exec -- /sandbox/keeper/bin/keeper skills list
nemohermes keeper exec -- /sandbox/keeper/bin/keeper skills prompt-check
```
