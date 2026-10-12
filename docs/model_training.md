# YOLOv8 detector training and evaluation

The repository contains a configurable trainer; no weights, GPU run, or metrics are included. The supplied Roboflow data has seven case-sensitive classes, duplicated case-only semantics, and 37 exact duplicate groups crossing splits. Its current test metrics are therefore exploratory and **not independent**.

Install dependencies and prepare the exported dataset in its extracted directory. Do not commit dataset contents or checkpoints.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python tools/audit_dataset.py "C:\Users\DELL\Downloads\Drowning Detection And Prevention In Swimming Pools.v3i.yolov8.zip"
Expand-Archive -LiteralPath "C:\Users\DELL\Downloads\Drowning Detection And Prevention In Swimming Pools.v3i.yolov8.zip" -DestinationPath .\data\roboflow-v3
python tools/prepare_dataset.py .\data\roboflow-v3
python tools/train_detector.py .\artifacts\dataset.yaml --model yolov8n.pt --epochs 50 --imgsz 640 --batch 8 --device 0
```

Use `--device cpu` if CUDA is unavailable (expect slow training). `--device 0` selects the first CUDA GPU. Reduce `--batch` on out-of-memory errors. The trainer seeds training and performs one test-split evaluation, while warning about contamination. Do not report its test values as independent. Report precision, recall, mAP50, mAP50-95, per-class metrics and confusion matrix from the real Ultralytics run; report video-level event metrics separately when temporal ground truth exists. The trainer does not fabricate or pre-fill any results.

The archive YAML references `../train/images`; `prepare_dataset.py` writes a corrected YAML pointing at the extracted root without changing the downloaded metadata. Ultralytics code and weights are subject to the license terms described in [Ultralytics licensing](https://www.ultralytics.com/license); review AGPL-3.0 obligations before redistributing or deploying this application.
