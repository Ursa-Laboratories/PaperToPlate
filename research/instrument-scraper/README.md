# Paper-to-protocol review corpus — October 21, 2026

Start with **[the 16-paper review shortlist](review_shortlist.html)** and the **[worked Bradford example](worked_example.md)** for the October 22 lab session. The likely first discussion is the BSA/RotiQuant calibration; the detergent-compatible Bradford variant and DTT time-course provide useful comparisons. Equipment, reagent availability and scientific choices still need the labmate's review.

This output reuses the existing Instrument Scraper data and the earlier ChemRxiv catalogue. It contains source-linked AI drafts, not independent ground truth, execution approval or physically validated assays. No paid model calls, old extraction pipeline, hardware operation or CubOS changes were made.

## Coverage and evidence

| Material inspected | Verified scope / finding |
|---|---|
| Joined OpenAlex Parquet | 1,670,726 rows across 2018–2025; 1,617,813 distinct OpenAlex IDs; 1,556,682 distinct normalized DOI strings. Rows are not unique papers. |
| Title/abstract screen | All joined rows screened; 1,440,987 had reconstructable abstracts; 98,031 row-level matches. This is a metadata screen, not a full-text protocol classifier. |
| Instrument model data | 1,426,476 rows contain model candidate output; 244,179 have errors; 71 have neither. These are not retained paper text. The top-level parsed `instruments` arrays are empty in this joined dataset. |
| Local ChemRxiv metadata | 35,509 rows / 35,499 exact DOI strings inspected; 2,988 row-level metadata matches; 33,168 declared supplement entries / 33,153 unique URLs inventoried. |
| Earlier ChemRxiv snapshot | 57,658 DOI records were already harvested; all 2,625 prior candidate entries are reused for the merge, with their versions and provenance. The earlier directory is unchanged. |
| Retained PDFs before this task | 15 files in the two checkouts, representing 10 unique SHA-256 documents. All 15 are parseable PDFs. The Ursa copies duplicate five saved-project PDFs. |
| Bounded public retrieval | 13 file requests: 8 PDFs obtained, 3 non-PDF responses, 2 HTTP 403s. This includes a publisher follow-up for reducing sugars and the recovered dust-assay supplement. |
| Sources now available | 23 local PDF paths / 18 unique documents: 17 main articles and 1 supplement. No confirmed truncated PDF was found. Completeness is apparent, not proof all pages and supporting information exist. |
| Text and model excerpts | 15 cached text files correspond to retained PDFs; zero unmatched text-only sources found. Five stored prompt files are not treated as source text. All ten retained-run model inputs were capped below full extracted text length. |
| Procedural curation | Nine selected assay-module drafts, nine benchmark case drafts, and 126 parameter evidence records. All short evidence passages occur on their cited PDF pages. |
| Remote storage | All 3,080 objects in the documented public S3 bucket listed; none has a PDF filename. Object content/signatures were not downloaded or verified. |

The merged catalogue contains **96,651 conservative candidates** (mostly metadata leads), **1,363 same-title alias review groups**, and **99,868 missing article/supplement entries**. All 2,625 prior ChemRxiv entries and all nine method drafts are represented. The final candidate and missing-material counts, exact/family DOI join evidence, source counts and alias-review count are in [candidate_join_summary.json](candidate_join_summary.json). The shortlist intentionally includes two papers found by actual retained-PDF method review even though their title/abstract screen did not match. This illustrates the screen's recall limit.

The nine drafts cover Bradford calibration, detergent-compatible Bradford, dust DTT kinetics, paper-based DPPH, an LPMO Ni-PV endpoint, BCA carbohydrate measurement, cellular ROS/SRB, 5-HT uptake and a PBMC culture assay. Several are challenging benchmark cases rather than suitable next-day physical experiments. The ROS protocol has an unreviewed correction; its publisher endpoint returned HTTP 468. Resolve the correction before approving a reference.

Selected method sections were reviewed for the nine drafts. This was not a cover-to-cover manual review of every available PDF. `retained_source_review.csv` records first-page triage and deferral reasons for the other retained papers. The concise [coverage report](coverage_report.md) summarizes the limits.

## Source selection and inspection limits

Both checkouts were inspected read-only before output creation. They share Git HEAD `7326d022250cacba2d852db29cd4aa810253218f`, but have different local files and pre-existing working changes. The saved project at `local-data/instrument-scraper` is the authoritative OpenAlex data source here because it contains the broad raw, joined and Parquet data, the DuckDB database and the ten-PDF run. The Ursa checkout contributes five duplicate PDFs, benchmark prompts/text and a normalized 2024 derivative. Neither checkout was merged, reset or overwritten.

The selected joined Parquet is a processed subset of the larger raw metadata collection. Large raw metadata shards, duplicate joined JSONL exports, normalized mirrors and derived databases were inventoried but not all rescreened. The `instruments.db` file is DuckDB, not SQLite; a read-only query confirmed 1,670,726 `papers` rows. Nested ZIP central directories were inspected; the five nested OpenAlex archives contain JSONL rather than PDF members. The complete local file inventory excludes dependencies, Git internals and this task's generated outputs. Files over 100 MB, except PDFs, are explicitly marked not hashed.

The original top-level OpenAlex `abstract` fields are empty. The screen reconstructs abstract word order from `raw_data.abstract_inverted_index`. Search patterns and ranking are in `scripts/build_workflow_corpus.py`. Broad matches include assay mentions, reviews, unrelated microplate-like terminology and instrument descriptions; they are not automatically promoted to methods evidence. DOI/version normalization is conservative; titles only generate alias flags. The existing snapshot's three historical alias merges are preserved as prior grouping, not newly certified identity.

