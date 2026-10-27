import json
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path

from demo.build_inbox_fixture import build


class DemoInboxTest(unittest.TestCase):
    def test_gold_expectations_are_complete_and_grounded(self):
        fixture = build()
        self.assertEqual(fixture["version"], 2)
        for email in fixture["emails"]:
            gold = email["gold"]
            self.assertEqual(gold["scam_flag"], bool(gold["scam_signals"]))
            self.assertGreater(len(gold["notes"]), 30)
            self.assertIn("previous_deadline", gold)
            if gold["deadline"]:
                self.assertIn(gold["deadline_evidence"], email["body_text"])
                self.assertEqual(gold["deadline"], gold["deadline_evidence"])
            else:
                self.assertIsNone(gold["deadline_evidence"])
            change = gold["expected_application_change"]
            if change:
                self.assertEqual(change["source_email_id"], email["id"])
                self.assertEqual(change["to_status"], gold["application_transition"])
                self.assertEqual(change["replay_history_entries_added"], 0)
                self.assertIn(change["from_status"], ("found", "applied", "interview"))
                if change["to_status"] == "decision":
                    self.assertIn(change["decision_outcome"], ("offer", "rejected"))
            else:
                self.assertIsNone(gold["application_transition"])

    def test_versioned_fixture_matches_generator_and_coverage(self):
        fixture = json.loads((Path(__file__).resolve().parents[1] / "demo/fixtures/inbox_75.json").read_text())
        self.assertEqual(fixture, build())
        emails = fixture["emails"]
        self.assertEqual(len(emails), 75)
        self.assertEqual(len({item["id"] for item in emails}), 75)
        self.assertEqual(Counter(item["gold"]["bucket"] for item in emails),
                         {"junk": 19, "actionable": 19, "due": 19, "newsletter": 18})
        dates = {datetime.fromisoformat(item["received_at"].replace("Z", "+00:00")).date() for item in emails}
        self.assertEqual(len(dates), 14)
        self.assertFalse(any(item["gold"]["career"] and item["gold"]["bucket"] == "junk" for item in emails))
        injections = [item for item in emails if item["gold"]["scenario"] == "prompt_injection"]
        self.assertEqual(len(injections), 1)
        self.assertEqual(injections[0]["gold"]["security_outcome"], "block_and_log")
        self.assertTrue(injections[0]["gold"]["attempted_destination"].startswith("https://keeper-exfil.example.test/"))
        for item in emails:
            if item["gold"]["bucket"] != "due":
                self.assertIsNone(item["gold"]["deadline"])


if __name__ == "__main__":
    unittest.main()
