"""Validate a Keeper runtime token without printing its contents."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from google_oauth import validate_token_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("token", type=Path)
    args = parser.parse_args(argv)
    try:
        validate_token_payload(json.loads(args.token.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"Invalid Keeper Google token: {exc}", file=sys.stderr)
        return 1
    print("Keeper Google token format and scopes: OK (no network check)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
