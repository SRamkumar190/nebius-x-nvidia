# Keeper build notes and feedback

Problems and workarounds from building Keeper, kept for the hackathon feedback submission.

## Nebius Token Factory

Tested 2026-10-15 from Windows 11 with the `openai` Python SDK against `https://api.tokenfactory.us-central1.nebius.com/v1/`.

The three Nemotron 3 ids follow three different naming conventions in `GET /v1/models`:

| Model | Catalog id |
| --- | --- |
| Nano | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| Super | `nvidia/nemotron-3-super-120b-a12b` |
| Ultra | `nvidia/Nemotron-3-Ultra-550b-a55b` |

I started with `nvidia/nemotron-3-nano-30b-a3b`, which is the pattern the Super id suggests, and got nothing back for it. The ids are case sensitive, so the only way to get them right is to copy them out of the catalog. Workaround: the probe now lists the catalog first and fixes case-only mismatches automatically.

Tool calling worked on the first try for all three. Each returned a proper `tool_calls` entry with `finish_reason=tool_calls` and valid JSON arguments. None returned the call as text, and I didn't need any extra request parameters.

Second run, one call per row:

| Model | Plain chat | Tool call |
| --- | --- | --- |
| Nano | 1.39s, 29 in / 252 out tokens | 1.19s, 293 / 165 |
| Super | 1.12s, 29 / 39 | 0.39s, 375 / 38 |
| Ultra | 0.93s, 29 / 260 | 0.23s, 328 / 59 |

Nano, the smallest model, was the slowest. It spent 252 output tokens on a one-sentence answer, which looks like reasoning tokens being counted in the output. Ultra's plain answer went from 53 output tokens on the first run to 260 on this one, so reasoning length varies a lot between calls. For short assistant replies, it would be worth finding out whether reasoning can be turned off per request.

Asked "what is Nebius Token Factory?" with no context, both models confidently described it as a platform for blockchain tokens. That's expected for a model with no search, but it's why Keeper needs a web search tool (Tavily) before it answers factual questions.

## NemoClaw / OpenShell / Hermes

### Found while reading the docs, before installing

- Nebius Token Factory isn't a built-in inference provider, even though Nebius co-runs this hackathon. It has to go through "Other OpenAI-compatible endpoint", which is listed as "Tested with limitations".
- On WSL the installer offers an Express setup, and pressing Enter picks a local Ollama model. Someone who means to use a hosted provider can easily end up on local Ollama without noticing. I set `NEMOCLAW_NO_EXPRESS=1` to avoid it.
- The docs contradict each other on public HTTPS custom endpoints. `reference/troubleshooting` says "DNS-backed HTTPS endpoint is not supported" can appear during custom-endpoint onboarding. The current onboarding code pins the hostname and accepts it. The fallback (`inference set` after onboarding with another provider) puts a 30-second total deadline on every upstream response.
- The two pages that list accepted `NEMOCLAW_PREFERRED_API` values disagree. The compatible-endpoint page lists `openai-completions` and `openai-responses`. The commands reference says `completions` is the only value it honors.

### Install log

(Add each failure or workaround here as it happens: command, exact error, fix.)

1. 2026-10-15, first run of the Hermes installer on WSL2 (Ubuntu). Node 22.23.3 installed through nvm and the NemoHermes CLI built fine. Then the OpenShell step stopped with:

   ```
   [ERROR] OpenShell gateway version mismatch: NemoClaw installed 0.0.116 at /home/sidis/.local/bin/openshell-gateway, but the existing upstream user service uses 0.1.2 at /usr/bin/openshell-gateway. Align or remove the upstream OpenShell package (for apt installs: sudo apt remove openshell), then rerun the installer.
   ```

   Cause: a standalone OpenShell 0.1.2 from apt was already installed, with its own systemd user service. NemoClaw pins a different gateway build and won't run alongside it. The hackathon brief describes Keeper as running "inside NVIDIA OpenShell", so installing OpenShell first is a natural thing to do, and it leads straight to this error. Nothing in the NemoClaw quickstart warns you not to. Fix: `sudo apt remove openshell` and rerun. The error message itself said exactly what to do, which was good, but the rerun command in the troubleshooting docs leaves out `NEMOCLAW_AGENT=hermes`.

