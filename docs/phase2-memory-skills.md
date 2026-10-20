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
| Keeper persona | the Keeper block in `/sandbox/.hermes/SOUL.md` | same |

The learning loop goes like this:

1. You correct Keeper in chat.
2. The `keeper-learn-from-corrections` skill has Keeper run `keeper skills draft`, which asks Nemotron 3 Ultra (through the router) to write a SKILL.md.
3. Keeper saves the draft with Hermes's `skill_manage` tool. With `skills.write_approval: true`, that write is staged and doesn't land yet.
4. You approve it with `/skills approve <id>`, in the terminal chat or in Telegram.
5. Next time a matching request comes in, Hermes loads the skill.

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
- adds the Keeper block to SOUL.md. It keeps whatever is already in that file and saves a backup to `~/keeper-backups/`.
- turns on `skills.write_approval`
- lets terminal commands see the Token Factory placeholder (`terminal.env_passthrough`). Hermes strips key-like variables from terminal commands by default.

It's safe to run again after every change.

If `nemohermes launch keeper` complains about port 8642 after the restart, use the fix from phase 1: run `sudo ss -ltnp 'sport = :8642'`, kill the `openshell` PID it shows, then run `nemohermes keeper recover`.

Check:

```bash
nemohermes keeper exec -- hermes config get skills.write_approval
nemohermes keeper exec -- hermes config get terminal.env_passthrough
nemohermes keeper exec -- /sandbox/keeper/bin/keeper skills list
```

The first command should print `true`, and the second should list `TOKENFACTORY_API_KEY`. The second should list `keeper-learn-from-corrections` and `keeper-memory`.

## 3. Proof: memory survives a restart

```bash
nemohermes keeper exec -- /sandbox/keeper/bin/keeper memory add deadlines "NVIDIA GTC student hackathon closes Nov 1"
nemohermes keeper stop && nemohermes keeper start
nemohermes keeper exec -- /sandbox/keeper/bin/keeper memory show deadlines
nemohermes keeper exec -- cat /sandbox/keeper/data/memory/deadlines.md
```

It passes if both of the last two commands still show the hackathon line.

## 4. Proof: a correction becomes a skill, and is used after a restart

1. Open the chat with `nemohermes launch keeper` and ask:

   > Give me a quick summary of what you can do for me.

   You'll most likely get a paragraph or a long list.

2. Correct it:

   > No. From now on, any summary you give me should be at most 3 bullets, deadlines first, and no intro sentence.

3. Keeper should:
   - say it will follow that rule
   - run `keeper skills draft` (you'll see the terminal tool call)
   - show you the proposed skill
   - call `skill_manage`
   - tell you to reply `/skills approve <id>`

   If it doesn't mention an id, type `/skills pending`.

4. Before approving, check that nothing has been saved yet:

   ```bash
   nemohermes keeper exec -- ls /sandbox/.hermes/skills/keeper/
   ```

   Only the two shipped skills should be there.

5. In the chat, type `/skills approve <id>`. Then type `/exit`.

6. Check the skill landed:

   ```bash
   nemohermes keeper exec -- /sandbox/keeper/bin/keeper skills list
   nemohermes keeper exec -- /sandbox/keeper/bin/keeper router recent -n 5
   ```

   You should see a third skill. In the router log there should be a `skill_write` row for `nvidia/Nemotron-3-Ultra-550b-a55b` with status `ok` and no "served by" note.

7. Restart, then ask the same question again in a new session:

   ```bash
   nemohermes keeper stop && nemohermes keeper start
   nemohermes launch keeper
   ```

   > Give me a quick summary of what you can do for me.

It passes if:
- Keeper loads the new skill (a `skill_view` call shows up in the chat)
- it answers in at most 3 bullets with no intro sentence
- the skill is still listed after the restart

Send me screenshots of steps 3, 6 and 7. If it fails, send whatever happened instead.
