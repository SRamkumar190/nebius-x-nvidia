# skills

Keeper's skills are standard Hermes `SKILL.md` files, so Hermes finds and loads them itself. Keeper requires three parts, which map onto Hermes's own fields:

| Keeper | SKILL.md |
| --- | --- |
| name | frontmatter `name` |
| trigger | frontmatter `description` ("Use when ...") and the `## When to Use` section |
| steps | numbered list under `## Procedure` |

`hermes/` holds the skills Keeper ships with. `agent/deploy.sh` copies them into `/sandbox/.hermes/skills/keeper/`.

- `keeper-learn-from-corrections`: when you correct Keeper, it asks Nemotron 3 Ultra for a skill draft (`keeper skills draft`) and saves it through Hermes's `skill_manage` tool. With `skills.write_approval: true`, nothing lands until you reply `/skills approve <id>`.
- `keeper-memory`: when to store and look up facts in Keeper's markdown memory.

The Python package in this folder backs the `keeper skills` command:

```bash
keeper skills list
keeper skills show <name>
keeper skills check path/to/SKILL.md
keeper skills draft --correction "..." [--context "..."] [--update <name>]
```

`draft` only prints a proposal. It never installs anything.

The inbox triage skill (item 4) and the opportunity radar (item 5) will land here too.
