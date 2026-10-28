"""Synthetic inbox preview: offline by default; --live opts into Nebius calls."""
import argparse
import json
import sys
from pathlib import Path

from keeper_core.adapters import AuthenticationError
from .model import RouterModel
from .preview import OfflineModel, load_emails, preview

DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "demo/fixtures/inbox_75.json"


def _limit(value):
    number = int(value)
    if not 1 <= number <= 1000:
        raise argparse.ArgumentTypeError("limit must be between 1 and 1000")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preview triage on synthetic email; never change Gmail.")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("preview", help="print proposed classifications as JSON")
    command.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    command.add_argument("--limit", type=_limit, default=5)
    command.add_argument("--live", action="store_true", help="use Nebius credits and write the router call log")
    args = parser.parse_args(argv)
    try:
        emails = load_emails(args.fixture)[:args.limit]
    except (OSError, ValueError, RecursionError):
        print("Invalid synthetic fixture: check source fields, UTC dates, IDs, and size.", file=sys.stderr)
        return 2
    model = OfflineModel()
    try:
        if args.live:
            from router.config import load_settings
            model = RouterModel(settings=load_settings())
        result = preview(emails, model)
    except (AuthenticationError, ValueError):
        print("Nebius configuration, credentials, or model access missing or rejected. Check environment settings.", file=sys.stderr)
        return 2
    print(json.dumps({"mode": "live-nebius" if args.live else "offline-demo", **result}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
