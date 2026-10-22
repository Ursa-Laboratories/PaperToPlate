# Worked review example: Bradford calibration

**Status: source-linked AI draft, awaiting human review.** This is the suggested first discussion for the October 22 session. It is not an execution approval.

Source: [Bradford Assay with RotiQuant (ROTH), DOI 10.17504/protocols.io.8gghttw](https://doi.org/10.17504/protocols.io.8gghttw), a published protocols.io protocol discovered in the existing OpenAlex collection. See its local PDF and hash in `pdf_supplement_manifest`, and full structured records `W2991390910` and `case-W2991390910` in the protocol and benchmark files. PDF pages 3–4 contain the method; page 2 identifies the materials and plate reader. The concentration table on page 3 was visually checked.

## Source facts to review

The source uses a 200 µg/mL BSA working stock in the sample-matched buffer. It prepares 200 µL of each standard using the following direct dilutions (p3, steps 1–3). These are not described as a serial dilution chain.

| Standard (µg/mL) | BSA working stock (µL) | Buffer (µL) |
|---:|---:|---:|
| 0 | 0 | 200 |
| 20 | 20 | 180 |
| 40 | 40 | 160 |
| 60 | 60 | 140 |
| 80 | 80 | 120 |
| 100 | 100 | 100 |

Page 3 specifies triplicate wells, 50 µL standard and 200 µL diluted reagent per well, followed by five minutes at room temperature and OD595 measurement. Page 4 specifies sample dilution choices, blanks, pigment controls when applicable, and dilution-factor correction. Each critical extracted parameter has a page-linked evidence row in `methods_evidence.jsonl`.

## Proposed adaptation — not a source instruction

Use two 100 µL strokes for each 200 µL reagent addition, subject to calibration and timing review. The resulting well contains 250 µL; confirm the plate's actual working capacity and mixing headroom. Stock preparation transfers can also be split. Do not infer minimum reliable dispensing volume from the 120 µL maximum.

A calibration-only layout needs 6 concentrations × 3 wells = **18 wells**. It consumes 150 µL of each prepared standard and 3.6 mL diluted reagent before handling losses. The nominal 200 µL standard preparation leaves 50 µL; confirm that this covers the stock vessel's dead volume. Preparing extra volume is a proposed adaptation that must preserve concentration.

One proposed staged layout uses six standards, one working reagent, one unknown and one buffer position: nine positions after preparation stocks are removed manually. Actual tube geometry, pipette reach, tips and waste remain unresolved. A plate reader capable of 595 nm is needed. Camera color is not a substitute for OD595.

## Questions for the labmate

1. Which RotiQuant product and buffer are on hand? Confirm the source's ratio notation against its explicit 4 mL concentrate plus 11 mL water recipe; do not silently reinterpret it.
2. What are the calibrated pipette range, plate working volume and holder dead volumes?
3. How should mixing, tip changes, dispensing order and per-well timing be implemented?
4. Which blank convention, calibration fit range, replicate CV limit and recovery tolerance should be accepted? These thresholds are deliberately unset.
5. Is the first reference calibration-only, or does it include an independently prepared unknown? Who prepares and records that reference?

## Proposed benchmark acceptance

The generator must preserve the source concentrations, volumes, controls and triplicates; distinguish source instructions from split-stroke proposals; compute volume/stock usage correctly; and raise the unresolved questions. The reviewer checks each fact against the actual PDF. The planned validator checks the approved equipment and volume constraints. A human-reviewed rubric and independent lab measurements must establish final scientific scoring. This task has neither generated nor validated a physical reference.
