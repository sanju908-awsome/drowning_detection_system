#!/usr/bin/env python
"""Audit a Roboflow YOLO dataset in place or directly inside its ZIP archive."""
import argparse
import collections
import hashlib
import json
import math
import posixpath
import re
import zipfile
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def audit_zip(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        read = archive.read
        return _audit(names, read, "zip")


def audit_directory(path: Path) -> dict:
    files = [p for p in path.rglob("*") if p.is_file()]
    names = [p.relative_to(path).as_posix() for p in files]
    contents = {p.relative_to(path).as_posix(): p for p in files}
    return _audit(names, lambda name: contents[name].read_bytes(), "directory")


def _audit(names, read, source_type: str) -> dict:
    image_decode_errors = []
    decode_check = "not run (OpenCV is unavailable)"
    try:
        import cv2
        import numpy as np
        decode_check = "OpenCV imdecode"
    except ImportError:
        cv2 = np = None
    metadata_file = next((n for n in names if posixpath.basename(n).lower() == "data.yaml"), None)
    class_count = None
    if metadata_file:
        match = re.search(r"(?m)^\s*nc\s*:\s*(\d+)\s*$", read(metadata_file).decode("utf-8", "replace"))
        if match:
            class_count = int(match.group(1))
    images = [n for n in names if posixpath.splitext(n)[1].lower() in IMAGE_EXTENSIONS
              and "/images/" in f"/{n.lower()}"]
    labels = [n for n in names if "/labels/" in f"/{n.lower()}"
              and posixpath.splitext(n)[1].lower() == ".txt"]
    image_by_stem = {(n.split("/", 1)[0], posixpath.splitext(posixpath.basename(n))[0]): n for n in images}
    label_by_stem = {(n.split("/", 1)[0], posixpath.splitext(posixpath.basename(n))[0]): n for n in labels}
    objects = collections.Counter()
    class_split = collections.defaultdict(collections.Counter)
    malformed, invalid, edge_boxes = [], [], []
    empty_labels = []
    for filename in labels:
        text = read(filename).decode("utf-8", "replace")
        if not text.strip():
            empty_labels.append(filename)
        split = filename.split("/", 1)[0]
        for line_number, line in enumerate(text.splitlines(), 1):
            fields = line.split()
            if not fields:
                continue
            try:
                if len(fields) != 5:
                    raise ValueError("expected class x_center y_center width height")
                class_id = int(fields[0])
                x, y, width, height = map(float, fields[1:])
                if class_id < 0 or (class_count is not None and class_id >= class_count) or not all(map(math.isfinite, (x, y, width, height))):
                    raise ValueError("invalid class ID or non-finite coordinates")
                if width <= 0 or height <= 0 or min(x, y, width, height) < 0 or max(x, y, width, height) > 1:
                    invalid.append(f"{filename}:{line_number}")
                elif x - width / 2 < -1e-6 or y - height / 2 < -1e-6 or x + width / 2 > 1 + 1e-6 or y + height / 2 > 1 + 1e-6:
                    edge_boxes.append(f"{filename}:{line_number}")
                objects[class_id] += 1
                class_split[split][class_id] += 1
            except (ValueError, OverflowError):
                malformed.append(f"{filename}:{line_number}")

    exact_hashes = collections.defaultdict(list)
    for filename in images:
        content = read(filename)
        exact_hashes[hashlib.sha256(content).hexdigest()].append(filename)
        if cv2 is not None and cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_UNCHANGED) is None:
            image_decode_errors.append(filename)
    cross_split = [files for files in exact_hashes.values()
                   if len({filename.split("/", 1)[0] for filename in files}) > 1]
    split_images = collections.Counter(n.split("/", 1)[0] for n in images)
    return {
        "source_type": source_type,
        "declared_class_count": class_count,
        "image_count": len(images), "label_file_count": len(labels),
        "image_splits": dict(split_images),
        "image_without_label_count": sum((n.split("/", 1)[0], posixpath.splitext(posixpath.basename(n))[0]) not in label_by_stem for n in images),
        "label_without_image_count": sum((n.split("/", 1)[0], posixpath.splitext(posixpath.basename(n))[0]) not in image_by_stem for n in labels),
        "empty_label_count": len(empty_labels), "object_counts_by_class_id": dict(sorted(objects.items())),
        "image_decode_check": decode_check, "image_decode_error_count": len(image_decode_errors),
        "image_decode_errors": image_decode_errors,
        "object_counts_by_split": {k: dict(sorted(v.items())) for k, v in sorted(class_split.items())},
        "malformed_label_lines": malformed, "invalid_label_lines": invalid,
        "boxes_crossing_image_edges": edge_boxes,
        "exact_duplicate_content_groups": sum(1 for n in exact_hashes.values() if len(n) > 1),
        "exact_duplicate_image_excess": sum(len(n) - 1 for n in exact_hashes.values() if len(n) > 1),
        "cross_split_exact_duplicate_groups": len(cross_split),
        "note": "Cross-split exact duplicates contaminate independent evaluation. Near-duplicates and source-video leakage require separate review.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Dataset directory or .zip archive")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    report = audit_zip(args.dataset) if args.dataset.suffix.lower() == ".zip" else audit_directory(args.dataset)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
