import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

from demo.mailbox import seed, reset
from demo.build_inbox_fixture import build
from integrations.gmail import LiveGmail
from integrations.ingestion import ingest
from keeper_core.db import migrate
from tests.test_gmail_live import Service, Request


class PipelineTest(unittest.TestCase):
    def test_provider_read_failure_does_not_drop_other_messages(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "keeper.db"
            migrate(db)
            api = Service()
            api.failures["messages.get"] = [TimeoutError()]
            result = ingest(LiveGmail(api, run_id="test", max_attempts=1), db, run_id="partial")
            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["stored"], 2)

    def test_reset_keeps_unrelated_database_rows_and_credentials(self):
        class API:
            def users(self): return self
            def messages(self): return self
            def get(self, **params):
                return Request(lambda: {"payload": {"headers": [{"name": "Message-ID", "value": "<owned>"}]}})
            def modify(self, **params): return Request(lambda: {})
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "keeper.db"
            credential = Path(folder) / "credential"
            credential.write_text("fictional")
            migrate(db)
            ingest(LiveGmail(Service(), run_id="test"), db, run_id="seed")
            manifest = {"account": "demo@example.test", "messages": {"one": {
                "status": "stored", "provider_id": "1", "message_id_header": "<owned>"}}}
            reset(API(), manifest, db)
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute("SELECT provider_id FROM email_records ORDER BY provider_id").fetchall(), [("2",), ("3",)])
            self.assertEqual(credential.read_text(), "fictional")

    def test_missing_subject_html_quotes_duplicate_and_partial_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "keeper.db"
            migrate(db)
            service = Service()
            message = service.message_map["1"]
            message["payload"]["headers"] = []
            message["payload"]["parts"] = [{"mimeType": "text/html", "body": {"data":
                base64.urlsafe_b64encode(b"<p>Reply</p><blockquote>Quoted prior reply</blockquote>").decode()}}]
            service.message_map["2"]["internalDate"] = "invalid"
            gmail = LiveGmail(service, run_id="test")
            self.assertEqual(gmail.read_email("gmail:1").record.subject, "")
            self.assertIn("Quoted prior reply", gmail.read_email("gmail:1").body_text)
            self.assertEqual(gmail.read_email("gmail:3").body_text, "Full body")
            first = ingest(gmail, db, run_id="one", page_size=2)
            self.assertEqual(first, dict(stored=2, failed=1, duplicate=0, page_failed=0))
            second = ingest(gmail, db, run_id="two")
            self.assertEqual(second["duplicate"], 2)
            service.failures["messages.list"] = [TimeoutError()] * 3
            gmail._sleep = lambda _: None
            self.assertEqual(ingest(gmail, db, run_id="three")["page_failed"], 1)
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM email_records").fetchone()[0], 2)
                self.assertEqual(conn.execute("SELECT count(*) FROM ingestion_outcomes").fetchone()[0], 7)

    def test_seed_replay_and_uncertain_insert_stop(self):
        class Messages:
            def __init__(self):
                self.calls = 0
            def users(self): return self
            def messages(self): return self
            def insert(self, **params):
                self.calls += 1
                return Request(lambda: {"id": str(self.calls)})
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / "manifest.json"
            fixture = build()
            fixture["emails"] = fixture["emails"][:2]
            api = Messages()
            seed(api, fixture, manifest, "demo@example.test")
            seed(api, fixture, manifest, "demo@example.test")
            self.assertEqual(api.calls, 2)
            data = json.loads(manifest.read_text())
            next(iter(data["messages"].values()))["status"] = "pending"
            manifest.write_text(json.dumps(data))
            with self.assertRaises(RuntimeError):
                seed(api, fixture, manifest, "demo@example.test")

    def test_reset_only_touches_verified_manifest_messages(self):
        class API:
            def __init__(self): self.modified = []
            def users(self): return self
            def messages(self): return self
            def get(self, **params):
                return Request(lambda: {"payload": {"headers": [{"name": "Message-ID", "value": "<demo>"}]},
                                        "labelIds": ["INBOX", "Label1"]})
            def modify(self, **params):
                self.modified.append(params["id"])
                return Request(lambda: {})
        api = API()
        manifest = {"account": "demo@example.test", "messages": {"one": {
            "status": "stored", "provider_id": "owned", "message_id_header": "<demo>"}}}
        reset(api, manifest)
        self.assertEqual(api.modified, ["owned"])
        manifest["messages"]["one"]["message_id_header"] = "<wrong>"
        with self.assertRaises(ValueError): reset(api, manifest)
        self.assertEqual(api.modified, ["owned"])
