# Phase 2, item 3: memory and skills

How to set up Keeper's memory and learned skills inside the `keeper` sandbox, and how to prove they survive a restart.

Everything below runs in the Ubuntu (WSL) window, from the repo folder:

```bash
cd /mnt/c/Users/sidis/nebius-x-nvidia
```

Run `git pull` in PowerShell first, so the new files are there.

## How it fits together

| Piece | Where it lives in the sandbox | Survives restart because |
| --- | --- | --- |
| Keeper's code (`router`, `memory`, `skills`) | `/sandbox/keeper/app/` | `/sandbox` is the sandbox's persistent OpenShell volume |
| `keeper` command | `/sandbox/keeper/bin/keeper` | same |
| Long-term memory, one markdown file per topic | `/sandbox/keeper/data/memory/*.md` | same |
| Router call log | `/sandbox/keeper/data/router.db` | same |
| Skills, shipped and learned | `/sandbox/.hermes/skills/keeper/<name>/SKILL.md` | same. Hermes loads them on its own. |
| Skill changes waiting for approval | `/sandbox/.hermes/pending/skills/` | Hermes keeps staged writes across restarts |
| Keeper persona | the Keeper section at the top of `/sandbox/SOUL.md` and `/sandbox/.hermes/SOUL.md` | same |
| Learned rules, one line per learned skill | right under the Keeper section in both SOUL.md files | same |

The learning loop goes like this:

1. You correct Keeper in chat. Keeper redoes the answer and tells you to type `/teach`.
2. `/teach` reads your correction from Hermes's session log and has Nemotron 3 Ultra (through the router) write a SKILL.md. You see the draft.
3. `/keep` installs it and adds its one-line rule to the "Learned rules" list in SOUL.md. `/drop` throws it away. Nothing is saved until you type `/keep`.
4. In the next conversation, the rule is in Keeper's prompt, and Hermes can load the full skill when it needs the steps.

## 1. Give the router all three models (one time)

The sandbox's built-in `inference.local` route rewrites every request to Super. This step adds an OpenShell provider for Token Factory instead:
- The router can then pick Nano, Super or Ultra itself.
- The real key stays in the OpenShell gateway.
- The sandbox only ever sees a placeholder.
- Only `/opt/hermes/.venv/bin/python` is allowed to reach Token Factory.

```bash
bash agent/openshell/setup-tokenfactory.sh
nemohermes keeper stop && nemohermes keeper start
```

The script asks for your Token Factory key with a hidden prompt. If any of its four steps fails, stop and send me the output. The OpenShell commands come from OpenShell 0.0.116's providers docs, but this is their first run on your install.

On OpenShell 0.0.116 with NemoClaw, the attachment works and the network rule lets the requests through. But OpenShell never swaps the placeholder for the key, so Token Factory answers 401. Turning on `providers_v2_enabled` didn't fix it either (`agent/openshell/try-providers-v2.sh` tries it, and turns it back off if it fails). What does work is putting the key in a file that only Keeper's router reads:

```bash
bash agent/openshell/install-key-file.sh
```

That puts the key inside the sandbox at `/sandbox/keeper/secrets/tokenfactory.key` (mode 600). The network rule still only lets `/opt/hermes/.venv/bin/python` call Token Factory's chat and models endpoints, and redeploys leave the file alone.

Check from inside the sandbox:

```bash
nemohermes keeper exec -- /sandbox/keeper/bin/keeper router smoke
```

You can only run this after step 2 below, because `keeper` isn't in the sandbox until then. All six lines should say OK. A line that says "asked for X but Y answered" means requests are still being rewritten to one model.

## 2. Deploy Keeper into the sandbox

```bash
bash agent/deploy.sh
nemohermes keeper stop && nemohermes keeper start
```

The deploy script:
- copies the code and the `keeper` command into `/sandbox/keeper/`
- installs the two Keeper skills
- puts the Keeper section at the top of both SOUL.md files. Learned rules and anything you added stay. NemoClaw's stock "You are Hermes Agent" paragraph is dropped, because it contradicts Keeper's name. A backup of each file goes to `~/keeper-backups/` first.
- turns on `skills.write_approval`
- adds the `/teach`, `/keep` and `/drop` quick commands
- lets terminal commands see the Token Factory placeholder (`terminal.env_passthrough`). Hermes strips key-like variables from terminal commands by default.

It's safe to run again after every change.

