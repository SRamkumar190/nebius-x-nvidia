import contextlib
from contextlib import closing
import io
import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from skills import promptcheck
from skills.session import latest_stored_prompt
from skills.soul import END, START, main as soul_main, merge_keeper_section, pin_rule

KEEPER = Path(__file__).resolve().parents[1].joinpath("agent", "SOUL.md").read_text(encoding="utf-8")
STOCK = ("You are Hermes Agent, an intelligent AI assistant created by Nous Research. "
         "You are helpful, knowledgeable, and direct.")
OLD_STYLE = (
    "<!-- keeper:start -->\n## Keeper\n\nold keeper text\n<!-- keeper:end -->\n\n"
    "<!-- keeper:learned:start -->\n### Learned rules\n\n"
    "The user taught you these. Always follow them. The full skill has the details if you need them.\n\n"
    "- **concise-summary-format**: Use when summarizing.\n<!-- keeper:learned:end -->\n\n" + STOCK + "\n"
)

FAKE_PROMPT_BUILDER = textwrap.dedent('''
    import os
    from pathlib import Path

    DEFAULT_AGENT_IDENTITY = "You are Hermes Agent, built by Nous Research. Be direct."

    def _scan_context_content(content, filename):
        if "<!--" in content:
            return f"[BLOCKED: {filename} contained potential prompt injection (html_comment). Content not loaded.]"
        return content

    def load_soul_md(home_override=None):
        path = Path(home_override or os.environ["HERMES_HOME"]) / "SOUL.md"
        if not path.exists():
            return None
        return _scan_context_content(path.read_text(encoding="utf-8").strip(), "SOUL.md")
''')


FAKE_HERMES = {
    "agent/__init__.py": "",
    "agent/prompt_builder.py": "def load_soul_md():\n    return '## Keeper\\n\\nYour name is Keeper.'\n",
    "run_agent.py": textwrap.dedent('''
        from agent.prompt_builder import load_soul_md

        class AIAgent:
            def __init__(self, skip_context_files=False, skip_memory=False, platform=None):
                self.prompt = self._build_system_prompt()

            def _build_system_prompt(self):
                soul = None if self.__dict__.get("skip", False) else load_soul_md()
                return soul or "You are Hermes Agent, built by Nous Research."
    '''),
    "hermes_cli/__init__.py": "",
    "hermes_cli/main.py": textwrap.dedent('''
        import os
        import sys
        from run_agent import AIAgent

        def _quiet_mode():
            os.environ["HERMES_IGNORE_RULES"] = "1"

        def main():
            _quiet_mode()
            agent = AIAgent(skip_context_files=True, skip_memory=True, platform="cli")
            print("answer: " + agent.prompt.splitlines()[0])
            print("argv: " + " ".join(sys.argv[1:]))
            return 0
    '''),
}


class PinTest(unittest.TestCase):
    def test_pin_adds_replaces_and_keeps_other_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            soul = Path(tmp) / "SOUL.md"
            soul.write_text(merge_keeper_section("Other notes.\n", KEEPER))
            pin_rule("a-rule", "Use when x.", soul)
            pin_rule("b-rule", "Use when y.", soul)
            pin_rule("a-rule", "Use when x, updated.", soul)
            text = soul.read_text()
            self.assertTrue(text.startswith("## Keeper\n"))
            self.assertEqual(text.count(START), 1)
            self.assertEqual(text.count(END), 1)
            self.assertIn("- **a-rule**: Use when x, updated.", text)
            self.assertNotIn("- **a-rule**: Use when x.\n", text)
            self.assertIn("- **b-rule**: Use when y.", text)
            self.assertLess(text.index("*End of Keeper section.*"), text.index(START))
            self.assertIn("Other notes.", text)
            self.assertNotIn("<!--", text)

    def test_old_html_learned_block_is_converted(self):
        with tempfile.TemporaryDirectory() as tmp:
            soul = Path(tmp) / "SOUL.md"
            soul.write_text(merge_keeper_section(OLD_STYLE, KEEPER))
            pin_rule("summary-style", "Use for summaries.", soul)
            text = soul.read_text()
            self.assertIn("- **concise-summary-format**: Use when summarizing.", text)
            self.assertIn("- **summary-style**: Use for summaries.", text)
            self.assertNotIn("<!--", text)

    def test_invisible_characters_are_dropped_from_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            soul = Path(tmp) / "SOUL.md"
            pin_rule("zw-rule", "Use​ when‮ asked.", soul)
            self.assertIn("- **zw-rule**: Use when asked.", soul.read_text())


