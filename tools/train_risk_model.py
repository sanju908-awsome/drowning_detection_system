#!/usr/bin/env python
"""Train a risk Random Forest only from human-labeled temporal track windows."""
import argparse
import csv
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit

from drowning_watch.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("labels_csv", type=Path, help="CSV with video_id, risk_label, and all motion-v1 features")
    cli.add_argument("--output", type=Path, default=Path("models/risk_model.joblib"))
    args = cli.parse_args()
    required = {"video_id", "risk_label", *FEATURE_NAMES}
    with args.labels_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("No annotation rows were found.")
    missing = required - set(rows[0])
    if missing:
        raise SystemExit(f"Missing required columns: {', '.join(sorted(missing))}")
    labels = [row["risk_label"].upper().strip() for row in rows]
    allowed = {"SAFE", "WARNING", "EMERGENCY"}
    if set(labels) - allowed:
        raise SystemExit("risk_label must contain only SAFE, WARNING, EMERGENCY.")
    if set(labels) != allowed:
        raise SystemExit("All three labels SAFE, WARNING, and EMERGENCY must be represented before fitting.")
    groups = [row["video_id"] for row in rows]
    if len(set(groups)) < 3:
        raise SystemExit("At least three distinct source videos are needed for group-separated train/test evaluation.")
    x = [[float(row[name]) for name in FEATURE_NAMES] for row in rows]
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(splitter.split(x, labels, groups))
    train_groups, test_groups = {groups[i] for i in train_idx}, {groups[i] for i in test_idx}
    if train_groups & test_groups:
        raise SystemExit("Source-video leakage detected in group split.")
    if {labels[i] for i in train_idx} != allowed or {labels[i] for i in test_idx} != allowed:
        raise SystemExit("The fixed group-held-out split must contain all three labels on both sides; add more labeled source videos.")
    model = RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample", random_state=42,
                                   min_samples_leaf=3, n_jobs=-1)
    model.fit([x[i] for i in train_idx], [labels[i] for i in train_idx])
    predictions = model.predict([x[i] for i in test_idx])
    print("Group-held-out evaluation (source videos are disjoint):")
    print(classification_report([labels[i] for i in test_idx], predictions, labels=sorted(allowed), zero_division=0))
    print("Confusion matrix label order", sorted(allowed))
    print(confusion_matrix([labels[i] for i in test_idx], predictions, labels=sorted(allowed)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"schema_version": FEATURE_SCHEMA_VERSION, "feature_names": FEATURE_NAMES,
                 "model": model, "labels": sorted(allowed), "train_source_videos": sorted(train_groups),
                 "test_source_videos": sorted(test_groups)}, args.output)
    print(f"Saved model: {args.output}")


if __name__ == "__main__":
    main()
