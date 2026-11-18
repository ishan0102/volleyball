import copy
import unittest
import json
import tempfile
from pathlib import Path
from contact_review import (
    signature,
    verdict,
    apply_results,
    region,
    publish,
    calibration_passed,
    VERSION,
)


class ContactReviewTest(unittest.TestCase):
    def setUp(self):
        self.clip = dict(
            id="one",
            keep=True,
            note="My title",
            description="My description",
            tags=[dict(name="A", skill="Touch", time=10)],
            detection=dict(
                status="automatic", name="A", time=10, box=[0.1, 0.2, 0.1, 0.2]
            ),
        )
        self.state = dict(clips=[self.clip], revision=1)
        self.result = dict(
            id="one",
            signature=signature(self.clip),
            verdict="supported",
            title="GPU title",
            evidence="A visible contact",
            model="test",
        )

    def test_review_keeps_candidates_and_preserves_human_prose(self):
        self.assertEqual(apply_results(self.state, dict(results=[self.result])), 1)
        self.assertTrue(self.clip["keep"])
        self.assertEqual(self.clip["detection"]["status"], "automatic")
        self.assertEqual(self.clip["note"], "My title")
        self.assertEqual(self.clip["description"], "My description")
        before = copy.deepcopy(self.state)
        self.assertEqual(apply_results(self.state, dict(results=[self.result])), 0)
        self.assertEqual(self.state, before)

    def test_human_dismissals_confirmations_and_identity_edits_win(self):
        for status in ("dismissed", "confirmed"):
            self.clip["detection"]["status"] = status
            self.assertEqual(apply_results(self.state, dict(results=[self.result])), 0)
        self.clip["detection"]["status"] = "automatic"
        self.clip["tags"][0]["name"] = "B"
        self.assertEqual(apply_results(self.state, dict(results=[self.result])), 0)

    def test_positive_requires_identity_and_in_window_contact(self):
        row = dict(start=9, end=11)
        result = dict(identity="same_player", contact="yes", time=10)
        self.assertEqual(verdict(result, row), "supported")
        self.assertEqual(verdict(dict(result, identity="unclear"), row), "unverified")
        self.assertEqual(verdict(dict(result, time=100), row), "unverified")
        self.assertEqual(
            verdict(dict(result, identity="different_player"), row), "rejected"
        )
        self.assertEqual(
            verdict(dict(result, contact="no", time=None), row), "rejected"
        )

    def test_negative_does_not_hide_or_unkeep_candidate(self):
        self.result["verdict"] = "rejected"
        apply_results(self.state, dict(results=[self.result]))
        self.assertTrue(self.clip["keep"])
        self.assertEqual(self.clip["detection"]["status"], "automatic")

    def test_focused_crop_stays_within_the_source_frame(self):
        for box in ([0, 0, 0.2, 0.4], [0.9, 0.8, 0.1, 0.2], [0.11, 0.63, 0.044, 0.217]):
            x, y, w, h = region(box)
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + w, 1.000001)
            self.assertLessEqual(y + h, 1.000001)
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)

    def test_changed_gpu_caption_updates_without_overwriting_human_edit(self):
        self.clip["note"] = "A · detected touch"
        self.clip["description"] = "Ball contact detected at 0:10."
        apply_results(self.state, dict(results=[self.result]))
        self.clip["description"] = "My correction"
        revised = dict(
            self.result, title="Revised GPU title", evidence="Revised evidence"
        )
        apply_results(self.state, dict(results=[revised]))
        self.assertEqual(self.clip["note"], "Revised GPU title")
        self.assertEqual(self.clip["description"], "My correction")

    def test_stale_verification_version_is_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "results.json"
            source.write_text(json.dumps(dict(version="old-method", results=[])))
            with self.assertRaises(ValueError):
                publish(folder, source)

    def test_calibration_requires_negative_and_correct_action(self):
        positive = dict(
            expected="supported",
            verdict="supported",
            expectedSkills=["Pass", "Dig"],
            skill="Pass",
        )
        negative = dict(expected="rejected", verdict="rejected")
        self.assertTrue(calibration_passed([positive, negative]))
        self.assertFalse(calibration_passed([]))
        self.assertFalse(calibration_passed([positive]))
        self.assertFalse(calibration_passed([dict(positive, skill="Serve"), negative]))
        self.assertFalse(
            calibration_passed([positive, dict(negative, verdict="supported")])
        )

    def test_results_without_passed_calibration_cannot_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "results.json"
            source.write_text(json.dumps(dict(version=VERSION, results=[self.result])))
            with self.assertRaises(ValueError):
                publish(folder, source)
