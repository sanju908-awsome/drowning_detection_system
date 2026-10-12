#!/usr/bin/env python
"""Write a corrected training YAML without editing the downloaded Roboflow files."""
import argparse
from pathlib import Path

import yaml


def prepare(root: Path, destination: Path) -> Path:
    root = root.resolve()
    metadata = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
    names = metadata.get("names")
    if not isinstance(names, (list, dict)) or not names:
        raise ValueError("data.yaml must define non-empty class names")
    nc = int(metadata.get("nc", len(names)))
    if nc != len(names):
        raise ValueError(f"data.yaml declares nc={nc}, but names contains {len(names)} classes")
    fixed = {"path": str(root), "train": "train/images", "val": "valid/images",
             "test": "test/images", "nc": nc, "names": names}
    for split in ("train", "valid", "test"):
        image_dir = root / split / "images"
        if not image_dir.is_dir() or not any(image_dir.iterdir()):
            raise FileNotFoundError(f"Missing or empty split: {image_dir}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(fixed, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return destination


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("dataset_root", type=Path)
    cli.add_argument("--output", type=Path, default=Path("artifacts/dataset.yaml"))
    args = cli.parse_args()
    print(prepare(args.dataset_root, args.output).resolve())
