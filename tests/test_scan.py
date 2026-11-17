import tempfile
import unittest
from pathlib import Path

from media import clip, save
from scan_players import apply_events, decide, read, references


class AppearanceReviewTest(unittest.TestCase):
    def test_scan_retries_and_review_decisions_preserve_existing_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "match.json"
            original = clip(0, 10)
            original["keep"] = True
            original["tags"] = [
                dict(name="A", time=4, x=0.5, y=0.5, skill="Serve", result="Positive")
            ]
            save(path, dict(clips=[original], duration=90, revision=2))
            tags = references(read(path))
            sample = dict(
                box=[0.4, 0.4, 0.1, 0.2], name="A", time=30, file="000030000-0.jpg"
            )
            auto = dict(sample, id="1" * 32, automatic=True)
            pending = dict(sample, id="2" * 32, automatic=False, time=70)
            events = [auto, pending]
            apply_events(folder, events, tags)
            state = read(path)
            self.assertEqual(state["clips"][0], original)
            self.assertEqual(state["clips"][1]["tags"][0]["source"], "automatic")
            self.assertFalse(state["clips"][1]["keep"])
            apply_events(folder, events, tags)
            self.assertEqual(read(path), state)
            decision = dict(id=pending["id"], file=pending["file"], name=None)
            decide(state, decision)
            decide(state, decision)
            save(path, state)
            apply_events(folder, events, tags)
            self.assertEqual(read(path), state)
