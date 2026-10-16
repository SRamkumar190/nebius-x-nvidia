# router

Picks a Nemotron model for each job and logs every call. Planned for phase 2, item 2.

`route(task_type, messages, tools)` sends:

| Task type | Model |
| --- | --- |
| Classification, triage | Nano |
| Tool calling, drafting | Super |
| Planning, skill writing | Ultra |

Each call goes into a local SQLite file with the timestamp, task type, model, token counts, latency and estimated cost. The phase 3 dashboard reads that file.
