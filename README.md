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

The backend uses Ollama Cloud with `gpt-oss:120b`. The existing local `.env`
already contains the configured Ollama key. For a fresh checkout, copy
`.env.example` to `.env`, then fill in:

```dotenv
OLLAMA_API_KEY=your_ollama_key
OLLAMA_URL=https://ollama.com
OLLAMA_MODEL=gpt-oss:120b
```

Restart `./start.sh` after changing `.env`. No OpenAI key or local model download
is needed. The UI shows whether configuration is present; a successful model
request establishes actual access. Account usage limits still apply, and rate
limit failures are displayed without automatically buying capacity or retrying
indefinitely. Keys stay server-side and `.env` is ignored by Git.

For an existing local Ollama server, set `OLLAMA_URL=http://127.0.0.1:11434`
and select a model installed there. A local endpoint does not require a cloud
key. Invalid model JSON receives one bounded format correction, then an explicit
error. Private diagnostic responses stay under the ignored data directory.

### Backend-to-frontend contract

1. `POST /api/papers` accepts multipart field `file` (PDF, TXT, or Markdown,
   maximum 25 MB). It stores the source and returns its `id`, page text, hash,
   and metadata. Image-only PDFs need OCR before upload.
2. `POST /api/runs` accepts JSON `paper_id`, `setup_id` (default `picus120`),
   `objective`, and `review_enabled` (default `true`). It returns HTTP 202 with
   the run `id`. Missing model configuration returns HTTP 503 before queuing.
3. `GET /api/runs/{id}` returns saved progress and results. The frontend polls
   while `status` is `queued` or `running`, then displays the extraction,
   protocol, source citations, review, validation, and preparation sheet.
   Terminal states include `ready`, `needs_attention`, `failed`, `cancelled`,
   and `interrupted`. `ready` means ready for operator review, not physical proof.
4. `POST /api/runs/{id}/cancel` stops generation. Completed stage artifacts
   remain available. Restarted jobs become `interrupted`; no automatic replay.

The backend runs extraction → plan generation → deterministic YAML compilation
→ separate AI review → offline CubOS validation, with one bounded plan repair.
The browser never calls Ollama directly. Drafts remain inspectable if the CubOS
validator is unavailable. No generation endpoint operates hardware. The question-led design flow below adds Valency retrieval before protocol compilation.

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
# Preparing stocks and running the protocol

Open `http://127.0.0.1:8785/?run=bradford-load-and-run` for the complete
Bradford example: the human prepares seven source liquids and leaves three
tubes empty; CubOS makes the 1:10 sample dilutions and assay plate. Human
incubation and the 590/450 nm reader step remain explicit after-run tasks.

The **Prepare & Run** view lists each source's concentration, recipe, load,
consumption, remaining volume and position. It compares loads and peak well
volumes with the configured deck limits. The nominal vial setting defaults
to the requested 5 mL; a smaller configured working limit still wins. Existing
4 mL deck geometry is not silently enlarged. Suggested loading reserves are
planning allowances, not measured dead volumes.

Generated model plans include structured stock-preparation records. Native
transfers are split into 5–120 uL strokes in 0.1 uL increments without changing
the requested total. Smaller quantities require a reviewed dilution. Missing
stock instructions, overflow, interleaved human actions and incomplete loading
prevent physical handoff. Editing stocks recalculates the proposed seed and
clears review, validation and loading confirmation. The loading acknowledgement
is specific to the complete protocol/setup/recipe revision.

After checking the loaded vials and human steps, confirm loading and use
**Run in CubOS**. Choose mock or physical execution; physical execution retains
scientific review, native validation and operator setup checks. CubOS owns all
motion and run control. `CUBOS_API_URL` must point to the operator's reachable
station. No physical run is performed by the app's development tests.

Focused verification: `python -m pytest tests/test_preparation.py tests/test_workflow.py -q`
(45 passed), plus `npm --prefix frontend run build`. Handoff tests mock the
network submission. A real Ollama synthetic-water generation smoke check and
native offline validation passed; neither establishes physical assay success.

## Design an experiment with Valency Bond

Choose **New experiment → Start from a question**. **Connect Bond** signs this
app into Valency with OAuth PKCE; the access/refresh tokens stay in the ignored
`data/private/bond.json` file with owner-only permissions. **Research & design**
retrieves papers through Bond and uses the configured Ollama model to produce
an evidence brief. Quotations are checked against the retrieved abstracts.

The first executable design family is a red/yellow/blue mixture screen. The
app calculates exact recipes, checks mapped sources, capacities and available
tips, then compiles a draft through the existing CubOS compiler and offline
validator. Other assay goals produce a research brief and require full-method
review through the paper-upload flow. None of these actions runs hardware.

**Open dye example** works without a new literature request using a clearly
labeled recorded Bond search. Click any well to inspect its recipe and origin.
Upload an actual camera image, select well centers and rank measured RGB values
against a target from the same image. Camera values are uncalibrated; no
absorbance, predicted liquid color or successful experiment is invented.

See [the demo procedure and video outline](docs/bond-color-demo.md). New routes
are `/api/bond/status`, `/api/bond/connect`, `/api/bond/callback`, `/api/designs`,
`/api/designs/{id}`, `/api/designs/{id}/protocol`, `/api/designs/{id}/images`,
and `/api/designs/{id}/measurements`. The experiment record preserves the Bond
query/request ID, retrieved papers, design settings, well recipes and measurements.
