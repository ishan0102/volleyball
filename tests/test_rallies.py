import copy
import unittest
from rallies import apply_analysis, combine_rallies, touch_supported
from media import clip
from analyze_match import validate, requested_clips


class RallyAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.rally = dict(
            start=10,
            end=30,
            start_visible=True,
            end_visible=True,
            title="A low save extends the rally",
            description="A serve leads to several exchanges and a low defensive recovery.",
            excitement=4,
            highlight_reason="Low defensive recovery",
            moments=[],
        )
        self.item = dict(
            clip(12, 19),
            id="original",
            note="My own title",
            description="My own description",
        )
        self.state = dict(clips=[self.item], duration=100, revision=1)
        self.data = dict(
            version="test-v1",
            model="test",
            minutes=[0],
            results=[
                dict(
                    rallies=[self.rally],
                    clips=[
                        dict(
                            id="original",
                            title="Generated title",
                            description="Generated description",
                            category="rally",
                            claimed_touch="not_applicable",
                            evidence="A low recovery.",
                        )
                    ],
                )
            ],
        )

    def test_preserve_human_prose_and_do_not_duplicate_on_cached_rerun(self):
        apply_analysis(self.state, self.data, "match")
        self.assertEqual(self.item["note"], "My own title")
        self.assertEqual(self.item["description"], "My own description")
        self.assertEqual(len(self.state["clips"]), 2)
        before = copy.deepcopy(self.state)
        self.assertEqual(apply_analysis(self.state, self.data, "match")["changed"], 0)
        self.assertEqual(self.state, before)

    def test_blank_clips_get_real_titles_and_descriptions(self):
        self.item.update(note="", description="")
        apply_analysis(self.state, self.data, "match")
        self.assertEqual(self.item["note"], "Generated title")
        self.assertEqual(self.item["description"], "Generated description")

    def test_overlap_merges_but_separate_rallies_stay_separate(self):
        result = combine_rallies(
            [
                self.rally,
                dict(self.rally, start=25, end=38),
                dict(self.rally, start=40, end=50),
            ]
        )
        self.assertEqual([(r["start"], r["end"]) for r in result], [(10, 38), (40, 50)])

    def test_visual_description_does_not_promote_old_touch_claim(self):
        self.item["detection"] = dict(status="automatic")
        self.data["results"][0]["clips"][0]["claimed_touch"] = "supported"
        apply_analysis(self.state, self.data, "match")
        self.assertFalse(touch_supported(self.item))
        self.item["detection"]["status"] = "confirmed"
        self.assertTrue(touch_supported(self.item))
        self.item["detection"]["status"] = "dismissed"
        self.assertFalse(touch_supported(self.item))

    def test_reject_hallucinated_boundaries_and_missing_labels(self):
        result = self.data["results"][0]
        with self.assertRaises(ValueError):
            validate(result, [dict(id="missing")], 0, 100)
        result["rallies"][0]["end"] = 120
        with self.assertRaises(ValueError):
            validate(result, [dict(id="original")], 0, 100)

    def test_concurrent_user_edit_is_preserved(self):
        self.data["baseline"] = {"original": dict(note="", description="")}
        apply_analysis(self.state, self.data, "match")
        self.assertEqual(self.item["note"], "My own title")

    def test_reviewed_rally_survives_another_model_run(self):
        apply_analysis(self.state, self.data, "match")
        reviewed = self.state["clips"][-1]
        reviewed["analysis"]["status"] = "reviewed"
        reviewed["keep"] = True
        reviewed["note"] = "Reviewed title"
        before = copy.deepcopy(reviewed)
        self.data["version"] = "another-model"
        self.data["results"][0]["rallies"][0]["start"] = 11
        apply_analysis(self.state, self.data, "match")
        self.assertEqual(len(self.state["clips"]), 2)
        self.assertEqual(reviewed, before)

    def test_only_full_rallies_are_excluded_from_relabeling(self):
        self.item["analysis"] = {"kind": "rally"}
        self.assertEqual(len(requested_clips(self.state, 0, 30)), 1)
        self.item["analysis"]["liveStart"] = 12
        self.assertEqual(requested_clips(self.state, 0, 30), [])