Known local sources are preferred. Failed or blocked links were recorded without bypassing restrictions. No 404/410 was observed among the small tested set; the many unchecked links are **not** declared live or dead. The prior ChemRxiv downloader recorded 3 access denials and left 2,624 links unattempted after the host block. Actual deposited/asset URLs remain in the exports.

## Why old instrument outputs are insufficient

The audited processing files are byte-identical in both checkouts:

- [gemini_processor.py](local-data/instrument-scraper/scrapers/gemini_processor.py:180) downloads into `tmp_pdfs_standard`, which was absent at inspection. Both configurations use an 8 MB threshold.
- [pdf_utils.py](local-data/instrument-scraper/scrapers/pdf_utils.py:27) can remove the References page and all subsequent pages. [The processor](local-data/instrument-scraper/scrapers/gemini_processor.py:193) discards its returned page-count information, so historic outputs do not prove whether their inputs were truncated.
- [Cleanup](local-data/instrument-scraper/scrapers/gemini_processor.py:118) deletes local source PDFs even on generation/parsing failures. The output contains instrument/model JSON, not paper full text.
- [The extraction prompt](local-data/instrument-scraper/scrapers/gemini_shared.py:12) permits instrument inference; its evidence strings require checking against a retained document. Its mention of two PDFs does not mean this processor downloaded a supplement.
- The retained `runs/gemma4_pdf_10` exception saved full extracted text and full PDFs before limiting model prompts. Those source files, rather than prior model labels, were used here.

The absent `deploy.sh` and unavailable CodeGraph index in the saved checkout were not created. With the user's instruction, structural inspection used the Ursa checkout's existing CodeGraph index. No credentials were printed.

## File guide

| Files | Use |
|---|---|
| `review_shortlist.html`, `.csv`, `.jsonl` | Sixteen ranked review entries, sources, needs and open questions. |
| `methods_evidence.csv`, `.jsonl` | Page-level parameter evidence with source hash and short supporting passage. |
| `protocol_drafts.csv`, `.jsonl` | Nine structured assay-module drafts: source facts, actions, dependencies, controls, quantities, timing, readout, adaptations and unknowns. |
| `benchmark_case_drafts.csv`, `.jsonl` | Explicit input documents, objectives, equipment, scientific invariants and draft acceptance criteria. |
| `worked_example.md`, `SCHEMA.md`, `schema.json` | Human walkthrough and documented machine schema. |
| `candidate_catalogue.csv`, `.jsonl` | Conservative merged candidates, exact versions/IDs and complete source records. These files are large. |
| `candidate_join_summary.json`, `alias_review.csv`, `.jsonl` | Join provenance and uncertain same-title aliases; no silent fuzzy merging. |
| `file_inventory.csv`, `.jsonl`, `archive_members.*`, `nested_archive_inventory.json` | Complete in-scope original local data-file inventory and ZIP member inspection. |
| `openalex_record_inventory.*`, `openalex_candidates.*`, `chemrxiv_local_metadata.*` | Full screened-row exports and reproducible candidate records. |
| `pdf_supplement_manifest.csv`, `.jsonl`, `file_duplicate_groups.*` | Verified local source files, hashes, page counts and duplicates. |
| `chemrxiv_supplement_links.csv`, `.jsonl` | All locally declared supplement asset URLs, including non-candidates. |
| `missing_materials.csv`, `.jsonl`, `download_attempts.*` | Separate absent-material/retrieval-status lists; untested is distinct from inaccessible. |
| `source_text/`, `downloads/`, `review/` | Page-indexed local text, downloaded PDFs, selected source records and three inspected page renders. |
| `coverage.json`, `model_output_profile.json`, `model_input_truncation_audit.json`, `remote_storage_*` | Coverage denominators and limits, model-slot errors/excerpts and remote inventory. |
| `provenance_validation.json`, `verification.json` | Citation, schema, identity and export validation results. |

## Reproduction

Use the existing project environment. No paid model batch is needed.

```bash
.venv/bin/python scripts/build_workflow_corpus.py
.venv/bin/python scripts/curate_workflow_methods.py
.venv/bin/python -m scripts.merge_workflow_catalogues --known-pdfs runs/gemma4_pdf_10/results.jsonl
.venv/bin/python scripts/build_workflow_review_packet.py
.venv/bin/python scripts/validate_workflow_exports.py
.venv/bin/python -m pytest tests/test_workflow_corpus_utils.py tests/test_build_workflow_corpus.py tests/test_merge_workflow_catalogues.py tests/test_curate_workflow_methods.py tests/test_fetch_workflow_sources.py -q
```

The inventory/screen script performs local reads only; it can be run by `--stage inventory`, `screen` or `chemrxiv`. Source fetching is a separate explicitly bounded script using the saved `review/fetch_plan.jsonl`; it records non-PDF content and access failures and performs no bypass. Re-running it makes new network requests and overwrites only its own status file. Preserve this snapshot before refreshing it.

The packet-generation scripts reproduce the exports from the curated source facts. They do not discover new facts. Human changes should be reviewed and versioned separately before any protocol is submitted to CubOS. Approval of a draft's scientific reference and independent physical validation are both outstanding.

Validation: 29 focused tests passed. `verification.json` records zero export, PDF-hash, evidence-page or schema errors. The HTML shortlist has 16 cards and no missing local file links; visual browser QA was unavailable because the browser rejected local file URLs (`html_static_validation.json`).
