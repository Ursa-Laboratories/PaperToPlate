"""Evaluation helpers for replayed liquid and pipette-tip detections.

The functions in this module deliberately operate on plain dictionaries.  They
are intended for offline evaluation of a recorded frame set, rather than for
training, threshold selection, or live instrument control.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from numbers import Real
from typing import Any


_SPLITS = {"train", "validation", "test", "excluded"}
_LABELS = {"liquid", "tip"}
_VISIBILITIES = {"clear", "uncertain"}


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def _probability(value: Any, name: str) -> float:
    number = _finite_number(value, name)
    if not 0 <= number <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _box(value: Any, name: str) -> list[float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 4:
        raise ValueError(f"{name} must contain four coordinates")
    coordinates = [_finite_number(item, f"{name}[{index}]") for index, item in enumerate(value)]
    if coordinates[2] <= coordinates[0] or coordinates[3] <= coordinates[1]:
        raise ValueError(f"{name} must be ordered as x1 < x2 and y1 < y2")
    return coordinates


def _validate_box_records(boxes: Any, name: str) -> list[dict[str, Any]]:
    if isinstance(boxes, (str, bytes)) or not isinstance(boxes, Sequence):
        raise ValueError(f"{name} must be a list")
    validated = []
    for index, record in enumerate(boxes):
        if not isinstance(record, Mapping):
            raise ValueError(f"{name}[{index}] must be an object")
        label = record.get("label")
        if label not in _LABELS:
            raise ValueError(f"{name}[{index}].label must be 'liquid' or 'tip'")
        validated.append({"label": label, "box": _box(record.get("box"), f"{name}[{index}].box")})
    return validated


def _frame_records(frames: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(frames, (str, bytes)):
        raise ValueError("frames must be an iterable of frame objects")
    try:
        rows = list(frames)
    except TypeError as exc:
        raise ValueError("frames must be an iterable of frame objects") from exc
    for index, frame in enumerate(rows):
        if not isinstance(frame, Mapping):
            raise ValueError(f"frames[{index}] must be an object")
    return rows


def validate_partition(frames: Iterable[Mapping[str, Any]], min_gap_s: float = 1) -> bool:
    """Validate annotation records and guard against temporal split leakage.

    A ``ValueError`` identifies an invalid partition.  On success the function
    returns ``True`` so callers can use it as an explicit preflight check.
    Frames marked ``uncertain`` or ``excluded`` are ignored only for the
    split-boundary temporal guard; hash reuse across split names is always
    rejected.
    """

    minimum_gap = _finite_number(min_gap_s, "min_gap_s")
    if minimum_gap < 0:
        raise ValueError("min_gap_s must be non-negative")
    rows = _frame_records(frames)
    seen_ids: set[Any] = set()
    hashes: dict[str, str] = {}
    split_times: dict[str, list[float]] = {split: [] for split in ("train", "validation", "test")}

    for index, frame in enumerate(rows):
        prefix = f"frames[{index}]"
        if "id" not in frame:
            raise ValueError(f"{prefix}.id is required")
        frame_id = frame["id"]
        try:
            duplicate = frame_id in seen_ids
            if not duplicate:
                seen_ids.add(frame_id)
        except TypeError as exc:
            raise ValueError(f"{prefix}.id must be hashable") from exc
        if duplicate:
            raise ValueError(f"duplicate frame id: {frame_id!r}")

        timestamp = _finite_number(frame.get("timestamp_s"), f"{prefix}.timestamp_s")
        split = frame.get("split")
        if split not in _SPLITS:
            raise ValueError(f"{prefix}.split is invalid")
        visibility = frame.get("visibility")
        if visibility not in _VISIBILITIES:
            raise ValueError(f"{prefix}.visibility is invalid")
        sha256 = frame.get("sha256")
        if not isinstance(sha256, str) or not sha256:
            raise ValueError(f"{prefix}.sha256 must be a non-empty string")
        prior_split = hashes.get(sha256)
        if prior_split is not None and prior_split != split:
            raise ValueError(f"sha256 appears in multiple splits: {sha256!r}")
        hashes[sha256] = split
        _validate_box_records(frame.get("boxes"), f"{prefix}.boxes")

        if visibility == "clear" and split in split_times:
            split_times[split].append(timestamp)

    split_names = tuple(split_times)
    for left_index, left_split in enumerate(split_names):
        for right_split in split_names[left_index + 1 :]:
            for left_timestamp in split_times[left_split]:
                for right_timestamp in split_times[right_split]:
                    if abs(left_timestamp - right_timestamp) < minimum_gap:
                        raise ValueError(
                            f"{left_split}/{right_split} frames are too close in time for the requested "
                            f"minimum gap ({minimum_gap:g}s)"
                        )
    return True


def _iou(left: Sequence[float], right: Sequence[float]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _validate_predictions(predictions: Mapping[Any, Iterable[Mapping[str, Any]]]) -> dict[Any, list[dict[str, Any]]]:
    if not isinstance(predictions, Mapping):
        raise ValueError("predictions must be a mapping from frame id to detections")
    result: dict[Any, list[dict[str, Any]]] = {}
    for frame_id, detections in predictions.items():
        if isinstance(detections, (str, bytes)) or not isinstance(detections, Iterable):
            raise ValueError(f"predictions[{frame_id!r}] must be an iterable")
        validated = []
        for index, detection in enumerate(detections):
            if not isinstance(detection, Mapping):
                raise ValueError(f"predictions[{frame_id!r}][{index}] must be an object")
            label = detection.get("label")
            if label not in _LABELS:
                raise ValueError(f"predictions[{frame_id!r}][{index}].label is invalid")
            confidence = _probability(detection.get("confidence"), f"predictions[{frame_id!r}][{index}].confidence")
            validated.append({"label": label, "confidence": confidence, "box": _box(detection.get("box"), f"predictions[{frame_id!r}][{index}].box")})
        result[frame_id] = validated
    return result


def evaluate(
    frames: Iterable[Mapping[str, Any]],
    predictions: Mapping[Any, Iterable[Mapping[str, Any]]],
    split: str = "test",
    label: str = "liquid",
    confidence: float = 0.25,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Evaluate one label with confidence-ordered greedy IoU matching.

    Frames with ``visibility='uncertain'`` are omitted because their boxes are
    explicitly not a clear ground truth.  Missing prediction entries are
    treated as empty and listed in ``missing_prediction_ids``.
    """

    if split not in _SPLITS:
        raise ValueError(f"split must be one of {sorted(_SPLITS)}")
    if label not in _LABELS:
        raise ValueError("label must be 'liquid' or 'tip'")
    confidence_threshold = _probability(confidence, "confidence")
    iou_cutoff = _finite_number(iou_threshold, "iou_threshold")
    if not 0 <= iou_cutoff <= 1:
        raise ValueError("iou_threshold must be between 0 and 1")

    rows = _frame_records(frames)
    validated_predictions = _validate_predictions(predictions)
    selected = []
    for index, frame in enumerate(rows):
        frame_split = frame.get("split")
        visibility = frame.get("visibility")
        if frame_split != split or visibility == "uncertain":
            continue
        if "id" not in frame:
            raise ValueError(f"frames[{index}].id is required")
        boxes = _validate_box_records(frame.get("boxes"), f"frames[{index}].boxes")
        selected.append((frame["id"], [row["box"] for row in boxes if row["label"] == label]))

    selected_ids = {frame_id for frame_id, _ in selected}
    missing_ids = [frame_id for frame_id, _ in selected if frame_id not in validated_predictions]
    unknown_ids = [frame_id for frame_id in validated_predictions if frame_id not in selected_ids]
    outcomes: dict[Any, dict[str, Any]] = {}
    true_positive = false_positive = false_negative = 0
    positive_frames = negative_frames = 0
    matched_ious: list[float] = []
    missed_positive_frames: list[Any] = []
    false_alarm_count = 0
    presence_counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}

    for frame_id, ground_truth in selected:
        candidates = [
            detection
            for detection in validated_predictions.get(frame_id, [])
            if detection["label"] == label and detection["confidence"] >= confidence_threshold
        ]
        candidates = sorted(enumerate(candidates), key=lambda item: (-item[1]["confidence"], item[0]))
        unmatched_ground_truth = set(range(len(ground_truth)))
        frame_tp = frame_fp = 0
        frame_matched_ious: list[float] = []
        for _, detection in candidates:
            best_index = None
            best_iou = -1.0
            for gt_index in unmatched_ground_truth:
                overlap = _iou(detection["box"], ground_truth[gt_index])
                if overlap > best_iou:
                    best_iou = overlap
                    best_index = gt_index
            if best_index is not None and best_iou >= iou_cutoff:
                unmatched_ground_truth.remove(best_index)
                frame_tp += 1
                frame_matched_ious.append(best_iou)
                matched_ious.append(best_iou)
            else:
                frame_fp += 1

        frame_fn = len(unmatched_ground_truth)
        true_positive += frame_tp
        false_positive += frame_fp
        false_negative += frame_fn
        has_positive = bool(ground_truth)
        if has_positive:
            positive_frames += 1
            if frame_tp == 0:
                missed_positive_frames.append(frame_id)
        else:
            negative_frames += 1
            if candidates:
                false_alarm_count += 1

        if has_positive and frame_tp:
            presence = "true_positive"
        elif has_positive:
            presence = "false_negative"
        elif candidates:
            presence = "false_positive"
        else:
            presence = "true_negative"
        presence_counts[{"true_positive": "tp", "false_positive": "fp", "false_negative": "fn", "true_negative": "tn"}[presence]] += 1
        outcomes[frame_id] = {
            "ground_truth_count": len(ground_truth),
            "prediction_count": len(candidates),
            "tp": frame_tp,
            "fp": frame_fp,
            "fn": frame_fn,
            "matched_ious": frame_matched_ious,
            "presence": presence,
        }

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else None
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    false_alarm_rate = false_alarm_count / negative_frames if negative_frames else None
    aggregate = {"tp": true_positive, "fp": false_positive, "fn": false_negative, "precision": precision, "recall": recall, "f1": f1}
    result = {
        "split": split,
        "label": label,
        "confidence": confidence_threshold,
        "iou_threshold": iou_cutoff,
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "aggregate": aggregate,
        "frame_presence": presence_counts,
        "presence_tp": presence_counts["tp"],
        "presence_fp": presence_counts["fp"],
        "presence_fn": presence_counts["fn"],
        "presence_tn": presence_counts["tn"],
        "positive_frames": positive_frames,
        "negative_frames": negative_frames,
        "false_alarm_count": false_alarm_count,
        "false_alarm_denominator": negative_frames,
        "false_alarm_rate": false_alarm_rate,
        "missed_positive_frames": missed_positive_frames,
        "matched_ious": matched_ious,
        "outcomes": outcomes,
        "missing_prediction_ids": missing_ids,
        "unknown_prediction_ids": unknown_ids,
    }
    return result
