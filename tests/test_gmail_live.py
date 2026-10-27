"""Offline contract tests for the live Gmail boundary."""
import base64
import json
import unittest
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser

from integrations.gmail import LiveGmail
from keeper_core.adapters import IdempotencyConflict, RateLimited


class Response(dict):
    def __init__(self, status, retry_after=None):
        super().__init__()
        self.status = status
        if retry_after is not None:
            self["retry-after"] = str(retry_after)


class Request:
    def __init__(self, callback):
        self.callback = callback

    def execute(self):
        return self.callback()


def gmail_error(status, reason=None, retry_after=None):
    failure = Exception("Gmail request failed")
    failure.resp = Response(status, retry_after)
    failure.content = json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()
    return failure


class Messages:
    def __init__(self, backend):
        self.backend = backend

    def list(self, **kwargs):
        def answer():
            self.backend.calls.append(("messages.list", kwargs))
            self.backend.maybe_fail("messages.list")
            start = int(kwargs.get("pageToken", "0"))
            ids = list(self.backend.message_map)[start:start + kwargs["maxResults"]]
            end = start + len(ids)
            result = {"messages": [{"id": item} for item in ids]}
            if end < len(self.backend.message_map):
                result["nextPageToken"] = str(end)
            return result
        return Request(answer)

    def get(self, **kwargs):
        def answer():
            self.backend.calls.append(("messages.get", kwargs))
            self.backend.maybe_fail("messages.get")
            return self.backend.message_map[kwargs["id"]]
        return Request(answer)

    def modify(self, **kwargs):
        def answer():
            self.backend.calls.append(("messages.modify", kwargs))
            self.backend.maybe_fail("messages.modify")
            self.backend.message_map[kwargs["id"]].setdefault("labelIds", []).extend(kwargs["body"]["addLabelIds"])
            return {}
        return Request(answer)


class Labels:
    def __init__(self, backend):
        self.backend = backend

    def list(self, **kwargs):
        return Request(lambda: {"labels": [{"id": value, "name": key} for key, value in self.backend.label_map.items()]})

    def create(self, **kwargs):
        def answer():
            self.backend.calls.append(("labels.create", kwargs))
            name = kwargs["body"]["name"]
            self.backend.label_map[name] = f"Label_{len(self.backend.label_map) + 1}"
            return {"id": self.backend.label_map[name]}
        return Request(answer)


class Drafts:
    def __init__(self, backend):
        self.backend = backend

    def list(self, **kwargs):
        def answer():
            self.backend.calls.append(("drafts.list", kwargs))
            start = int(kwargs.get("pageToken", "0"))
            ids = list(self.backend.draft_map)[start:start + kwargs["maxResults"]]
            result = {"drafts": [{"id": item} for item in ids]}
            if start + len(ids) < len(self.backend.draft_map):
                result["nextPageToken"] = str(start + len(ids))
            return result
        return Request(answer)

    def get(self, **kwargs):
        def answer():
            self.backend.calls.append(("drafts.get", kwargs))
            return self.backend.draft_map[kwargs["id"]]
        return Request(answer)

    def create(self, **kwargs):
        def answer():
            self.backend.calls.append(("drafts.create", kwargs))
            self.backend.maybe_fail("drafts.create")
            draft_id = f"draft-{len(self.backend.draft_map) + 1}"
            self.backend.draft_map[draft_id] = kwargs["body"]
            return {"id": draft_id}
        return Request(answer)


class Service:
    def __init__(self):
        self.calls = []
        self.failures = {}
        self.label_map = {}
        self.draft_map = {}
        encoded = base64.urlsafe_b64encode(b"Full body").decode()
        self.message_map = {
            str(index): {"id": str(index), "threadId": f"thread-{index}",
                         "internalDate": "1790000000000", "snippet": "Preview",
                         "labelIds": ["INBOX"], "payload": {"mimeType": "multipart/alternative",
                         "headers": [{"name": "From", "value": "Ada <ada@example.test>"},
                                     {"name": "Subject", "value": f"Subject {index}"},
                                     {"name": "Message-ID", "value": f"<{index}@example.test>"}],
                         "parts": [{"mimeType": "text/plain", "body": {"data": encoded}}]}}
            for index in range(1, 4)
        }

    def users(self):
        return self

    def messages(self):
        return Messages(self)

    def labels(self):
        return Labels(self)

    def drafts(self):
        return Drafts(self)

    def maybe_fail(self, operation):
        queue = self.failures.get(operation, [])
        if queue:
            raise queue.pop(0)


