---
name: keeper-memory
description: Use when the user shares a lasting fact (a deadline, a preference, a person, their profile) or asks what Keeper remembers. Stores and searches Keeper's long-term markdown memory.
version: 1.0.0
---

# Keeper memory

## When to Use
The user tells you something worth keeping beyond this conversation, such as a deadline, a preference, details about a person, or facts about their studies. Also use it when they ask what you remember about something, and before you make a suggestion that depends on what they told you earlier.

## Procedure
1. To remember a fact, run `/sandbox/keeper/bin/keeper memory add <topic> "<fact in one sentence>"`. Use one of these topics: `profile`, `deadlines`, `people`, `preferences`, `opportunities-seen`. If none fit, use a short new lowercase topic.
2. To look something up, run `/sandbox/keeper/bin/keeper memory search <words>`. To read a whole topic, run `/sandbox/keeper/bin/keeper memory show <topic>`.
3. Tell the user what you saved or found, in one line.

## Pitfalls
- Your built-in memory tool (MEMORY.md and USER.md) is tiny, about 3,500 characters in total. Keep it for the few facts you need in every conversation, and put everything else here.
- One fact per entry, written so it still makes sense without the chat around it.
- Never store passwords, API keys or anything the user calls secret.
