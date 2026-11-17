import unittest
from media import clip, reel_clips
from volleyball import update


class ClipSemanticsTest(unittest.TestCase):
    def test_player_reels_require_that_players_touch(self):
        seen = {
            **clip(0, 5),
            "keep": True,
            "tags": [
                dict(name="A", skill="Appearance"),
                dict(name="B", skill="Attack"),
            ],
        }
        touched = {**clip(5, 10), "keep": True, "tags": [dict(name="A", skill="Pass")]}
        unkept = {**clip(10, 15), "tags": [dict(name="A", skill="Serve")]}
        unknown = {**clip(15, 20), "keep": True, "tags": [dict(name="A")]}
        state = dict(clips=[seen, touched, unkept, unknown])
        self.assertEqual(reel_clips(state, "A"), [touched])
        self.assertEqual(reel_clips(state, "B"), [seen])
        self.assertEqual(reel_clips(state), [seen, touched, unknown])

    def test_description_survives_legacy_edits_and_can_be_cleared(self):
        item = {**clip(0, 5), "description": "A low pass keeps the rally alive."}
        state = dict(clips=[item], revision=1, duration=20)
        legacy = {k: v for k, v in item.items() if k != "description"}
        update(state, dict(legacy, revision=1, keep=True))
        self.assertEqual(item["description"], "A low pass keeps the rally alive.")
        update(state, dict(item, revision=2, description=""))
        self.assertEqual(item["description"], "")

    def test_stale_summary_edit_cannot_replace_newer_work(self):
        item = {**clip(0, 5), "description": "Reviewed description"}
        state = dict(clips=[item], revision=2, duration=20)
        with self.assertRaises(ValueError):
            update(state, dict(item, revision=1, description="Stale summary"))
        self.assertEqual(item["description"], "Reviewed description")