class GmailAdapterTest(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.waits = []
        self.gmail = LiveGmail(self.service, run_id="test-run", sleep=self.waits.append,
                               now=lambda: datetime(2026, 10, 27, tzinfo=timezone.utc))

    def test_list_pages_and_read_body(self):
        first = self.gmail.list_emails(limit=2)
        second = self.gmail.list_emails(cursor=first.next_cursor, limit=2)
        self.assertEqual([item.id for item in first.records + second.records],
                         ["gmail:1", "gmail:2", "gmail:3"])
        self.assertIsNone(second.next_cursor)
        self.assertEqual(self.gmail.read_email("gmail:1").body_text, "Full body")
        self.assertEqual(first.records[0].received_at.tzinfo, timezone.utc)

    def test_rate_limit_retries_and_exhaustion(self):
        self.service.failures["messages.list"] = [gmail_error(429, retry_after=4)]
        self.gmail.list_emails(limit=1)
        self.assertEqual(self.waits, [4])
        self.service.failures["messages.get"] = [gmail_error(403, "userRateLimitExceeded")] * 3
        with self.assertRaises(RateLimited):
            self.gmail.read_email("gmail:1")
        self.assertEqual(self.waits[-2:], [1, 2])

    def test_labels_are_additive_and_retries_do_not_duplicate(self):
        self.gmail.add_labels("gmail:1", ("KEEPER_ACTIONABLE",), idempotency_key="label-1")
        self.gmail.add_labels("gmail:1", ("KEEPER_ACTIONABLE",), idempotency_key="label-1")
        self.assertEqual(len([name for name, _ in self.service.calls if name == "messages.modify"]), 1)
        self.assertEqual(self.service.message_map["1"]["labelIds"], ["INBOX", "Label_1"])
        with self.assertRaises(IdempotencyConflict):
            self.gmail.add_labels("gmail:2", ("KEEPER_ACTIONABLE",), idempotency_key="label-1")
        with self.assertRaises(ValueError):
            self.gmail.add_labels("gmail:1", ("INBOX",), idempotency_key="invalid")

    def test_draft_deduplication_and_no_send(self):
        first = self.gmail.create_draft("gmail:1", "Re: Subject 1", "Draft text", idempotency_key="draft-1")
        second = self.gmail.create_draft("gmail:1", "Re: Subject 1", "Draft text", idempotency_key="draft-1")
        self.assertEqual(first, second)
        self.assertEqual(len(self.service.draft_map), 1)
        raw = self.service.draft_map[first]["message"]["raw"]
        mime = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(raw))
        self.assertEqual(mime["In-Reply-To"], "<1@example.test>")
        self.assertEqual(mime.get_content().strip(), "Draft text")
        self.assertFalse(any(mime.get(name) for name in ("To", "Cc", "Bcc")))
        self.assertEqual(self.service.draft_map[first]["message"]["threadId"], "thread-1")
        self.assertFalse(hasattr(self.gmail, "send_email"))
        self.assertTrue(all("send" not in name for name, _ in self.service.calls))
        with self.assertRaises(IdempotencyConflict):
            self.gmail.create_draft("gmail:1", "Re: Subject 1", "Changed", idempotency_key="draft-1")

    def test_uncertain_draft_create_is_not_retried(self):
        self.service.failures["drafts.create"] = [gmail_error(429, retry_after=2)]
        with self.assertRaises(RateLimited):
            self.gmail.create_draft("gmail:1", "Subject", "Body", idempotency_key="draft-2")
        self.assertEqual(len([name for name, _ in self.service.calls if name == "drafts.create"]), 1)
        self.assertEqual(self.waits, [])


if __name__ == "__main__":
    unittest.main()
