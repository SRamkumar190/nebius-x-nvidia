# agent

Keeper runs on the Hermes agent inside NVIDIA OpenShell, set up with NemoClaw. Phase 1 confirmed that stack works with Nemotron on Token Factory, so this folder has no custom agent loop.

It will hold Keeper's Hermes configuration:

- the persona file (`SOUL.md`)
- config overrides
- small scripts that copy them into the `keeper` sandbox with `nemohermes keeper upload`

Install and sandbox setup are in `docs/phase1-nemoclaw.md`.
