# Phase 2, item 3 report: memory and skills

Date: October 22, 2026. Verdict: **done.** Setup and test steps are in [phase2-memory-skills.md](phase2-memory-skills.md).

## What item 3 asked for, and the proof

| Requirement | How Keeper does it | Proof |
| --- | --- | --- |
| Persistent memory as markdown files on a mounted volume | `keeper memory` keeps one markdown file per topic in `/sandbox/keeper/data/memory/`, on the sandbox's persistent `/sandbox` volume | Wrote a line to a `restart-check` topic, ran `nemohermes keeper stop && start`, and `keeper memory show restart-check` still returned `2026-10-22 01:05 UTC \| written before the Oct 21 restart` |
| Skills are markdown with a name, a trigger and steps | Hermes SKILL.md files: `name` and `description` in the frontmatter, a "When to Use" section as the trigger, and a numbered "Procedure". `keeper skills check` rejects anything else | `concise-summary-format` and `summarize-concisely`, both written by Nemotron 3 Ultra from corrections in chat |
| When corrected, propose a new or updated skill and save it only after the user confirms | After a correction, Keeper redoes the answer and tells you to type `/teach`. `/teach` has Ultra draft the skill from your correction (as an update if a skill with that name exists) and shows it. `/keep` saves it, `/drop` throws it away. All three are Hermes quick commands, so the model can't save anything on its own. `skills.write_approval` stays on as a backstop | `/teach` drafted `concise-summary-format` on the first try, and `/keep` installed it |
| Use it next time, across a restart | `/keep` also adds the skill's one-line rule to the "Learned rules" list in SOUL.md, which Hermes puts at the top of every new session's prompt | The skill was saved before the Docker crash, restored into the re-created sandbox, and the sandbox has been stopped and started since. In a new chat, "Give me a quick summary of what you can do for me" came back as three bullets with no intro sentence. `keeper skills prompt-check` shows that session's prompt (7,793 characters) starting with Keeper's section and holding both learned rules: "Verdict: Keeper's persona is in the prompt." |

## What it took

The memory store and the skill format worked early. Nearly all the time went into two problems, both logged in `NOTES_FEEDBACK.md`:

- **Saving skills from chat (notes 16 to 20).** Nemotron 3 Super kept calling Hermes's own `skill_manage` tool with malformed SKILL.md files instead of following our procedure. Moving the save into user-typed quick commands (`/teach`, `/keep`, `/drop`) took the model out of the loop.
- **Keeper's persona never reaching the prompt (notes 20 to 25).** Inside a NemoClaw sandbox, Hermes reads SOUL.md from `/sandbox/.hermes/runtime/`, the folder NemoClaw keeps the session database in. Neither project documents that folder, and Hermes fell back to its built-in "You are Hermes Agent" identity without logging anything. `keeper skills trace-prompt`, a traced one-shot chat, found the `load_soul_md(home_override=/sandbox/.hermes/runtime)` call. `agent/deploy.sh` now writes Keeper's section to that file as well.

A Docker Desktop crash in the middle also cost a sandbox. `agent/restore.sh` and [recover-error-sandbox.md](recover-error-sandbox.md) cover rebuilding one.

## Tools left behind for later items

| Command | What it's for |
| --- | --- |
| `keeper skills prompt-check` | What each SOUL.md holds, what Hermes's own scanner and loader make of the one it reads, and whether the latest chat's prompt has Keeper's persona |
| `keeper skills trace-prompt` | One traced one-shot chat: which SOUL.md Hermes loads, the flags each agent is built with, and the start of the prompt |
| `agent/restore.sh` | Puts memory, the router log, the key file and learned skills back into a re-created sandbox |

## Things to carry into item 4

- **Telegram will need permission fixes for `/teach` and `/keep`.** Hermes's messaging gateway runs as a separate `gateway` user, and quick commands typed in Telegram run as that user. The folders `/teach` and `/keep` write to, and the three SOUL.md files, are owned by `sandbox`. I expect permission errors there until they're made group-writable.
- **Telegram sessions keep their prompt until `/new`.** After a deploy, send `/new` before testing a change in Telegram.
- **Rerun `agent/deploy.sh` after any persona change.** It keeps all three SOUL.md copies in sync, and `/sandbox/.hermes/runtime/SOUL.md` is the one that counts.
- **The terminal chat still says "Hermes".** The response box label and the "NOUS HERMES" banner come from Hermes's display skin, not from the model. Hermes has custom skins, which might fix this before the demo video. I haven't tried one.
- **Hermes's own chat calls don't show up in `router.db`.** Only Keeper's router calls are logged (the drafting, and later triage and radar). The phase 3 dashboard will need Hermes's usage numbers too.
