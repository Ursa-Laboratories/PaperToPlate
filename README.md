# Ursa Paper to Plate

A local research workbench over CubOS: paper upload, Ollama-assisted method
extraction, native protocol generation, a separate reviewer, offline validation,
transparent scoring, video evidence and an explicit operator handoff.

## Open the application

On this Mac: **http://127.0.0.1:8785/**

If the application is not running:

```bash
cd PaperToPlate
./start.sh
```

The app binds only to the local computer. Keep its process running while a model
job is active. It does not connect or move the gantry at startup.

Morning questions and the reference-run checklist are in
[docs/morning-lab-review.txt](docs/morning-lab-review.txt). An optional private
Google Doc link can be configured locally with `PAPER_TO_PLATE_MORNING_DOC_URL`.

## Work included in this repository

- `src/`, `frontend/`, `tests/`: the working application and its verification.
- `examples/bradford-workflow/`: separate stock-dilution and assay protocols,
  water commissioning drafts, supplied configuration snapshots and offline tests.
- `research/three-assay-review/`: the three new assay extractions, original
  CC-BY source papers, source-page evidence, PDF/HTML reports and structured JSON.
- `research/chemrxiv/`: catalogue collection/screening tools, metadata exports,
  workbook and PDF-link lists. These links are not a downloaded-paper corpus.
- `research/instrument-scraper/`: the earlier source-linked method drafts,
  shortlist and collection coverage reports.
- `docs/`: implementation status, verification receipt, screenshot and lab review.

Credentials, runtime uploads/model responses, dependencies and bulk downloaded
PDF collections stay local. The three source papers in the extraction review
are included under their stated CC-BY licenses; see `THIRD_PARTY_NOTICES.md`.

## First use

1. Open **Morning paper library** to read the curated shortlist. Local PDFs
   open directly; retrieval leads are labeled. **Use this paper** imports the
   available main article and supplements into a combined source with page
   provenance. Or choose **New experiment** and upload your own PDF/text.
2. Describe the experimental objective and review **Lab setup**. Source
   identities, stock concentrations and loading volumes are part of the input.
   The default setup is the original JoVE Bradford example with prepared 1:10
   samples. It is not interchangeable with the RotiQuant paper's setup.
3. Click **Generate protocol**. The app extracts the method, proposes typed
   liquid-handling operations, compiles native CubOS YAML, reviews the source
   independently in a separate model call, and invokes the installed CubOS
   validator. One plan repair and one format correction per model call are
   bounded. No stage starts a hardware run.
4. Inspect **Review**, **Validation** and **Source**. Questions and assumptions
   remain visible. Edit YAML when needed; saving invalidates the old review,
   validation and video alignment. Re-run the review and validator afterward.
   If the reviewer is wrong, **Human review** records a named reviewer, a
   substantive response to each critical finding and unresolved question,
   and the overall decision. The model's original verdict stays in the record.
   Human decisions are tied to the exact protocol and review revision.
5. Add video and mark protocol steps at the current playback time. Markers are
   manually assigned, not detected or verified by a vision model. The bundled
   Ursa video is explicitly labeled as unrelated demo footage.
6. In **Results**, add independently reviewed final-volume criteria or import
   Bradford A590/A450 readings using the provided CSV template. The app computes
   blank-corrected ratios, calibration, dilution-corrected concentrations and
   replicate CV. It does not apply a universal physical-success threshold.
7. Export the source/configuration/evaluation bundle, or choose **Review
   handoff** to submit through CubOS's public run API. Mock mode is the default.

## Physical handoff

Physical execution belongs to CubOS. Its operator interface must be reachable
and the station must already be commissioned and appropriately connected by
the operator. The app submits an inline gantry/deck/protocol bundle and the
declared initial-fluid seed to `/api/v1/runs`; it does not automatically home,
connect, calibrate or resume a robot.

A physical submission requires a current passing offline validation, current
review, no unaddressed critical findings or unsupported manual interleaving,
and explicit operator confirmations for the procedure, physical setup and
manual steps. Validation runs again immediately before submission. Stable
submission IDs and a persisted submission-attempt record prevent accidental
double submission or replay after an uncertain response. Inspect CubOS if
submission fails; do not assume the experiment did not start.

A documented human adjudication can resolve model findings; it cannot bypass
failed native validation, stale revisions, unsupported manual interleaving or
physical setup confirmation. No live-run human approval was entered during
development.

Use **Copy draft** for a separate attempt. Copies clear execution evidence,
review and validation, and require a fresh setup verification. They are not an
instruction to replay an interrupted experiment. Controls for a running
physical protocol remain in CubOS.

