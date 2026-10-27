import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from integrations.http_json import HttpFailure
from integrations.telegram import LiveTelegram
from keeper_core.adapters import (IdempotencyConflict, InvalidProviderResponse,
                                  ProviderUnavailable, RateLimited)
from keeper_core.db import migrate


class TelegramTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "keeper.db"
        migrate(self.db)
        self.calls = []
        self.responses = []
        self.waits = []

        def transport(url, payload, headers, timeout):
            self.calls.append((url, payload, timeout))
            outcome = self.responses.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        self.bot = LiveTelegram("demo-secret", self.db, transport=transport, sleep=self.waits.append,
                                now=lambda: datetime(2026, 10, 27, tzinfo=timezone.utc))

    def tearDown(self):
        self.tmp.cleanup()

    def row(self):
        with sqlite3.connect(self.db) as conn:
            return conn.execute("SELECT status, provider_message_id, error, recipient_reference FROM notification_records").fetchone()

    def test_delivery_logged_and_replay_returns_saved_id(self):
        self.responses = [{"ok": True, "result": {"message_id": 23}}]
        self.assertEqual(self.bot.send_message("123", "Digest", idempotency_key="run:1"), "23")
        self.assertEqual(self.bot.send_message("123", "Digest", idempotency_key="run:1"), "23")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.row(), ("delivered", "23", None, "123"))
        with self.assertRaises(IdempotencyConflict):
            self.bot.send_message("123", "Changed", idempotency_key="run:1")

    def test_rate_limit_retries_and_logs(self):
        self.responses = [HttpFailure(429, {"parameters": {"retry_after": 2}}),
                          {"ok": True, "result": {"message_id": 24}}]
        self.assertEqual(self.bot.send_message("123", "Digest", idempotency_key="run:2"), "24")
        self.assertEqual(self.waits, [2])
        self.assertEqual(self.row()[0], "delivered")

    def test_exhausted_rate_limit_can_retry_known_failed_send(self):
        self.responses = [HttpFailure(429, {})] * 3
        with self.assertRaises(RateLimited):
            self.bot.send_message("123", "Digest", idempotency_key="run:3")
        self.assertEqual(self.row()[0], "failed")
        self.responses = [{"ok": True, "result": {"message_id": 25}}]
        self.assertEqual(self.bot.send_message("123", "Digest", idempotency_key="run:3"), "25")
        self.assertEqual(self.row()[0], "delivered")

    def test_timeout_is_pending_and_never_replayed_blindly(self):
        self.responses = [TimeoutError("ambiguous")]
        with self.assertRaises(ProviderUnavailable):
            self.bot.send_message("123", "Digest", idempotency_key="run:4")
        self.assertEqual(self.row()[0], "pending")
        with self.assertRaises(ProviderUnavailable):
            self.bot.send_message("123", "Digest", idempotency_key="run:4")
        self.assertEqual(len(self.calls), 1)

    def test_malformed_success_is_logged_as_uncertain(self):
        self.responses = [{"ok": True, "result": {}}]
        with self.assertRaises(InvalidProviderResponse):
            self.bot.send_message("123", "Digest", idempotency_key="run:5")
        self.assertEqual(self.row()[0], "pending")
        self.assertIn("unknown", self.row()[2])


if __name__ == "__main__":
    unittest.main()
