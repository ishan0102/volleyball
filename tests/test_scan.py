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

    def test_undo_review_removes_only_its_tag_and_preserves_originals(self):
        from scan_players import decide, undo_review

        original = clip(0, 40)
        original["tags"] = [
            dict(name="A", time=4, x=0.5, y=0.5, skill="Serve", result="Positive")
        ]
        event = dict(
            id="3" * 32,
            status="pending",
            name="A",
            file="000030000-0.jpg",
            time=30,
            box=[0.4, 0.4, 0.1, 0.2],
        )
        state = dict(
            clips=[original], duration=90, revision=1, appearances={event["id"]: event}
        )
        decide(state, dict(id=event["id"], file=event["file"], name="A"))
        self.assertEqual(len(original["tags"]), 2)
        with self.assertRaises(ValueError):
            undo_review(state, dict(id=event["id"], revision=1))
        request = dict(id=event["id"], revision=state["revision"])
        undo_review(state, request)
        undo_review(state, request)
        self.assertEqual(len(original["tags"]), 1)
        self.assertEqual(original["tags"][0]["skill"], "Serve")
        self.assertEqual(event["status"], "pending")

    def test_undo_removes_a_clip_created_by_its_review(self):
        from scan_players import decide, undo_review

        original = clip(0, 10)
        original["tags"] = [
            dict(name="A", time=4, x=0.5, y=0.5, skill="Serve", result="Positive")
        ]
        event = dict(
            id="4" * 32,
            status="pending",
            name="A",
            file="000030000-0.jpg",
            time=30,
            box=[0.4, 0.4, 0.1, 0.2],
        )
        state = dict(
            clips=[original], duration=90, revision=1, appearances={event["id"]: event}
        )
        decide(state, dict(id=event["id"], file=event["file"], name="A"))
        self.assertEqual(len(state["clips"]), 2)
        undo_review(state, dict(id=event["id"], revision=state["revision"]))
        self.assertEqual(state["clips"], [original])
