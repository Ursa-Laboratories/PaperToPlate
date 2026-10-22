#!/usr/bin/env python3
"""Prepare the public OT2 source archive for leakage-aware local training.

The source archive contains YOLO text labels.  Images from one source capture
sequence are kept in one split by a deterministic filename-family grouping.
This script copies the source into an ignored, runnable dataset directory and
writes a machine-readable manifest used by ``vision_train.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image


DEFAULT_SOURCE = Path("data/vision/source/extracted/Images_with_Labels_tips_n_Liquid")
DEFAULT_OUT = Path("data/vision/dataset")
CLASS_NAMES = {0: "tip", 1: "liquid"}


def group_name(stem: str) -> str:
    """Map source filename families to capture/source groups.

    These groups are intentionally conservative: volume sequences and camera
    families are never split across train/validation/test.
    """

    value = stem.casefold()
    if value.startswith("deckimage"):
        return "deck"
    if value.startswith("tipswaterred"):
        return "tips_water_red"
    if value.startswith("tipswater"):
        return "tips_water"
    if value.startswith("tipsemptyresdual"):
        return "tips_empty_residual"
    if value.startswith("ai__h60__blue"):
        return "ai_h60_blue"
    if value.startswith("ai__h60__light blue"):
        return "ai_h60_light_blue"
    if value.startswith("ai__h60"):
        return "ai_h60"
    if value.startswith("ai"):
        return "ai_series"
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_") or "unknown"


# Explicit families make the held-out source domain stable and auditable.  The
# source has only a handful of camera/run families, so a random image split
# would materially overstate generalization.
SPLIT_BY_GROUP = {
    "tips_water_red": "test",
    "ai_h60_light_blue": "validation",
    "deck": "validation",
    "ai_h60": "train",
    "ai_h60_blue": "train",
    "ai_series": "train",
    "tips_water": "train",
    "tips_empty_residual": "train",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_labels(path: Path) -> list[str]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        text = line.strip()
        if not text:
            continue
        fields = text.split()
        if len(fields) != 5:
            raise ValueError(f"{path}:{line_number}: expected YOLO class x y w h")
        class_id = int(fields[0])
        if class_id not in CLASS_NAMES:
            raise ValueError(f"{path}:{line_number}: unsupported class {class_id}")
        coords = [float(value) for value in fields[1:]]
        if any(not math.isfinite(value) or value < 0 or value > 1 for value in coords) or coords[2] <= 0 or coords[3] <= 0:
            raise ValueError(f"{path}:{line_number}: normalized coordinates out of range")
        rows.append(text)
    return rows


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "frame"


def _read_reviewed_annotations(directory: Path, target_split: str) -> list[dict]:
    """Read human-reviewed pixel boxes only after an explicit split choice."""

    if target_split not in {"train", "validation", "test"}:
        raise ValueError("--target-split must be train, validation or test")
    records = []
    for annotation in sorted(directory.glob("*.json")):
        payload = json.loads(annotation.read_text())
        if payload.get("reviewed") is not True:
            raise ValueError(f"{annotation}: only reviewed=true annotations can be imported")
        frame_id = str(payload.get("frame_id", "")).strip()
        image_raw = str(payload.get("image_path", "")).strip()
        if not frame_id or not image_raw:
            raise ValueError(f"{annotation}: frame_id and image_path are required")
        image_path = Path(image_raw)
        if not image_path.is_absolute():
            image_path = (annotation.parent / image_path).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"{annotation}: image_path does not exist: {image_path}")
        with Image.open(image_path) as opened:
            width, height = opened.size
        labels = []
        for index, box_record in enumerate(payload.get("boxes", [])):
            label = str(box_record.get("label", "")).casefold()
            if label not in ("tip", "liquid"):
                raise ValueError(f"{annotation}: boxes[{index}] label must be tip or liquid")
            box = box_record.get("box")
            if not isinstance(box, list) or len(box) != 4:
                raise ValueError(f"{annotation}: boxes[{index}] box must be [x1,y1,x2,y2]")
            x1, y1, x2, y2 = (float(value) for value in box)
            if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                raise ValueError(f"{annotation}: boxes[{index}] is outside image bounds")
            class_id = 0 if label == "tip" else 1
            labels.append(f"{class_id} {(x1+x2)/(2*width):.6f} {(y1+y2)/(2*height):.6f} {(x2-x1)/width:.6f} {(y2-y1)/height:.6f}")
        session_id = str(payload.get("session_id", frame_id)).strip() or frame_id
        records.append({"source": str(image_path), "image": f"target_{_safe_name(frame_id)}{image_path.suffix.lower()}", "frame_id": frame_id, "session_id": session_id, "split": target_split, "group": f"target:{session_id}", "width": width, "height": height, "labels": labels, "annotation": str(annotation.resolve())})
    return records


def prepare(source: Path, out: Path, archive: Path | None = None, annotations: Path | None = None, target_split: str | None = None) -> dict:
    if out.resolve() == source.resolve() or out.resolve() in source.resolve().parents:
        raise ValueError('The prepared dataset cannot replace the source or a source parent.')
    if out.exists() and not (out / 'manifest.json').is_file():
        raise ValueError('Refusing to replace a directory without a generated dataset manifest.')
    images = sorted([*source.glob("*.jpg"), *source.glob("*.jpeg"), *source.glob("*.png")])
    if not images:
        raise FileNotFoundError(f"No images found under {source}")
    records = []
    class_counts = Counter()
    split_counts = Counter()
    group_counts = Counter()
    for image in images:
        labels_path = image.with_suffix(".txt")
        if not labels_path.exists():
            raise FileNotFoundError(f"Missing label file for {image.name}")
        labels = parse_labels(labels_path)
        group = group_name(image.stem)
        split = SPLIT_BY_GROUP.get(group, "train")
        with Image.open(image) as opened:
            width, height = opened.size
        for row in labels:
            class_counts[CLASS_NAMES[int(row.split()[0])]] += 1
        split_counts[split] += 1
        group_counts[group] += 1
        records.append({"image": image.name, "group": group, "split": split, "width": width, "height": height, "labels": labels})

    if len({record["group"] for record in records if record["split"] == "test"}) < 1:
        raise ValueError("Leakage-aware test group is empty")
    if set(record["split"] for record in records) != {"train", "validation", "test"}:
        raise ValueError("Expected train, validation and test splits")

    annotation_records = []
    if annotations and annotations.is_dir() and list(annotations.glob("*.json")):
        if not target_split:
            raise ValueError("Reviewed annotations require an explicit --target-split train|validation|test")
        annotation_records = _read_reviewed_annotations(annotations, target_split)
    elif target_split:
        raise ValueError("--target-split requires --annotations with reviewed JSON files")
    records.extend(annotation_records)
    for record in annotation_records:
        split_counts[record["split"]] += 1
        group_counts[record["group"]] += 1
        for row in record["labels"]:
            class_counts[CLASS_NAMES[int(row.split()[0])]] += 1
    if out.exists():
        shutil.rmtree(out)
    for split in ("train", "validation", "test"):
        (out / split / "images").mkdir(parents=True, exist_ok=True)
        (out / split / "labels").mkdir(parents=True, exist_ok=True)
    for record in records:
        source_image = Path(record.get("source", source / record["image"]))
        split = record["split"]
        shutil.copy2(source_image, out / split / "images" / record["image"])
        (out / split / "labels" / f"{Path(record['image']).stem}.txt").write_text("\n".join(record["labels"]) + "\n")

    data_yaml = "\n".join([
        f"path: {out.resolve()}",
        "train: train/images",
        "val: validation/images",
        "test: test/images",
        "names: [tip, liquid]",
        "nc: 2",
        ""])
    (out / "data.yaml").write_text(data_yaml)
    archive_record = None
    if archive and archive.exists():
        archive_record = {"path": str(archive), "sha256": sha256(archive), "bytes": archive.stat().st_size}
    manifest = {
        "source": {
            "repository": "https://github.com/BDD-G/OT2-Computer-Vision",
            "archive_name": "Training Data/Images_with_Labels_tips_n_Liquid.rar",
            "archive": archive_record,
            "class_mapping": {"0": "tip", "1": "liquid"},
            "license_status": "Repository license was not present at collection time; source images and weights are retained locally for research and are not redistributed.",
        },
        "split_policy": "Capture-family/group-aware; no image from one filename family is shared across splits. Reviewed target annotations are imported only with an explicit --target-split choice and retained under their annotation session group.",
        "groups": dict(sorted(group_counts.items())),
        "split_images": dict(split_counts),
        "label_instances": dict(class_counts),
        "records": records,
        "target_annotations": annotation_records,
        "paths": {"data_yaml": str((out / "data.yaml").resolve()), "root": str(out.resolve())},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--archive", type=Path, default=Path("data/vision/source/Images_with_Labels_tips_n_Liquid.rar"))
    parser.add_argument("--annotations", type=Path, help="Directory of reviewed annotation JSON files")
    parser.add_argument("--target-split", choices=("train", "validation", "test"), help="Required explicit split for imported reviewed annotations")
    args = parser.parse_args()
    manifest = prepare(args.source, args.out, args.archive, args.annotations, args.target_split)
    print(json.dumps({key: manifest[key] for key in ("groups", "split_images", "label_instances", "paths")}, indent=2))


if __name__ == "__main__":
    main()