class SoulPathsTest(unittest.TestCase):
    def test_runtime_soul_is_read_last_when_nemoclaw_has_a_runtime_folder(self):
        from skills.soul import soul_path, soul_paths
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / ".hermes"
            home.mkdir()
            env = {k: v for k, v in os.environ.items() if k != "KEEPER_SOUL_FILES"}
            env["HERMES_HOME"] = str(home)
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(soul_paths()[-1], home / "SOUL.md")
                (home / "runtime").mkdir()
                self.assertEqual(soul_path(), home / "runtime" / "SOUL.md")
                self.assertEqual(len(soul_paths()), 3)


class MergeTest(unittest.TestCase):
    def test_old_style_file_becomes_plain_markdown(self):
        merged = merge_keeper_section(OLD_STYLE, KEEPER)
        self.assertTrue(merged.startswith("## Keeper\n\nYour name is Keeper."))
        self.assertNotIn("<!--", merged)
        self.assertNotIn("old keeper text", merged)
        self.assertNotIn("You are Hermes Agent", merged)
        self.assertIn(START, merged)
        self.assertIn("- **concise-summary-format**: Use when summarizing.\n\n" + END, merged)

    def test_merge_is_idempotent_and_keeps_user_text(self):
        once = merge_keeper_section("My own note.\n\n" + STOCK + "\n", KEEPER)
        twice = merge_keeper_section(once, KEEPER)
        self.assertEqual(once, twice)
        self.assertIn("My own note.", once)
        self.assertEqual(once.count("## Keeper"), 1)

    def test_empty_file_gets_just_the_keeper_section(self):
        self.assertEqual(merge_keeper_section("", KEEPER), KEEPER.rstrip() + "\n")

    def test_command_line_rewrites_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target, keeper = Path(tmp) / "SOUL.md", Path(tmp) / "keeper.md"
            target.write_text(OLD_STYLE)
            keeper.write_text(KEEPER)
            self.assertEqual(soul_main(["merge", str(target), str(keeper)]), 0)
            self.assertTrue(target.read_text().startswith("## Keeper"))


def make_db(path, with_messages=True):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE system_prompts (hash TEXT, prompt TEXT)")
    conn.execute("CREATE TABLE sessions (id TEXT, source TEXT, started_at REAL, system_prompt_hash TEXT)")
    conn.execute("INSERT INTO system_prompts VALUES ('h1', 'Your name is Keeper. Learned rules /teach'), "
                 "('h2', 'You are Hermes Agent, built by Nous Research.')")
    # 'chat' is the conversation; 'smoke' is newer but has no user messages.
    conn.execute("INSERT INTO sessions VALUES ('chat', 'cli', 1000, 'h1'), ('smoke', 'cli', 2000, 'h2')")
    if with_messages:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT)")
        conn.execute("INSERT INTO messages (session_id, role, content) VALUES ('chat', 'user', 'hi')")
    conn.commit()
    conn.close()


class StoredPromptTest(unittest.TestCase):
    def test_prefers_the_latest_session_you_typed_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            make_db(db)
            stored = latest_stored_prompt(db)
            self.assertEqual((stored.session_id, stored.source, stored.started_at), ("chat", "cli", 1000.0))
            self.assertIn("Your name is Keeper", stored.prompt)

    def test_without_messages_takes_the_newest_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            make_db(db, with_messages=False)
            self.assertEqual(latest_stored_prompt(db).session_id, "smoke")


class PromptCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        hermes = root / "hermes-src" / "agent"
        hermes.mkdir(parents=True)
        (hermes / "__init__.py").write_text("")
        (hermes / "prompt_builder.py").write_text(FAKE_PROMPT_BUILDER)
        self.home = root / "home"
        self.home.mkdir()
        self.soul = self.home / "SOUL.md"
        self.db = root / "state.db"
        make_db(self.db)
        self.env = mock.patch.dict(os.environ, {
            "KEEPER_HERMES_SRC": str(root / "hermes-src"),
            "HERMES_HOME": str(self.home),
            "KEEPER_SOUL_FILES": str(self.soul),
            "KEEPER_HERMES_STATE_DB": str(self.db),
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_probe_reports_a_blocked_file(self):
        self.soul.write_text("<!-- keeper:start -->\n## Keeper\n<!-- keeper:end -->\n")
        view = promptcheck.hermes_view(self.soul)
        self.assertEqual(view["scanner"], "agent.prompt_builder._scan_context_content")
        self.assertTrue(view["scan"].startswith("BLOCKED"), view)
        self.assertIn("Content not loaded", view["load_soul_md"])
        self.assertTrue(view["fallback_identity"].startswith("You are Hermes Agent"))

    def test_probe_passes_a_clean_file(self):
        self.soul.write_text(merge_keeper_section("", KEEPER))
        view = promptcheck.hermes_view(self.soul)
        self.assertEqual(view["scan"], "passes")
        self.assertIn("Your name is Keeper", view["load_soul_md"])

    def test_probe_asks_the_loader_about_the_files_own_folder(self):
        runtime = self.home / "runtime"
        runtime.mkdir()
        (runtime / "SOUL.md").write_text(merge_keeper_section("", KEEPER))
        view = promptcheck.hermes_view(runtime / "SOUL.md")  # HERMES_HOME's own SOUL.md doesn't exist
        self.assertEqual(view["load_soul_md_home"], str(runtime))
        self.assertIn("Your name is Keeper", view["load_soul_md"])

    def test_report_flags_invisible_characters_and_html(self):
        self.soul.write_text("## Keeper\n\nhi​\n<!-- x -->\n", encoding="utf-8")
        report = "\n".join(promptcheck.file_report(self.soul))
        self.assertIn("U+200B", report)
        self.assertIn("on line 3", report)
        self.assertIn("HTML comments: 1", report)

    def test_run_says_when_the_chat_is_older_than_the_persona(self):
        self.soul.write_text(merge_keeper_section("", KEEPER))
        os.utime(self.soul, (5000, 5000))  # SOUL.md changed after the chat started (1000)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE system_prompts SET prompt = 'You are Hermes Agent.'")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            promptcheck.run()
        self.assertIn("scanner: passes", out.getvalue())
        self.assertIn("Verdict: no conversation since SOUL.md last changed", out.getvalue())

    def test_run_copes_without_a_session_log(self):
        self.soul.write_text(merge_keeper_section("", KEEPER))
        self.db.unlink()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(promptcheck.run(), 0)
        self.assertIn("couldn't read Hermes's session log", out.getvalue())

    def test_trace_reports_env_writes_agent_flags_and_prompt(self):
        src = Path(self.tmp.name) / "trace-src"
        for rel, body in FAKE_HERMES.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(body)
        trace = Path(promptcheck.__file__).with_name("hermes_trace.py")
        env = dict(os.environ, KEEPER_HERMES_SRC=str(src))
        done = subprocess.run([sys.executable, "-I", str(trace), "What is your name?"],
                              capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("argv: chat --oneshot -q What is your name?", done.stdout)
        self.assertIn("os.environ['HERMES_IGNORE_RULES'] = '1' at main.py:7 _quiet_mode <- main.py:10 main", done.stderr)
        self.assertIn("AIAgent(skip_context_files=True, skip_memory=True, platform='cli')", done.stderr)
        self.assertIn("load_soul_md returned", done.stderr)
        self.assertIn("_build_system_prompt built a prompt starting", done.stderr)

    def test_verdicts(self):
        self.assertIn("refuses", promptcheck.verdict("BLOCKED: x", False, False, True))
        self.assertIn("is in the prompt", promptcheck.verdict("passes", True, False, True))
        self.assertIn("no conversation", promptcheck.verdict("passes", False, True, True))
        self.assertIn("Send me this output", promptcheck.verdict("passes", False, False, True))


if __name__ == "__main__":
    unittest.main()