2. 2026-10-15, after removing the apt OpenShell, the installer finished. `nemohermes` wasn't on PATH in the same shell until I ran `source ~/.bashrc` and `export PATH="$HOME/.local/bin:$PATH"`. Not a big deal, but the installer could print that line at the end.

3. `nemohermes onboard` stopped at preflight with "Docker is not reachable". Docker Desktop was installed, but WSL couldn't reach it. Fix: start Docker Desktop, enable WSL integration for this distro, run `wsl --shutdown`, reopen, and check `docker info`. The error message listed exactly those steps, which helped a lot. The resume hint at the end says `nemohermes onboard --resume --name <sandbox>`, but at preflight no sandbox name has been chosen yet, so it's unclear which name to pass.

4. 2026-10-16, after enabling Docker Desktop WSL integration, `nemohermes onboard --name keeper` got past preflight. I chose "Other OpenAI-compatible endpoint" with `https://api.tokenfactory.us-central1.nebius.com/v1` and `nvidia/nemotron-3-super-120b-a12b`. Step 4/8 printed `Inference smoke passed` and `Inference route set` for compatible-endpoint. Onboarding accepted the public HTTPS hostname without the "DNS-backed HTTPS endpoint is not supported" error, so the troubleshooting page's warning about custom-endpoint onboarding looks out of date, at least for the installed release.

5. The review screen warned: "Container runtime is under-provisioned; the sandbox build may take 30+ minutes or stall." It would help if the message said which resource is short (CPU or memory) and what value it wants. On Windows the fix is a `.wslconfig` memory setting, and the NemoClaw docs don't mention that.

6. Onboarding finished. At the resource profile prompt I chose "No profile", so no CPU or memory cap, since the runtime was already flagged as under-provisioned. At the policy presets I kept the Balanced defaults (npm, pypi, huggingface, brew-balanced). The sandbox build didn't stall. Afterwards, `nemohermes keeper status` showed `Hermes Agent: running`. `nemohermes inference get` showed provider compatible-endpoint, model `nvidia/nemotron-3-super-120b-a12b`, endpoint `https://api.tokenfactory.us-central1.nebius.com/v1`. `curl http://127.0.0.1:8642/health` returned `{"status": "ok", "platform": "hermes-agent", "version": "0.21.3"}`. That completes phase 1 task 2.

   Small feedback: the presets list includes `local-memory`, which sounds like Hermes memory but is actually network access to a separate Hindsight memory service on the host. The description is only in the preset YAML, not on the selection screen.

7. 2026-10-16, right after onboarding, `nemohermes launch keeper` failed with "Host port 8642 for 'keeper' is held by a listener that NemoClaw cannot attribute to this sandbox's OpenShell forward" and then "Launch readiness final validation failed due to health". `recover` and `connect` printed the same port warning. `connect` still opened a sandbox shell. `launch` did not.

   `sudo ss -ltnp 'sport = :8642'` showed `openshell` (pid 5991) listening on `0.0.0.0:8642`, but `openshell forward list` said "No active forwards". So an `openshell` forward process was still holding the port, but no forward record pointed to it. Onboarding seems to have left it behind. A health check through that port worked, so it was a real forward to Hermes. Two problems: NemoClaw's own tooling couldn't see or clean it up, and it was bound to all interfaces (`0.0.0.0`), not loopback.

   Fix: `kill 5991`, then `nemohermes keeper recover`. Suggestion: the error message could name the PID and say whether it's an `openshell` process, because the generic "free the port" advice made it look like some unrelated app had the port.

8. Memory test (phase 1 task 3). Inside the sandbox, Super was told to save "my Keeper test codeword is PELICAN-7342" with the memory tool. It said SAVED, and `grep -rn PELICAN-7342 ~/.hermes/memories/` found the line. After `kill 5991` and `nemohermes keeper recover`, the health check was ok and `nemohermes launch keeper` worked. Then `nemohermes backup-all`, `nemohermes keeper stop`, and `nemohermes keeper start`. After the restart, `grep` still found the codeword, and a new session (20261016_001857) answered `PELICAN-7342`. Tool calling and memory persistence both work through NemoClaw with Nemotron 3 Super on Token Factory.

   The Hermes banner showed `tirith security scanner enabled but not available - command scanning will use pattern matching only`. Nothing in the onboarding output explained what's missing or how to install it.

