---
name: keeper-learn-from-corrections
description: Use when the user corrects Keeper or says how something should be done from now on. Turns the correction into a new or updated skill and stages it for the user's approval.
version: 1.0.0
# Hermes strips key-like variables from terminal commands unless a loaded skill
# declares them. In the sandbox this is only OpenShell's placeholder, which the
# proxy swaps for the real key at Token Factory.
required_environment_variables:
  - name: TOKENFACTORY_API_KEY
    prompt: Token Factory key (in the sandbox, set by the keeper-tokenfactory OpenShell provider)
---

# Learn from corrections

## When to Use
The user tells you that you got something wrong, or tells you how they want something done next time. Typical phrasing: "no, ...", "that's wrong", "next time ...", "from now on ...", "always ..." or "never ...".

## Procedure
1. Acknowledge the correction in one short line. If there was a task, redo it the corrected way.
2. Check whether an existing skill already covers this. Run `/sandbox/keeper/bin/keeper skills list` in the terminal, and look at your own skill list too.
3. Ask Nemotron 3 Ultra for the draft. Run `/sandbox/keeper/bin/keeper skills draft --correction "<the user's rule, in their words>" --context "<one line on what you did before>"`. Add `--update <skill-name>` if step 2 found a skill that covers this. The command prints a complete SKILL.md.
4. If that command fails, write the draft yourself in the same shape: frontmatter `name` and a `description` that starts with "Use when", then `## When to Use`, then `## Procedure` with numbered steps.
5. Show the user the proposal in a few lines: the skill name, when it triggers, and its steps.
6. Save it with the `skill_manage` tool. Use action `create` with category `keeper` and the full draft as content. To update an existing skill, use `edit` with the full updated file. The write-approval gate stages the change. It doesn't apply it yet.
7. Tell the user: "Proposed skill `<name>`. Reply `/skills approve <id>` to save it, or `/skills reject <id>` to drop it." The id is in the `skill_manage` result. If it isn't there, ask the user to run `/skills pending`.

## Pitfalls
- Never write skill files with the file or terminal tools. That skips the approval gate, and the user said nothing gets saved without their confirmation.
- Don't say a skill is saved until the user has approved it.
- Update the existing skill instead of creating a near-duplicate. Two skills with overlapping triggers confuse you later.
- One rule per correction. Don't bundle unrelated preferences into one skill.
