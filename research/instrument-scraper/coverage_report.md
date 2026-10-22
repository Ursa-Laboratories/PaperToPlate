# Coverage receipt — October 21, 2026

**Usable result:** 16 review candidates, nine source-linked assay-module drafts, nine benchmark drafts and 126 page-level parameter records. The Bradford calibration is the first review suggestion. Every scientific reference requirement awaits human review; none has been physically validated.

| Layer | What was covered |
|---|---|
| OpenAlex | 1,670,726 joined rows screened; 1,617,813 distinct work IDs. Abstracts reconstructed for 1,440,987 rows. |
| ChemRxiv | 35,509 local metadata rows inspected; all 2,625 entries in the earlier candidate snapshot joined. The prior 57,658 DOI records were reused, not freshly harvested. |
| Candidate corpus | 96,651 conservative candidates, including two discovered by retained-PDF review despite a negative metadata screen. 1,363 uncertain title-alias groups remain separate. |
| Retained sources | 15 original PDF files / 10 unique hashes. Both checkouts inspected; five Ursa PDFs duplicate saved-project files. |
| Bounded retrieval | Eight PDFs recovered from 13 file requests: seven articles and one supplement. Three responses were not PDFs and two returned 403. |
| Current source files | 23 local PDF paths / 18 unique documents: 17 articles and one supplement. All signatures, hashes, parseability and page counts checked. |
| Missing material | 99,868 article/supplement entries. Actual available URLs retained. Untested, denied and non-PDF responses remain distinct; none of the tested URLs returned 404/410. |
| Public remote storage | Complete 3,080-object listing inspected; no PDF filenames. Payloads/signatures not verified. |

**What is incomplete:** the metadata screen does not cover every raw OpenAlex shard or every article's full text. The joined dataset is a processed subset. Nine selected methods modules were curated; other retained documents received first-page relevance triage, not exhaustive procedural exclusion. Relevant methods may exist in metadata nonmatches. The ROS source has a correction whose publisher returned HTTP 468; it remains unresolved. No existing PDF was confirmed truncated, but associated supplements and external method references may still be missing. All ten saved model prompts were shorter than the retained full extracted text; historical instrument results cannot prove input completeness.

**What was included and deferred:** direct plate/assay, dilution, liquid-handling, calibration and contextual readout terms seeded the broad list. Review priority favored available procedural parameters, controls and measurable outcomes. Metadata-only papers remain retrieval leads. Reviews, material-fabrication topics, specialized imaging/clinical workflows and assay-name-only mentions were not treated as ready protocols. `retained_source_review.*` gives explicit retained-paper decisions; `review_shortlist.*` gives source, needs and unresolved questions for each selected entry.

**Validation:** 29 focused tests passed; all paired exports agree row for row; all 126 quoted passages occur on their cited PDF pages; all nine draft schemas validate. These checks verify the export and citation mechanics, not scientific correctness. Three priority method pages were visually checked. The optional HTML browser preview was blocked by local-file URL policy; static structure and local links passed.

The camera remains an uncalibrated imaging device. Split transfers may legitimately exceed 120 µL in total, but calibrated minimum stroke, well capacity, stock positions, dead volumes and timing still need approval. No hardware was operated, no CubOS code was modified and no paid extraction job was started.
