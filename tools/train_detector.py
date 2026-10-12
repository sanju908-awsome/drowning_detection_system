#!/usr/bin/env python
"""Train and independently validate a YOLOv8 detector from a corrected dataset YAML."""
import argparse
from pathlib import Path

import yaml


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("dataset_yaml", type=Path)
    cli.add_argument("--model", default="yolov8n.pt")
    cli.add_argument("--epochs", type=int, default=50)
    cli.add_argument("--imgsz", type=int, default=640)
    cli.add_argument("--batch", type=int, default=8)
    cli.add_argument("--device", default="")
    cli.add_argument("--project", default="runs/detect")
    cli.add_argument("--name", default="poolwatch")
    cli.add_argument("--workers", type=int, default=4)
    args = cli.parse_args()
    data = yaml.safe_load(args.dataset_yaml.read_text(encoding="utf-8"))
    if not data.get("names") or int(data.get("nc", 0)) != len(data["names"]):
        raise SystemExit("Dataset YAML class names and nc do not match.")
    # The export repeats several semantic classes with case-only spelling differences.
    print("Dataset classes:", data["names"])
    print("Review docs/dataset_report.md: duplicated case-only classes and cross-split exact duplicates were found.")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install requirements.txt before training (Ultralytics/PyTorch required).") from exc
    model = YOLO(args.model)
    results = model.train(data=str(args.dataset_yaml.resolve()), epochs=args.epochs, imgsz=args.imgsz,
                          batch=args.batch, device=args.device or None, project=args.project,
                          name=args.name, workers=args.workers, seed=42, deterministic=True,
                          patience=15, plots=True)
    best = Path(results.save_dir) / "weights" / "best.pt"
    if not best.is_file():
        raise SystemExit(f"Training finished but expected checkpoint was not found: {best}")
    print(f"Best checkpoint: {best}")
    print("Running one test-split evaluation. Treat metrics as contaminated until duplicate/source leakage is resolved.")
    metrics = YOLO(str(best)).val(data=str(args.dataset_yaml.resolve()), split="test", plots=True)
    print("Test metrics (not independent because the supplied archive has cross-split duplicates):")
    print(metrics.results_dict)


if __name__ == "__main__":
    main()
