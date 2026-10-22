#!/usr/bin/env python3
"""Train and evaluate the local source-data vision baselines.

This script runs two complementary experiments:

* a small YOLOv8 detector trained on the source YOLO annotations;
* a frozen pretrained DINOv2 ViT-S/14 feature extractor with a fitted
  multiclass logistic-regression head over tip, liquid and background crops.

The DINO head is a feature classifier rather than an object detector.  The
optional reranker uses YOLO candidate boxes; the independent adapter uses sliding windows to
re-score/label those candidates.  Target-domain frames and annotations are
never silently mixed into the source split; ``data/vision/annotations`` is an
explicit future correction/retraining input.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
import joblib


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data/vision/dataset"
DEFAULT_REPORT = ROOT / "data/vision/training-report.json"
DEFAULT_MODELS = ROOT / "data/vision/models"
SEED = 20261022
CLASS_NAMES = ["tip", "liquid", "background"]


def seed_everything(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def device_name() -> str:
    return "mps" if torch.backends.mps.is_available() else "cpu"


def read_boxes(label_path: Path, width: int, height: int) -> list[tuple[int, tuple[int, int, int, int]]]:
    boxes = []
    if not label_path.exists():
        return boxes
    for row in label_path.read_text().splitlines():
        fields = row.split()
        if len(fields) != 5:
            continue
        class_id, cx, cy, bw, bh = int(fields[0]), *(float(v) for v in fields[1:])
        x1 = max(0, int((cx - bw / 2) * width))
        y1 = max(0, int((cy - bh / 2) * height))
        x2 = min(width, int((cx + bw / 2) * width))
        y2 = min(height, int((cy + bh / 2) * height))
        if x2 > x1 and y2 > y1:
            boxes.append((class_id, (x1, y1, x2, y2)))
    return boxes


def iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union else 0.0


def crop_box(image: Image.Image, box: tuple[int, int, int, int], padding: float = 0.15) -> Image.Image:
    width, height = image.size
    x1, y1, x2, y2 = box
    dx, dy = (x2 - x1) * padding, (y2 - y1) * padding
    return image.crop((max(0, int(x1 - dx)), max(0, int(y1 - dy)), min(width, int(x2 + dx)), min(height, int(y2 + dy))))


def dino_samples(dataset: Path, split: str, target_background_manifest: Path | None = None) -> tuple[list[Image.Image], list[int], list[dict[str, Any]]]:
    images, labels, metadata = [], [], []
    image_dir = dataset / split / "images"
    label_dir = dataset / split / "labels"
    for image_path in sorted(image_dir.glob("*")):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
        boxes = read_boxes(label_dir / f"{image_path.stem}.txt", *image.size)
        for class_id, box in boxes:
            if class_id not in (0, 1):
                continue
            images.append(crop_box(image, box))
            labels.append(class_id)
            metadata.append({"image": image_path.name, "class": CLASS_NAMES[class_id], "source": "label"})
        # Deterministic background candidates. These are candidate regions, not
        # synthetic negatives, and are rejected when they overlap an annotation.
        width, height = image.size
        candidate_w, candidate_h = max(32, int(width * 0.22)), max(32, int(height * 0.28))
        candidates = []
        for row in range(4):
            for col in range(5):
                x1 = int((width - candidate_w) * col / 4)
                y1 = int((height - candidate_h) * row / 3)
                candidate = (x1, y1, min(width, x1 + candidate_w), min(height, y1 + candidate_h))
                if all(iou(candidate, box) < 0.04 for _, box in boxes):
                    candidates.append(candidate)
        for index, candidate in enumerate(candidates[:3]):
            images.append(image.crop(candidate))
            labels.append(2)
            metadata.append({"image": image_path.name, "class": "background", "source": "candidate", "index": index})
    if split == "train" and target_background_manifest and target_background_manifest.exists():
        manifest = json.loads(target_background_manifest.read_text())
        image_path = Path(manifest["image_path"])
        if not image_path.is_file():
            raise FileNotFoundError(f"Target background image is missing: {image_path}")
        with Image.open(image_path) as opened:
            background_image = opened.convert("RGB")
        width, height = background_image.size
        for index, raw_box in enumerate(manifest.get("boxes", [])):
            if len(raw_box) != 4:
                raise ValueError(f"Target background box {index} must have four coordinates")
            box = tuple(int(value) for value in raw_box)
            if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
                raise ValueError(f"Target background box {index} is outside the image")
            images.append(background_image.crop(box))
            labels.append(2)
            metadata.append({"image": str(image_path), "class": "background", "source": manifest.get("label_source", "assistant_visual_review"), "index": index, "evaluation": "training_only"})
    return images, labels, metadata


def load_dino(device: str):
    """Load DINOv2 Vits14 weights from the official Facebook Research hub."""

    # trust_repo is supported by current torch and avoids an interactive prompt.
    model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14", trust_repo=True)
    model.eval().to(device)
    return model


def dino_transform():
    from torchvision import transforms

    return transforms.Compose([
        transforms.Resize((224, 224), antialias=True),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])


def dino_features(model, crops: list[Image.Image], device: str, batch_size: int = 32) -> np.ndarray:
    transform = dino_transform()
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(crops), batch_size):
            batch = torch.stack([transform(crop) for crop in crops[start:start + batch_size]]).to(device)
            outputs.append(model(batch).detach().cpu().numpy())
    return np.concatenate(outputs, axis=0) if outputs else np.empty((0, 384), dtype=np.float32)


def classification_metrics(y_true: list[int], y_pred: np.ndarray) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=[0, 1, 2], zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=[0, 1, 2], average="macro", zero_division=0)),
        "per_class": {CLASS_NAMES[index]: {"precision": float(precision[index]), "recall": float(recall[index]), "f1": float(f1[index]), "support": int(support[index])} for index in range(3)},
        "confusion_matrix_rows_true_cols_pred": confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist(),
    }


def predict_head_proba(head, features: np.ndarray) -> np.ndarray:
    """Numerically checked linear-head probabilities without arm64 BLAS warnings."""

    values = np.asarray(features, dtype=np.float64, order="C")
    if values.ndim != 2 or not np.isfinite(values).all():
        raise RuntimeError("DINO feature extractor returned non-finite values")
    logits = np.einsum("nd,cd->nc", values, np.asarray(head.coef_, dtype=np.float64), optimize=True)
    logits += np.asarray(head.intercept_, dtype=np.float64)
    if not np.isfinite(logits).all():
        raise RuntimeError("DINO classifier produced non-finite logits")
    logits -= logits.max(axis=1, keepdims=True)
    probabilities = np.exp(logits)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    if not np.isfinite(probabilities).all():
        raise RuntimeError("DINO classifier produced non-finite probabilities")
    return probabilities


def dense_windows(width: int, height: int) -> list[tuple[int, int, int, int]]:
    windows = []
    for width_fraction, height_fraction in ((0.06, 0.58), (0.045, 0.34)):
        window_width = max(18, int(width * width_fraction))
        window_height = max(40, int(height * height_fraction))
        step_x, step_y = max(10, window_width // 2), max(12, window_height // 3)
        xs = list(range(0, max(1, width - window_width + 1), step_x))
        ys = list(range(0, max(1, height - window_height + 1), step_y))
        if not xs or xs[-1] != width - window_width:
            xs.append(max(0, width - window_width))
        if not ys or ys[-1] != height - window_height:
            ys.append(max(0, height - window_height))
        windows.extend((x, y, min(width, x + window_width), min(height, y + window_height)) for y in ys for x in xs)
    return windows


def dense_nms(detections: list[dict[str, Any]], width: int, threshold: float = 0.25) -> list[dict[str, Any]]:
    kept = []
    for candidate in sorted(detections, key=lambda item: item["confidence"], reverse=True):
        x1, y1, x2, y2 = candidate["box"]
        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        suppress = False
        for prior in kept:
            if candidate["label"] != prior["label"]:
                continue
            a1, b1, a2, b2 = prior["box"]
            intersection = max(0.0, min(x2, a2) - max(x1, a1)) * max(0.0, min(y2, b2) - max(y1, b1))
            prior_area = max(0.0, a2 - a1) * max(0.0, b2 - b1)
            union = area + prior_area - intersection
            if union and intersection / union >= threshold:
                suppress = True
                break
        if not suppress:
            kept.append(candidate)
    return [item for label in ("tip", "liquid") for item in sorted((x for x in kept if x["label"] == label), key=lambda x: x["confidence"], reverse=True)[:16]]


def dense_detector_metrics(model, head, dataset: Path, device: str) -> dict[str, Any]:
    """Measure independent dense DINO boxes at IoU >= .50 on source test images."""

    transform = dino_transform()
    totals = {name: {"tp": 0, "fp": 0, "fn": 0} for name in ("tip", "liquid")}
    for image_path in sorted((dataset / "test/images").glob("*")):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        image = Image.open(image_path).convert("RGB")
        windows = dense_windows(*image.size)
        crops = [transform(image.crop(window)) for window in windows]
        probabilities = []
        with torch.inference_mode():
            for start in range(0, len(crops), 32):
                batch = torch.stack(crops[start:start + 32]).to(device)
                features = model(batch).float().detach().cpu().numpy()
                probabilities.extend(predict_head_proba(head, features))
        detections = []
        for box, probability in zip(windows, probabilities):
            tip_p, liquid_p, background_p = [float(value) for value in probability]
            class_id = 0 if tip_p >= liquid_p else 1
            score = (1.0 - background_p) * max(tip_p, liquid_p)
            if score >= 0.50:
                detections.append({"label": CLASS_NAMES[class_id], "confidence": score, "box": [float(value) for value in box]})
        detections = dense_nms(detections, image.width)
        ground_truth = []
        for class_id, box in read_boxes(dataset / "test/labels" / f"{image_path.stem}.txt", *image.size):
            ground_truth.append((CLASS_NAMES[class_id], box, False))
        used = [False] * len(ground_truth)
        for detection in detections:
            best_iou, best_index = 0.0, None
            for index, (label, box, _) in enumerate(ground_truth):
                if used[index] or label != detection["label"]:
                    continue
                x1, y1, x2, y2 = detection["box"]
                a1, b1, a2, b2 = box
                intersection = max(0.0, min(x2, a2) - max(x1, a1)) * max(0.0, min(y2, b2) - max(y1, b1))
                union = (x2 - x1) * (y2 - y1) + (a2 - a1) * (b2 - b1) - intersection
                overlap = intersection / union if union else 0.0
                if overlap > best_iou:
                    best_iou, best_index = overlap, index
            if best_iou >= 0.50 and best_index is not None:
                used[best_index] = True
                totals[detection["label"]]["tp"] += 1
            else:
                totals[detection["label"]]["fp"] += 1
        for index, (label, _, _) in enumerate(ground_truth):
            if not used[index]:
                totals[label]["fn"] += 1
    for values in totals.values():
        precision = values["tp"] / (values["tp"] + values["fp"]) if values["tp"] + values["fp"] else 0.0
        recall = values["tp"] / (values["tp"] + values["fn"]) if values["tp"] + values["fn"] else 0.0
        values.update({"precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0})
    return {"iou_threshold": 0.50, "score_threshold": 0.50, "per_class": totals, "note": "Independent sliding-window DINOv2 boxes; no YOLO proposals. Exploratory source-family metric, not MX Brio validation."}


def train_dino(dataset: Path, models: Path, device: str, seed: int, target_background_manifest: Path | None = None) -> dict[str, Any]:
    started = time.time()
    dino = load_dino(device)
    train_crops, train_labels, train_meta = dino_samples(dataset, "train", target_background_manifest)
    val_crops, val_labels, val_meta = dino_samples(dataset, "validation")
    test_crops, test_labels, test_meta = dino_samples(dataset, "test")
    train_features = dino_features(dino, train_crops, device)
    val_features = dino_features(dino, val_crops, device)
    test_features = dino_features(dino, test_crops, device)
    head = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed, multi_class="auto")
    head.fit(train_features, train_labels)
    head_path = models / "dino-v2-vits14-head.joblib"
    joblib.dump(head, head_path)
    val_pred = np.argmax(predict_head_proba(head, val_features), axis=1)
    test_pred = np.argmax(predict_head_proba(head, test_features), axis=1)
    # Keep crop metadata beside the report for future error analysis.
    (models / "dino-v2-vits14-feature-metadata.json").write_text(json.dumps({"train": train_meta, "validation": val_meta, "test": test_meta}, indent=2))
    return {
        "model_id": "facebookresearch/dinov2:dinov2_vits14",
        "feature_dim": int(train_features.shape[1]),
        "head": "sklearn LogisticRegression(class_weight=balanced, max_iter=1000)",
        "weights_path": str(head_path.resolve()),
        "train_crops": len(train_labels),
        "validation_crops": len(val_labels),
        "test_crops": len(test_labels),
        "target_background_training": {
            "manifest": str(target_background_manifest.resolve()) if target_background_manifest and target_background_manifest.exists() else None,
            "crops": sum(1 for item in train_meta if item.get("source") == "assistant_visual_review"),
            "label_source": "assistant_visual_review; training-only background crops, not human annotations or evaluation truth",
        },
        "validation": classification_metrics(val_labels, val_pred),
        "test": classification_metrics(test_labels, test_pred),
        "end_to_end_detection": dense_detector_metrics(dino, head, dataset, device),
        "seconds": round(time.time() - started, 2),
        "localization": "Independent dense sliding-window candidate boxes; no YOLO proposals. The optional dino_rerank adapter uses YOLO proposals separately.",
    }


def train_yolo(dataset: Path, models: Path, device: str, epochs: int, seed: int, imgsz: int, model_path: str, project: Path, run_name: str, lr0: float, batch: int, amp: bool) -> dict[str, Any]:
    from ultralytics import YOLO

    started = time.time()
    model = YOLO(model_path)
    run_dir = project
    results = model.train(
        data=str((dataset / "data.yaml").resolve()),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        workers=0,
        patience=max(3, min(8, epochs // 2)),
        seed=seed,
        project=str(run_dir),
        name=run_name,
        exist_ok=True,
        verbose=False,
        plots=True,
        lr0=lr0,
        amp=amp,
    )
    best_path = Path(results.save_dir) / "weights/best.pt"
    target_path = models / "yolov8n-tip-liquid-source.pt"
    shutil.copy2(best_path, target_path)
    metrics = model.val(data=str((dataset / "data.yaml").resolve()), split="test", imgsz=imgsz, batch=8, device=device, plots=True, verbose=False)
    box = metrics.box
    return {
        "model_id": "ultralytics/yolov8n",
        "initialization": str(Path(model_path).resolve()),
        "classes": ["tip", "liquid"],
        "epochs_requested": epochs,
        "imgsz": imgsz,
        "weights_path": str(target_path.resolve()),
        "run_dir": str(Path(results.save_dir).resolve()),
        "test": {
            "map50": float(box.map50),
            "map50_95": float(box.map),
            "precision": float(box.mp),
            "recall": float(box.mr),
            "per_class_map50": [float(x) for x in box.ap50],
            "per_class_map50_95": [float(x) for x in box.maps],
            "per_class_order": ["tip", "liquid"],
        },
        "seconds": round(time.time() - started, 2),
        "device": device,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--models", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--model-path", default="yolov8n.pt")
    parser.add_argument("--project", type=Path, default=ROOT / "data/vision/runs/yolo")
    parser.add_argument("--run-name", default="tip-liquid-source")
    parser.add_argument("--lr0", type=float, default=0.01)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-yolo", action="store_true")
    parser.add_argument("--skip-dino", action="store_true")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--target-background-manifest", type=Path, default=ROOT / "data/vision/target-background-review.json")
    args = parser.parse_args()
    seed_everything(args.seed)
    args.models.mkdir(parents=True, exist_ok=True)
    device = device_name()
    existing: dict[str, Any] = {}
    if args.report.exists() and (args.skip_yolo or args.skip_dino):
        try:
            existing = json.loads(args.report.read_text())
        except json.JSONDecodeError:
            existing = {}
    report: dict[str, Any] = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": args.seed,
        "device": device,
        "python": os.sys.version,
        "torch": torch.__version__,
        "dataset_manifest": str((args.dataset / "manifest.json").resolve()),
        "models": dict(existing.get("models", {})),
        "runtime_smoke": existing.get("runtime_smoke", {}),
        "numerical_stability": existing.get("numerical_stability", {
            "observed_during_investigation": "Finite DINO features triggered NumPy 2.2.3 arm64 BLAS warnings inside sklearn safe_sparse_dot; raw feature/probability values remained finite.",
            "runtime_fix": "Adapter uses checked float64 einsum plus stable softmax and raises RuntimeError on non-finite features, logits or probabilities.",
            "invalid_output_policy": "Invalid model output fails inference rather than becoming an apparent low-confidence detection.",
        }),
        "limitations": [
            "Source archive provenance and license were not independently verified; images/weights remain local and are not redistributed.",
            "The source set is small and capture-family split; held-out metrics estimate source-family transfer only, not MX Brio performance.",
            "No MX Brio target-domain frames were available for human review during this run.",
            "Detector outputs are visual evidence only and do not establish liquid volume, identity, sterility, or protocol correctness.",
            "DINOv2 crop-head metrics are distinct from its lower end-to-end dense-box metrics; independent mode uses sliding windows and no YOLO proposals.",
            "The official facebook/dinov3-vits16-pretrain-lvd1689m endpoint returned HTTP 401 (restricted/authenticated) in this environment; DINOv2 was used instead.",
        ],
    }
    if not args.skip_yolo:
        report["models"]["yolo"] = train_yolo(args.dataset, args.models, device, args.epochs, args.seed, args.imgsz, args.model_path, args.project, args.run_name, args.lr0, args.batch, args.amp)
    if not args.skip_dino:
        report["models"]["dino"] = train_dino(args.dataset, args.models, device, args.seed, args.target_background_manifest)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
