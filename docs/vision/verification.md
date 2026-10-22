# Verification receipt — October 22, 2026

The user story is: open Vision lab, read fresh MX Brio frames through CubOS,
run a learned detector, inspect actual overlays, save reviewed frames and
record timestamped evidence while keeping physical robot control separate.

| Boundary | Evidence |
|---|---|
| Camera → CubOS bridge | Changing 1920x1080 frames at about 30 fps; original duplicate-frame pacing issue fixed. CubOS PR #369 has six focused tests. |
| CubOS → model worker | Current snapshots consumed independently of inference; stale/repeated data invalidates observations. |
| Model → live image | Original source model failed on the attached tip. A local calibration model subsequently placed the box on the transparent tip in later live frames. |
| Worker → app → browser | Live mode showed one tip, roughly 90% model confidence, and fresh frame IDs. Model selection and recorded examples were exercised. |
| Browser → review capture | A raw frame was saved and displayed by the review editor. Label bounds, provenance and experiment revision linkage passed endpoint tests. |
| Browser → recording → download | A 30-second positive-view recording saved 52 unannotated frames with timestamped predictions. The archive is local and not published. |
| Regression checks | Full vision environment suite passed (35 tests before the final tile-boundary regression; all four adapter tests passed afterward). Main app tests passed (21; optional ML tests skip without ML dependencies). Frontend production build passed. |

The brief live sample is recorded in `live-verification.json`: twenty distinct
processed frames, twenty live states, and twenty positive tip observations.
The confidence values are model scores, not calibrated probabilities or an
accuracy estimate. This is one current scene following few-shot calibration.
The three positive calibration images and their crop variants are training
data, not held-out independent experiments.

The DINOv2 classifier runs independently but performs poorly at localization.
DINOv3 checkpoint access was unavailable. An additional pretrained Grounding
DINO diagnostic also produced incorrect background boxes on the live scene
and was not selected as the default. No eight-channel assumption or fixed
pipette-position box is used to manufacture a successful result.

Liquid regions are predicted by the original source model inside detected
local tips. This has not yet passed a local known-filled versus known-empty
check. Camera measurements do not establish volume or assay success. No
robot movement or protocol was performed by the agent.

During browser testing an older build attempted `toFixed` on a null inference
measurement during startup. The final build checks numeric types and shows
unknown values until inference is ready. Invalid DINO numeric outputs now fail
explicitly, rather than becoming apparent absence detections. The fixed
probability path uses finite float64 operations to avoid the observed arm64
BLAS warnings.

The vision-only publication snapshot was also tested in a separate temporary
checkout, excluding concurrent preparation/Ollama edits in the shared working
tree. With the compatible installed CubOS validator configured, 35 tests
passed and one optional Torch-dependent test skipped; that tile-boundary
regression passed in the ML environment. Its independent frontend build passed.
The 26 staged files passed the repository's private-value/credential scan.
