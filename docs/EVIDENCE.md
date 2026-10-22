# Evidence & evaluation · What the prototype establishes

[← Project](../README.md) · [Valency integration](VALENCY_BOND.md) · [Demo](DEMO.md)

**Evidence snapshot: October 22, 2026.** Software checks, controller completion, camera observations, and independent scientific measurements are different kinds of evidence. This page keeps their scope explicit.

## Physical color-mixture run

| Observation | Recorded result |
|---|---|
| CubOS terminal state | `succeeded` |
| Completed commands | 94 |
| Wells reported mixed | 10 |
| Controller run duration | 1,207.72 seconds — approximately 20 minutes |
| Planned well volume | 120 µL |
| Evidence retained locally | Original video, controller events, source/protocol/configuration identity, final image |

The [public execution summary](evidence/color-run-summary.json) identifies the run and preserves these limits. The [README preview](assets/color-run.webp) is a time-compressed excerpt of the actual recording.

**Established:** the system progressed from a source-informed design to a physical liquid-handling run that CubOS reported complete, with recorded evidence retained.

**Not independently established:** delivered-volume accuracy, calibrated color distance, a successful target match, detector accuracy, or performance of an iterative optimizer.

The CMYK literature workflow was adapted to the available red/yellow/blue stocks. The first-round mixture design is local; it is not a reproduction of the source paper's optimizer.

## Bradford preparation example

The [colored-water example](../examples/bradford-color-demo/README.md) preserves a published Bradford preparation structure: six standard levels, one diluted unknown, and a separate water blank in triplicate. The full design contains 24 wells at 200 µL and uses 72 fresh tips.

Its native protocol has passed offline checks. That establishes compatibility with the supplied software/configuration model, not protein chemistry, analytical sensitivity, physical pipetting accuracy, or calibrated positions.

The actual [Ernst/Zor protocol](https://pmc.ncbi.nlm.nih.gov/articles/PMC3164080/) uses a two-wavelength absorbance ratio. The colored-water demo does not generate a protein concentration. Other Bradford variants remain distinct methods.

## Computer vision

The vision layer detects tips and visible liquid, retains observations, and supports development of execution-error detection.

The [recorded-run adaptation report](vision/local-liquid-replay.md) documents a small test of the local liquid detector: three correct liquid regions among four positive frames and no false alarms among four negative frames. Those frames share the same camera/run and assistant-authored labels; the counts are **not a general accuracy estimate**.

A later operator recording was inspected with the same frozen models, providing additional qualitative observations. It was not an exhaustively labeled benchmark. The complete limitations and hashes are preserved in the linked reports.

| Signal | What it can support today | What it cannot establish alone |
|---|---|---|
| Tip detection | A predicted tip region in a frame | Successful pickup or correct attachment |
| Visible-liquid detection | A predicted region of liquid appearance | Delivered µL, concentration, or successful dispense |
| Controller event | A reported command/state transition | Independent physical success |
| Camera replay | Inspection of recorded behavior | Exhaustive error-detection accuracy |

## Software verification

The repository includes tests for structured output handling, source/artifact boundaries, deterministic compilation, volume arithmetic, native validation, state invalidation, handoff behavior, and vision adapters.

Run the current code rather than relying on a static badge:

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend run build
```

Historical receipts retain their own scope and dates:

- [Initial application checks](verification/final-verification.json).
- [Vision implementation checks](vision/verification.md).
- [Vision replay measurements](vision/liquid-replay-report.json).
- [Additional operator-run observations](vision/repeat-run-report.json).

The local prototype is under active development. The paper-selection interface and run-recording integration may advance ahead of the published app code. This documentation update publishes the project story and curated evidence without treating concurrent unfinished code as a verified release.

## Toward a proper evaluation

We will build an evaluation set from **human-verified paper-to-protocol pairs**, then test both the digital translation and the resulting physical work.

| Evaluation layer | Reference evidence | Example measurements |
|---|---|---|
| Literature selection | Human-reviewed candidate relevance and requirements | Relevant-method retrieval, unsupported substitutions, missing requirements |
| Source extraction | Annotated full methods and supplements | Quantity/unit accuracy, step coverage, citation support |
| Experiment adaptation | Reviewed equipment-specific plans | Explicit assumptions, supported controls, adaptation errors |
| Compilation | Independently checked recipes and execution constraints | Volume conservation, valid strokes, tip use, capacity conflicts |
| Physical execution | Independent volume measurements and operator labels | Delivered-volume error, failed transfers, recovery behavior |
| Scientific outcome | Appropriate assay/readout controls | Agreement with reference methods and acceptance criteria |
| Vision | Human-reviewed independent runs | Missed errors, false alarms, unknown cases, run-level performance |

Future data splits should separate complete runs and sessions. Adjacent video frames do not become independent trials, and model-generated labels do not become ground truth without review.

**The aim:** identify where the agent can act reliably, where it should expose uncertainty, and where a human decision is required.