The default hardware API address is `http://localhost:8742`. Configure a
different authorized address through server-side `CUBOS_API_URL` in `.env`.
For a Pi station, use the station's established localhost tunnel and existing
CubOS operator workflow. `CUBOS_API_TOKEN` is optional when the station requires
native-client authentication. Neither token nor Ollama key is sent to the UI
or included in export bundles.

## What is validated, and what is not

- Native CubOS validates command schemas, fluid volumes, reachable targets and
  configured collision-aware routes. The local interpreter is selected using
  `CUBOS_VALIDATOR_PYTHON`; it imports its installed `cubos` package. The older
  main checkout cannot load the supplied routing configuration.
- The compiler currently supports transfer and mix operations. Transfers use
  strokes of at most 100 uL, with a fresh tip for each transfer stroke. An
  immediate destination mix can reuse that stroke's tip. Tip exhaustion is an
  explicit compilation failure. Other instruments and manual tasks are not
  silently synthesized into unsupported commands.
- Source text is extracted with page provenance. The AI context prioritizes
  relevant methods within a 36,000-character limit; source coverage is recorded.
  Scanned/image-only PDFs need OCR, and tables/figures still merit human review.
- A reviewer finding is model output, not independent scientific truth. The
  free hosted model may miss details or raise incorrect concerns. Keep a human
  reference rubric and inspect primary sources.
- Current independent automatic rubric support checks final volumes. Other
  scientific acceptance criteria remain explicit human-reviewed requirements.
- Reader-data analysis currently implements the JoVE **590/450 nm ratio**
  method. A **595 nm RotiQuant** result needs its own analysis; do not relabel
  its reading as a ratio input. The morning pack presents these as distinct
  methods, not interchangeable variants.
- The supplied deck is a camera-derived candidate with a tip-height label
  discrepancy. Liquid immersion, volume accuracy, mixing, inventory, reagent
  identity and physical assay performance remain operator verification tasks.
- No hardware was operated during development. No model score or video marker
  is represented as proof that a physical assay succeeded.

## Model and files

The app uses the user's authorized hosted Ollama configuration, copied from
Loci into a private `.env`. The default is the existing `gpt-oss:120b` model.
Credentials stay server-side. Usage and limits depend on that account; the app
does not purchase capacity. Invalid model JSON receives one bounded format
correction, then becomes an explicit error. Private diagnostic responses are
kept under the ignored data directory for troubleshooting.

`data/` stores paper uploads, model runs, reviews and video evidence. These are
research artifacts, not a cache of live CubOS inventory. Setup snapshots are
the explicit inputs used for each draft. Do not commit `.env` or `data/`.

`examples/review-library.json` contains the curated paper-review metadata and
document hashes. The optional PDFs in `examples/library/` are not committed;
a fresh checkout labels them as retrieval leads until the matching PDFs are
placed there. Upload a paper directly through the app to use any other PDF.
The larger catalogue and source-linked method drafts are in `research/`. Original
brand template assets were retained unchanged; the app uses copied references,
the approved palette and a locally hosted open-license DM Sans implementation.

## Install and verify

```bash
./setup.sh
cp .env.example .env  # only for a fresh installation; do not overwrite an existing key
# Configure the model service and an interpreter with compatible installed CubOS.
.venv/bin/python -m pytest -q
cd frontend && npm run build
```

The initial npm peer resolver crashed on this machine; `--legacy-peer-deps`
produced the checked-in lockfile and a successful build. Dependencies stay in
this project's environment. The focused tests cover compilation, native offline
validation, dilution/readout math, upload/host boundaries, stale reviews,
submission deduplication, evidence invalidation and structured model correction.

`examples/water-workflow-test.pdf` is an explicitly synthetic software fixture.
It is not a published paper or a physically performed assay. Live model test
receipts are kept in `artifacts/` and do not imply hardware validation.

The included `start.sh` starts the app after a computer restart. Server process
management is local to each installation. Build-machine logs and session state
are not included in this repository.

## Live tip and liquid detection

The **Vision lab** link opens `http://127.0.0.1:8785/?vision=1`. It includes the
MX Brio feed through CubOS, trained YOLO and experimental independent DINOv2
models, recorded source examples, frame annotation and short evidence exports.
Start configured services with `./demo.sh`; see [setup and operation](docs/vision/README.md)
and [training/data requirements](docs/training.md). Model files are local
artifacts and are not included in this repository. Source-test results are not
claims of accuracy on the MX Brio or proof of liquid volume.
