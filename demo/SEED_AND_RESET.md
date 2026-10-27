# Seed, ingest, and reset the demo inbox

Run this host-only tool as `python3 -m demo.mailbox` from the repository root. Install `requirements.txt` first. It is deliberately outside the deployed `integrations` package. Use a disposable Google account and a **separate demo OAuth Desktop client/project**; never add seeding scopes to Keeper's runtime credential or install the seeding credential in the sandbox. Keep both Desktop client JSON and generated tokens in a private directory outside this checkout. Authorization commands require Unix/WSL, a browser, and a directory with mode 700.

```bash
python3 -m demo.mailbox authorize-seed --client /private/demo/client.json --token /private/demo/seed.json --account YOUR_DEMO_ACCOUNT
python3 -m demo.mailbox seed --token /private/demo/seed.json --account YOUR_DEMO_ACCOUNT --manifest data/demo-seed.json
```

The seeding token has exactly `gmail.insert`. The tool uses `messages.insert`, which imports into the specified mailbox without sending mail, and `internalDateSource=dateHeader` to retain fixture UTC dates. See [Google's insert reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/insert). Gold annotations are never copied into MIME. The generated MIME and Message-ID headers are deterministic; real Gmail IDs are saved in the manifest. Reruns skip stored entries. A pending entry means the outcome of an insert is uncertain: find its recorded Message-ID in the demo mailbox and reconcile its provider ID before replaying. Do not clear a pending entry without checking whether the insert succeeded. A lock prevents overlapping CLI runs; after a crashed process, confirm it is no longer running before removing its stale `.lock` file.

Ingest using Keeper's separately authorized runtime token:

```bash
python3 -m demo.mailbox ingest --token /private/runtime/google-token.json --account YOUR_DEMO_ACCOUNT --db data/demo-keeper.db
```

This confirms the runtime account, migrates the database, pages inbox message IDs, skips IDs already present, normalizes received timestamps from Gmail internalDate into UTC, and stores the canonical record. Missing subjects remain empty. Multipart plain text is preferred, HTML is converted to visible text when plain text is absent, and quoted replies remain source content. Malformed messages and per-message provider errors produce failed outcomes without losing successful messages in the same page. Page failures stop the run; rerun from the first page to recover, using stored identities to skip completed work. Migration 002 adds append-only processing outcomes with run ID, Gmail provider ID, status, error class, and UTC processing timestamp. Error bodies and credentials are not logged.

Reset the Phase 3 inbox and ingestion state with a **separate demo reset token**, not the insert token:

```bash
python3 -m demo.mailbox authorize-reset --client /private/demo/client.json --token /private/demo/reset.json --account YOUR_DEMO_ACCOUNT
python3 -m demo.mailbox reset --token /private/demo/reset.json --account YOUR_DEMO_ACCOUNT --manifest data/demo-seed.json --db data/demo-keeper.db
```

The reset credential has exactly `gmail.modify`. Reset verifies each synthetic Message-ID against the manifest, restores INBOX/UNREAD labels, and removes subsequent labels only on those messages. It does not delete mailbox messages, credentials, files, or labels on unrelated messages. It removes only those Gmail IDs from the ingestion database and their processing outcomes, leaving unrelated rows intact. A foreign-key reference from later pipeline stages blocks database cleanup and rolls that database transaction back: reconcile the dependent demo records explicitly rather than disabling foreign keys. This reset targets the Phase 3 ingestion baseline; it does not reset later application, draft, or Calendar workflows. Gmail label operations and the SQLite transaction are not atomic together; repeating reset is safe after a partial failure. Existing credentials and the seed manifest are retained.

Revoke the demo OAuth project grants when finished. Live seed/reset calls require operator-supplied credentials; tests exercise an offline Gmail service and real temporary SQLite databases. Run `python3 -m unittest tests.test_demo_pipeline tests.test_gmail_live tests.test_keeper_db`.
