import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from keeper_core.adapters import IdempotencyConflict, ProviderNotFound, RateLimited
from keeper_core.fakes import load_fakes


FIXTURE = Path(__file__).resolve().parents[1] / "demo" / "fixtures" / "adapter_responses.json"


class FakeAdapterTest(unittest.TestCase):
    def setUp(self):
        self.gmail, self.calendar, self.telegram, self.tavily, self.model = load_fakes(FIXTURE)

    def test_gmail_pagination_labels_and_unsent_drafts(self):
        first = self.gmail.list_emails(limit=1)
        second = self.gmail.list_emails(cursor=first.next_cursor, limit=1)
        self.assertEqual([record.provider_id for record in first.records + second.records],
                         ["demo-001", "demo-002"])
        self.assertIsNone(second.next_cursor)
        self.gmail.add_labels("gmail:demo-001", ("KEEPER_ACTIONABLE",), idempotency_key="label:1")
        self.gmail.add_labels("gmail:demo-001", ("KEEPER_ACTIONABLE",), idempotency_key="label:1")
        self.assertEqual(self.gmail.labels_by_email["gmail:demo-001"], {"KEEPER_ACTIONABLE"})
        with self.assertRaises(IdempotencyConflict):
            self.gmail.add_labels("gmail:demo-002", ("KEEPER_DUE",), idempotency_key="label:1")
        first_id = self.gmail.create_draft("gmail:demo-001", "Re: Interview", "Thank you",
                                           idempotency_key="draft:1")
        self.assertEqual(first_id, self.gmail.create_draft("gmail:demo-001", "Re: Interview",
                                                               "Thank you", idempotency_key="draft:1"))
        self.assertEqual(len(self.gmail.drafts_by_key), 1)
        with self.assertRaises(IdempotencyConflict):
            self.gmail.create_draft("gmail:demo-002", "Different", "Body", idempotency_key="draft:1")
        self.assertFalse(hasattr(self.gmail, "send_email"))

    def test_calendar_update_and_telegram_retry(self):
        original = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        extended = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
        event_id = self.calendar.upsert_deadline("deadline:1", original, "Apply", idempotency_key="event:1")
        self.assertEqual(event_id, self.calendar.upsert_deadline("deadline:1", extended, "Apply",
                                                                 idempotency_key="event:1", provider_event_id=event_id))
        self.assertEqual(len(self.calendar.events_by_key), 1)
        self.assertEqual(self.calendar.events_by_key["event:1"][2], extended)
        with self.assertRaises(IdempotencyConflict):
            self.calendar.upsert_deadline("deadline:other", extended, "Apply", idempotency_key="event:1")
        sent = self.telegram.send_message("demo-chat", "Summary", idempotency_key="digest:1")
        self.assertEqual(sent, self.telegram.send_message("demo-chat", "Summary", idempotency_key="digest:1"))
        self.assertEqual(len(self.telegram.messages_by_key), 1)
        with self.assertRaises(IdempotencyConflict):
            self.telegram.send_message("another-chat", "Summary", idempotency_key="digest:1")

    def test_search_model_and_error_contract(self):
        hits = self.tavily.search("software internship 2027", limit=1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(self.tavily.search("no fixture"), ())
        response = self.model.complete("triage", "synthetic email")
        self.assertEqual(json.loads(response.content)["bucket"], "actionable")
        self.assertEqual(response.metadata.prompt_version, "fixture-v1")
        with self.assertRaises(ProviderNotFound):
            self.model.complete("draft", "anything")
        error = RateLimited("slow down", retry_after_seconds=3)
        self.assertEqual(error.retry_after_seconds, 3)


if __name__ == "__main__":
    unittest.main()
