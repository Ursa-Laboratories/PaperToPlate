# Color matching: Bond → paper → plate → recording

Open `http://127.0.0.1:8785/?color=1`. Enter the three working-stock
descriptions, target color, source load, plate row, first fresh tip and stock
aspiration offset in millimetres. Stock depth is required; it is not silently
defaulted to zero. Enter unavailable or unreachable tips under **Skip tips**,
and bind an existing workcell to its **CubOS inventory ID**. **Explore with
Bond** performs live retrieval and an Ollama brief, then downloads the full
reviewed liquid-dye benchmark when it is present in the results. Source
retrieval failures remain blockers; they are not silently replaced by a demo.

The supported method anchor is [Ginsburg et al., Exploring Benchmarks for
Self-Driving Labs using Color Matching](https://arxiv.org/abs/2310.00510).
Its CMYK dye/camera workflow informs our proposed RYB screen. The first-round
recipes are calculated locally, not extracted numerical recipes or an
implementation of the paper's iterative optimizer. RGB measurements are
uncalibrated, and a target can be outside the reachable color range.

## Prepared first run

The default uses 10 wells at 120 uL, three single-color references, three
pairwise mixtures, three center repeats and a water blank. Nonblank wells
contain 60 uL total colored stock plus 60 uL water. There are 28 fresh tips, 94 commands and ten 60-uL pipette-mixing operations.
The exact tip range depends on the first tip, unavailable slots and exclusions.
Native validation must pass for those actual coordinates.

| Vial | Working liquid | Load | Consumption | Planned remainder |
|---|---|---:|---:|---:|
| A1 | Red | 1500 uL | 180 uL | 1320 uL |
| A2 | Yellow | 1500 uL | 180 uL | 1320 uL |
| A3 | Blue | 1500 uL | 180 uL | 1320 uL |
| A4 | Water | 1500 uL | 660 uL | 840 uL |

These are proposed loads, not observed live inventory. The operator must
verify that the actual source depth is reachable. The current imported deck
allows 4 mL per stock and 300 uL per assay well. No limits were enlarged to
match the nominal 5 mL vial specification.

The app reads fresh copies of the previously supplied station filenames:
`picus120_fast_camera_20261014.yaml` and the current `cub_deck.yaml`.
The older camera-derived deck candidate was rejected during preflight because
it did not match the current inventory geometry.
It records their hashes and rejects physical handoff if the station files
change. The operator must still confirm that these saved files match the
physical workcell. File availability is not proof of commissioning.

## Operator run and recording

1. Confirm A1/A2/A3/A4 liquid identities and volumes, empty plate wells
   in the selected row, and all tips in the compiled range. Verify pickup, waste, clearance and aspiration/
   dispense heights at the station before any assay. A `0` height offset means
   the calibrated labware anchor, not the deck floor. For the current checked
   stock vials, the operator corrected the aspiration offset to **−40 mm**;
   plate dispensing and mixing remain at **0 mm**. Confirm actual immersion
   while keeping the tip clear of the bottom; do not infer safety from the
   numerical offset or from the model review alone.
2. **Open run** shows the loading sheet and native protocol. Inspect the
   source, recipe checks and any blocking findings. Keep a record of the
   physical height checks; no loading approval is prefilled.
3. Check the four loaded vials, confirm preparation and loading, then **Run**.
   Select physical execution and keep **Record this run** checked. Confirm the
   operator checks before **Run & record**.
4. The app verifies the setup, starts a working video stream, then submits the
   protocol once to CubOS. If recording cannot start, no run is submitted.
   A lost submission response is not retried; inspect CubOS before any replay.
5. The execution panel reads live status from CubOS. Its **CubOS controls**
   link opens the authoritative operator interface. **Stop recording** stops
   video only; it does not stop the robot. A camera failure never triggers an
   automatic retry or motion command.
6. On terminal run status, recording stops. After a successful run, the app
   attempts a final fresh camera image and attaches it to the experiment.
   Open **Results & image comparison**, verify plate visibility, select well
   centers and a same-image target, then rank the observed mixtures. If final
   capture failed, upload a plate image manually.

## Recorded evidence

- MP4: H.264, 1280×720, 15 fps, from the CubOS camera bridge; no audio.
- Original observation JPEGs and unreviewed tip/liquid predictions at up to
  two samples per second, retained separately from video overlays.
- Source paper hash, declared stocks, protocol hash and CubOS run ID.
- Raw CubOS events with local receipt timestamps and run-state observations.
- Final plate image where available, and manually selected RGB measurements.

The default recording limit is 30 minutes (maximum one hour). A duration
limit or interrupted/failed recording is recorded explicitly. Video uses the
bridge's nominal 30-fps input; local receipt and server event timestamps are
not calibrated to sensor exposure or to one another. This is an evidence
bundle, not proof of exact step synchronization or successful liquid delivery.
Detections remain research predictions, not validated error diagnoses.

## Initial software verification

Live Bond returned 12 papers and the full six-page benchmark PDF downloaded.
The generated ten-well draft passed native local fluid/motion validation and
the station's validation-only API. For the station mock validator, physical
state is omitted as required by its API; seeded fluid checks ran locally.
No physical protocol was submitted during that initial software phase.

An eight-second camera-only recording produced a valid H.264 MP4 at 1280×720,
15 fps. Tests cover recording-before-submission, recorder failures blocking
submission, duplicate prevention, configuration drift, completion-event
handling, final-frame association, bounded source retrieval and recording
stop behavior. The model initially made an incorrect claim about tip order;
an explicit command-order trace corrected it on re-review. Physical-height findings require evidence from the actual setup; model approval
does not establish immersion.


## Corrected physical demo — 2026-10-22

The first physical attempt was cancelled at the user's request because its
stock aspiration offset was zero. A logged water transfer was not treated as
proof of delivered water. The interrupted red transfer was resolved from its
failure during the pre-aspiration move; it was never replayed.

For the authorized retry, the user provided a new plate, confirmed a fresh
C6 tip and bare nozzle, and reaffirmed setup and operator checks. CubOS state16
records the new plate while retaining consumed tip slots. The corrected run
uses A1–A10, tips C6–E11 excluding C12/D12, and −40-mm stock aspiration offsets.
Water is conservatively tracked at1440uL; dyes at1500uL each. Local and remote
native validation passed. The 26 focused tests and frontend build passed.

App run: `8acbc9beb35c47bc8d2c9e08575f5b64`. This corrected run completed successfully (94 commands, 10 wells, 20 min 7.7 s);
consult CubOS for authoritative completion and the canonical plan for the
final evidence. Its annotated replay uses saved predictions on the exact
source images, selected for visibility rather than accuracy evaluation.
