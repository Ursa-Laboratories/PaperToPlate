# Paper to Plate × Valency Bond: color matching demo

Open the app, choose **New experiment → Start from a question → Open dye example**.
The example uses an actual Bond search captured on October 22, 2026, with request
ID `12342d8431ca4081a5ba1f85f02646bd`. It is labeled recorded. For live searches,
click **Connect Bond**, complete Valency sign-in, and select **Research & design**.
The app uses its own OAuth connection; it does not extract the assistant's tokens.

## The question

“Which red/yellow/blue water-dye recipe is closest to this target green under
our camera?” Use a physical colored target beside the plate if possible. A
screen swatch is a convenient starting point, but screen RGB and camera RGB
are not calibrated equivalents. A target can be outside the dyes' reachable
color range. The first screen identifies the best observed candidate; it does
not claim a global optimum or run an autonomous optimization campaign.

Bond retrieved [Exploring Benchmarks for Self-Driving Labs using Color Matching](https://arxiv.org/abs/2310.00510).
The [full methods](https://arxiv.org/html/2310.00510v1), sections 2.1, 2.4 and 2.5,
describe CMYK dye mixtures, camera measurements and iterative solvers. This demo
adapts the workflow to the user's red/yellow/blue stocks. The recipes below,
120 µL volume, 50% stock fraction and 3-cycle mix are local proposed choices;
they are not values extracted from that paper. LED light-mixing papers in the
search results are background leads, not interchangeable dye protocols.

## Default 10-well screen

The order is randomized with seed 42. All amounts are µL. Center repeats are
technical repeats from the same working stocks.

| Well | Purpose | Red | Yellow | Blue | Water | Total |
|---|---|---:|---:|---:|---:|---:|
| A1 | Center repeat 2 | 20 | 20 | 20 | 60 | 120 |
| A2 | Red + yellow | 30 | 30 | 0 | 60 | 120 |
| A3 | Blue reference | 0 | 0 | 60 | 60 | 120 |
| A4 | Center repeat 3 | 20 | 20 | 20 | 60 | 120 |
| A5 | Yellow + blue | 0 | 30 | 30 | 60 | 120 |
| A6 | Center repeat 1 | 20 | 20 | 20 | 60 | 120 |
| A7 | Water blank | 0 | 0 | 0 | 120 | 120 |
| A8 | Red + blue | 30 | 0 | 30 | 60 | 120 |
| A9 | Red reference | 60 | 0 | 0 | 60 | 120 |
| A10 | Yellow reference | 0 | 60 | 0 | 60 | 120 |

Consumption is 180 µL of each dye and 660 µL of water. The loading planner
proposes a reserve; default loads are 400 µL per dye and 900 µL water. These
reserves do not establish reachable liquid depth or physically sufficient
immersion. The operator must check the selected vial geometry and working
stock depth. There are 28 fresh transfer tips, ten final-well mixing actions,
and 94 compiled commands. A 20-well two-block option repeats the screen with
an independently randomized spatial order.

Sources: the user specified column 1 red, column 2 yellow, column 3 blue.
The UI proposes row A of `10_vial_holder`, with water at A4. The source row,
water location, stock concentration, tip inventory and working geometry must
be confirmed in CubOS; these are not observations of live inventory. Select
another setup or edit source positions if the station uses a different holder.
Never replace existing stocks simply because the default map says to.

The Pi at http://10.193.33.24:8742 responded to read-only health/status calls
and reported connected, idle, and no active run on October 22. Its saved deck
files differ in calibration and holder names; availability of a config is not
proof it is the commissioned/current physical setup. This task did not change
station configuration or execute any physical command.

## Operator procedure

1. Confirm this is a suitable benign dye demonstration and review the exact
   setup in CubOS. Pilot the dye dilution so central well pixels are neither
   saturated nor too faint; do not assume the three stocks have equal strength.
2. Select the intended setup, confirm source row/water position, choose the
   first fresh tip and an empty destination region, then create the draft.
3. Inspect the loading sheet, protocol, source evidence and offline validation.
   Have an operator review calibration, reachable liquid depths, tip/waste
   positions and the proposed mixing settings. Review and loading confirmation
   are still required by the existing handoff workflow.
4. The operator performs any physical run through CubOS. This feature never
   starts a hardware run automatically.
5. With fixed camera position, exposure, white balance and diffuse lighting,
   image the whole plate after mixing and bubbles settle. Include a physical
   target and white reference. Save the actual PNG/JPEG.
6. Return to **Experiment design**, upload that image, select each well and
   click its center. The app averages a 7×7 pixel region; avoid glare, edges,
   bubbles and background. Pick the target from the same image when available.
7. Rank measured wells. The blank is reported but excluded from the winner.
   Partial results remain labeled partial. Keep the image and RGB evidence.
   These are uncalibrated camera comparisons, not absorbance measurements.

## Suggested 90-second video

- 0–15 s: show “Start from a paper” and “Start from a question”; enter the question.
- 15–30 s: run live Bond search; show the paper and the difference between
  reported CMYK work and proposed RYB adaptation. Use recorded mode only with
  its label visible if live access is unavailable.
- 30–45 s: click A5. Explain 30 µL yellow + 30 µL blue + 60 µL water, plus the
  controls and repeated center. Change the well budget to show a new design.
- 45–60 s: show the loading sheet and compiled protocol. Include genuine footage
  of an operator-approved run only if that run actually happened.
- 60–80 s: upload the real image, sample wells and show the closest observed
  mixture. A lower distance is an observation, not proof of an optimal recipe.
- 80–90 s: “From a question, through the literature, to an experiment where every
  well has a reason.” Show the Bond retrieval receipt and linked source.

## Scope

Executable generation currently supports the bounded three-component mixture
screen. Other assay questions receive a live literature/AI brief, then require
full-method review through the paper-upload route. No automatic Bayesian
optimizer, general arbitrary-assay DoE compiler or autonomous camera feedback
loop is claimed. Camera scoring is manual region selection from a saved image.

## Verification receipt — October 22, 2026

- Connected this app to Valency through its own OAuth sign-in.
- Completed a live two-query Bond search and Ollama `gpt-oss:120b` brief;
  12 distinct papers retrieved and two abstract quotations matched literally.
- Live design: `8b46aa4407714fabb4a571953d707516`.
- Draft run: `050bcbb6aa364b10b0f1052eb4cd5140`, using the color-column setup.
- Native CubOS offline validation passed. Hardware was not contacted; no
  handoff was submitted and the draft still requires review/loading confirmation.
- 67 focused backend tests passed; production TypeScript/Vite build passed.
- Browser checked both entry points, live/recorded evidence labels, per-well
  recipes, protocol/loading handoff, and image-region sampling/ranking.
- Pixel sampling was checked on a separate clearly labeled synthetic chart:
  red returned (255,0,0), identical sampled target yielded RGB distance 0,
  and the output was correctly labeled a partial result. This is software
  verification, not physical color-matching performance.
- The preview is at http://127.0.0.1:8786/?design=1 while the other local app
  remains on 8785. Starting the updated source normally uses 8785.
