# Troubleshooting

* **`YOLO weights not found`** — train the detector, then set `YOLO_MODEL` to the real `best.pt` path in `.env`. This repository does not include weights.
* **PyTorch/CUDA installation fails** — use the official PyTorch install selector for your Windows/CUDA version, then install remaining packages. CPU works but can be slow.
* **DeepSORT import error** — activate the project virtual environment and run `pip install -r requirements.txt`.
* **Video output cannot open** — try MP4 H.264 or AVI input, update OpenCV, ensure `data/outputs` is writable, and check MP4V codec support.
* **Upload rejected** — supported extensions: MP4, MOV, AVI, MKV, WEBM. The default maximum is 500 MB.
* **Risk shows UNASSESSED** — expected until you have independently labeled temporal track windows, train a schema-matched model, and configure `RISK_MODEL`.
* **Pose says MODEL MISSING** — download a compatible MediaPipe Pose Landmarker `.task` model from the official task documentation, set `POSE_MODEL` and `POSE_ENABLED=true`, and restart the backend.
* **Dashboard says service offline** — start FastAPI at port 8000 and Vite at port 5173; set `FRONTEND_ORIGINS` if using another development address.
* **Test data reports leakage** — expected for this export. Do not quote its test metrics as independent; the audit identified duplicate image content across splits.
