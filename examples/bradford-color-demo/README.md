# Bradford colored-water demonstration

Open `http://127.0.0.1:8785/?run=bradford-color-demo`.
The original biochemical Bradford example remains separate and unchanged.
This workflow demonstrates its liquid-handling pattern using the user's
prepared colors. No protein assay, absorbance reading, shaker or incubation
is part of this demonstration.

## Stock-holder map

These are stock-holder columns, not assay-plate columns. Both rows follow:

| Row | 1 · red | 2 · yellow | 3 · blue | 4 · water | 5 · empty |
|---|---|---|---|---|---|
| A | Standard surrogate: load 1.5 mL | Sample surrogate: load 1.5 mL | Working-reagent surrogate: load 3.0 mL | Dilution water: load 1.5 mL | Start empty; receives yellow 1:10 dilution |
| B | Untouched backup | Untouched backup | Untouched backup | Plate water: load 3.0 mL | Remains empty |

Use each prepared colored stock as supplied; its chemical concentration was
not specified. The blue liquid represents an already-prepared working
reagent, so no extra 2.5-fold reagent dilution is introduced. Backup volumes
are unspecified and omitted from the fluid seed rather than invented.

The saved deck retains its 4 mL configured working limit, below the user's
5 mL nominal vial specification. No geometry or calibration was changed.
Planned residual volumes do not prove the liquid is reachable by the tip.

## CubOS workflow

1. A4 water → A5: 900 uL. A2 yellow → A5: 100 uL; mix ten 100 uL cycles.
2. Plate columns 1–6: add 0, 10, 20, 30, 40 and 50 uL red from A1,
   topping each up to 100 uL with water from B4. Rows A/B/C are triplicates.
3. Plate column 7: 100 uL diluted yellow from A5, in rows A/B/C.
4. Plate column 8: 200 uL plain water from B4, in rows A/B/C.
5. Add 100 uL blue from A3 to all wells in plate columns 1–7; mix three
   80 uL cycles. All 24 used wells finish at 200 uL.

Native YAML: `protocol.yaml`. Proposed inventory: `initial_fluids.yaml`.
Tip allocation: A1–F12 inclusive, 72 fresh tips. The 900 uL addition is split
into eight 112.5 uL strokes; 200 uL additions use two 100 uL strokes.
Every transfer stroke receives a fresh tip. No stroke exceeds 120 uL.

## Expected liquid totals

| Position | Load uL | Consumed uL | Remaining uL |
|---|---:|---:|---:|
| A1 red | 1500 | 450 | 1050 |
| A2 yellow | 1500 | 100 | 1400 |
| A3 blue | 3000 | 2100 | 900 |
| A4 water | 1500 | 900 | 600 |
| B4 water | 3000 | 1950 | 1050 |
| A5 dilution | 0 initially; receives 1000 | 300 | 700 |

Visually inspect or photograph the series and replicate wells. Colors depend
on the prepared dyes and lighting; no expected RGB value or protein result is
claimed. In the yellow sample wells, the original yellow-stock equivalent is
10 uL in 200 uL final volume (5% v/v), with 100 uL blue and 90 uL water.

## Verification and operator handoff

The native offline validator passed with unchanged setup snapshots in
`../bradford-workflow/setup/`. Tests check the column mapping, exact color
mass balance, 1:10 tube dilution, 200 uL wells, untouched backups, unique tips,
and absence of protein readout on this demo. No hardware was operated.

Before physical operation: reconcile actual stocks/tips and setup; verify
calibration, liquid heights, pickup and waste on the station. Confirm the
app's loading sheet and review, then use its operator-controlled Run handoff.
Do not reset actual inventory from the proposed seed after a partial run.
Observe transfer delivery and tip handling under supervision, and measure
volumes independently before claiming pipetting accuracy.
