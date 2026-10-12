#!/usr/bin/env python
"""Train the app's motion-v2 temporal classifier from CVAT swimmer track labels.

The input is the labels directory from Z5cc/drowning-detection's Lifeguard dataset.
This intentionally creates a binary SAFE/EMERGENCY prototype: the source annotations
distinguish swim from drown and do not define an intermediate WARNING label.
"""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit

from drowning_watch.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, TrackHistory


WINDOW_MIN = 30
WINDOW_MAX = 150
WINDOW_STEP = 15


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return intersection / max(1e-8, area_a + area_b - intersection)


def load_windows(labels_dir: Path):
    features, labels, groups = [], [], []
    parsed_clips = 0
    for xml_path in sorted(labels_dir.glob("*.xml")):
        # YouTube source IDs are eleven characters; grouping on this avoids clip leakage.
        source_id = xml_path.stem[:11]
        if len(source_id) != 11:
            continue
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            continue

        active = []
        histories = []
        track_labels = []
        last_emitted = []
        frames = sorted(root.findall("image"), key=lambda item: int(item.get("id", "0")))
        if not frames:
            continue
        parsed_clips += 1
        for image in frames:
            frame_number = int(image.get("id", "0"))
            boxes = []
            for box in image.findall("box"):
                label = (box.get("label") or "").strip().casefold()
                if label not in {"swim", "drown"}:
                    continue
                xyxy = tuple(float(box.get(k, "0")) for k in ("xtl", "ytl", "xbr", "ybr"))
                if xyxy[2] <= xyxy[0] or xyxy[3] <= xyxy[1]:
                    continue
                boxes.append((label, xyxy))

            candidates = []
            for box_idx, (label, xyxy) in enumerate(boxes):
                for track_idx, track in enumerate(active):
                    if track["label"] == label and frame_number - track["frame"] <= 1:
                        overlap = iou(track["box"], xyxy)
                        if overlap >= 0.05:
                            candidates.append((overlap, box_idx, track_idx))
            used_boxes, used_tracks, assignments = set(), set(), {}
            for overlap, box_idx, track_idx in sorted(candidates, reverse=True):
                if box_idx not in used_boxes and track_idx not in used_tracks:
                    assignments[box_idx] = track_idx
                    used_boxes.add(box_idx)
                    used_tracks.add(track_idx)

            next_active = []
            for box_idx, (label, xyxy) in enumerate(boxes):
                if box_idx in assignments:
                    active_idx = assignments[box_idx]
                    track_id = active[active_idx]["id"]
                    history = histories[track_id]
                    track_labels[track_id] = label
                    last_emitted[track_id] += 1
                else:
                    track_id = len(histories)
                    history = TrackHistory(max_observations=WINDOW_MAX)
                    histories.append(history)
                    track_labels.append(label)
                    last_emitted.append(0)
                history.add(frame_number / 30.0, xyxy, 1.0, None)
                next_active.append({"label": label, "box": xyxy, "frame": frame_number, "id": track_id})
                count = len(history.observations)
                if count >= WINDOW_MIN and last_emitted[track_id] >= WINDOW_STEP:
                    vec = history.vector()
                    features.append(vec)
                    labels.append("EMERGENCY" if label == "drown" else "SAFE")
                    groups.append(source_id)
                    last_emitted[track_id] = 0
            active = next_active
    return features, labels, groups, parsed_clips


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels_dir", type=Path, help="Directory containing CVAT XML label files")
    parser.add_argument("--output", type=Path, default=Path("models/risk_model.joblib"))
    parser.add_argument("--report", type=Path, default=Path("docs/temporal_model_evaluation.json"))
    args = parser.parse_args()
    x, y, groups, clip_count = load_windows(args.labels_dir)
    allowed = {"SAFE", "EMERGENCY"}
    if not x or set(y) != allowed:
        raise SystemExit(f"Need labeled temporal windows for both swim and drown; got {len(x)} windows and {sorted(set(y))}.")
    group_ids = sorted(set(groups))
    split = None
    for seed in range(42, 142):
        candidate = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed).split(x, y, groups))
        train_idx, test_idx = candidate
        if {y[i] for i in train_idx} == allowed and {y[i] for i in test_idx} == allowed:
            split = train_idx, test_idx
            break
    if split is None:
        raise SystemExit("Could not make a source-video-separated split containing both labels on each side.")
    train_idx, test_idx = split
    train_groups = sorted({groups[i] for i in train_idx})
    test_groups = sorted({groups[i] for i in test_idx})
    if set(train_groups) & set(test_groups):
        raise SystemExit("Source-video leakage detected.")

    model = RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample",
                                   min_samples_leaf=3, random_state=42, n_jobs=-1)
    model.fit([x[i] for i in train_idx], [y[i] for i in train_idx])
    predictions = model.predict([x[i] for i in test_idx])
    report_text = classification_report([y[i] for i in test_idx], predictions,
                                        labels=["SAFE", "EMERGENCY"], zero_division=0)
    matrix = confusion_matrix([y[i] for i in test_idx], predictions,
                              labels=["SAFE", "EMERGENCY"]).tolist()
    report = {
        "model": "RandomForest motion-v2; binary SAFE/EMERGENCY prototype",
        "source": "Z5cc/drowning-detection Lifeguard CVAT annotations",
        "parsed_clips": clip_count,
        "temporal_windows": len(x),
        "source_video_groups": len(group_ids),
        "train_source_videos": train_groups,
        "test_source_videos": test_groups,
        "test_classification_report": report_text,
        "test_confusion_matrix_label_order": ["SAFE", "EMERGENCY"],
        "test_confusion_matrix": matrix,
        "limitations": [
            "Binary source labels do not define WARNING; this artifact cannot predict WARNING.",
            "Training features come from human-annotated boxes, while live features come from detector/tracker boxes.",
            "Evaluation is grouped by source video but is not independent deployment validation.",
            "Metrics do not establish safety, calibration, camera-hour false alarm rate, or response delay."
        ],
    }
    # Keep the held-out evaluation above, then use all reviewed windows in the
    # installed artifact so it does not discard the evaluation group's labels.
    model.fit(x, y)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"schema_version": FEATURE_SCHEMA_VERSION, "feature_names": FEATURE_NAMES,
                 "model": model, "labels": ["SAFE", "EMERGENCY"],
                 "train_source_videos": train_groups, "test_source_videos": test_groups,
                 "provenance": report["source"]}, args.output, compress=3)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Parsed {clip_count} clips, {len(x)} windows, {len(group_ids)} source videos.")
    print("Source-video-disjoint evaluation:")
    print(report_text)
    print("Confusion matrix [SAFE, EMERGENCY]:")
    print(matrix)
    print(f"Saved model: {args.output}")
    print(f"Saved evaluation: {args.report}")


if __name__ == "__main__":
    main()
