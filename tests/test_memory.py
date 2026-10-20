import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from memory import MemoryStore
from memory.store import BadTopic


class MemoryStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "memory")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_writes_readable_markdown(self):
        when = datetime(2026, 10, 20, 14, 3, tzinfo=timezone.utc)
        self.store.add("deadlines", "GTC hackathon closes Nov 1", when=when)
        text = (Path(self.tmp.name) / "memory" / "deadlines.md").read_text()
        self.assertEqual(text, "# Deadlines\n\n- 2026-10-20 14:03 UTC | GTC hackathon closes Nov 1\n")

    def test_entries_survive_a_new_store_instance(self):
        # What a restart looks like from the code's point of view.
        self.store.add("people", "Priya is my lab partner")
        again = MemoryStore(self.store.root)
        self.assertEqual([e.text for e in again.entries("people")], ["Priya is my lab partner"])

    def test_dedupe_ignores_case_and_spacing(self):
        self.assertTrue(self.store.add("deadlines", "GTC closes Nov 1"))
        self.assertFalse(self.store.add("deadlines", "  gtc   CLOSES nov 1 "))
        self.assertEqual(len(self.store.entries("deadlines")), 1)

    def test_multiline_text_becomes_one_entry(self):
        self.store.add("preferences", "bullets\nnot paragraphs")
        [entry] = self.store.entries("preferences")
        self.assertEqual(entry.text, "bullets not paragraphs")

    def test_search_matches_all_words_across_topics(self):
        self.store.add("deadlines", "NVIDIA hackathon closes Nov 1")
        self.store.add("opportunities-seen", "Nebius hackathon in SF")
        self.store.add("people", "Sam runs the robotics club")
        hits = self.store.search("hackathon nvidia")
        self.assertEqual([(e.topic, e.text) for e in hits], [("deadlines", "NVIDIA hackathon closes Nov 1")])

    def test_bad_topic_names_are_rejected(self):
        for bad in ["../etc", "Deadlines", "a b", "", "x" * 65]:
            with self.subTest(topic=bad), self.assertRaises(BadTopic):
                self.store.add(bad, "text")

    def test_hand_edited_lines_without_the_format_are_ignored(self):
        path = self.store.root / "notes.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Notes\n\nsome free text\n- 2026-10-20 10:00 UTC | kept\n")
        self.assertEqual([e.text for e in self.store.entries("notes")], ["kept"])

    def test_topics_lists_files(self):
        self.store.add("b-topic", "x")
        self.store.add("a-topic", "y")
        self.assertEqual(self.store.topics(), ["a-topic", "b-topic"])


if __name__ == "__main__":
    unittest.main()
