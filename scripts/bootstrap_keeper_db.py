"""Run from the repository root: python3 scripts/bootstrap_keeper_db.py [--db PATH]."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keeper_core.db import main


if __name__ == "__main__":
    raise SystemExit(main())
