# ChemRxiv assay and pipetting workflow catalogue

Snapshot cutoff: **October 21, 2026** (America/New_York). Exact UTC retrieval
timestamps are preserved in the harvest manifest.

This is a complete harvest of the accessible Crossref posted-content records
under ChemRxiv's DOI prefix for the stated cutoff, with a transparent metadata
screen for assay and liquid-handling workflows. **It is not a verified list of
every runnable protocol on ChemRxiv.** Full methods and supporting information
were not accessible for comprehensive screening.

## Results and files

| Measure | Count |
|---|---:|
| DOI records retrieved / reported by Crossref | 57,658 / 57,658 |
| DOI families after version grouping | 45,635 |
| Families matching assay or liquid-handling terminology | 1,663 |
| Families matching direct or broader workflow terms | 2,628 |
| Candidate entries after conservative migration-alias grouping | 2,625 |
| Deposited PDF URLs for candidate families, all versions | 3,344 |
| Deposited PDF URLs across the entire harvested corpus | 57,604 |
| DOI records without a deposited PDF URL | 53 |
| DOI records without an abstract | 514 |

Start with **`ChemRxiv-workflow-catalogue.xlsx`**, a filterable table containing
all 2,625 candidate entries, clickable PDF links, matched terms, short evidence
excerpts, dates, DOIs and source links. Its second sheet explains coverage.

For data processing or bulk links:

- `workflow_candidates_deduplicated.csv`: the candidate list in CSV format.
- `workflow_candidates_deduplicated.jsonl`: the same groups with all underlying
  DOI identifiers, PDF links and provenance arrays retained.
- `workflow_pdf_links.txt`: all 3,344 deposited PDF links for all versions in
  matching DOI families.
- `workflow_latest_pdf_links.txt`: 2,627 PDF links for the latest record in each
  matching DOI family, before the three extra migration-alias merges. One
  matching family has no deposited PDF URL.
- `all_pdf_links.txt`: all 57,604 unique deposited PDF links, including papers
  with no metadata match. This is the broadest fallback for later full-text
  screening and avoids silently excluding papers whose methods are not in
  their abstracts.
- `all_paper_families.csv` / `.jsonl`: all 45,635 DOI families and their screening
  results, including nonmatches.
- `all_doi_records.jsonl`: all 57,658 individual DOI records before version
  grouping, including provenance and original deposited links.
- `missing_pdf_links.jsonl`: the 53 records lacking a deposited PDF link,
  with their DOI and landing-page URLs. No PDF URLs were fabricated.
- `raw_crossref/`: 59 compressed API responses, including the final empty page.
- `harvest_manifest.json` / `catalogue_manifest.json`: exact retrieval counts,
  filters and screening regexes.

The 57,604 unique URLs correspond to 57,605 DOI records with links; one URL is
shared by two records. Counts refer to DOI records and conservative families,
not an independently verified count of unique scientific studies.

## Screening and deduplication

The collection source is the [Crossref REST API](https://api.crossref.org/prefixes/10.26434/works).
The exact filter is `type:posted-content,until-pub-date:2026-10-21`. Cursor
pagination requested 1,000 records per page until an empty page was returned.
Retrieved counts match the API total, and DOI uniqueness was checked. This
does not establish that every item hosted by ChemRxiv has a current Crossref
deposit, or include later/backdated deposits that arrived after collection.

Each version's title and abstract was screened for:

1. Pipetting, liquid handling, serial dilution, aliquoting, dispensing and
   aspiration.
2. Microplates, microwells, microtiter plates, well plates and plate readers.
3. Assays, bioassays, immunoassays, enzyme activity, cell viability and protein
   quantification, plus named methods such as Bradford, ELISA and resazurin.
4. Broader experimental methods, including high-throughput screening,
   sample preparation, automated synthesis and reaction optimization.
5. Readout terms such as colorimetry or absorbance, included only when the
   same metadata also contains method, measurement, detection or related context.

The exact expressions are preserved in `build_catalogue.py` and the manifest.
Matching occurs on any version in a family, so a family can remain included
when relevant terms disappear from the latest abstract. An evidence excerpt
contains at most 20 words and is not an extracted experimental procedure.

Version suffixes `.vN`, `/vN` and `-vN` are stripped to form DOI families. Within
each family, the highest numbered version is selected, using posted date as a
tie-breaker. The complete version list is retained. Three additional alias
families were grouped only where normalized titles and complete ordered
author lists were identical. **507 DOI families share normalized titles**;
other potential duplicates remain flagged because author metadata or identity
differs. Different titles may also refer to the same work. No fuzzy merging
was used to discard uncertain matches.

Metadata matching is deliberately inclusive. A paper can discuss an assay
without providing a reusable protocol, and a review or environmental analysis
can mention liquid handling. Conversely, full-text-only and supplement-only
methods will be missed by the candidate filter. The workbook flags titles
suggesting a review or analysis and retains nonmatching papers in the complete
catalogue for later screening. No result is labeled as an experimentally
validated CubOS protocol.

## PDF download outcome

Three independent requests to deposited ChemRxiv PDF URLs returned **HTTP 403**.
The downloader then stopped requests to that host and recorded the remaining
2,624 latest-candidate URLs as **not attempted after host access denial**.
**No PDFs were downloaded.** These are retrieval results, not a claim that the
links are broken or that a person cannot download them in a normal browser.

`pdf_download_status.jsonl` records each attempted or skipped link, and
`pdf_download_manifest.json` summarizes the result. The earlier legacy Engage
API probe also returned 403, and one original Figshare article lookup returned
404. No authentication, CAPTCHA or access-control bypass was attempted.

## Valency status after collection

The original collection used Crossref while Valency authentication was still
unverified. On October 22, an actual Valency `list_sources` call succeeded and
returned nine enabled sources, including ChemRxiv. Valency provides search
access; ChemRxiv still denied automated PDF downloads. The historical download
manifest describes that earlier attempt, not the separately supplied paper ZIP.
No credentials or OAuth state are included in this repository.

Full record and family exports are committed as compressed `.gz` files. The
uncompressed versions and raw API cache are local generated data; the scripts
below can reproduce them. `gzip -dk filename.gz` expands a chosen export.

## Reproduce

The collection and normalization scripts use Python's standard library and
`curl`. They do not need a research-service API key:

```bash
python3 collect_crossref.py
python3 build_catalogue.py
python3 download_pdfs.py
```

`collect_crossref.py` reuses saved pages. To collect a new snapshot, use a new
output directory, update the cutoff and retain the previous snapshot. It does
not silently refresh saved pages. The downloader checks PDF signatures and
stops after three access denials per host. Running it again retries blocked
links; do so only when legitimate access conditions have changed.

The workbook builder uses the bundled `@oai/artifact-tool` dependency. The
JSONL and CSV data exports are independently usable without that dependency.
PDF hyperlinks in the workbook open remote sources; downloaded PDF status
is documented above rather than implied by link presence.
