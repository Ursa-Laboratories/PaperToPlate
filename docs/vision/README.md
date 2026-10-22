# Live pipette-tip and liquid observation

Open `http://127.0.0.1:8785/?vision=1` after starting the local services. The
page also opens from **Vision lab** in the experiment's execution-evidence
panel. This is an observational research demo. It never sends movement,
protocol, recovery or retry commands.

## Start on the configured Mac

```bash
./demo.sh
```

The launcher uses the existing CubOS camera bridge at localhost:8090, the
isolated vision worker at localhost:8793 and the Paper to Plate app at
localhost:8785. Existing healthy services are reused. It does not terminate
or replace another service. If CubOS is elsewhere, use
`./demo.sh --cubos-root /absolute/path/to/CubOS`. The launcher discovers the
MX Brio's current device index instead of assuming a permanent camera number.

The CubOS camera bridge change is in
[PR #369](https://github.com/Ursa-Laboratories/CubOS/pull/369), commit
`4612de39`. A CubOS checkout containing `tools/livestream_camera.py` with
`/frame.jpg` and `/status` is required. Acquisition belongs to CubOS;
Paper to Plate only reads its localhost endpoints. All services bind to
localhost. Camera frames are not uploaded to an external inference provider.

For a fresh checkout, use the normal `./setup.sh` app installation, build the
frontend, then create an isolated Python 3.12 environment:

```bash
python3.12 -m venv .venv-vision
.venv-vision/bin/python -m pip install -r requirements-vision.txt
.venv-vision/bin/python -m pip install -e '.[dev]'
```

Follow [the training instructions](../training.md) to obtain the source data
and train local checkpoints. Weights and the original dataset are not bundled
with this repository; absent checkpoints appear as unavailable models.

## Use the demo

Select a trained model to inspect the live camera. Detection boxes are
predictions; a missed box does not prove an absent tip. Liquid boxes are shown
only when they overlap a predicted tip. This rejects unrelated vessel liquid
regions, but does not measure volume. The independent DINO option is an
exploratory alternative; consult the training report for its method and
limitations.

**Recorded examples** show held-out OT-2 source images with live model
inference. They are explicitly separate from MX Brio footage. Switching models
reruns inference on the selected example.

**Save frame for review** captures a fresh raw frame. Draw tip and liquid boxes,
or save no boxes to mark a genuine negative example. Labels remain local in
`data/vision/annotations/`; captures are in `data/vision/captures/`. All boxes
use original-image coordinates. Mark every visible target of the class before
saving. If the scene is occluded or the state is uncertain, do not label it as
an empty negative.

**Record 30 seconds** saves up to two processed raw frames per second plus
associated model outputs. Download the archive when complete. It contains
`session.json`, `observations.jsonl` and matching JPEGs. Predictions remain
unreviewed; the export is not training ground truth. Inference may sample less
than two frames per second on slow hardware. There is no automatic alignment
to a protocol run; timestamps reflect camera-bridge receipt, not sensor
exposure or verified action times.

## Evidence and limits

The source-training report is kept at `data/vision/training-report.json` and
surfaced by the status endpoint. Source-image results do not establish
performance on a new camera. The initial MX Brio scene contained the deck and
racked consumables but no clearly observable liquid-filled mounted tip. A
close side view, controlled lighting, operator-presented tips and reviewed
positive/negative sequences are needed to establish target-domain accuracy.
No physical validation run was performed.

Frames that stop arriving or repeat for more than three seconds are marked
stale. Old detections are removed; the UI reports unknown counts. Capture and
inference use separate threads with a latest-frame buffer, so slow inference
does not accumulate a delayed camera queue. The displayed frame rate is camera
capture rate; inference latency and the result timestamp are separate.

Model files, recordings and raw images stay under ignored `data/`; the main
app's credentials stay in its private `.env`. The public repository contains
original integration/training code and aggregate results only.

## Check and stop

```bash
.venv/bin/python -m pytest -q
.venv-vision/bin/python -m pytest tests/test_vision.py -q
cd frontend && npm run build
```

Inspect a service with `tmux attach -t paper-to-plate-vision` (or
`paper-to-plate-camera`, `paper-to-plate`). Detach with Ctrl-B then D. To stop a
service started by the launcher, send Ctrl-C to that named session. Stopping
the vision worker does not stop or resume a physical experiment.

## Calibrate a missed tip on this camera

The initial source detector missed an attached CUB tip in live testing. The
local calibration therefore uses three user-confirmed tip views with
assistant-reviewed boxes, plus clear background crops. These are calibration
images, not independent test data. Cropped/augmented copies never increase the
count of independent scenes.

`scripts/vision_adapt_tip.py` trains a one-class local tip model. Its manifest
is a JSON list with `image` (or `image_path`) and `boxes` in original pixels;
boxes can be `[x1,y1,x2,y2]` or the annotation UI's `{label,box}` objects.
For example:

```bash
.venv-vision/bin/python scripts/vision_adapt_tip.py \
  --manifest data/vision/local-tip-manifest.json \
  --out data/vision/new-tip-calibration --epochs 30
```

Use a new output directory for each run. Training-set metrics are not an
accuracy benchmark. After inspecting a later real frame, promote the final
`runs/local-tip/weights/last.pt` to `data/vision/models/local-tip.pt` and restart
only the vision worker. The camera adapter searches overlapping tiles across
the entire frame; it does not draw a fixed box at an annotated position.
Liquid predictions still use the original source model on detected tip crops
and require separate local liquid-filled/empty reference data. The original
source baseline remains selectable for comparison.
