# Bond → Bradford → colored-water demonstration

In **New experiment → Start from a question**, leave **Choose from my question**
selected and enter:

> Find a plate-based Bradford assay that measures protein in an unknown sample
> using a standard curve. Recreate its pipetting structure as a colored-water
> demonstration: red for standards, yellow for one unknown, blue for reagent,
> plus plain water. Include dilution, replicates and blanks. I have a 120 µL
> single-channel pipette and a camera, but no protein or absorbance reader.

Click **Research & design**. The app runs the user's query through Bond, then a
focused method query to locate the reviewed Ernst/Zor microplate protocol.
Broad searches also find camera-based RGBradford papers; those are not silently
substituted for this source. The protocol button requires retrieval of
[Ernst & Zor, 2010, DOI 10.3791/1918](https://pmc.ncbi.nlm.nih.gov/articles/PMC3164080/).

The paper's scientific question is protein quantification using a BSA calibration
curve and a two-wavelength absorbance ratio. The demonstration's question is
whether the representative liquid-handling pattern produces the intended
series, repeated unknown wells and distinct blanks. Colored water cannot test
the paper's protein-binding chemistry, analytical sensitivity or concentration
accuracy. The app identifies that difference in its evidence and result views.

## What the app generates

The source-specific template was checked against the full published protocol.
AI supplies the literature interpretation; deterministic code computes the
supported recipe, tip demand and native CubOS commands. It does not claim that
an unrestricted model independently invented or validated a new assay.

With three technical replicates, rows A/B/C repeat eight conditions:

| Plate column | Represents | Red | Diluted yellow | Water | Blue | Final |
|---|---|---:|---:|---:|---:|---:|
| 1 | Reagent-only zero standard | 0 | 0 | 100 | 100 | 200 |
| 2 | Standard level 1 | 10 | 0 | 90 | 100 | 200 |
| 3 | Standard level 2 | 20 | 0 | 80 | 100 | 200 |
| 4 | Standard level 3 | 30 | 0 | 70 | 100 | 200 |
| 5 | Standard level 4 | 40 | 0 | 60 | 100 | 200 |
| 6 | Standard level 5 | 50 | 0 | 50 | 100 | 200 |
| 7 | One unknown, diluted 1:10 | 0 | 100 | 0 | 100 | 200 |
| 8 | Water-only blank | 0 | 0 | 200 | 0 | 200 |

All values are µL. No protein mass is assigned to a red-water level. The zero
standard includes reagent surrogate; the water blank does not. This is the
useful scientific detail to highlight in the video.

Before plating, the generated protocol adds **900 µL water from stock A4 +
100 µL yellow from stock A2 into empty stock A5**, then mixes. Plate column 7
receives that dilution. Its final original-yellow-stock equivalent is 10 µL
in 200 µL total. The 1:10 surrogate dilution is a local demonstration choice.

Stock-holder columns remain: **1 red, 2 yellow, 3 blue, 4 water, 5 empty**.
The active sources are A1 red, A2 yellow, A3 blue, A4 dilution water and B4 plate
water. A5 starts empty and receives the dilution. B1/B2/B3 backups are not used;
B5 stays empty. Do not confuse stock-holder columns with assay-plate columns.

## Choose the video length

| Setting | Plate wells | Fresh tips | Compiled commands |
|---|---:|---:|---:|
| 3 technical replicates | 24 | 72 | 238 |
| 2 technical replicates | 16 | 51 | 168 |
| 1 replicate | 8 | 30 | 98 |

Triplicates match the paper. The shorter versions are explicitly labeled
adaptations. One replicate cannot establish within-condition repeatability.
All transfer strokes remain within the existing 5–120 µL compiler profile.
Large additions are split; fresh tips are allocated for each stroke.

## Review and operator execution

1. Select the **Color columns** setup and the first genuinely fresh tip.
2. Create the protocol draft. Review the five stock loads, source locations,
   empty destinations and native validation. The existing full-demo guide at
   `examples/bradford-color-demo/README.md` describes the proposed loads.
3. Run the model reviewer and inspect its findings. Record independent human
   review only after actually checking the source and the planned liquid work.
4. Reconcile actual stock/tip inventory and verify physical calibration, liquid
   immersion, plate emptiness and waste on the Pi. Confirm the loading sheet.
5. The operator may then choose **Run in CubOS** and explicitly select/confirm
   physical execution. The local preview's configured handoff address is
   `http://10.193.33.24:8742`; generation and offline checks never start a run.
6. Photograph the plate after mixing and bubbles settle. Under fixed lighting
   and camera settings, upload the image in **Experiment design**, select wells
   and sample their centers. Compare RGB appearance within the standard/sample
   replicate groups. Do not fit a protein calibration curve to these colors.

A new draft proposes an initial loading; it is not a live inventory reading.
After any partial run, reconcile with CubOS instead of replaying or resetting
inventory from this proposal.

## Video sequence

- Ask the question and click **Research & design**.
- Show Bond's retrieved source and its actual scientific objective.
- Show the adaptation: red → standard, yellow → unknown, blue → reagent.
- Click a standard, the sample and the water blank to inspect recipes/source steps.
- Show the 1:10 dilution and loading sheet; then genuine operator-approved footage.
- Show the resulting plate and camera observations, labeled colored-water demo.
- Close on “A research question becomes a sourced, reviewable experiment.”

**Open Bradford example** is a labeled replay of actual saved Bond retrievals.
For the prize submission, demonstrate live retrieval when access is available;
do not label recorded evidence or synthetic test images as a live experiment.
