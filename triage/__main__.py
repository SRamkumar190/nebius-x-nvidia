"""Phase 4 triage: preview, persist, explicitly apply, and compare."""
import argparse
import json
import sys
import sqlite3
import uuid
from pathlib import Path

from keeper_core.adapters import AdapterError, AuthenticationError
from keeper_core.db import default_db_path
from .model import RouterModel
from .preview import OfflineModel, load_emails, preview
from .run import run_triage
from .sources import FixtureSource, GmailSource
from .store import ResultStore

DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "demo/fixtures/inbox_75.json"


def _limit(value):
    number = int(value)
    if not 1 <= number <= 1000:
        raise argparse.ArgumentTypeError("limit must be between 1 and 1000")
    return number


def _parser():
    parser = argparse.ArgumentParser(description="Triage synthetic email; dry-run by default, explicit --apply for Gmail.")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("preview", help="print proposed classifications as JSON")
    command.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    command.add_argument("--limit", type=_limit, default=5)
    command.add_argument("--live", action="store_true", help="use Nebius credits and write the router call log")
    run = sub.add_parser("run", help="classify, optionally save, and explicitly apply additive labels")
    source = run.add_mutually_exclusive_group()
    source.add_argument("--fixture", type=Path, default=None)
    source.add_argument("--gmail", action="store_true", help="use only verified Phase 3 seed manifest messages")
    run.add_argument("--manifest", type=Path)
    run.add_argument("--account", help="disposable demo Gmail account")
    run.add_argument("--token", type=Path, help="private runtime OAuth token outside checkout")
    run.add_argument("--db", type=Path, default=default_db_path())
    run.add_argument("--limit", type=_limit, default=1000)
    run.add_argument("--live", action="store_true", help="use Nebius credits")
    mode = run.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only (default)")
    mode.add_argument("--save", action="store_true", help="save immutable decisions in SQLite")
    mode.add_argument("--apply", action="store_true", help="save first, then add KEEPER_ labels to verified demo Gmail")
    compare = sub.add_parser("compare", help="score saved output against fixture gold after inference")
    compare.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    compare.add_argument("--report", type=Path, required=True)
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "compare":
        return _compare(args)
    if args.command == "run":
        if args.apply and not (args.gmail and args.live):
            parser.error("--apply requires --gmail --live and a verified demo manifest")
        if args.gmail and not (args.live and args.account and args.manifest and args.token):
            parser.error("--gmail requires --live --account --manifest --token")
        if not args.gmail and (args.account or args.manifest or args.token):
            parser.error("Gmail account, manifest, and token options require --gmail")
        return _run(args)
    return _preview(args)


def _preview(args):
    try:
        emails = load_emails(args.fixture)[:args.limit]
    except (OSError, ValueError, RecursionError):
        print("Invalid synthetic fixture: check source fields, UTC dates, IDs, and size.", file=sys.stderr)
        return 2
    try:
        result = preview(emails, _model(args.live))
    except (AuthenticationError, ValueError):
        print("Nebius configuration, credentials, or model access missing or rejected. Check environment settings.", file=sys.stderr)
        return 2
    print(json.dumps({"mode": "live-nebius" if args.live else "offline-demo", **result}, indent=2))
    return 0


def _model(live):
    if live:
        from router.config import load_settings
        return RouterModel(settings=load_settings())
    return OfflineModel()


def _run(args):
    try:
        model = _model(args.live)
        if args.gmail:
            from .credentials import gmail_from_token
            gmail = gmail_from_token(args.token, run_id="triage:" + uuid.uuid4().hex)
            source = GmailSource.from_manifest(gmail, args.manifest, args.account)
        else:
            source = FixtureSource.from_path(args.fixture or DEFAULT_FIXTURE)
        result = run_triage(
            source, model, ResultStore(args.db, account=source.account),
            save=args.save or args.apply, apply=args.apply, limit=args.limit, require_live=args.live,
        )
    except (AdapterError, OSError, ValueError, sqlite3.Error, RecursionError) as exc:
        print(f"Triage stopped ({type(exc).__name__}); check source identity, credentials, and database.", file=sys.stderr)
        return 2
    print(json.dumps({"mode": "live-nebius" if args.live else "offline-demo", **result}, indent=2))
    if result["fatal_error"]:
        print("Triage stopped; partial results are preserved in the report. Check provider configuration.", file=sys.stderr)
        return 2
    return 1 if result["errors"] else 0


def _compare(args):
    from .evaluate import compare_results
    try:
        if args.report.stat().st_size > 2_000_000:
            raise ValueError("Report too large")
        report = json.loads(args.report.read_text(encoding="utf-8"))
        result = compare_results(args.fixture, report)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"Comparison failed ({type(exc).__name__}); check fixture and prediction report.", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
