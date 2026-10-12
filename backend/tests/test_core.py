import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
import numpy as np
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drowning_watch.features import FEATURE_NAMES, TrackHistory
from drowning_watch.risk import RiskClassifier
from drowning_watch.risk_logic import RiskStateLogic
from tools.audit_dataset import audit_zip


class CoreTests(unittest.TestCase):
    def test_features_are_stable_and_handle_zero_time_delta(self):
        history = TrackHistory()
        history.add(0, (0, 0, 10, 10), 0.8)
        history.add(0, (10, 0, 20, 10), 0.9, 0.5)
        history.add(1, (20, 0, 30, 10), 0.7, 0.7)
        values = history.as_features()
        self.assertEqual(tuple(values), FEATURE_NAMES)
        self.assertEqual(values["observations"], 3.0)
        self.assertEqual(values["mean_center_speed_px_s"], 10.0)
        self.assertAlmostEqual(values["pose_visibility_ratio"], 0.6)

    def test_risk_model_missing_means_unassessed(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as tmp:
            classifier = RiskClassifier(Path(tmp) / "missing.joblib")
        self.assertFalse(classifier.ready)
        self.assertEqual(classifier.predict({})["state"], "UNASSESSED")

    def test_risk_state_requires_confirmation_and_holds_alert_in_uncertainty(self):
        logic = RiskStateLogic(min_observations=1, min_probability=0.6,
                               warning_frames=3, emergency_frames=2, clear_frames=3)
        warning = {"state": "WARNING", "score": 0.8}
        self.assertEqual(logic.update(warning, 1)["state"], "UNASSESSED")
        self.assertEqual(logic.update(warning, 2)["state"], "UNASSESSED")
        self.assertEqual(logic.update(warning, 3)["state"], "WARNING")
        held = logic.update({"state": "UNASSESSED", "score": None}, 4)
        self.assertEqual(held["state"], "WARNING")
        emergency = {"state": "EMERGENCY", "score": 0.9}
        logic.update(emergency, 4)
        self.assertEqual(logic.update(emergency, 5)["state"], "EMERGENCY")
        safe = {"state": "SAFE", "score": 0.85}
        logic.update(safe, 6); logic.update(safe, 7)
        self.assertEqual(logic.update(safe, 8)["state"], "SAFE")

    def test_zip_audit_finds_cross_split_duplicate_and_bad_pairing(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as tmp:
            archive = Path(tmp) / "toy.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("train/images/a.jpg", b"same image")
                z.writestr("train/labels/a.txt", "0 0.5 0.5 0.2 0.2\n")
                z.writestr("test/images/a-copy.jpg", b"same image")
                z.writestr("test/labels/a-copy.txt", "1 0.5 0.5 0.2 0.2\n")
                z.writestr("valid/images/orphan.jpg", b"orphan")
            report = audit_zip(archive)
        self.assertEqual(report["image_count"], 3)
        self.assertEqual(report["image_without_label_count"], 1)
        self.assertEqual(report["cross_split_exact_duplicate_groups"], 1)

    def test_health_endpoint_reports_prototype_status(self):
        from drowning_watch.main import health
        response = health()
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["mode"], "research-prototype")
        self.assertFalse(response["cctv_enabled"])

    def test_upload_rejects_non_video_extension(self):
        from drowning_watch.main import validate_video_upload
        with self.assertRaises(HTTPException) as result:
            validate_video_upload("notes.txt", "text/plain")
        self.assertEqual(result.exception.status_code, 415)

    def test_upload_uses_safe_basename_and_accepts_video_mime(self):
        from drowning_watch.main import validate_video_upload
        self.assertEqual(validate_video_upload("folder/clip.MP4", "video/mp4"), ("clip.MP4", ".mp4"))

    def test_deepsort_keeps_identity_for_moving_detection(self):
        from deep_sort_realtime.deepsort_tracker import DeepSort
        tracker = DeepSort(max_age=2, n_init=1, embedder="mobilenet", embedder_gpu=False)
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        visible_ids = []
        for x in (10, 12, 14):
            tracks = tracker.update_tracks([([x, 20, 30, 50], 0.9, 0)], frame=frame)
            visible_ids.extend(track.track_id for track in tracks
                               if track.is_confirmed() and track.time_since_update == 0)
        self.assertGreaterEqual(len(visible_ids), 2)
        self.assertEqual(len(set(visible_ids)), 1)


if __name__ == "__main__":
    unittest.main()
