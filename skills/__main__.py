"""Command line for Keeper's skills.

    keeper skills list
    keeper skills show <name>
    keeper skills check <file>
    keeper skills draft --correction "..." [--context "..."] [--update <name>]
    keeper skills teach | keep | drop     (behind the /teach, /keep, /drop quick commands)
    keeper skills pin <name>              (put an installed skill's rule in SOUL.md)
    keeper skills prompt-check            (is Keeper's persona in Hermes's prompt?)

`draft` only prints a proposal. `teach` drafts one from your last chat
message and `keep` installs it, so nothing is saved until you say so.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .draft import draft_skill
from .format import SkillFormatError, parse_skill
from .library import find_skill, iter_skills, skills_root
from . import teach as teach_flow


def _save_draft_copy(name: str, text: str) -> Path:
    drafts = Path(os.environ.get("KEEPER_DATA_DIR", "./data")) / "skill-drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    path = drafts / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="keeper skills")
    sub = parser.add_subparsers(dest="command", required=True)
    lst = sub.add_parser("list")
    lst.add_argument("--all", action="store_true", help="include Hermes's built-in skills")
    show = sub.add_parser("show")
    show.add_argument("name")
    check = sub.add_parser("check")
    check.add_argument("file")
    draft = sub.add_parser("draft")
    draft.add_argument("--correction", required=True)
    draft.add_argument("--context")
    draft.add_argument("--update", metavar="NAME")
    for name in ("teach", "keep", "drop"):
        sub.add_parser(name)
    sub.add_parser("prompt-check", help="is Keeper's persona in the prompt Hermes used?")
    pin = sub.add_parser("pin", help="put an installed skill's rule in SOUL.md")
    pin.add_argument("name")
    args = parser.parse_args(argv)

    if args.command == "pin":
        print(teach_flow.pin(args.name))
        return 0

    if args.command == "prompt-check":
        from .promptcheck import run
        return run()

    if args.command in ("teach", "keep", "drop"):
        try:
            print(getattr(teach_flow, args.command)())
        except Exception as exc:  # shown in chat, so keep it to one line
            print(f"Couldn't {args.command}: {exc}")
            return 1
        return 0

    if args.command == "list":
        root = skills_root()
        for path, skill in iter_skills(root):
            rel = path.parent.relative_to(root)
            if not args.all and rel.parts[:1] != ("keeper",):
                continue
            if skill:
                print(f"{skill.name:<32} {str(rel.parent):<20} {skill.description[:80]}")
            else:
                print(f"{'(not Keeper format)':<32} {str(rel):<20}")
        return 0

    if args.command == "show":
        found = find_skill(args.name)
        if not found:
            print(f"no skill named {args.name!r} under {skills_root()}", file=sys.stderr)
            return 1
        print(found[1].text)
        return 0

    if args.command == "check":
        try:
            skill = parse_skill(Path(args.file).read_text(encoding="utf-8"))
        except SkillFormatError as exc:
            print("not a valid Keeper skill:\n- " + "\n- ".join(exc.problems))
            return 1
        print(f"ok: {skill.name}, {len(skill.steps)} steps")
        return 0

    existing = None
    if args.update:
        found = find_skill(args.update)
        if not found:
            print(f"no skill named {args.update!r} to update", file=sys.stderr)
            return 1
        existing = found[1]
    try:
        skill, served = draft_skill(args.correction, args.context, existing)
    except SkillFormatError as exc:
        print("Ultra's draft broke the skill format twice: " + "; ".join(exc.problems), file=sys.stderr)
        return 1
    copy = _save_draft_copy(skill.name, skill.text)
    # Hermes reads stdout and stderr together. Flush the skill first, so the
    # note can't land in front of the '---' line and get copied into content.
    sys.stdout.write(skill.text)
    sys.stdout.flush()
    print(f"\n[draft by {served or 'unknown model'}; copy saved to {copy}; not installed yet]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