If `nemohermes launch keeper` complains about port 8642 after the restart, use the fix from phase 1: run `sudo ss -ltnp 'sport = :8642'`, kill the `openshell` PID it shows, then run `nemohermes keeper recover`.

Check:

```bash
nemohermes keeper exec -- hermes config get skills.write_approval
nemohermes keeper exec -- hermes config get terminal.env_passthrough
nemohermes keeper exec -- /sandbox/keeper/bin/keeper skills list
```

The first command should print `true`, the second should list `TOKENFACTORY_API_KEY`, and the third should list `keeper-learn-from-corrections` and `keeper-memory`.

## 3. Check that Hermes uses Keeper's persona

Hermes builds a session's system prompt once, when the session starts, and keeps it for that whole session. So start a fresh chat after every deploy:

```bash
nemohermes launch keeper
```

Send `hi`, check that it introduces itself as Keeper, and type `/exit`. Then:

```bash
nemohermes keeper exec -- /sandbox/keeper/bin/keeper skills prompt-check
```

It prints three things:
- what each SOUL.md holds
- what Hermes's own prompt-injection scanner and SOUL.md loader say about the file Hermes reads. Hermes skips a SOUL.md it thinks is an injection attempt and uses its built-in "You are Hermes Agent" identity instead.
- what the system prompt of your latest chat contains

The last line is the verdict. "Keeper's persona is in the prompt" means it works. "No conversation since SOUL.md last changed" means the latest chat started before the deploy, so start a new one and run it again. Anything else, send me the whole output.

Telegram and other gateway sessions don't restart on their own, so send `/new` there after a deploy.

## 4. Proof: memory survives a restart

```bash
nemohermes keeper exec -- /sandbox/keeper/bin/keeper memory add deadlines "NVIDIA GTC student hackathon closes Nov 1"
nemohermes keeper stop && nemohermes keeper start
nemohermes keeper exec -- /sandbox/keeper/bin/keeper memory show deadlines
nemohermes keeper exec -- cat /sandbox/keeper/data/memory/deadlines.md
```

It passes if both of the last two commands still show the hackathon line.

## 5. Proof: a correction becomes a skill, and is used after a restart

Skills are learned with three commands that you type in the chat, in the terminal or in Telegram. Hermes runs them as quick commands without asking the chat model, so the model can't save anything on its own:

| Command | What it does |
| --- | --- |
| `/teach` | Reads your last message, has Nemotron 3 Ultra write a skill from it (name, trigger, steps), checks the format, and shows you the draft |
| `/keep` | Saves the draft to `/sandbox/.hermes/skills/keeper/<name>/SKILL.md`, and adds its one-line rule to the "Learned rules" list in SOUL.md, which is in every session's prompt |
| `/drop` | Throws the draft away |

1. Open the chat with `nemohermes launch keeper`. Then type:

   ```
   Give me a quick summary of what you can do for me.
   ```

2. Correct it:

   ```
   That's too long. From now on, any summary you give me is at most 3 bullets, deadlines first, and no intro sentence.
   ```

   Keeper should redo the summary and end with "Type /teach to save this as a skill."

3. Type `/teach`. After a few seconds you get Ultra's draft: the skill name, when it triggers, and its steps.

4. Type `/keep`. It should say `Saved skill <name>`. Then type `/exit`.

5. Restart, check the file, and ask again in a new session:

   ```bash
   nemohermes keeper stop && nemohermes keeper start
   nemohermes keeper exec -- /sandbox/keeper/bin/keeper skills list
   nemohermes keeper exec -- /sandbox/keeper/bin/keeper router recent -n 3
   nemohermes launch keeper
   ```

   ```
   Give me a quick summary of what you can do for me.
   ```

It passes if:
- `skills list` shows the new skill after the restart
- `router recent` has a `skill_write` row on `nvidia/Nemotron-3-Ultra-550b-a55b`
- the answer has at most 3 bullets and no intro sentence

Why the one-line rule is needed: Hermes only loads a skill's full text when the model asks for it, and in testing Nemotron 3 Super answered without loading the new skill. The rule in SOUL.md is always in front of it. To pin a skill that was saved before this change, run `nemohermes keeper exec -- /sandbox/keeper/bin/keeper skills pin <name>`.

`skills.write_approval` stays on as a backstop. If the model or Hermes's background review calls `skill_manage` anyway, the write waits in `/skills pending` until you approve or reject it.
