import copy
import unittest
from scan_touches import apply_events, decide, peaks
from media import reel_clips, reel_segments
from ball_tracking import verify


class TouchDetectionTest(unittest.TestCase):
    def setUp(self):
        self.state = dict(clips=[], duration=100, revision=1)
        self.event = dict(
            time=20.0,
            score=0.8,
            box=[0.2, 0.3, 0.1, 0.3],
            name="A",
            identityScore=0.7,
            identityMargin=0.1,
            uncertain=False,
        )

    def test_candidates_are_visible_and_preserve_review_decisions(self):
        self.assertEqual(apply_events(self.state, [self.event], "match"), 1)
        c = self.state["clips"][0]
        self.assertEqual(reel_clips(self.state, "A"), [c])
        decide(self.state, dict(id=c["id"], revision=2, status="confirmed"))
        self.assertEqual(reel_clips(self.state, "A"), [c])
        decide(self.state, dict(id=c["id"], revision=3, status="dismissed"))
        self.assertEqual(reel_clips(self.state), [])
        self.assertEqual(reel_clips(self.state, "A"), [])
        self.assertEqual(
            apply_events(self.state, [dict(self.event, time=20.2)], "match"), 0
        )
        decide(self.state, dict(id=c["id"], revision=4, status="automatic"))
        self.assertEqual(reel_clips(self.state, "A"), [c])

    def test_manual_contact_not_duplicated_or_overwritten(self):
        self.state["clips"] = [
            dict(
                id="manual",
                start=18,
                end=25,
                keep=False,
                note="My title",
                tags=[dict(name="A", skill="Serve", time=20.5)],
            )
        ]
        before = copy.deepcopy(self.state)
        self.assertEqual(apply_events(self.state, [self.event], "match"), 0)
        self.assertEqual(self.state, before)

    def test_other_player_touch_is_not_suppressed_by_manual_label(self):
        self.state["clips"] = [dict(tags=[dict(name="B", skill="Block", time=20.0)])]
        self.assertEqual(apply_events(self.state, [self.event], "match"), 1)

    def test_stale_review_does_not_change_state(self):
        apply_events(self.state, [self.event], "match")
        with self.assertRaises(ValueError):
            decide(
                self.state,
                dict(id=self.state["clips"][0]["id"], revision=1, status="dismissed"),
            )
        self.assertEqual(self.state["clips"][0]["detection"]["status"], "automatic")

    def test_adjacent_frame_peaks_collapse_but_separate_contacts_survive(self):
        rows = [
            dict(time=t, score=s)
            for t, s in [
                (1, 0.6),
                (1.06, 0.9),
                (1.12, 0.7),
                (3, 0.8),
                (3.06, 0.6),
                (6, 0.99),
            ]
        ]
        self.assertEqual([r["time"] for r in peaks(rows)], [1.06, 3])

    def test_overlapping_reel_footage_is_exported_once(self):
        apply_events(self.state, [self.event, dict(self.event, time=23)], "match")
        for item in self.state["clips"]:
            item["detection"]["status"] = "confirmed"
        self.assertEqual(reel_segments(self.state, "A"), [dict(start=17, end=27)])

    def test_contact_requires_nearby_moving_ball(self):
        stationary = [[19.7 + i * 0.05, 0.25, 0.35, 0.8] for i in range(14)]
        moving = [[19.7 + i * 0.05, 0.20 + i * 0.008, 0.35, 0.8] for i in range(14)]
        remote = [[t, x + 0.5, y, score] for t, x, y, score in moving]
        self.assertEqual(verify([self.event], stationary), [])
        self.assertEqual(verify([self.event], remote), [])
        self.assertEqual(len(verify([self.event], moving)), 1)

    def test_clip_boundaries_clamped_to_recording(self):
        apply_events(
            self.state, [dict(self.event, time=1), dict(self.event, time=99)], "match"
        )
        self.assertEqual(self.state["clips"][0]["start"], 0)
        self.assertEqual(self.state["clips"][-1]["end"], 100)


if __name__ == "__main__":
    unittest.main()
