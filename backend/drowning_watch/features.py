"""Versioned, label-free per-track motion features (schema v1)."""

from collections import deque
from dataclasses import dataclass, field
from math import hypot
from typing import Any

FEATURE_SCHEMA_VERSION = "motion-v1"
FEATURE_NAMES = (
    "observations",
    "track_duration_seconds",
    "mean_center_speed_px_s",
    "center_speed_std_px_s",
    "displacement_px",
    "mean_detection_confidence",
    "pose_visibility_ratio",
)


@dataclass
class TrackHistory:
    max_observations: int = 150
    observations: deque[dict[str, Any]] = field(default_factory=deque)

    def add(self, timestamp_s: float, box: tuple[float, float, float, float], confidence: float,
            pose_visibility: float | None = None) -> None:
        x1, y1, x2, y2 = box
        self.observations.append({
            "t": float(timestamp_s), "cx": (x1 + x2) / 2, "cy": (y1 + y2) / 2,
            "confidence": float(confidence), "pose_visibility": pose_visibility,
        })
        while len(self.observations) > self.max_observations:
            self.observations.popleft()

    def as_features(self) -> dict[str, float]:
        rows = list(self.observations)
        if not rows:
            return dict.fromkeys(FEATURE_NAMES, 0.0)
        speeds = []
        for previous, current in zip(rows, rows[1:]):
            dt = current["t"] - previous["t"]
            if dt > 0:
                speeds.append(hypot(current["cx"] - previous["cx"], current["cy"] - previous["cy"]) / dt)
        duration = max(0.0, rows[-1]["t"] - rows[0]["t"])
        visible = [r["pose_visibility"] for r in rows if r["pose_visibility"] is not None]
        return {
            "observations": float(len(rows)),
            "track_duration_seconds": duration,
            "mean_center_speed_px_s": sum(speeds) / len(speeds) if speeds else 0.0,
            "center_speed_std_px_s": (sum((x - sum(speeds) / len(speeds)) ** 2 for x in speeds) / len(speeds)) ** 0.5 if speeds else 0.0,
            "displacement_px": hypot(rows[-1]["cx"] - rows[0]["cx"], rows[-1]["cy"] - rows[0]["cy"]),
            "mean_detection_confidence": sum(r["confidence"] for r in rows) / len(rows),
            "pose_visibility_ratio": sum(visible) / len(visible) if visible else 0.0,
        }

    def vector(self) -> list[float]:
        features = self.as_features()
        return [features[name] for name in FEATURE_NAMES]
