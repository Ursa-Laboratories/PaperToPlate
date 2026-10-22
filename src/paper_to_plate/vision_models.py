"""Local vision model adapters used by the paper-to-plate sidecar.

The public contract is intentionally small: ``load_detector(...).predict``
accepts an RGB numpy image and returns pixel-coordinate boxes with one of the
labels ``tip`` or ``liquid``.  DINO is a frozen feature model plus a trained
classification head with independent sliding-window localization. An optional
reranker adapter is also available and explicitly depends on YOLO proposals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


CLASS_NAMES = {0: "tip", 1: "liquid"}


def _predict_head_proba(head: Any, features: np.ndarray) -> np.ndarray:
    """Evaluate the saved linear head without the noisy arm64 BLAS matmul.

    NumPy 2.2.3's arm64 matmul path emits divide/overflow warnings for these
    small finite matrices even when its result is finite. ``einsum`` avoids
    that path; explicit checks prevent invalid model output from becoming
    apparent low-confidence detections.
    """

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


def available_models(data_root: str | Path | None = None) -> list[dict[str, Any]]:
    """Return model availability for a UI/API model picker."""

    root = Path(data_root) if data_root else Path(__file__).resolve().parents[2] / "data/vision"
    models = root / "models"
    yolo = models / "yolov8n-tip-liquid-source.pt"
    local_tip = models / "local-tip.pt"
    dino = models / "dino-v2-vits14-head.joblib"
    return [
        {"id": "yolo", "label": "MX Brio · local tip + source liquid" if local_tip.is_file() else "YOLOv8n · source baseline", "available": yolo.is_file(), "detail": "Few-shot tip calibration; liquid detection remains unverified on this camera." if local_tip.is_file() else "Source-data detector; target-camera accuracy not established."},
        {"id": "yolo_source", "label": "YOLOv8n · original source baseline", "available": yolo.is_file(), "detail": "Unadapted OT-2 model for comparison and source examples."},
        {"id": "dino", "label": "DINOv2 · experimental detector", "available": dino.is_file(), "detail": "Independent DINOv2 localization. Low source-test precision; expect false positives."},
    ]


def _as_pil(image: Any) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("predict expects an RGB image array with shape HxWx3")
    return Image.fromarray(array.astype(np.uint8), mode="RGB")


class YoloDetector:
    def __init__(self, weights: Path, device: str | None = None, imgsz: int | None = None):
        from ultralytics import YOLO

        self.weights = weights
        self.device = device
        self.imgsz = imgsz
        self.model = YOLO(str(weights))

    def predict(self, image: Any) -> list[dict[str, Any]]:
        pil = _as_pil(image)
        kwargs = {"conf": 0.10, "verbose": False}
        if self.device:
            kwargs["device"] = self.device
        if self.imgsz:
            kwargs["imgsz"] = self.imgsz
        # Ultralytics treats numpy input as BGR; passing the PIL RGB object
        # preserves the adapter's documented RGB input contract.
        result = self.model.predict(pil, **kwargs)[0]
        detections = []
        if result.boxes is None:
            return detections
        boxes = result.boxes.xyxy.detach().cpu().numpy()
        confidences = result.boxes.conf.detach().cpu().numpy()
        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
        for box, confidence, class_id in zip(boxes, confidences, classes):
            label = CLASS_NAMES.get(int(class_id))
            if label:
                detections.append({"label": label, "confidence": float(confidence), "box": [float(value) for value in box]})
        return detections


class CameraTipDetector:
    """Learned local tip detector over a generic overlapping image grid.

    Tile locations do not encode the pipette position. The source model examines
    actual detected tip crops for liquid; all returned boxes come from models.
    """
    def __init__(self, models_dir: Path, device: str | None = None):
        import torch
        from ultralytics import YOLO
        self.weights = models_dir / "local-tip.pt"
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.model = YOLO(str(self.weights))
        self.liquid = YoloDetector(models_dir / "yolov8n-tip-liquid-source.pt", self.device, imgsz=640)

    def predict(self, image: Any) -> list[dict[str, Any]]:
        pil = _as_pil(image)
        width, height = pil.size
        side = min(640, width, height)
        xs = sorted(set([*range(0, max(1, width-side), max(1, side*3//4)), max(0, width-side)]))
        ys = sorted(set([*range(0, max(1, height-side), max(1, side*3//4)), max(0, height-side)]))
        origins = [(x,y) for y in ys for x in xs]
        crops = [pil.crop((x,y,x+side,y+side)) for x,y in origins]
        results = self.model.predict(crops, imgsz=512, conf=.25, device=self.device, verbose=False)
        tips=[]
        for (x,y), result in zip(origins,results):
            for box,confidence in zip(result.boxes.xyxy.cpu().numpy(),result.boxes.conf.cpu().numpy()):
                a,b,c,d=map(float,box)
                # Prefer a complete observation from the overlapping neighbor
                # over a high-confidence box cut by an internal tile boundary.
                if (a < 3 and x > 0) or (b < 3 and y > 0) or (c > side-3 and x+side < width) or (d > side-3 and y+side < height):
                    continue
                tips.append({"label":"tip","confidence":float(confidence),"box":[a+x,b+y,c+x,d+y]})
        tips=_nms(tips,iou_threshold=.35)
        liquid=[]
        for tip in tips[:12]:
            a,b,c,d=tip['box']
            pad=max(c-a,24)
            left,top=max(0,int(a-pad)),max(0,int(b-20))
            right,bottom=min(width,int(c+pad)),min(height,int(d+20))
            if right<=left or bottom<=top:continue
            for detection in self.liquid.predict(pil.crop((left,top,right,bottom))):
                if detection['label']!='liquid':continue
                q,r,t,u=detection['box']
                liquid.append({**detection,'box':[q+left,r+top,t+left,u+top]})
        return tips+_nms(liquid,iou_threshold=.35)


class DinoProposalReranker:
    """DINOv2 feature head over YOLO candidate boxes.

    This preserves the adapter contract while making the dependency clear:
    candidates come from the trained YOLO detector, and DINO changes their
    label/confidence using the frozen feature extractor and saved head.
    """

    def __init__(self, models_dir: Path, device: str | None = None):
        import joblib
        import torch
        from torchvision import transforms

        self.models_dir = models_dir
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.yolo = YoloDetector(models_dir / "yolov8n-tip-liquid-source.pt", self.device)
        self.head = joblib.load(models_dir / "dino-v2-vits14-head.joblib")
        self.torch = torch
        self.transform = transforms.Compose([
            transforms.Resize((224, 224), antialias=True),
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])
        self.model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14", trust_repo=True)
        self.model.eval().to(self.device)

    def predict(self, image: Any) -> list[dict[str, Any]]:
        pil = _as_pil(image)
        proposals = self.yolo.predict(pil)
        if not proposals:
            return []
        crops = []
        width, height = pil.size
        for proposal in proposals:
            x1, y1, x2, y2 = proposal["box"]
            dx, dy = (x2 - x1) * 0.15, (y2 - y1) * 0.15
            crop = pil.crop((max(0, int(x1 - dx)), max(0, int(y1 - dy)), min(width, int(x2 + dx)), min(height, int(y2 + dy))))
            crops.append(self.transform(crop))
        with self.torch.inference_mode():
            features = self.model(self.torch.stack(crops).to(self.device)).float().detach().cpu().numpy()
        probabilities = _predict_head_proba(self.head, features)
        output = []
        for proposal, probability in zip(proposals, probabilities):
            tip_p, liquid_p, background_p = [float(value) for value in probability]
            class_id = 0 if tip_p >= liquid_p else 1
            confidence = (1.0 - background_p) * max(tip_p, liquid_p)
            output.append({"label": CLASS_NAMES[class_id], "confidence": float(confidence), "box": proposal["box"]})
        return sorted(output, key=lambda row: row["confidence"], reverse=True)


def _dense_windows(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """Generate deterministic multiscale windows for the independent DINO mode."""

    windows = []
    # Dimensions are derived from the source annotations, not from YOLO. The
    # classifier decides the label; these aspect-ratio families only cover the
    # observed tip and liquid geometry.
    for width_fraction, height_fraction in ((0.06, 0.58), (0.045, 0.34)):
        window_width = max(18, int(width * width_fraction))
        window_height = max(40, int(height * height_fraction))
        step_x = max(10, window_width // 2)
        step_y = max(12, window_height // 3)
        xs = list(range(0, max(1, width - window_width + 1), step_x))
        ys = list(range(0, max(1, height - window_height + 1), step_y))
        if not xs or xs[-1] != width - window_width:
            xs.append(max(0, width - window_width))
        if not ys or ys[-1] != height - window_height:
            ys.append(max(0, height - window_height))
        windows.extend((x, y, min(width, x + window_width), min(height, y + window_height)) for y in ys for x in xs)
    return windows


def _nms(detections: list[dict[str, Any]], iou_threshold: float = 0.25) -> list[dict[str, Any]]:
    kept = []
    for candidate in sorted(detections, key=lambda item: item["confidence"], reverse=True):
        x1, y1, x2, y2 = candidate["box"]
        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        overlap = False
        for prior in kept:
            if candidate["label"] != prior["label"]:
                continue
            a1, b1, a2, b2 = prior["box"]
            intersection = max(0.0, min(x2, a2) - max(x1, a1)) * max(0.0, min(y2, b2) - max(y1, b1))
            prior_area = max(0.0, a2 - a1) * max(0.0, b2 - b1)
            union = area + prior_area - intersection
            if union and intersection / union >= iou_threshold:
                overlap = True
                break
        if not overlap:
            kept.append(candidate)
    return kept


class DinoDenseDetector:
    """Independent DINOv2 dense detector using sliding windows only."""

    def __init__(self, models_dir: Path, device: str | None = None):
        import joblib
        import torch
        from torchvision import transforms

        self.models_dir = models_dir
        self.torch = torch
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.head = joblib.load(models_dir / "dino-v2-vits14-head.joblib")
        self.transform = transforms.Compose([
            transforms.Resize((224, 224), antialias=True),
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])
        self.model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14", trust_repo=True)
        self.model.eval().to(self.device)

    def predict(self, image: Any) -> list[dict[str, Any]]:
        pil = _as_pil(image)
        windows = _dense_windows(*pil.size)
        crops = [self.transform(pil.crop(window)) for window in windows]
        probabilities = []
        with self.torch.inference_mode():
            for start in range(0, len(crops), 32):
                batch = self.torch.stack(crops[start:start + 32]).to(self.device)
                features = self.model(batch).float().detach().cpu().numpy()
                probabilities.extend(_predict_head_proba(self.head, features))
        detections = []
        for box, probability in zip(windows, probabilities):
            tip_p, liquid_p, background_p = [float(value) for value in probability]
            class_id = 0 if tip_p >= liquid_p else 1
            score = (1.0 - background_p) * max(tip_p, liquid_p)
            if score >= 0.50:
                detections.append({"label": CLASS_NAMES[class_id], "confidence": score, "box": [float(value) for value in box]})
        kept = _nms(detections)
        # The source frame families contain at most eight columns of tips and
        # liquid regions. Cap each class after NMS so a weak background score
        # cannot flood the observation UI with hundreds of windows.
        return [item for label in ("tip", "liquid") for item in sorted((x for x in kept if x["label"] == label), key=lambda x: x["confidence"], reverse=True)[:16]]


def load_detector(model_id: str = "yolo", data_root: str | Path | None = None, device: str | None = None):
    """Load ``yolo`` or ``dino`` using the local training artifact paths."""

    root = Path(data_root) if data_root else Path(__file__).resolve().parents[2] / "data/vision"
    models_dir = root / "models"
    if model_id == "yolo" and (models_dir / "local-tip.pt").is_file():
        return CameraTipDetector(models_dir, device)
    if model_id in {"yolo", "yolo_source", "yolov8n", "yolov8n-tip-liquid-source"}:
        return YoloDetector(models_dir / "yolov8n-tip-liquid-source.pt", device)
    if model_id in {"yolo_target", "yolov8n-tip-liquid-target-adapted"}:
        return YoloDetector(models_dir / "yolov8n-tip-liquid-target-adapted.pt", device, imgsz=1280)
    if model_id in {"dino", "dino-v2", "dino-v2-vits14"}:
        return DinoDenseDetector(models_dir, device)
    if model_id in {"dino_rerank", "dino-proposals"}:
        return DinoProposalReranker(models_dir, device)
    path = Path(model_id)
    if path.exists():
        return YoloDetector(path, device)
    raise ValueError(f"Unknown local vision model: {model_id}")
