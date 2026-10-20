import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from skills.draft import draft_skill
from skills.format import SkillFormatError, clean_model_output, parse_skill
from skills.library import find_skill, iter_skills

REPO = Path(__file__).resolve().parent.parent

GOOD = """---
name: summary-style
description: Use when the user asks for a summary. Keeps summaries short.
version: 1.0.0
---

# Summary style

## When to Use
The user asks for a summary of anything.

## Procedure
1. Use at most three bullets.
2. Put deadlines first.

## Pitfalls
- No intro sentence.
"""


def fake_route(*replies, model="nvidia/Nemotron-3-Ultra-550b-a55b"):
    calls = []

    def route_fn(task_type, messages, **params):
        calls.append((task_type, [dict(m) for m in messages], params))
        content = replies[len(calls) - 1]
        return SimpleNamespace(model=model, choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return route_fn, calls


class FormatTest(unittest.TestCase):
    def test_good_skill_parses_name_trigger_and_steps(self):
        skill = parse_skill(GOOD)
        self.assertEqual(skill.name, "summary-style")
        self.assertEqual(skill.trigger, "The user asks for a summary of anything.")
        self.assertEqual(skill.steps, ["1. Use at most three bullets.", "2. Put deadlines first."])

    def test_missing_parts_are_all_reported(self):
        bad = "---\nname: Bad Name\n---\n\n# Nothing here\n"
        with self.assertRaises(SkillFormatError) as ctx:
            parse_skill(bad)
        self.assertEqual(len(ctx.exception.problems), 4)

    def test_procedure_without_numbered_steps_fails(self):
        with self.assertRaises(SkillFormatError):
            parse_skill(GOOD.replace("1. Use", "- Use").replace("2. Put", "- Put"))

    def test_nested_frontmatter_blocks_are_allowed(self):
        text = GOOD.replace("version: 1.0.0", "version: 1.0.0\nmetadata:\n  hermes:\n    tags: [style]")
        self.assertEqual(parse_skill(text).name, "summary-style")

    def test_frontmatter_comments_are_ignored(self):
        text = GOOD.replace("version: 1.0.0", "version: 1.0.0\n# note: not a key")
        self.assertNotIn("# note", parse_skill(text).meta)

    def test_clean_model_output_strips_fences_and_chatter(self):
        wrapped = "Here is the skill:\n```markdown\n" + GOOD + "```"
        self.assertEqual(parse_skill(clean_model_output(wrapped)).name, "summary-style")

    def test_shipped_hermes_skills_pass_keepers_own_check(self):
        files = sorted((REPO / "skills" / "hermes").glob("*/SKILL.md"))
        self.assertGreaterEqual(len(files), 2)
        for path in files:
            with self.subTest(skill=path.parent.name):
                self.assertEqual(parse_skill(path.read_text()).name, path.parent.name)


class DraftTest(unittest.TestCase):
    def test_draft_goes_to_skill_write_and_returns_served_model(self):
        route_fn, calls = fake_route(GOOD)
        skill, served = draft_skill("keep summaries to three bullets", "I wrote a paragraph", route_fn=route_fn)
        self.assertEqual(skill.name, "summary-style")
        self.assertEqual(served, "nvidia/Nemotron-3-Ultra-550b-a55b")
        self.assertEqual(calls[0][0], "skill_write")
        self.assertIn("keep summaries to three bullets", calls[0][1][1]["content"])

    def test_bad_first_draft_gets_one_retry_with_the_problems(self):
        route_fn, calls = fake_route("just some prose", GOOD)
        skill, _ = draft_skill("x", route_fn=route_fn)
        self.assertEqual(skill.name, "summary-style")
        self.assertEqual(len(calls), 2)
        self.assertIn("breaks the format", calls[1][1][-1]["content"])

    def test_two_bad_drafts_raise(self):
        route_fn, _ = fake_route("nope", "still nope")
        with self.assertRaises(SkillFormatError):
            draft_skill("x", route_fn=route_fn)

    def test_update_keeps_the_existing_name(self):
        existing = parse_skill(GOOD)
        route_fn, calls = fake_route(GOOD.replace("name: summary-style", "name: summaries-v2"))
        skill, _ = draft_skill("also no emojis", existing=existing, route_fn=route_fn)
        self.assertEqual(skill.name, "summary-style")
        self.assertIn("Update this existing skill", calls[0][1][1]["content"])


class LibraryTest(unittest.TestCase):
    def test_finds_skills_and_skips_hidden_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "keeper" / "summary-style").mkdir(parents=True)
            (root / "keeper" / "summary-style" / "SKILL.md").write_text(GOOD)
            (root / ".hub" / "quarantine" / "x").mkdir(parents=True)
            (root / ".hub" / "quarantine" / "x" / "SKILL.md").write_text(GOOD)
            (root / "other" / "legacy").mkdir(parents=True)
            (root / "other" / "legacy" / "SKILL.md").write_text("---\nname: legacy\n---\nfree form\n")
            found = list(iter_skills(root))
            self.assertEqual(len(found), 2)
            self.assertIsNone(dict((p.parent.name, s) for p, s in found)["legacy"])
            path, skill = find_skill("summary-style", root)
            self.assertEqual(skill.name, "summary-style")


if __name__ == "__main__":
    unittest.main()
