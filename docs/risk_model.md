# Temporal risk model

## Installed model

An **experimental binary temporal classifier** is installed locally at `models/risk_model.joblib`. It was trained from public Lifeguard CVAT annotations in [Z5cc/drowning-detection](https://github.com/Z5cc/drowning-detection), using per-track motion windows derived from annotated bounding boxes. That upstream repository does not specify a license for the annotation data, so the generated checkpoint is not committed or pushed. It predicts `SAFE` or `EMERGENCY`; the source data has no `WARNING` annotation, so this model cannot predict `WARNING`. It runs on tracked frames in uploaded-video analysis and on the RTSP CCTV stream. The separate YOLO `Drowning` class also emits an immediate detector warning.

The model is research-only, not a validated rescue device. On a source-video-disjoint test split, its binary argmax classifier had `EMERGENCY` precision 0.39 and recall 0.72. These results use annotation-derived boxes; live inference uses detector/tracker boxes, so performance may differ. The complete report is in [temporal_model_evaluation.json](temporal_model_evaluation.json). It does not establish calibrated probabilities, incident-level latency, camera-hour false alarms, or safety. Continue human supervision and emergency procedures.

## Feature schema motion-v2

`backend/drowning_watch/features.py` keeps up to 150 observations per track; processing resets a history after a gap longer than one second. Before feature extraction, boxes are normalized to a 224x224 reference canvas. This removes resolution-only scaling differences; camera angle, crop, perspective, frame rate and occlusion remain domain shifts. Features are: observation count (frames), track duration (seconds), mean center speed (reference pixels/second), population standard deviation of speed (reference pixels/second), net center displacement (reference pixels), mean detector confidence (unit interval), and pose visibility ratio (mean MediaPipe landmark visibility; 0 when unavailable). The installed model was trained with confidence fixed at 1 and pose unavailable, so it learns motion features, not pose.

Pose uses MediaPipe Tasks Pose Landmarker in IMAGE mode on each tracked crop. It requires a compatible `.task` model asset at `models/pose_landmarker.task`; pose is enabled by default in local settings and missing/low-visibility landmarks do not stop video processing. Visible landmarks are overlaid in the processed video. Pose has not been evaluated for this classifier.

## Training and evaluation

The installed artifact was trained with `tools/train_temporal_from_cvat.py`, using CVAT XML box trajectories. The tool associates adjacent-frame boxes by class and IoU, extracts motion-v2 windows, and groups by the original 11-character YouTube source ID to prevent clips from one source leaking across the split. It prints the held-out report and then fits the installed artifact using all annotated windows. Reproduce with the labels directory from Z5cc/drowning-detection:

```powershell
$env:PYTHONPATH = "backend"
python tools/train_temporal_from_cvat.py C:\path\to\drowning-detection\dataset_lifeguard\labels
```

The public annotations distinguish `swim` from `drown`; they do not define a warning class. Training tracks are reconstructed from adjacent boxes, while live tracking comes from the project's detector and DeepSORT. The source-video-held-out metrics are promising enough for software integration only, not deployment. The existing `tools/train_risk_model.py` remains available for project-specific CSVs with independently reviewed SAFE/WARNING/EMERGENCY windows.

The runtime settings `RISK_MIN_OBSERVATIONS=30`, `RISK_MIN_PROBABILITY=0.7`, `RISK_EMERGENCY_CONFIRMATION_FRAMES=3`, and `RISK_CLEAR_CONFIRMATION_FRAMES=15` are configurable guardrails, not empirically selected values. The report uses argmax predictions and does not estimate deployed alert behavior under these thresholds. Probability calibration, repeated grouped cross-validation, event-level sensitivity, alert delay, and false alarms per camera-hour remain unmeasured.
