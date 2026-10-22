# Bradford assay: stock dilution, then plate preparation

Two CubOS protocols for three unknown samples, using the supplied Picus 2
120 uL gantry and ten-position stock holder. **Offline validated; no hardware
or assay validation performed.** The camera remains mounted but is not used
for absorbance measurements.

1. `01_dilute_samples_1_in_10.yaml` makes three 1 mL stock dilutions: 100 uL
   original sample plus 900 uL water, mixed with ten 100 uL cycles.
2. `02_bradford_assay.yaml` prepares standards, transfers each diluted unknown
   into three wells, and adds dye. Each dye-containing well is mixed with
   three 80 uL cycles. Use an external plate reader afterward.

Source: Ernst and Zor, *Linearization of the Bradford Protein Assay*, JoVE 38
(2010), [DOI 10.3791/1918](https://doi.org/10.3791/1918),
[paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3164080/).
The plate layout, 1:10 sample dilution, loading reserves, tip choices and
pipette mixing cycles are implementation choices, not validated parameters
from the paper. Confirm that mixing homogenizes the tubes without bubbles.

## Runtime and physical prerequisites

The `setup/` files are byte-for-byte copies of the user attachments. No offsets,
working bounds, collision envelopes, tips, or speed settings were changed.

Use a CubOS version supporting `motion_planning`, labware `motion`,
`cnc.default_feed_rate_mm_min`, and `mix.cycles`. Offline validation passed in
the existing `CubOS-wt/color-demo-layer` environment at commit `6eb70575`.
The main `CubOS` checkout at `442c3a5d` is older and rejects the supplied feed
rate field (and uses the older `mix.repetitions` interface). Do not remove
collision geometry or rename fields blindly to run on that checkout. Validate
the exact final files with the station's installed version before running.

Routing v1 only accepts supported liquid-handling commands in these protocols.
**Home through the operator controls before each protocol. Incubation and
reader timing are manual.** There are no software readiness prompts, homing
steps, timed pauses, or absorbance acquisitions inside these YAML files.

Before liquid work, verify:

- The supplied deck is marked as a camera-derived XY candidate, not a completed
  physical calibration. Verify plate and stock-holder alignment with the bare
  pipette, then verify tip-attached clearance with the operator present.
- The tip-rack description says pickup Z 81.0, but the actual `pickup_z` and A1
  Z are 73.28. Resolve this discrepancy physically before pickup. The numeric
  value was preserved. Confirm the waste location, which is also marked as
  requiring hardware confirmation.
- All liquid commands use explicit relative height `0.0`, meaning the supplied
  labware anchor Z. Verify actual immersion and bottom clearance in both stock
  tubes and plate wells, including at the lowest final source volumes. No
  liquid-level tracking or measured dead-volume floor is supplied for the
  stock holder, which is modeled as a well plate. Retained volumes below are
  planned reserves, not proof that the liquid is reachable.
- Use a clean absorbance-compatible 96-well plate matching the supplied
  geometry, compatible 42 mm tips, and a waste receptacle that can accept 78
  discarded tips. The YAML's 5 mL liquid capacity does not establish tip capacity.
- Confirm the reagent identity. This draft assumes the paper's Bio-Rad Bradford
  reagent diluted **2.5-fold**: 1 part stock plus 1.5 parts water. For the 3.5 mL
  load, combine 1.4 mL stock with 2.1 mL water off-deck. Do not apply this dilution
  automatically to a different or ready-to-use reagent. Reagent identity and
  availability of 590/450 nm readings are still unconfirmed.

## Load the ten-position holder

Positions refer to `10_vial_holder`, not the assay plate. This fills all ten
positions and avoids a water refill between protocols. Use the displayed deck
orientation to identify A/B; do not infer it from the plate's row direction.

| Stock position | Contents at start | Load (uL) | After dilution (uL) | After assay (uL) |
|---|---|---:|---:|---:|
| A1 | Deionized water for dilution | 3500 | 800 | 800 |
| A2 | BSA, 0.1 mg/mL | 1500 | 1500 | 1050 |
| A3 | Bradford reagent, already diluted 2.5-fold | 3500 | 3500 | 800 |
| A4 | Unknown 1, original sample | 1500 | 1400 | 1400 |
| A5 | Unknown 2, original sample | 1500 | 1400 | 1400 |
| B1 | Unknown 3, original sample | 1500 | 1400 | 1400 |
| B2 | Empty; becomes unknown 1 at 1:10 | 0 | 1000 | 700 |
| B3 | Empty; becomes unknown 2 at 1:10 | 0 | 1000 | 700 |
| B4 | Empty; becomes unknown 3 at 1:10 | 0 | 1000 | 700 |
| B5 | Deionized water for assay | 3000 | 3000 | 1050 |

Each original sample contributes only 100 uL. The larger source load is an
unvalidated allowance for this tall stock-holder geometry. Do not consume
scarce samples to meet it without first establishing an appropriate tube,
aspiration height and minimum usable volume, and updating the fluid seed.

Start with an empty plate, no attached tip, and fresh tips A1-G6 inclusive
(row-major order). Protocol 1 uses A1-A6; protocol 2 uses A7-G6. The remaining
tips are unused. Retain this allocation if running the protocols separately.
`tip_present` in the attachment is a planned inventory, not a physical sensor.

## Assay plate map

Rows A, B and C are triplicates of the same layout. Rows D-H and columns 11-12
remain unused. All used wells finish at 200 uL.

| Column | Identity | Water (uL) | BSA stock (uL) | Diluted unknown (uL) | Diluted dye (uL) |
|---|---|---:|---:|---:|---:|
| 1 | 0 ug BSA, dye-only standard | 100 | 0 | 0 | 100 |
| 2 | 1 ug BSA | 90 | 10 | 0 | 100 |
| 3 | 2 ug BSA | 80 | 20 | 0 | 100 |
| 4 | 3 ug BSA | 70 | 30 | 0 | 100 |
| 5 | 4 ug BSA | 60 | 40 | 0 | 100 |
| 6 | 5 ug BSA | 50 | 50 | 0 | 100 |
| 7 | Unknown 1, from stock B2 | 0 | 0 | 100 | 100 |
| 8 | Unknown 2, from stock B3 | 0 | 0 | 100 | 100 |
| 9 | Unknown 3, from stock B4 | 0 | 0 | 100 | 100 |
| 10 | Optical blank, water only | 200 | 0 | 0 | 0 |

Protocol 2 loads water first, then BSA, then diluted samples, and finally dye
in column order (A1, B1, C1, A2, ... C9). Each destination/reagent addition has
a fresh tip. The water blanks use two 100 uL transfers with one dedicated tip
per blank. A dye tip mixes only its destination and is discarded before any
return to the reagent source. Each aspiration is at most 100 uL.

## Offline checks

From this repository, with a compatible installed CubOS interpreter configured:

```bash
cd PaperToPlate
BRADFORD_DIR="$PWD/examples/bradford-workflow"
BRADFORD_PYTHON="$CUBOS_VALIDATOR_PYTHON"
"$BRADFORD_PYTHON" -m cubos.tools.validate_setup \
  "$BRADFORD_DIR/setup/picus120_fast_camera_20261014.yaml" \
  "$BRADFORD_DIR/setup/cub_deck_xy_camera_20261021.yaml" \
  "$BRADFORD_DIR/01_dilute_samples_1_in_10.yaml" \
  "$BRADFORD_DIR/01_initial_fluids.yaml"
"$BRADFORD_PYTHON" -m cubos.tools.validate_setup \
  "$BRADFORD_DIR/setup/picus120_fast_camera_20261014.yaml" \
  "$BRADFORD_DIR/setup/cub_deck_xy_camera_20261021.yaml" \
  "$BRADFORD_DIR/02_bradford_assay.yaml" \
  "$BRADFORD_DIR/02_prepared_fluids.yaml"
"$BRADFORD_PYTHON" -m pytest -c /dev/null --rootdir="$BRADFORD_DIR" \
  "$BRADFORD_DIR/test_workflow.py" -q
```

These commands do not operate hardware. Repeat setup validation with the
station's own Python environment and actual file paths before a physical run.
The test command selects the installed routing-enabled package without the
older checkout's pytest configuration overriding its import path.
Saved results are in `validation/*_routing_runtime.txt`. Other logs are earlier
schema compatibility probes and do not represent the final validation result.

## Operator commissioning and run order

Do these steps with an operator at the station. No physical step below has
been performed by the author.

1. Resolve the calibration, pickup, waste, liquid-height and reagent checks
   above. Home through the operator controls with no attached tip. Confirm the
   original fast motion settings are appropriate; the protocol does not lower
   the gantry speed.
2. For a short water check, load 3500 uL water in stock A1, leave other liquid
   positions empty, and use a fresh test plate and tips A1/A4/A7/A8. Validate
   `00_water_commissioning.yaml` with `00_water_fluids.yaml`, then have the
   operator load and run it. It creates 1 mL water in B2, mixes it, and transfers
   200 uL to plate A1 using two tips, mixing after the second transfer. Inspect
   for air aspiration, leakage, collision, pickup/ejection failure and bubbles;
   check the delivered volume with a suitable balance or independent method.
3. On a separate fresh setup, commission the full route with water replacing
   all stocks, empty B2-B4 and an empty plate. Use `water_01_initial_fluids.yaml`
   and, after verifying completion, `water_02_prepared_fluids.yaml`. These keep
   the same volumes with water-only composition labels. Run protocols 1 and 2 in order under
   supervision. Check every used plate well and stock position, all 78 tip
   operations, and the elapsed dye-stage equivalent time. The short check
   alone does not cover all stock/tip/plate positions. Confirm small-volume
   transfer accuracy (10-50 uL) before trusting the standard curve.
4. Restore a fresh assay setup using the loading table and fresh tips. Load the
   unchanged setup files and protocol 1. Seed `01_initial_fluids.yaml` only
   after verifying the stated contents. Home before starting. After successful
   completion, confirm B2-B4 each contain 1 mL of the appropriate 1:10 dilution.
5. Retain these tubes and the same empty assay plate. Confirm tips A7-G6 are
   available. For protocol 2, retain the verified tracked fluid state if the
   station workflow supports it, or seed `02_prepared_fluids.yaml` into a new
   run only after reconciling the actual inventory. Home with no attached tip,
   then start protocol 2 with the external reader ready.
6. Record the times of the first and last dye transfers. After completion,
   wait at least five minutes after the last dye transfer, then read 590 and
   450 nm. Complete both readings within sixty minutes of the first dye
   transfer. This conservative window covers every well. The YAML does not
   enforce it. If addition, interruptions or reading exceed the window, treat
   that plate as invalid and prepare a fresh one; do not resume blindly.
7. Never restart either YAML from step one on a partially completed physical
   setup. Reconcile fluid and tip inventory first. The seed files and
   `expected_final_fluids.yaml` describe planned states, not measured state.
   Keep assay timing and sample identities with the reader results.

## Readout and dilution correction

Subtract the mean water-blank absorbance at each wavelength before computing
the ratio `R = A590_net / A450_net`. Reject zero/near-zero denominators or reader
saturation. Fit `R = m * protein_ug_per_well + b` using the standards, including
the zero-protein dye wells. Do not force the intercept to zero. Inspect
triplicate agreement and fit residuals; dilute and repeat samples outside the
calibration range. A camera image does not supply these absorbance values.

For the unknowns, `protein_ug_per_well = (R - b) / m`. Each well contains 0.1 mL
of a 1:10 dilution, so **original concentration (ug/mL) =
protein_ug_per_well * 100**. Do not apply another factor of two for the dye
addition when fitting against protein mass per well. The selected 1:10 dilution
is provisional; it does not establish that the samples lie within the curve.

## Verification status

All three final protocols passed the routing-enabled offline setup validator:
schema/loading, motion bounds, collision-aware planning, semantics, and seeded
fluid-volume checks. Focused tests additionally check the inter-protocol fluid
handoff, exact standard masses, 1:10 dilution, water-only blanks, capacity and
fresh-tip allocation (**6 tests passed**). Physical calibration, liquid handling, reagent identity,
mixing performance, timing and reader/assay performance remain unverified.
