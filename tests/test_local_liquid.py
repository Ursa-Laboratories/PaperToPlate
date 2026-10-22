import importlib.util
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")
from PIL import Image

from paper_to_plate.vision_evaluation import evaluate, validate_partition
from paper_to_plate.vision_models import CameraTipDetector, YoloDetector


class _Tensor:
    def __init__(self, value):
        self.value = np.asarray(value)

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.value


def _fake_result(boxes=((1, 2, 8, 12),), confidence=(.9,), classes=(0,)):
    return SimpleNamespace(
        boxes=SimpleNamespace(
            xyxy=_Tensor(boxes),
            conf=_Tensor(confidence),
            cls=_Tensor(classes),
        )
    )


def test_local_liquid_class_mapping_keeps_only_liquid(monkeypatch, tmp_path):
    calls = []

    class FakeYOLO:
        def __init__(self, weights):
            calls.append(("init", weights))

        def predict(self, image, **kwargs):
            calls.append(("predict", kwargs))
            return [_fake_result(classes=(0, 1), boxes=((1, 2, 8, 12), (20, 20, 30, 30)), confidence=(.9, .8))]

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    detector = YoloDetector(tmp_path / "local-liquid.pt", device="cpu", imgsz=320, class_names={0: "liquid"})
    detections = detector.predict(Image.new("RGB", (40, 40)))

    assert [detection["label"] for detection in detections] == ["liquid"]
    assert calls[1][1]["imgsz"] == 320


def test_camera_tip_detector_uses_local_liquid_checkpoint_when_present(monkeypatch, tmp_path):
    calls = []

    class FakeYOLO:
        def __init__(self, weights):
            calls.append(Path(weights))

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    (tmp_path / "local-tip.pt").touch()
    (tmp_path / "local-liquid.pt").touch()

    detector = CameraTipDetector(tmp_path, device="cpu")

    assert detector.liquid.weights == tmp_path / "local-liquid.pt"
    assert detector.liquid.imgsz == 320
    assert detector.checkpoint_paths == [tmp_path / "local-tip.pt", tmp_path / "local-liquid.pt"]
    assert calls == [tmp_path / "local-tip.pt", tmp_path / "local-liquid.pt"]


def _load_liquid_training_script():
    path = Path(__file__).parents[1] / "scripts" / "vision_train_liquid.py"
    spec = importlib.util.spec_from_file_location("vision_train_liquid_test_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_frame_image(path: Path, color: tuple[int, int, int] = (40, 50, 60)):
    Image.new("RGB", (1800, 1000), color).save(path)


def test_liquid_prepare_keeps_heldout_frames_out_of_train_and_preserves_split_counts(tmp_path):
    trainer = _load_liquid_training_script()
    frames = []
    specs = [
        ("train-positive", 0.0, "train", True),
        ("train-negative", 1.3, "train", False),
        ("validation-positive", 3.0, "validation", True),
        ("test-positive", 4.5, "test", True),
    ]
    for index, (frame_id, timestamp, split, positive) in enumerate(specs):
        image_path = tmp_path / f"{frame_id}.jpg"
        _write_frame_image(image_path, color=(40 + index * 30, 50, 60))
        frames.append(
            {
                "id": frame_id,
                "timestamp_s": timestamp,
                "split": split,
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "image_path": str(image_path),
                "training_roi": [100, 100, 300, 300],
                "boxes": [{"label": "liquid", "box": [150, 150, 250, 250]}] if positive else [],
                "visibility": "clear",
            }
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"frames": frames}))
    output = tmp_path / "prepared"

    _, counts = trainer.prepare(manifest, output)

    assert counts == {"train": 51, "validation": 1, "test": 1}
    provenance = json.loads((output / "provenance.json").read_text())["derived_examples"]
    train_sources = {row["source_id"] for row in provenance if row["split"] == "train"}
    assert train_sources == {"train-positive", "train-negative"}
    assert not train_sources.intersection({"validation-positive", "test-positive"})
    with pytest.raises(ValueError, match="existing datasets"):
        trainer.prepare(manifest, output)


def test_liquid_prepare_rejects_changed_source_hash(tmp_path):
    trainer = _load_liquid_training_script()
    image_path = tmp_path / "frame.jpg"
    _write_frame_image(image_path)
    frame = {
        "id": "frame",
        "timestamp_s": 0,
        "split": "test",
        "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "image_path": str(image_path),
        "training_roi": [100, 100, 300, 300],
        "boxes": [],
        "visibility": "clear",
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"frames": [frame]}))
    image_path.write_bytes(b"changed")

    with pytest.raises(ValueError, match="Frame changed"):
        trainer.prepare(manifest, tmp_path / "output")


def test_evaluation_rejects_out_of_range_probabilities_and_all_split_boundary_leaks():
    frame = lambda frame_id, timestamp, split: {
        "id": frame_id,
        "timestamp_s": timestamp,
        "split": split,
        "sha256": frame_id,
        "boxes": [],
        "visibility": "clear",
    }
    with pytest.raises(ValueError, match="between 0 and 1"):
        evaluate([frame("test", 0, "test")], {"test": [{"label": "liquid", "confidence": 1.1, "box": [0, 0, 1, 1]}]})
    with pytest.raises(ValueError, match="too close"):
        validate_partition([frame("train", 0, "train"), frame("validation", .5, "validation")])
    with pytest.raises(ValueError, match="too close"):
        validate_partition([frame("validation", 2, "validation"), frame("test", 2.5, "test")])


def test_worker_fingerprint_changes_when_only_liquid_weights_change(monkeypatch, tmp_path):
    from paper_to_plate import vision_models, vision_service

    tip = tmp_path / "local-tip.pt"
    liquid = tmp_path / "local-liquid.pt"
    tip.write_bytes(b"unchanged-tip")
    liquid.write_bytes(b"liquid-v1")
    monkeypatch.setattr(vision_models, "load_detector", lambda *args: SimpleNamespace(
        weights=tip, checkpoint_paths=[tip, liquid]
    ))
    worker = vision_service.Vision(tmp_path)
    worker.load("yolo")
    first = worker.model_fingerprint
    components = dict(worker.model_components)
    liquid.write_bytes(b"liquid-v2")
    worker.load("yolo")
    assert worker.model_fingerprint != first
    assert worker.model_components[tip.name] == components[tip.name]
    assert worker.model_components[liquid.name] != components[liquid.name]
