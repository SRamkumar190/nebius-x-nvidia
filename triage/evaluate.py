"""Compare predictions with synthetic gold labels after inference, never in prompts."""
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from keeper_core.contracts import TriageBucket
from .preview import load_emails

BUCKETS = tuple(bucket.value for bucket in TriageBucket)
INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _instant(value):
    if value is None:
        return None
    if not isinstance(value, str) or INSTANT.fullmatch(value) is None:
        raise ValueError("Evaluation dates must include an explicit time and timezone")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _signals(value):
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError("Evaluation scam signals must be a list of nonempty strings")
    return bool(value)


def _gold(fixture_path):
    load_emails(fixture_path)  # validate source schema and IDs independently of gold
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    result = {}
    for item in data["emails"]:
        gold = item.get("gold")
        if not isinstance(gold, dict) or not {"bucket", "career", "scam_flag", "scam_signals", "deadline"} <= gold.keys():
            raise ValueError("Fixture gold labels are missing required fields")
        if not isinstance(gold["bucket"], str) or gold["bucket"] not in BUCKETS:
            raise ValueError("Invalid gold bucket")
        if type(gold["career"]) is not bool or type(gold["scam_flag"]) is not bool:
            raise ValueError("Gold career and scam flags must be booleans")
        if _signals(gold["scam_signals"]) != gold["scam_flag"]:
            raise ValueError("Gold scam flag contradicts its signals")
        result[item["id"]] = {
            "bucket": gold["bucket"], "career": gold["career"],
            "scam": gold["scam_flag"], "deadline": _instant(gold["deadline"]),
        }
    return result


def _predictions(report, gold):
    if not isinstance(report, dict) or not isinstance(report.get("results"), list):
        raise ValueError("Expected a report with a results list")
    mode = report.get("mode", "unknown")
    if not isinstance(mode, str):
        raise ValueError("Report mode must be text")
    errors = report.get("errors", [])
    if not isinstance(errors, list):
        raise ValueError("Report errors must be a list")
    predictions = {}
    for row in report["results"]:
        identity = _identity(row, gold, predictions)
        if not {"bucket", "scam_signals", "extracted_deadline"} <= row.keys():
            raise ValueError("Prediction fields are missing")
        bucket = row["bucket"]
        if bucket is not None and (not isinstance(bucket, str) or bucket not in BUCKETS):
            raise ValueError("Invalid predicted bucket")
        model = row.get("model")
        if model is not None and not isinstance(model, dict):
            raise ValueError("Prediction model metadata must be an object or null")
        requested_model = (model or {}).get("requested_model")
        if requested_model is not None and not isinstance(requested_model, str):
            raise ValueError("Requested model must be text")
        predictions[identity] = {
            "bucket": bucket, "scam": _signals(row["scam_signals"]),
            "deadline": _instant(row["extracted_deadline"]), "requested_model": requested_model,
        }
    for row in errors:
        identity = _identity(row, gold, predictions)
        error_type = row.get("error_type")
        if not isinstance(error_type, str) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", error_type) is None:
            raise ValueError("Expected an error class name")
        predictions[identity] = {
            "bucket": None, "scam": False, "deadline": None,
            "requested_model": None, "error_type": error_type,
        }
    return mode, predictions


def _identity(row, gold, predictions):
    if not isinstance(row, dict) or not isinstance(row.get("email_id"), str) or not row["email_id"].strip():
        raise ValueError("Prediction email ID is missing")
    identity = row.get("fixture_id", row["email_id"])
    if not isinstance(identity, str) or identity not in gold or identity in predictions:
        raise ValueError("Prediction ID is unknown or duplicated")
    return identity


def compare_results(fixture_path: Path, report: dict) -> dict:
    """Score only selected IDs; preserve review failures and explicit fixture coverage."""
    gold = _gold(Path(fixture_path))
    mode, predictions = _predictions(report, gold)
    support = Counter(gold[identity]["bucket"] for identity in predictions)
    bucket_correct = Counter()
    reviews = career_to_junk = true_positive = false_positive = false_negative = 0
    expected_dates = predicted_dates = correct_dates = missed_dates = incorrect_dates = 0
    mismatches = []
    for identity, actual in predictions.items():
        expected = gold[identity]
        bucket_correct[expected["bucket"]] += actual["bucket"] == expected["bucket"]
        reviews += actual["bucket"] is None
        career_to_junk += expected["career"] and actual["bucket"] == "junk"
        true_positive += expected["scam"] and actual["scam"]
        false_positive += not expected["scam"] and actual["scam"]
        false_negative += expected["scam"] and not actual["scam"]
        expected_dates += expected["deadline"] is not None
        predicted_dates += actual["deadline"] is not None
        correct_dates += expected["deadline"] is not None and actual["deadline"] == expected["deadline"]
        missed_dates += expected["deadline"] is not None and actual["deadline"] != expected["deadline"]
        incorrect_dates += actual["deadline"] is not None and actual["deadline"] != expected["deadline"]
        fields = [key for key in ("bucket", "scam", "deadline") if actual[key] != expected[key]]
        if fields:
            mismatches.append({
                "email_id": identity, "fields": fields,
                "expected_bucket": expected["bucket"], "actual_bucket": actual["bucket"],
                **({"error_type": actual["error_type"]} if "error_type" in actual else {}),
            })
    names = [row["requested_model"] for row in predictions.values()]
    live = mode == "live-nebius" and bool(names) and all(
        name is not None and name != "offline-demo" for name in names
    )
    missing_ids = [identity for identity in gold if identity not in predictions]
    total = len(predictions)
    correct = sum(bucket_correct.values())
    return {
        "mode": mode, "measured_model_quality": live,
        "notice": ("Scores use reported live model predictions." if live else
                   "Offline or unverified predictions; these scores are not live model quality evidence."),
        "fixture_total": len(gold), "evaluated": total, "total": total,
        "fixture_coverage": _ratio(total, len(gold)),
        "missing": len(missing_ids), "missing_ids": missing_ids,
        "failures": sum("error_type" in prediction for prediction in predictions.values()),
        "correct": correct, "accuracy": _ratio(correct, total),
        "review_count": reviews, "career_to_junk": career_to_junk,
        "per_bucket": {
            bucket: {"support": support[bucket], "correct": bucket_correct[bucket],
                     "accuracy": _ratio(bucket_correct[bucket], support[bucket])}
            for bucket in BUCKETS
        },
        "scam": {
            "true_positive": true_positive, "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": _ratio(true_positive, true_positive + false_positive),
            "recall": _ratio(true_positive, true_positive + false_negative),
        },
        "deadlines": {
            "expected": expected_dates, "predicted": predicted_dates, "correct": correct_dates,
            "missed": missed_dates, "incorrect": incorrect_dates,
        },
        "mismatches": mismatches,
    }
