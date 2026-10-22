# MX Brio liquid detector: recorded-run adaptation

The adapted YOLOv8n liquid model now finds the pink liquid in Alex's October 22
recording. It is enabled in the local Vision lab demo. It does not measure µL.
The existing tip detector supplies candidate crops; losing the tip can therefore
also lose the liquid detection. DINO remains a separate experimental option.

## What was tested

The original 192.47-second, 1920×1080 recording contains one operator-run transfer.
Twenty-two original frames were visually labeled by the assistant: ten training,
four validation and eight test frames. Training used four liquid-positive frames
and six negative frames, including empty tips and colored vial backgrounds.
Augmentation produced 258 training crops, not 258 independent observations.
Splits have at least 1.2 seconds between them, but share the same camera and run.
Labels have not received independent human review.

Training used generic YOLOv8n initialization, 35 fixed epochs, 320-pixel inputs,
AdamW, seed 20261022 and the final checkpoint. Neither the confidence threshold
(0.25) nor the checkpoint was selected using test results. Evaluation runs the
whole tip → liquid → overlap-filter pipeline on full original frames; a correct
liquid box must overlap its label by IoU ≥0.5.

| Test result | Original liquid model | Adapted liquid model |
|---|---:|---:|
| Correct liquid regions / 4 positive frames | 0/4 | 3/4 |
| Missed liquid regions | 4 | 1 |
| False liquid alarms / 4 negative frames | 0/4 | 0/4 |

The missed test frame at 155.6 seconds has no predicted tip, blocking downstream
liquid detection. The other three test boxes have IoU 0.65–0.70. These very small,
correlated counts are an initial replay result, not a general accuracy estimate.

The complete replay processed 963 frames at 5 fps, with 15 liquid-positive frames
between 152.4 and 155.4 seconds and none outside that interval. Predictions flicker.
The entire replay is not exhaustively labeled and includes training frames; it is
not an additional held-out benchmark. Original video remains at 15 fps.

## Local evidence and reproduction

Raw video, annotation coordinates, checkpoints and output videos stay in ignored
`data/vision/`. The public [aggregate report](liquid-replay-report.json) includes
hashes, counts, limitations and per-frame evaluation outcomes. On the configured
Mac, from the repository root:

```bash
.venv-vision/bin/python scripts/vision_train_liquid.py \
  --manifest data/vision/liquid-adaptation/annotations.json \
  --out data/vision/liquid-adaptation/new-training --epochs 35

# Copy the new final weights as local-liquid.pt into a separate model directory
# alongside the frozen local-tip.pt and yolov8n-tip-liquid-source.pt.
.venv-vision/bin/python scripts/vision_evaluate_recording.py \
  --manifest data/vision/liquid-adaptation/annotations.json \
  --models data/vision/liquid-adaptation/probe-models \
  --out data/vision/liquid-adaptation/new-evaluation

.venv-vision/bin/python scripts/vision_replay.py \
  --video data/vision/experiments/operator-protocol-20261022-152407/camera-original.mp4 \
  --models data/vision/liquid-adaptation/probe-models \
  --out data/vision/liquid-adaptation/new-replay
```

Each output directory must be new. Replay uses Apple MPS. The existing results are
in `evaluation-v1/` and `replay-v1-complete/` under `data/vision/liquid-adaptation/`.
`liquid-detection-highlight.mp4` is a cropped half-speed excerpt; its captions
identify it as recorded replay containing both training and held-out frames.
`annotated-replay.mp4` contains the whole recording. `predictions.jsonl` preserves
per-frame timestamps and outputs. Live observation logs fingerprint both the tip
and liquid checkpoints, so later model changes can be traced.

The deployed checkpoint is `data/vision/models/local-liquid.pt`, SHA256
`4458b43576918b41c47c3470ded2ad1e73a5a55717a7a889b23aaf403d211964`.
Removing that file and restarting only the vision worker restores source-liquid
inference. No physical protocol was run for this training or evaluation.

## What is still needed

Collect and label independent runs with empty and loaded tips across positions,
lighting, motion, occlusion, bubbles and liquid colors, including clear liquids.
Split future data by complete run, not adjacent frames. Review these labels with
the operator and keep a future run untouched for evaluation. Add tip labels for
the missed motion/occlusion cases; liquid retraining alone cannot fix missing tips.
Volume estimation additionally needs independently measured volumes and tip/camera
geometry calibration; commanded protocol volumes are not measurement labels.

Validation: 28 focused vision tests passed. The local worker was restarted and
verified live with the adapted checkpoint. This verifies deployment, not a second
physical liquid-transfer experiment.
