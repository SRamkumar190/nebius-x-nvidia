import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from skills import teach
from skills.session import last_correction
from tests.test_skills import GOOD


def make_state_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT)")
    conn.execute("CREATE VIRTUAL TABLE messages_fts USING fts5(content)")
    conn.executemany("INSERT INTO messages (session_id, role, content) VALUES ('s1', ?, ?)", rows)
    conn.commit()
    conn.close()


class SessionTest(unittest.TestCase):
    def test_finds_latest_correction_and_answer_before_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            make_state_db(db, [
                ("user", "Give me a summary"),
                ("assistant", "Here is a long paragraph..."),
                ("user", "Too long. At most 3 bullets, deadlines first."),
                ("assistant", "- a\n- b\n- c"),
                ("user", "/teach"),
            ])
            correction, context = last_correction(db)
            self.assertEqual(correction, "Too long. At most 3 bullets, deadlines first.")
            self.assertEqual(context, "Here is a long paragraph...")

    def test_json_part_lists_are_read_as_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            make_state_db(db, [("assistant", "old answer"),
                               ("user", json.dumps([{"type": "text", "text": "never call hackathons junk"}]))])
            self.assertEqual(last_correction(db)[0], "never call hackathons junk")

    def test_missing_db_is_a_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            last_correction(Path("/nonexistent/state.db"))


class TeachFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "state.db"
        make_state_db(self.db, [("assistant", "long list"), ("user", "Summaries: 3 bullets max, deadlines first")])
        self.skills = root / "skills"
        self.env = mock.patch.dict(os.environ, {
            "KEEPER_DATA_DIR": str(root / "data"),
            "KEEPER_SKILLS_DIR": str(self.skills),
            "KEEPER_HERMES_STATE_DB": str(self.db),
            "HERMES_HOME": str(root / "hermes"),
            "KEEPER_SOUL_FILES": os.pathsep.join([str(root / "SOUL.md"), str(root / "hermes" / "SOUL.md")]),
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def route(self, *replies):
        calls = []

        def route_fn(task_type, messages, **params):
            calls.append(messages)
            return SimpleNamespace(model="nvidia/Nemotron-3-Ultra-550b-a55b",
                                   choices=[SimpleNamespace(message=SimpleNamespace(content=replies[len(calls) - 1]))])
        return route_fn, calls

    def test_teach_then_keep_installs_the_skill(self):
        route_fn, _ = self.route(GOOD)
        msg = teach.teach(route_fn)
        self.assertIn("summary-style", msg)
        self.assertIn("/keep", msg)
        self.assertFalse((self.skills / "keeper" / "summary-style" / "SKILL.md").exists())
        self.assertIn("Saved skill summary-style", teach.keep())
        self.assertTrue((self.skills / "keeper" / "summary-style" / "SKILL.md").exists())
        self.assertFalse(teach.pending_path().exists())
        for soul_file in os.environ["KEEPER_SOUL_FILES"].split(os.pathsep):
            self.assertIn("- **summary-style**: Use when the user asks for a summary.", Path(soul_file).read_text())

    def test_drop_discards_without_installing(self):
        route_fn, _ = self.route(GOOD)
        teach.teach(route_fn)
        self.assertIn("Dropped", teach.drop())
        self.assertFalse((self.skills / "keeper").exists())
        self.assertIn("Nothing to keep", teach.keep())

    def test_existing_skill_gets_an_update_draft_and_a_backup(self):
        target = self.skills / "keeper" / "summary-style" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text(GOOD)
        updated = GOOD.replace("2. Put deadlines first.", "2. Put deadlines first.\n3. No emojis.")
        route_fn, calls = self.route(GOOD, updated)
        self.assertIn("Update skill", teach.teach(route_fn))
        self.assertIn("Update this existing skill", calls[1][1]["content"])
        teach.keep()
        self.assertIn("No emojis", target.read_text())
        self.assertEqual(len(list((Path(os.environ["KEEPER_DATA_DIR"]) / "skill-drafts" / "replaced").iterdir())), 1)


class SystemPromptTest(unittest.TestCase):
    def test_reads_prompt_through_hash_table(self):
        from skills.session import latest_system_prompt
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE system_prompts (hash TEXT, prompt TEXT)")
            conn.execute("CREATE TABLE sessions (id TEXT, started_at REAL, system_prompt TEXT, system_prompt_hash TEXT)")
            conn.execute("INSERT INTO system_prompts VALUES ('h1', 'old prompt'), ('h2', 'Your name is Keeper.')")
            conn.execute("INSERT INTO sessions VALUES ('a', 1, NULL, 'h1'), ('b', 2, NULL, 'h2')")
            conn.commit()
            conn.close()
            self.assertEqual(latest_system_prompt(db), "Your name is Keeper.")


if __name__ == "__main__":
    unittest.main()
