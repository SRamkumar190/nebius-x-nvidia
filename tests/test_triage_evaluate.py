"""Deterministic evaluation tests; constructed answers are not live model evidence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from triage.evaluate import compare_results
from triage.preview import OfflineModel, load_emails, preview


FIXTURE = Path(__file__).resolve().parents[1] / "demo/fixtures/inbox_75.json"


def source():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def predicted(item, **changes):
    gold = item["gold"]
    return {
        "email_id": item["id"], "bucket": gold["bucket"],
        "scam_signals": gold["scam_signals"], "extracted_deadline": gold["deadline"],
        "model": {"requested_model": "nvidia/test-nano", "served_model": "nvidia/test-nano"},
        **changes,
    }


class TriageEvaluationTest(unittest.TestCase):
    def test_complete_constructed_predictions_score_all_buckets(self):
        fixture = source()
        result = compare_results(FIXTURE, {
            "mode": "offline-demo", "results": [predicted(item) for item in fixture["emails"]],
        })
        self.assertEqual(result["fixture_total"], 75)
        self.assertEqual(result["evaluated"], 75)
        self.assertEqual(result["correct"], 75)
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["fixture_coverage"], 1.0)
        self.assertEqual(result["mismatches"], [])
        self.assertFalse(result["measured_model_quality"])
        for row in result["per_bucket"].values():
            self.assertGreater(row["support"], 0)
            self.assertEqual(row["accuracy"], 1.0)

    def test_reviews_stay_in_accuracy_denominator_and_missing_coverage_is_explicit(self):
        first, second = source()["emails"][:2]
        result = compare_results(FIXTURE, {
            "mode": "live-nebius",
            "results": [predicted(first), predicted(second, bucket=None)],
        })
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["correct"], 1)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["review_count"], 1)
        self.assertEqual(result["missing"], 73)
        self.assertEqual(len(result["missing_ids"]), 73)
        self.assertEqual(result["per_bucket"]["junk"]["support"], 2)
        self.assertEqual(result["per_bucket"]["junk"]["accuracy"], 0.5)
        self.assertTrue(result["measured_model_quality"])

    def test_failed_cases_count_as_review_predictions_in_the_denominator(self):
        first, second = source()["emails"][:2]
        result = compare_results(FIXTURE, {
            "mode": "live-nebius", "results": [predicted(first)],
            "errors": [{"email_id": "gmail:failed", "fixture_id": second["id"],
                        "error_type": "ProviderUnavailable", "message": "private error text"}],
        })
        self.assertEqual(result["evaluated"], 2)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["review_count"], 1)
        self.assertEqual(result["missing"], 73)
        self.assertEqual(result["per_bucket"]["junk"]["support"], 2)
        self.assertEqual(result["per_bucket"]["junk"]["accuracy"], 0.5)
        self.assertFalse(result["measured_model_quality"])
        self.assertNotIn("private error text", json.dumps(result))
        self.assertEqual(result["mismatches"][0]["error_type"], "ProviderUnavailable")

    def test_only_failures_are_evaluated_without_claiming_model_evidence(self):
        item = source()["emails"][0]
        result = compare_results(FIXTURE, {
            "mode": "live-nebius", "results": [],
            "errors": [{"email_id": item["id"], "error_type": "TimeoutError"}],
        })
        self.assertEqual(result["accuracy"], 0.0)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["evaluated"], 1)
        self.assertEqual(result["missing"], 74)
        self.assertFalse(result["measured_model_quality"])

    def test_malformed_duplicate_and_colliding_errors_are_rejected(self):
        item = source()["emails"][0]
        valid = {"email_id": item["id"], "error_type": "TimeoutError"}
        invalid = [
            None, {}, {"email_id": "unknown", "error_type": "TimeoutError"},
            {"email_id": item["id"], "error_type": ""},
            {"email_id": item["id"], "error_type": 3},
            {"email_id": item["id"], "error_type": "arbitrary error text"},
            {"email_id": item["id"], "fixture_id": None, "error_type": "TimeoutError"},
        ]
        for error in invalid:
            with self.subTest(error=error), self.assertRaises(ValueError):
                compare_results(FIXTURE, {"mode": "offline-demo", "results": [], "errors": [error]})
        for errors in [None, {}, "failed", [valid, valid]]:
            with self.subTest(errors=errors), self.assertRaises(ValueError):
                compare_results(FIXTURE, {"mode": "offline-demo", "results": [], "errors": errors})
        with self.assertRaises(ValueError):
            compare_results(FIXTURE, {"mode": "live-nebius", "results": [predicted(item)], "errors": [valid]})

    def test_gmail_provider_ids_are_mapped_back_to_fixture_ids(self):
        item = source()["emails"][0]
        result = compare_results(FIXTURE, {
            "mode": "live-gmail",
            "results": [predicted(item, email_id="gmail:provider-id", fixture_id=item["id"])],
        })
        self.assertEqual(result["correct"], 1)
        self.assertEqual(result["evaluated"], 1)

    def test_career_junk_and_scam_errors_are_visible(self):
        items = source()["emails"]
        career = next(item for item in items if item["gold"]["career"] and not item["gold"]["scam_flag"])
        scam = next(item for item in items if item["gold"]["scam_flag"])
        result = compare_results(FIXTURE, {"mode": "live-nebius", "results": [
            predicted(career, bucket="junk", scam_signals=["upfront_fee"]),
            predicted(scam, scam_signals=[]),
        ]})
        self.assertEqual(result["career_to_junk"], 1)
        self.assertEqual(result["scam"]["false_positive"], 1)
        self.assertEqual(result["scam"]["false_negative"], 1)
        self.assertEqual(result["scam"]["precision"], 0.0)
        self.assertEqual(result["scam"]["recall"], 0.0)
        self.assertEqual(len(result["mismatches"]), 2)
        self.assertNotIn("body_text", json.dumps(result))

    def test_deadline_equivalence_misses_and_invented_dates_are_distinct(self):
        items = source()["emails"]
        due = next(item for item in items if item["gold"]["deadline"])
        other_due = next(item for item in items if item["gold"]["deadline"] and item != due)
        no_date = next(item for item in items if item["gold"]["deadline"] is None)
        equivalent = due["gold"]["deadline"].replace("Z", ".000000+00:00")
        result = compare_results(FIXTURE, {"mode": "live-nebius", "results": [
            predicted(due, extracted_deadline=equivalent),
            predicted(other_due, extracted_deadline=None),
            predicted(no_date, extracted_deadline="2026-11-01T00:00:00Z"),
        ]})
        self.assertEqual(result["deadlines"], {
            "expected": 2, "predicted": 2, "correct": 1, "missed": 1, "incorrect": 1,
        })

    def test_offline_pipeline_cannot_be_reported_as_live_quality(self):
        report = {"mode": "offline-demo", **preview(load_emails(FIXTURE), OfflineModel())}
        result = compare_results(FIXTURE, report)
        self.assertFalse(result["measured_model_quality"])
        self.assertEqual(result["review_count"], 75)
        self.assertEqual(result["accuracy"], 0.0)
        report["mode"] = "live-nebius"
        self.assertFalse(compare_results(FIXTURE, report)["measured_model_quality"])
        report = {"mode": "live-nebius", "results": [predicted(source()["emails"][0], model=None)]}
        self.assertFalse(compare_results(FIXTURE, report)["measured_model_quality"])

    def test_empty_selected_report_has_no_fabricated_ratios(self):
        result = compare_results(FIXTURE, {"mode": "live-nebius", "results": []})
        self.assertEqual(result["total"], 0)
        self.assertIsNone(result["accuracy"])
        self.assertEqual(result["missing"], 75)
        self.assertIsNone(result["scam"]["precision"])
        self.assertIsNone(result["scam"]["recall"])
        self.assertFalse(result["measured_model_quality"])
        self.assertTrue(all(row["accuracy"] is None for row in result["per_bucket"].values()))

    def test_empty_fixture_has_null_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "empty.json"
            fixture.write_text(json.dumps({"synthetic": True, "emails": []}))
            result = compare_results(fixture, {"mode": "offline-demo", "results": []})
        self.assertEqual(result["fixture_total"], 0)
        self.assertIsNone(result["fixture_coverage"])

    def test_duplicate_unknown_and_missing_prediction_id_are_rejected(self):
        item = source()["emails"][0]
        for rows in [
            [predicted(item), predicted(item)],
            [predicted(item, email_id="unknown")],
            [{key: value for key, value in predicted(item).items() if key != "email_id"}],
            [predicted(item, fixture_id=None)],
            [predicted(item), predicted(item, email_id="gmail:x", fixture_id=item["id"])],
        ]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                compare_results(FIXTURE, {"mode": "offline-demo", "results": rows})

    def test_invalid_prediction_shapes_are_rejected(self):
        item = source()["emails"][0]
        for changes in [
            {"bucket": "spam"}, {"bucket": []}, {"scam_signals": "fee"},
            {"scam_signals": [None]}, {"extracted_deadline": "2026-10-12"},
            {"extracted_deadline": "2026-10-12T12:00:00"}, {"extracted_deadline": 3},
            {"extracted_deadline": "2026-99-99T00:00:00Z"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                compare_results(FIXTURE, {"mode": "offline-demo", "results": [predicted(item, **changes)]})
        for report in [None, [], {}, {"mode": "offline-demo", "results": None},
                       {"mode": [], "results": []}, {"mode": "offline-demo", "results": [None]}]:
            with self.subTest(report=report), self.assertRaises(ValueError):
                compare_results(FIXTURE, report)

    def test_gold_contract_is_validated_before_scoring(self):
        fixture = source()
        item = fixture["emails"][0]
        invalid_gold = [
            None, {}, {**item["gold"], "bucket": "spam"},
            {**item["gold"], "career": "yes"}, {**item["gold"], "scam_flag": 1},
            {**item["gold"], "scam_signals": [None]},
            {**item["gold"], "deadline": "2026-10-12"},
        ]
        for gold in invalid_gold:
            with self.subTest(gold=gold), tempfile.TemporaryDirectory() as directory:
                changed = copy.deepcopy(fixture)
                changed["emails"][0]["gold"] = gold
                path = Path(directory) / "fixture.json"
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    compare_results(path, {"mode": "offline-demo", "results": []})

    def test_inputs_are_not_mutated(self):
        report = {"mode": "offline-demo", "results": [predicted(source()["emails"][0])]}
        original = copy.deepcopy(report)
        compare_results(FIXTURE, report)
        self.assertEqual(report, original)


if __name__ == "__main__":
    unittest.main()
