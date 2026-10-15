# Phase 1: NemoClaw + Hermes on Token Factory

Steps for tasks 2 and 3 on Windows 11. They come from the NVIDIA/NemoClaw docs on `main` as of 2026-10-14 (release v0.0.134). If an answer doesn't match what you see on screen, trust the screen and write the difference down in `NOTES_FEEDBACK.md`.

NemoClaw does not run in PowerShell. You only need PowerShell for steps 1 and 2. Everything after that runs inside the Ubuntu (WSL) shell.

## Task 2: install and point it at Token Factory

### 1. Check WSL and Docker (PowerShell)

```powershell
wsl -l -v
```

You want `Ubuntu-24.04` listed with VERSION `2`. If it isn't there, run NVIDIA's bootstrap script. It turns on WSL2, installs Ubuntu 24.04 and Docker Desktop, and enables Docker's WSL integration. It does not install NemoClaw.

```powershell
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/NVIDIA/NemoClaw/main/scripts/bootstrap-windows.ps1' -OutFile "$env:TEMP\bootstrap-windows.ps1"; powershell.exe -ExecutionPolicy Bypass -File "$env:TEMP\bootstrap-windows.ps1"
```

In Docker Desktop, open Settings > Resources > WSL integration and switch on Ubuntu-24.04. Keep Docker Desktop running for everything below.

### 2. Open Ubuntu (PowerShell)

```powershell
wsl -d Ubuntu-24.04
```

From here on, every command goes into this Ubuntu shell.

### 3. Pre-flight (Ubuntu)

```bash
docker info > /dev/null && echo docker-ok
free -h
df -h ~
```

You need to see `docker-ok`, at least 8 GB of total memory (16 GB is recommended) and 20 GB of free disk (40 GB recommended). With less than 8 GB, the image build can get killed for running out of memory. If `free -h` shows less, raise the WSL memory cap. Create `C:\Users\sidis\.wslconfig` containing:

```
[wsl2]
memory=12GB
```

Then run `wsl --shutdown` in PowerShell and reopen Ubuntu.

### 4. Install and onboard (Ubuntu)

```bash
export NEMOCLAW_NO_EXPRESS=1
curl -fsSL https://www.nvidia.com/nemoclaw.sh | NEMOCLAW_AGENT=hermes NEMOCLAW_SANDBOX_NAME=keeper bash
```

`NEMOCLAW_NO_EXPRESS=1` matters on WSL. Without it, the installer offers an "Express" setup, and pressing Enter there silently picks a local Ollama model instead of Token Factory.

Answer the onboarding prompts like this:

| Prompt | Answer |
| --- | --- |
| Third-party software notice | Accept |
| Inference provider | Other OpenAI-compatible endpoint |
| Base URL | `https://api.tokenfactory.us-central1.nebius.com/v1` |
| Model | `nvidia/nemotron-3-super-120b-a12b` |
| API key | Paste your Token Factory key at the hidden prompt |
| Sandbox name | `keeper` (already set by the command) |
| Review screen | Apply |
| Tavily search, messaging channels | Skip for now |
| Network policy tier | Balanced (the default) |

What happens behind those answers:

- The key is stored with the OpenShell gateway on your machine. It never goes into the sandbox image, and the agent only ever sees a placeholder.
- The sandbox doesn't need its own network rule for Token Factory. Hermes sends requests to `inference.local`, and the gateway forwards them to Token Factory.
- During onboarding, NemoClaw sends a test request and only continues if Token Factory returns a structured tool call. So if onboarding gets past the provider check, tool calling works through NemoClaw, which answers most of task 4.
- The first build takes several minutes. The image is about 2.4 GB.
- If the installer says it added you to the `docker` group, run `newgrp docker` and run the install command again.

### 5. Confirm it worked (Ubuntu)

```bash
command -v nemohermes
nemohermes keeper status
nemohermes inference get
curl -sf http://127.0.0.1:8642/health
```

What to expect:

- `status` shows the inference check as healthy. It sends one real request to Token Factory.
- `inference get` shows provider `compatible-endpoint` and the Super model.
- The health check prints `{"status":"ok","platform":"hermes-agent"}`.

If `nemohermes` isn't found, run `source ~/.bashrc` or open a new Ubuntu window. If the health check can't connect, run `nemohermes keeper recover` and try again.

### If the installer reports an OpenShell gateway version mismatch

