# PoolWatch — drowning detection research prototype

PoolWatch is a local research prototype for analyzing swimming-pool videos with YOLO detection, mandatory DeepSORT tracking, optional MediaPipe pose observations, per-track motion features, and a Random Forest risk classifier **only when a properly labeled and schema-matched model is supplied**.

> This is a safety-support prototype. It is not validated for rescue decisions and does not replace trained lifeguards, emergency procedures, or continuous human supervision. An experimental binary temporal classifier is installed in the current workspace; it predicts SAFE/EMERGENCY only and is not safety-validated.

## Current implementation

* FastAPI accepts bounded video uploads and runs jobs in a local worker thread.
* OpenCV decodes/annotates video, Ultralytics YOLO performs frame detections, and DeepSORT maintains track IDs. The selected job shows a refreshed tracking preview while processing.
* The supplied detector's `Drowning` class creates a provisional WARNING incident; it is a detector result, not a validated temporal risk score. Browser tones must be armed in the dashboard.
* MediaPipe Pose draws visible body landmarks when its local task asset is present; the local setup enables pose by default.
* A versioned motion feature extractor keeps per-track histories. The installed experimental classifier predicts binary SAFE/EMERGENCY from temporal motion windows. It is not validated for rescue decisions.
* SQLite stores job/incident history. React + TypeScript + Vite presents uploads, progress, processed video and event history.
* Reproducible dataset audit, dataset YAML preparation, YOLO training/test evaluation, and group-separated RF training tools are included.

Live CCTV, auth, PostgreSQL, remote storage, production queue, alert providers/buzzer, deployment, and model weights are not included. See [architecture](docs/architecture.md) and [deployment](docs/deployment.md).

## Windows setup

Use Python 3.10–3.12. Install PyTorch using the official selector if you need CUDA acceleration, then install this project:

```powershell
cd "C:\Users\DELL\OneDrive\Documents\ChatGPT\drowning_detection_system"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
New-Item -ItemType Directory -Force models | Out-Null
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task" -OutFile ".\models\pose_landmarker.task"
```

The pose task asset and detector weights are local files and are excluded from Git. The dashboard enables pose when the task asset is present.

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again. PyTorch/OpenCV installation varies by hardware; see [troubleshooting](docs/troubleshooting.md).

## Audit and prepare the Roboflow dataset

The archive is not included in Git. Keep it in Downloads or another private data folder.

```powershell
python tools/audit_dataset.py "C:\Users\DELL\Downloads\Drowning Detection And Prevention In Swimming Pools.v3i.yolov8.zip" --output artifacts/dataset_audit.json
Expand-Archive -LiteralPath "C:\Users\DELL\Downloads\Drowning Detection And Prevention In Swimming Pools.v3i.yolov8.zip" -DestinationPath .\data\roboflow-v3
python tools/prepare_dataset.py .\data\roboflow-v3
```

Archive audit summary and licensing are in [dataset report](docs/dataset_report.md). The audit found exact duplicates across splits, including train/test, and three case-only class pairs. The test split is not independent. The preparation script fixes YAML paths but does not modify labels or merge classes.

## Train a detector

```powershell
python tools/train_detector.py .\artifacts\dataset.yaml --model yolov8n.pt --epochs 50 --imgsz 640 --batch 8 --device 0
```

Use `--device cpu` if CUDA is unavailable and lower `--batch` if memory is insufficient. Ultralytics downloads a pretrained YOLOv8 checkpoint when first used. Configure the resulting actual checkpoint in `.env`, for example `YOLO_MODEL=./runs/detect/poolwatch/weights/best.pt`. Review the model's license and the dataset license before sharing artifacts. See [training notes](docs/model_training.md).

## Start the application

Terminal 1:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn drowning_watch.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd .\frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Upload a pool video and follow the job. The backend API docs are at `http://localhost:8000/docs`. Before YOLO weights are configured, a job will fail with an explicit missing-weights message.

## Temporal risk model

The local prototype was trained from public temporal CVAT box annotations. To reproduce it, see [risk-model schema and workflow](docs/risk_model.md). The generated checkpoint is not tracked because the upstream annotation repository does not specify a dataset license. For project-specific three-class training, use independently reviewed temporal windows; the CSV requires `video_id`, `risk_label` (SAFE/WARNING/EMERGENCY), and every motion-v2 feature column.

```powershell
$env:PYTHONPATH = "backend"
python tools/train_risk_model.py .\annotations\track_windows.csv --output .\models\risk_model.joblib
```

At least three distinct source videos are required. The utility groups train/test by video ID and prints real held-out metrics; do not treat those values as general performance without adequate sampling and independent validation.

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
```

Tests are software checks only; they do not validate detection accuracy or drowning-risk performance. Actual outcomes are recorded in the handover once run.

## Documentation

* [Architecture](docs/architecture.md) · [Dataset audit](docs/dataset_report.md) · [Research comparison](docs/research_comparison.md)
* [YOLO training](docs/model_training.md) · [DeepSORT](docs/deepsort.md) · [Risk model](docs/risk_model.md)
* [Camera setup status](docs/camera_setup.md) · [Alerts status](docs/alerts_setup.md) · [Deployment status](docs/deployment.md)
* [Troubleshooting](docs/troubleshooting.md)
