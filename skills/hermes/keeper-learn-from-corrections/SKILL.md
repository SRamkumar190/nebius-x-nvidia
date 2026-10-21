---
name: keeper-learn-from-corrections
description: Use when the user corrects Keeper or asks to save a rule as a skill. Explains the /teach, /keep and /drop commands.
version: 2.0.0
---

# Learn from corrections

## When to Use
The user tells you that you got something wrong, tells you how to do something from now on, or asks you to save a rule as a skill.

## Procedure
1. Redo the answer the corrected way.
2. Tell the user: "Type /teach to save this as a skill." `/teach` asks Nemotron 3 Ultra to write a skill from the user's last message and shows it to them.
3. If they like the draft, they type `/keep` to save it, and you'll use it from the next conversation. `/drop` throws it away.

## Pitfalls
- Don't call `skill_manage` to create or edit skills yourself. Skills written by hand in chat have repeatedly been malformed, and `/teach` keeps the user in control.
- `/teach` reads the user's last message, so the user should type it straight after stating the rule.
