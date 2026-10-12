"""Per-frame detector, tracker, and experimental temporal risk analysis."""
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import cv2

from .features import REFERENCE_FRAME_SIZE, TrackHistory
from .risk import RiskClassifier
from .risk_logic import RiskStateLogic
from .settings import Settings


class LiveRiskAnalyzer:
    def __init__(self, settings: Settings):
        if not settings.yolo_model.is_file():
            raise FileNotFoundError(f"YOLO weights not found: {settings.yolo_model}")
        from ultralytics import YOLO
        from deep_sort_realtime.deepsort_tracker import DeepSort

        self.detector = YOLO(str(settings.yolo_model))
        self.tracker = DeepSort(max_age=settings.deepsort_max_age, n_init=settings.deepsort_n_init,
                                max_cosine_distance=settings.deepsort_max_cosine_distance)
        self.risk = RiskClassifier(settings.risk_model)
        self.histories: dict[int, TrackHistory] = defaultdict(TrackHistory)
        self.logic: dict[int, RiskStateLogic] = defaultdict(lambda: RiskStateLogic(
            min_observations=settings.risk_min_observations,
            min_probability=settings.risk_min_probability,
            warning_frames=settings.risk_warning_confirmation_frames,
            emergency_frames=settings.risk_emergency_confirmation_frames,
            clear_frames=settings.risk_clear_confirmation_frames,
        ))
        self.settings = settings
        self.alerted_detector_tracks: set[int] = set()
        self.alerted_risk_tracks: set[int] = set()
        self.detector_warning_hits: dict[int, deque[int]] = defaultdict(
            lambda: deque(maxlen=settings.drowning_alert_window_frames))
        self.last_seen: dict[int, float] = {}
        self.track_count = 0
        self.latest_state = "UNASSESSED"

    def process(self, frame, timestamp_seconds: float) -> tuple[Any, list[dict]]:
        height, width = frame.shape[:2]
        result = self.detector.predict(frame, conf=self.settings.yolo_confidence,
                                       imgsz=self.settings.yolo_image_size, verbose=False)[0]
        raw = []
        if result.boxes is not None:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                raw.append(([x1, y1, x2 - x1, y2 - y1], float(box.conf[0]), int(box.cls[0])))
        tracks = self.tracker.update_tracks(raw, frame=frame)
        events = []
        seen = 0
        states = []
        for track in tracks:
            if not track.is_confirmed() or track.time_since_update > 0:
                continue
            x1, y1, x2, y2 = map(int, track.to_ltrb())
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            seen += 1
            track_id = int(track.track_id)
            class_id = track.get_det_class()
            names = self.detector.names
            class_name = str(names.get(class_id, class_id) if isinstance(names, dict) else names[class_id])
            confidence = track.get_det_conf()
            history = self.histories[track_id]
            if track_id in self.last_seen and timestamp_seconds - self.last_seen[track_id] > 1.0:
                history = TrackHistory()
                self.histories[track_id] = history
                self.logic[track_id] = RiskStateLogic(
                    min_observations=self.settings.risk_min_observations,
                    min_probability=self.settings.risk_min_probability,
                    warning_frames=self.settings.risk_warning_confirmation_frames,
                    emergency_frames=self.settings.risk_emergency_confirmation_frames,
                    clear_frames=self.settings.risk_clear_confirmation_frames,
                )
                self.alerted_detector_tracks.discard(track_id)
                self.alerted_risk_tracks.discard(track_id)
                self.detector_warning_hits.pop(track_id, None)
            self.last_seen[track_id] = timestamp_seconds
            scale_x = REFERENCE_FRAME_SIZE / max(1, width)
            scale_y = REFERENCE_FRAME_SIZE / max(1, height)
            history.add(timestamp_seconds,
                        (x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y),
                        confidence if confidence is not None else 0.0, None)
            features = history.as_features()
            prediction = self.risk.predict(features)
            state = self.logic[track_id].update(prediction, int(features["observations"]))
            drowning_candidate = class_name.strip().casefold() == "drowning"
            confidence_value = float(confidence) if confidence is not None else 0.0
            warning_hits = self.detector_warning_hits[track_id]
            warning_hits.append(int(drowning_candidate and confidence_value >= self.settings.drowning_alert_confidence))
            detector_drowning = sum(warning_hits) >= self.settings.drowning_alert_confirmation_frames
            states.append("WARNING" if detector_drowning else state["state"])
            color = (0, 0, 255) if detector_drowning or state["state"] == "EMERGENCY" else (0, 150, 255) if drowning_candidate or state["state"] == "WARNING" else (0, 210, 0)
            if detector_drowning:
                label = f"DROWNING WARNING | ID {track_id} | {confidence_value:.2f}"
            elif drowning_candidate:
                label = f"DROWNING CANDIDATE | ID {track_id} | {confidence_value:.2f}"
            else:
                label = f"{class_name} | ID {track_id} | {state['state']}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, color, 2, cv2.LINE_AA)
            event = None
            if detector_drowning and track_id not in self.alerted_detector_tracks:
                self.alerted_detector_tracks.add(track_id)
                event = {"track_id": track_id, "state": "WARNING",
                         "score": confidence_value,
                         "timestamp_seconds": timestamp_seconds, "class_name": "Drowning detector"}
            elif state["state"] == "EMERGENCY" and track_id not in self.alerted_risk_tracks:
                self.alerted_risk_tracks.add(track_id)
                event = {"track_id": track_id, "state": "EMERGENCY", "score": state["score"],
                         "timestamp_seconds": timestamp_seconds, "class_name": "Drowning detector"}
            if event:
                events.append(event)
        self.track_count = seen
        self.latest_state = "EMERGENCY" if "EMERGENCY" in states else "WARNING" if "WARNING" in states else "SAFE" if "SAFE" in states else "UNASSESSED"
        label = f"LIVE TEMPORAL ANALYSIS | {self.latest_state} | Tracks {seen}"
        cv2.rectangle(frame, (0, 0), (min(width, 590), 34), (18, 31, 42), -1)
        cv2.putText(frame, label, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.58,
                    (50, 80, 255) if self.latest_state in {"WARNING", "EMERGENCY"} else (225, 235, 240),
                    2, cv2.LINE_AA)
        return frame, events
