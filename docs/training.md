# Vision training and local inference

This project includes a small, reproducible source-data baseline for the OT-2
computer-vision labels published in the public `BDD-G/OT2-Computer-Vision`
repository. The source archive is downloaded into the ignored
`data/vision/source` directory and extracted locally. The repository did not
provide a license file when this work was collected, so source images and model
weights are retained for private research only and are not redistributed. The
original scripts and the measured report are the shareable project artifacts.

The archive contains 71 JPEGs (640×480) and 995 YOLO instances (563 `Tip`, 432
`Liquid`). The source `classes.txt`/dataset configuration maps class 0 to Tip
and class 1 to Liquid. `scripts/vision_prepare.py` groups volume/capture
families before splitting: 54 train images, 9 validation images and 8 held-out
test images. The complete `tipsWaterRed` family is the test group;
`DeckImage` and `AI__H60__light blue` are validation groups. This avoids the
random-frame leakage that would make a volume sequence appear easier than a
new capture. These 71 vision images are a small computer-vision subset and are
separate from the paper corpus (456 paper records); paper-corpus coverage does
not imply camera-domain coverage.

## Re-run preparation

Use the isolated Python 3.12 environment. The main app environment is Python
3.14 and is intentionally not used for ML dependencies.

```bash
cd /Users/alexchan/Documents/Ursa/projects/paper-to-plate
/Users/alexchan/.pyenv/versions/3.12.11/bin/python -m venv .venv-vision
.venv-vision/bin/python -m pip install -r requirements-vision.txt
.venv-vision/bin/python -m pip install -e '.[dev]'
mkdir -p data/vision/source/extracted
curl -L --fail -o data/vision/source/Images_with_Labels_tips_n_Liquid.rar \
  'https://github.com/BDD-G/OT2-Computer-Vision/raw/main/Training%20Data/Images_with_Labels_tips_n_Liquid.rar'
bsdtar -xf data/vision/source/Images_with_Labels_tips_n_Liquid.rar \
  -C data/vision/source/extracted
.venv-vision/bin/python scripts/vision_prepare.py
```

The output is `data/vision/dataset/manifest.json` and an Ultralytics
`data.yaml`. The `data/vision/annotations/` directory is reserved for reviewed
target-domain corrections. A correction file has the form:

```json
{
  "frame_id": "mx-brio-2026-10-22-0001",
  "image_path": "/absolute/path/to/frame.jpg",
  "reviewed": true,
  "boxes": [{"label": "tip", "box": [x1, y1, x2, y2]}]
}
```

Reviewed target frames can be imported as a separately identified correction
set only with an explicit split assignment. For example, this adds reviewed
frames to training while keeping their capture session grouped:

```bash
.venv-vision/bin/python scripts/vision_prepare.py \
  --annotations data/vision/annotations \
  --target-split train
```

Use `--target-split test` only for a deliberately held-out target session. The
command rejects unreviewed files, out-of-bounds boxes and missing images; it
never silently places target frames into a source split.

## Train and evaluate

```bash
.venv-vision/bin/python scripts/vision_train.py --epochs 12
```

The script selects Apple MPS when available and otherwise uses CPU. It trains
a small YOLOv8n detector at 320 pixels and evaluates it on the held-out source
family. It also loads frozen pretrained DINOv2 ViT-S/14 features and trains a
balanced logistic-regression head over `tip`, `liquid` and deterministic
background crops. The official `facebook/dinov3-vits16-pretrain-lvd1689m`
endpoint returned HTTP 401 (restricted/authenticated) in this environment, so
DINOv2 was used instead. The DINO crop metrics are classification metrics and
must not be read as end-to-end detection metrics. The `dino` runtime adapter
uses dense sliding-window localization with no YOLO proposals. The optional
`dino_rerank` adapter uses YOLO proposals for comparison.

The run writes model artifacts under ignored `data/vision/models/`, the YOLO
run under ignored `data/vision/runs/`, and the complete machine-readable result
to `data/vision/training-report.json`. The report records exact image/instance
counts, model IDs, epochs, device, paths, held-out metrics and limitations.
When `data/vision/target-background-review.json` is present, its explicitly
listed clear regions are added as training-only DINO background crops and are
recorded under `target_background_training`; they are excluded from source
evaluation and do not represent human annotations or target-positive labels.
In the executed 12-epoch run, YOLO achieved held-out source-family mAP50
0.9939, mAP50–95 0.7300, precision 0.9536 and recall 0.9815. Per-class AP50
was 0.9928 for tip and 0.9950 for liquid; per-class AP50–95 was 0.7770 and
0.6830. DINO crop-head accuracy and macro-F1 were both 1.0 on the held-out
crop set, but those figures exclude localization. With ungated dense windows,
the independent DINO box evaluator at IoU 0.5 measured tip
precision/recall/F1 of 0.164/0.328/0.219 and liquid
precision/recall/F1 of 0.305/0.609/0.406 on the held-out source family after
adding eight assistant-visually-reviewed background crops to training. On the
initial background-only target frame, it still produced 20 false-positive boxes; it is
not the live default.

## Runtime adapter

```python
from paper_to_plate.vision_models import load_detector

detector = load_detector("yolo", data_root="data/vision")
rows = detector.predict(rgb_numpy_frame)
# [{"label": "tip", "confidence": 0.9, "box": [x1, y1, x2, y2]}]

dino = load_detector("dino", data_root="data/vision")
rows = dino.predict(rgb_numpy_frame)
```

Both adapters return pixel-coordinate boxes. They are visual evidence only:
they do not prove liquid volume, identity, sterility, pipetting correctness or
hardware state. No MX Brio target-domain frames were available for human review
in this baseline, and no hardware motion or protocol run was performed.


## Camera-specific tip calibration

The source baseline failed to detect the user-attached tip in live testing.
A separate one-class local tip model was trained for 30 epochs from three
user-confirmed views with assistant-reviewed boxes and two background regions
(120 derived training crops). The runtime searches overlapping tiles across
the whole image, then runs the source liquid model on detected tip crops.
The original source checkpoint is retained as `yolo_source`. See
[the local calibration workflow](vision/README.md#calibrate-a-missed-tip-on-this-camera)
and [the live verification receipt](vision/live-verification.json).
Twenty later processed frames all showed a tip box over the actual transparent
tip. These repeated same-scene observations do not establish general accuracy.
Liquid-filled/empty discrimination on this camera remains unverified.
