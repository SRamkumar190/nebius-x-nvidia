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
