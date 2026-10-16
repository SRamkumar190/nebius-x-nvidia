# memory

Code and templates for Keeper's long-term memory: plain markdown files that Keeper reads and updates. Planned for phase 2, item 3.

Live memory isn't stored in git. It lives under `KEEPER_DATA_DIR`, which points into `/sandbox` in the sandbox so it survives restarts. Hermes's own MEMORY.md (about 2,200 characters) and USER.md (about 1,375) are far too small for inbox history or deadlines, so Keeper needs this separate store.
