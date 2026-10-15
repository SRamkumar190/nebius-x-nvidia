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

Tool calling worked on the first try for Super and Ultra. Both returned a proper `tool_calls` entry with `finish_reason=tool_calls` and valid JSON arguments. Neither returned the call as text, and I didn't need any extra request parameters.

Asked "what is Nebius Token Factory?" with no context, both models confidently described it as a platform for blockchain tokens. That's expected for a model with no search, but it's why Keeper needs a web search tool (Tavily) before it answers factual questions.

## NemoClaw / OpenShell / Hermes

Not started yet (phase 1, task 2).
