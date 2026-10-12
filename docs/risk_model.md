# Temporal risk model

## Current state

No temporal labels or trained classifier were present. The inference path returns `UNASSESSED` when no valid artifact exists, and also rejects a model whose schema version or feature ordering differs. Detector class names do not train this model. Warning and emergency incidents are persisted only if a compatible RF artifact returns those labels.

## Feature schema motion-v1

`backend/drowning_watch/features.py` maintains the latest 150 observations per track (window capped by count, not seconds). Processing resets a history after a gap longer than one second. Features are raw pixel/time values and should only be compared under consistent camera geometry and frame timing. Missing pose observations are omitted from the visibility average; a track with no pose observations gets 0.0. Features are: observation count (frames), track duration (seconds), mean center speed (pixels/second), population standard deviation of speed (pixels/second), net center displacement (pixels), mean detector confidence (unit interval), and pose visibility ratio (mean MediaPipe landmark visibility; 0 when unavailable). These describe motion/quality; none alone identifies distress.

Pose uses MediaPipe Tasks Pose Landmarker in IMAGE mode on each tracked crop. It requires a compatible `.task` model asset; set `POSE_ENABLED=true` and `POSE_MODEL=...` only after installing that asset. Pose errors or missing/low-visibility landmarks do not stop video processing. The official task guide lists model options and supported modes: [MediaPipe Pose Landmarker for Python](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python). The supplied project has no pose model asset, and swimming-pool pose availability/benefit has not been evaluated.

## Training workflow

Create a CSV with `video_id`, `risk_label`, and every feature in `FEATURE_NAMES`. Labels must be human-reviewed SAFE/WARNING/EMERGENCY temporal windows with a documented annotation protocol. Split by source video using the included GroupShuffleSplit workflow; do not let clips from one source enter both partitions. The tool requires all three labels in both partitions; otherwise add more independently labeled source videos. Check class coverage and uncertainty before fitting. `tools/train_risk_model.py` prints a group-held-out classification report and confusion matrix and saves a schema-versioned artifact. Its metrics are meaningful only for the supplied independently annotated video groups and class balance. Calibration, repeated grouped cross-validation, incident-level delay, sensitivity, and false alarms per camera-hour remain to be implemented.

The window cap is frame-based. Experimental confirmation/hysteresis settings are `RISK_MIN_OBSERVATIONS=30`, `RISK_MIN_PROBABILITY=0.7`, `RISK_WARNING_CONFIRMATION_FRAMES=5`, `RISK_EMERGENCY_CONFIRMATION_FRAMES=3`, and `RISK_CLEAR_CONFIRMATION_FRAMES=15`. The RF probabilities are not calibrated, and these starting values are not empirically selected; they are configurable guardrails for software evaluation only. Treat resulting alerts as research outputs only.
