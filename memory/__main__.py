"""Command line for Keeper's memory.

    keeper memory topics
    keeper memory show deadlines
    keeper memory add deadlines "GTC hackathon closes Nov 1"
    keeper memory search hackathon
"""
from __future__ import annotations

import argparse
import sys

from .store import BadTopic, default_store


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="keeper memory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("topics")
    show = sub.add_parser("show")
    show.add_argument("topic")
    add = sub.add_parser("add")
    add.add_argument("topic")
    add.add_argument("text", nargs="+")
    search = sub.add_parser("search")
    search.add_argument("query", nargs="+")
    args = parser.parse_args(argv)

    store = default_store()
    try:
        if args.command == "topics":
            for topic in store.topics():
                print(f"{topic} ({len(store.entries(topic))} entries)")
        elif args.command == "show":
            for e in store.entries(args.topic):
                print(f"{e.when} | {e.text}")
        elif args.command == "add":
            added = store.add(args.topic, " ".join(args.text))
            print("saved" if added else "already in memory, not added again")
        else:
            for e in store.search(" ".join(args.query)):
                print(f"[{e.topic}] {e.when} | {e.text}")
    except BadTopic as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