This happens when a standalone OpenShell from apt is already installed. Its background gateway service runs a different version from the one NemoClaw pins. First check that the old gateway isn't managing anything you need:

```bash
dpkg -l | grep -i openshell
/usr/bin/openshell sandbox list 2>/dev/null || echo "no old CLI"
```

Then remove it and run the install again:

```bash
systemctl --user stop openshell-gateway.service
sudo apt remove openshell
systemctl --user daemon-reload
export NEMOCLAW_NO_EXPRESS=1
curl -fsSL https://www.nvidia.com/nemoclaw.sh | NEMOCLAW_AGENT=hermes NEMOCLAW_SANDBOX_NAME=keeper bash
```

If onboarding then says `migration N was previously applied`, NemoClaw's older gateway has found the newer one's database. Run the stop/move commands it prints.

### If onboarding says "DNS-backed HTTPS endpoint is not supported"

NemoClaw's docs contradict each other on this. The troubleshooting page says a custom endpoint with a public hostname "can" be rejected during onboarding. The current source code suggests Token Factory will be accepted. If you do get this error:

1. Onboard with NVIDIA Endpoints instead, using a free key from build.nvidia.com.
2. Switch the sandbox over to Token Factory:

```bash
read -rs COMPATIBLE_API_KEY && export COMPATIBLE_API_KEY
nemohermes inference set --provider compatible-endpoint --model nvidia/nemotron-3-super-120b-a12b --endpoint-url https://api.tokenfactory.us-central1.nebius.com/v1 --credential-env COMPATIBLE_API_KEY --inference-api openai-completions --sandbox keeper
unset COMPATIBLE_API_KEY
```

`read -rs` waits for you to paste the key without showing it. This route has a catch: each response has 30 seconds in total, so long Super or Ultra answers can get cut off.

### Known WSL problems (open issues as of Oct 2026)

- The sandbox never becomes Ready, with `ControlSupervisorStartFailed`. Reported workarounds are turning on Docker Desktop host networking, or editing the gateway config. See [OpenShell #3880](https://github.com/NVIDIA/OpenShell/issues/3880).
- The Hermes chat accepts a prompt but never replies on WSL2 + Docker Desktop. There's no fix yet. Check `nemohermes keeper logs --follow`. See [NemoClaw #11398](https://github.com/NVIDIA/NemoClaw/issues/11398).
- Port 8642 shows "connection refused" after onboarding. Run `nemohermes keeper recover`. See [NemoClaw #10385](https://github.com/NVIDIA/NemoClaw/issues/10385).
- Ports 8080, 8642 and 18789 must be free. Other Docker containers sometimes use 8080.

### Write it down

Every time something fails or needs a workaround, add it to `NOTES_FEEDBACK.md` under "NemoClaw / OpenShell / Hermes": what you ran, the exact error (with keys removed), and what fixed it. Judges score the feedback, and anything you don't write down now is hard to remember later.

## Task 3: talk to it, then test memory across a restart

Only start this once task 2 passes.

### 1. Say hello

```bash
nemohermes launch keeper
```

That opens the Hermes chat in your terminal. Type `/exit` to leave. There's also a browser dashboard: run `nemohermes keeper dashboard-url --quiet` and open the address it prints. The docs don't say whether a Windows browser can reach it, so try it and note what happens.

### 2. Give it one fact

In the chat, send:

> Use your memory tool to save this fact about me: my Keeper test codeword is PELICAN-7342. Only say SAVED after the tool call succeeds.

Then type `/exit`.

### 3. Check that it really saved

```bash
nemohermes keeper exec -- grep -rn PELICAN-7342 /sandbox/.hermes/memories/
```

Models sometimes say "saved" without actually calling the tool. If `grep` finds nothing, the memory tool was never called. That's a tool-calling failure through Hermes, so note it, because it matters for task 4.

### 4. Back up, then restart

```bash
nemohermes backup-all
nemohermes keeper stop
nemohermes keeper start
```

Take the backup first because [NemoClaw #7199](https://github.com/NVIDIA/NemoClaw/issues/7199) reported a stop/start wiping memory on an older release.

### 5. Ask for it back in a new session

```bash
nemohermes keeper exec -- grep -rn PELICAN-7342 /sandbox/.hermes/memories/
nemohermes launch keeper
```

In the chat, ask: "What is my Keeper test codeword?"

Hermes loads memory when a session starts, which is why this uses a fresh `launch` rather than the old chat. The test passes if the reply says PELICAN-7342 and `grep` still finds it in the file.
