from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import cv2

from .features import REFERENCE_FRAME_SIZE, TrackHistory
from .risk import RiskClassifier
from .risk_logic import RiskStateLogic
from .settings import Settings

MAX_TRACK_HISTORY_GAP_SECONDS = 1.0
# Render's free instance is CPU-limited. Running YOLO on every source frame can
# leave uploads appearing stuck at 0%; sample a smaller, steady set of frames.
MAX_ANALYSIS_FPS = 5.0


def process_video(source: Path, destination: Path, settings: Settings,
                  progress: Callable[[float], None] | None = None,
                  preview: Callable[[bytes], None] | None = None,
                  on_event: Callable[[dict], None] | None = None) -> dict:
    """Run detector -> DeepSORT -> optional pose -> per-track motion features."""
    if not settings.yolo_model.is_file():
        raise FileNotFoundError(f"YOLO weights not found: {settings.yolo_model}. Train a detector and set YOLO_MODEL.")
    from ultralytics import YOLO
    from deep_sort_realtime.deepsort_tracker import DeepSort

    detector = YOLO(str(settings.yolo_model))
    tracker = DeepSort(max_age=settings.deepsort_max_age, n_init=settings.deepsort_n_init,
                       max_cosine_distance=settings.deepsort_max_cosine_distance)
    risk = RiskClassifier(settings.risk_model)
    pose = None
    pose_reason = None
    if settings.pose_enabled and not settings.pose_model.is_file():
        pose_reason = f"Pose model asset is missing: {settings.pose_model}."
    elif settings.pose_enabled:
        try:
            import mediapipe as mp
            options = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(settings.pose_model)),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
            )
            pose = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        except Exception as exc:
            pose_reason = f"Pose task could not be initialized: {type(exc).__name__}."

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError("OpenCV could not open the uploaded video.")
    fps = capture.get(cv2.CAP_PROP_FPS)
    fps = fps if fps and fps > 0 else 25.0
    frame_stride = max(1, round(fps / MAX_ANALYSIS_FPS))
    analysis_fps = fps / frame_stride
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    destination.parent.mkdir(parents=True, exist_ok=True)
    # VP8/WebM is supported by Chromium without platform H.264 encoder libraries.
    writer = cv2.VideoWriter(str(destination), cv2.VideoWriter_fourcc(*"VP80"), analysis_fps, (width, height))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("Could not create processed video. Check codec support and output permissions.")

    histories: dict[int, TrackHistory] = defaultdict(TrackHistory)
    risk_logic: dict[int, RiskStateLogic] = defaultdict(lambda: RiskStateLogic(
        min_observations=settings.risk_min_observations,
        min_probability=settings.risk_min_probability,
        warning_frames=settings.risk_warning_confirmation_frames,
        emergency_frames=settings.risk_emergency_confirmation_frames,
        clear_frames=settings.risk_clear_confirmation_frames,
    ))
    events: dict[tuple[int, str], dict] = {}
    detector_alerted: set[int] = set()
    pose_detections = 0
    frame_index = 0
    source_frame_index = 0
    people_seen: set[int] = set()
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if source_frame_index % frame_stride:
                source_frame_index += 1
                continue
            result = detector.predict(frame, conf=settings.yolo_confidence, imgsz=settings.yolo_image_size, verbose=False)[0]
            raw = []
            if result.boxes is not None:
                for box in result.boxes:
                    xyxy = box.xyxy[0].tolist()
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    raw.append(([xyxy[0], xyxy[1], xyxy[2] - xyxy[0], xyxy[3] - xyxy[1]], confidence, class_id))
            tracks = tracker.update_tracks(raw, frame=frame)
            now = source_frame_index / fps
            for track in tracks:
                if not track.is_confirmed() or track.time_since_update > 0:
                    continue
                x1, y1, x2, y2 = map(int, track.to_ltrb())
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(width, x2), min(height, y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                track_id = int(track.track_id)
                people_seen.add(track_id)
                class_id = track.get_det_class()
                names = detector.names
                class_name = str(names.get(class_id, class_id) if isinstance(names, dict) else names[class_id])
                confidence = track.get_det_conf()
                detector_drowning = class_name.strip().casefold() == "drowning"
                history = histories[track_id]
                if history.observations and now - history.observations[-1]["t"] > MAX_TRACK_HISTORY_GAP_SECONDS:
                    history = TrackHistory()
                    histories[track_id] = history
                    risk_logic[track_id] = RiskStateLogic(
                        min_observations=settings.risk_min_observations,
                        min_probability=settings.risk_min_probability,
                        warning_frames=settings.risk_warning_confirmation_frames,
                        emergency_frames=settings.risk_emergency_confirmation_frames,
                        clear_frames=settings.risk_clear_confirmation_frames,
                    )
                visibility = None
                if pose is not None:
                    try:
                        rgb_crop = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
                        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_crop)
                        pose_result = pose.detect(mp_image)
                        if pose_result.pose_landmarks:
                            landmarks = pose_result.pose_landmarks[0]
                            visibility = sum(lm.visibility for lm in landmarks) / len(landmarks)
                            pose_detections += 1
                            points = []
                            crop_h, crop_w = rgb_crop.shape[:2]
                            for landmark in landmarks:
                                point = (x1 + int(landmark.x * crop_w), y1 + int(landmark.y * crop_h))
                                points.append(point)
                                if landmark.visibility >= 0.45:
                                    cv2.circle(frame, point, 4, (70, 230, 245), -1)
                            for start, end in ((11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
                                               (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
                                               (24, 26), (26, 28)):
                                if landmarks[start].visibility >= 0.45 and landmarks[end].visibility >= 0.45:
                                    cv2.line(frame, points[start], points[end], (70, 230, 245), 2)
                    except Exception:
                        visibility = None
                # Normalize pixel motion to the 224px canvas used by training clips.
                scale_x = REFERENCE_FRAME_SIZE / max(1, width)
                scale_y = REFERENCE_FRAME_SIZE / max(1, height)
                normalized_box = (x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y)
                history.add(now, normalized_box, confidence if confidence is not None else 0.0, visibility)
                features = history.as_features()
                raw_prediction = risk.predict(features)
                risk_state = risk_logic[track_id].update(raw_prediction, int(features["observations"]))
                label = f"{class_name} | ID {track_id} | {risk_state['state']}"
                color = (0, 180, 255) if risk_state["state"] == "WARNING" else (0, 0, 255) if risk_state["state"] == "EMERGENCY" else (0, 220, 0)
                if detector_drowning:
                    label = f"DROWNING DETECTION WARNING | ID {track_id}"
                    color = (0, 0, 255)
                    if track_id not in detector_alerted:
                        event = {"track_id": track_id, "state": "WARNING",
                                 "score": float(confidence) if confidence is not None else None,
                                 "timestamp_seconds": now, "class_name": "Drowning detector"}
                        events[(track_id, "DETECTOR_WARNING")] = event
                        detector_alerted.add(track_id)
                        if on_event:
                            on_event(event)
                thickness = max(2, round(width / 720))
                font_scale = max(0.58, min(0.9, width / 1500))
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
                text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
                text_y = max(text_size[1] + 8, y1)
                cv2.rectangle(frame, (x1, text_y - text_size[1] - 8),
                              (min(width - 1, x1 + text_size[0] + 10), text_y + 4), color, -1)
                cv2.putText(frame, label, (x1 + 5, text_y - 2), cv2.FONT_HERSHEY_SIMPLEX,
                            font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
                if risk_state["state"] in {"WARNING", "EMERGENCY"}:
                    key = (track_id, risk_state["state"])
                    if key not in events:
                        event = {"track_id": track_id, "state": risk_state["state"],
                                 "score": risk_state["score"], "timestamp_seconds": now,
                                 "class_name": class_name}
                        events[key] = event
                        if on_event:
                            on_event(event)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            cv2.putText(frame, f"{stamp} | SAFETY SUPPORT PROTOTYPE | Risk: {'active model' if risk.ready else 'UNASSESSED'}",
                        (10, height - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            writer.write(frame)
            if preview and frame_index % max(1, int(analysis_fps / 4)) == 0:
                preview_width = min(960, width)
                preview_height = max(1, int(height * preview_width / width))
                preview_frame = cv2.resize(frame, (preview_width, preview_height))
                encoded_ok, encoded = cv2.imencode(".jpg", preview_frame,
                                                    [cv2.IMWRITE_JPEG_QUALITY, 78])
                if encoded_ok:
                    preview(encoded.tobytes())
            frame_index += 1
            source_frame_index += 1
            if progress and frame_count:
                progress(min(99.0, source_frame_index * 100.0 / frame_count))
    finally:
        capture.release()
        writer.release()
        if pose is not None:
            pose.close()
    if progress:
        progress(100.0)
    return {"frames_processed": frame_index, "source_fps": fps, "analysis_fps": analysis_fps,
            "tracks_seen": len(people_seen),
            "risk_assessed": risk.ready, "events": list(events.values()),
            "risk_reason": risk.reason or None, "pose_available": pose is not None,
            "pose_detections": pose_detections,
            "pose_reason": pose_reason}
