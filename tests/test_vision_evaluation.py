import math

import pytest

from paper_to_plate.vision_evaluation import evaluate, validate_partition


def frame(frame_id, timestamp, split, boxes, *, sha=None, visibility="clear"):
    return {
        "id": frame_id,
        "timestamp_s": timestamp,
        "split": split,
        "sha256": sha or frame_id,
        "boxes": boxes,
        "visibility": visibility,
    }


def box(label, coordinates):
    return {"label": label, "box": coordinates}


def detection(label, confidence, coordinates):
    return {"label": label, "confidence": confidence, "box": coordinates}


def test_wrong_location_on_positive_is_not_a_true_positive():
    frames = [frame("positive", 10, "test", [box("liquid", [0, 0, 10, 10])])]
    result = evaluate(frames, {"positive": [detection("liquid", .9, [20, 20, 30, 30])]})
    assert result["tp"] == 0
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["missed_positive_frames"] == ["positive"]


def test_duplicate_prediction_counts_as_false_positive():
    frames = [frame("positive", 10, "test", [box("liquid", [0, 0, 10, 10])])]
    predictions = {"positive": [detection("liquid", .95, [0, 0, 10, 10]), detection("liquid", .9, [0, 0, 10, 10])]}
    result = evaluate(frames, predictions)
    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 0


def test_clean_negative_has_a_false_alarm_denominator_without_accuracy_inflation():
    frames = [frame("negative", 10, "test", [])]
    result = evaluate(frames, {"negative": []})
    assert result["negative_frames"] == 1
    assert result["false_alarm_count"] == 0
    assert result["false_alarm_denominator"] == 1
    assert result["false_alarm_rate"] == 0
    assert "accuracy" not in result


def test_undefined_metrics_have_none_and_missing_predictions_are_reported():
    frames = [frame("positive", 10, "test", [box("liquid", [0, 0, 10, 10])])]
    result = evaluate(frames, {})
    assert result["tp"] == 0 and result["fp"] == 0 and result["fn"] == 1
    assert result["precision"] is None
    assert result["recall"] == 0
    assert result["f1"] is None
    assert result["missing_prediction_ids"] == ["positive"]


def test_validate_partition_rejects_duplicate_ids_hash_reuse_bad_boxes_and_temporal_leakage():
    with pytest.raises(ValueError, match="duplicate"):
        validate_partition([frame("same", 0, "test", []), frame("same", 2, "test", [])])
    with pytest.raises(ValueError, match="multiple splits"):
        validate_partition([frame("train", 0, "train", [], sha="same"), frame("test", 2, "test", [], sha="same")])
    with pytest.raises(ValueError, match="ordered"):
        validate_partition([frame("bad", 0, "test", [box("liquid", [2, 0, 1, 3])])])
    with pytest.raises(ValueError, match="too close"):
        validate_partition([frame("train", 0, "train", []), frame("test", .5, "test", [])], min_gap_s=1)


def test_temporal_guard_ignores_uncertain_and_excluded_frames():
    frames = [
        frame("train", 0, "train", []),
        frame("uncertain", .1, "test", [], visibility="uncertain"),
        frame("excluded", .2, "excluded", []),
    ]
    assert validate_partition(frames, min_gap_s=1)


def test_matched_iou_and_per_frame_presence_are_localized():
    frames = [
        frame("positive", 1, "test", [box("liquid", [0, 0, 10, 10])]),
        frame("negative", 2, "test", []),
    ]
    result = evaluate(
        frames,
        {
            "positive": [detection("liquid", .8, [1, 1, 9, 9])],
            "negative": [detection("liquid", .8, [1, 1, 9, 9])],
        },
    )
    assert math.isclose(result["matched_ious"][0], .64)
    assert result["outcomes"]["positive"]["presence"] == "true_positive"
    assert result["outcomes"]["negative"]["presence"] == "false_positive"
    assert result["false_alarm_count"] == 1
