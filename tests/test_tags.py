import unittest
from uuid import uuid4

from media import clip
from tags import save_tag
from volleyball import update


class PlayerTagsTest(unittest.TestCase):
    def setUp(self):
        self.clip = clip(4, 14)
        self.state = {"clips": [self.clip], "revision": 2, "duration": 30}
        self.tag = dict(
            id=uuid4().hex,
            name="Player A",
            skill="Appearance",
            result="Ungraded",
            time=9,
            x=0.3,
            y=0.4,
        )

    def test_labels_from_two_tabs_merge_and_retries_do_not_duplicate(self):
        first = {"clipId": self.clip["id"], "tag": self.tag}
        save_tag(self.state, first)
        save_tag(
            self.state,
            {
                "clipId": self.clip["id"],
                "tag": dict(self.tag, id=uuid4().hex, name="Player B"),
            },
        )
        save_tag(self.state, first)
        self.assertEqual(
            [tag["name"] for tag in self.clip["tags"]], ["Player A", "Player B"]
        )
        self.assertEqual(self.state["revision"], 4)

    def test_tag_at_match_end_creates_only_one_clip(self):
        data = {"clipId": None, "tag": dict(self.tag, time=30)}
        key = save_tag(self.state, data)
        self.assertEqual(save_tag(self.state, data), key)
        self.assertEqual(len(self.state["clips"]), 2)
        self.assertEqual(self.state["clips"][-1]["end"], 30)

    def test_clip_edits_preserve_old_and_new_labels(self):
        old = {k: v for k, v in self.tag.items() if k != "id"}
        self.clip["tags"].append(old)
        save_tag(self.state, {"clipId": self.clip["id"], "tag": self.tag})
        update(self.state, {**self.clip, "revision": 3, "keep": True})
        self.assertEqual(self.clip["tags"], [old, self.tag])

    def test_trimmed_clip_rejects_out_of_bounds_tag(self):
        with self.assertRaises(ValueError):
            save_tag(
                self.state, {"clipId": self.clip["id"], "tag": dict(self.tag, time=29)}
            )
        self.assertFalse(self.clip["tags"])
        self.assertEqual(self.state["revision"], 2)