## Phase 2

9. 2026-10-20, while designing the model router: a NemoClaw sandbox on a custom endpoint gets one model, full stop. Its route is the shared `inference.local` route. OpenShell's inference page (docs/how-it-works/inference.mdx, "Now" section) says clients of that route "supplied a placeholder key and model, and relied on OpenShell to rewrite the request". So a workload that asks `inference.local` for Nano or Ultra silently gets Super, the onboarded model, and nothing returns an error. That only comes out of OpenShell's migration notes. NemoClaw's inference docs don't mention it. NemoClaw's own "Model Router" option doesn't help: it's a learned cost/quality router over an NVIDIA Endpoints pool, not routing by task type, and it doesn't cover custom endpoints. To use three Token Factory models from one sandbox, the workload needs an OpenShell provider attachment for the Token Factory host (OpenShell's documented way for a workload to choose its own model). I still need to confirm the rewrite on our install. The router records `served_model` next to the requested model, so a rewrite shows up in the log.

10. 2026-10-20, item 3 (memory and skills). The plan was to give Keeper's code in the sandbox its own OpenShell provider for the Token Factory host (`agent/openshell/`), so the router can pick Nano, Super or Ultra while the key stays in the gateway. That collides with a Hermes default. Hermes's `terminal` and `execute_code` tools strip "sensitive" environment variables from child processes, and that includes the `TOKENFACTORY_API_KEY` placeholder that OpenShell injects. So a script Hermes runs never sees the placeholder unless a loaded skill declares it in `required_environment_variables`, or it's listed in `terminal.env_passthrough`. The variable only holds a placeholder inside OpenShell, so passing it through is safe. But neither NemoClaw's nor Hermes's docs connect the two systems: OpenShell's model assumes the workload can read the placeholder, and Hermes's default hides it. NemoClaw sidesteps this for Tavily with a request-body rewrite in the Tavily profile, but nothing explains the general case.

    Hermes's built-in skill system covered most of item 3 without new code. `skill_manage` creates and edits skills, Hermes's system prompt already asks it to record a skill "when the user corrected its approach", and `skills.write_approval: true` stages every write until `/skills approve <id>`, which also works from Telegram. Hermes's docs are clear here.

11. 2026-10-21, item 2 checked live from Windows with `py -m router smoke`. All six task types answered on the intended model. Token Factory's response `model` field matched the requested id exactly on every call, so the router's served-model check works against the real API. The six calls cost $0.0038 in total (Nano $0.000115, Super $0.000252, Ultra $0.003480).

    Nano spent a lot of tokens on tiny answers. A one-word email classification took 174 to 281 output tokens and 1.1 to 3.3 seconds. Ultra spent 977 output tokens on a plan of under 50 words. These look like reasoning tokens counted as completion tokens. Token Factory's model pages don't say whether reasoning can be turned off per request for Nemotron 3 (for example with a chat template flag or a system-prompt switch). That matters for triage, which runs Nano over a whole inbox every 30 minutes.



12. 2026-10-21, `agent/openshell/setup-tokenfactory.sh` on OpenShell 0.0.116. The custom profile linted and imported fine. Two things then went wrong:
    - `openshell provider create --type tokenfactory-keeper-v1 --from-existing` failed with "failed to discover existing provider data: unsupported provider type: tokenfactory-keeper-v1". The profile has a `discovery` section, but in this version `--from-existing` only works for built-in types (the docs say discovery uses the profile only when `providers_v2_enabled=true`, and NemoClaw's gateway doesn't turn that on). The fix was `--credential TOKENFACTORY_API_KEY` with no value, which reads it from the environment.
    - Running `openshell provider profile lint` again on a profile that's already imported fails with "custom provider profile ... already exists". Lint is meant to check a file, so failing because the gateway already has that profile is surprising, and it makes scripts that check before importing fail on every rerun.

13. 2026-10-21, first `agent/deploy.sh` run. Two upload surprises, one of them silent data corruption:
    - **Files uploaded from the Windows drive arrive as zeros.** `nemohermes keeper upload` (which wraps `openshell sandbox upload`), run in WSL on a file under `/mnt/c/...`, produced a file in the sandbox with the right size (514 bytes) whose contents were all zero bytes (`od -c` shows `\0` throughout). The same command on a file staged in `/tmp` (the WSL Linux filesystem) arrived intact. No error, no warning. The broken file only showed up when bash refused to run it ("cannot execute binary file: Exec format error"). My best guess is that the transfer uses sparse-file detection that misreads the Windows filesystem WSL mounts at `/mnt/c` (drvfs). The windows-preparation page has people clone and work under `/mnt/c` happily, so this will bite others. Workaround: copy everything to a Linux temp directory before uploading.
    - **Folder uploads nest.** `upload ./app/ /sandbox/keeper/app/` created `/sandbox/keeper/app/app/`. The folder goes *into* the destination, like `cp -r src dest/`, even with trailing slashes on both. The Deep Agents example in the commands reference (`upload ./agent-skills/ /sandbox/.deepagents/agent/skills/`) reads as if it copies the folder's contents. Workaround: upload each folder to its parent.

14. 2026-10-21, the custom Token Factory provider attaches and its traffic is allowed, but the key is never swapped in. Setup: profile `tokenfactory-keeper-v1` (endpoint `api.tokenfactory.us-central1.nebius.com:443`, bearer auth on `authorization`), provider `keeper-tokenfactory` attached to `keeper`, and a NemoClaw custom preset that allows the same host. What we saw:
    - The sandbox process gets `TOKENFACTORY_API_KEY=openshell:...` (63 characters), so the placeholder is generated.
    - OpenShell's log shows each request `ALLOWED POST http://api.tokenfactory.us-central1.nebius.com:443/v1/chat/completions [policy:nemoclaw_custom__keeper-tokenfactory__keeper_tokenfactory engine:l7]`, so TLS is terminated and L7 inspection happens.
    - Token Factory answers 401 "Couldn't authenticate", so the placeholder went upstream unchanged.
    - There's no `credential_endpoint_mismatch` 403 and no credential log line at all, so nothing explains why OpenShell didn't treat the placeholder as one to replace.
    - Re-storing a known-good key with `openshell provider update --credential` changed nothing.

    The 0.0.116 docs say static placeholders resolve at profile endpoints even when `providers_v2_enabled` is off. That isn't what happened here, unless the custom preset admitting the traffic is the problem. One log line per request saying "placeholder seen, not substituted, because ..." would have saved an hour. Next try: turn on `providers_v2_enabled` (agent/openshell/try-providers-v2.sh). Fallback: a key file read only by Keeper's router (agent/openshell/install-key-file.sh). That works, but it puts the key inside the sandbox.

15. Follow-up to 14. Turning on `providers_v2_enabled` globally (`openshell settings set --global ...`, which prompts that it "will disable sandbox-level management for this key") and restarting the sandbox changed nothing: still a 401 with the placeholder sent upstream. Removing it put the gateway back cleanly. The fallback worked straight away: the key lives in `/sandbox/keeper/secrets/tokenfactory.key` (mode 600), the router reads it there, and the smoke test from inside the sandbox passed on all three models, each served as requested. The trade-off is that the key is now inside the sandbox. The network preset still restricts it to `/opt/hermes/.venv/bin/python` calling Token Factory's two endpoints. I'd like to switch back to placeholders once custom-profile substitution works on a NemoClaw gateway.

16. 2026-10-21, first chat correction test. Keeper applied the correction right away (it answered in three bullets), and `skills.write_approval` staged four skill writes. `/skills approve all` then rejected all four with "SKILL.md must start with YAML frontmatter (---) ... batch aborted, all touched skills rolled back." Two of them came from my own bug: `keeper skills draft` printed the skill on stdout and a note on stderr, and the note reached Hermes's tool output first, so the agent copied it to the top of the content. The agent also used the category `keeper` as the skill name. Fixed by flushing the skill before the note and making the skill_manage parameters explicit in the skill. Hermes feedback: frontmatter is only checked when you approve, not when a write is staged. A malformed `skill_manage create` looks fine in `/skills pending`, and you only find out at approval time, when the whole batch rolls back. Checking at stage time and returning the error to the agent would let it fix its own call. The two `quick_help` writes I never asked for look like they came from Hermes's background self-review and failed the same check.

