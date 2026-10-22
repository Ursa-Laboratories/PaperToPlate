# Research outputs

## Three new assay extractions

Start with `three-assay-review/review-pack/three-new-protocols.pdf`, or open
`three-assay-review/review-pack/index.html` locally. Original paper PDFs,
source-page images and structured JSON are alongside it. The extracted
procedures retain missing values and contradictions and are not hardware-ready
protocols.

The report builders use the selected PDFs, extracted page text, inventory and
the app's font assets. To rebuild, use a separate environment with `pypdf`,
`reportlab` and `Pillow` installed, then run:

```bash
python three-assay-review/build_review.py
python three-assay-review/render_review_pdf.py
```

The inventory contains metadata for the 100 supplied PDFs. Only the three
CC-BY originals supporting this review are redistributed.

## ChemRxiv catalogue

`chemrxiv/ChemRxiv-workflow-catalogue.xlsx` is the filterable candidate workbook.
`workflow_candidates_deduplicated.csv` is the equivalent tabular export.
`workflow_pdf_links.txt` contains 3,344 candidate-family links across versions;
`all_pdf_links.txt` contains 57,604 links across the snapshot. Links are not
guarantees of downloadable PDFs or complete methods.

Full record/family exports are included as `.gz` files to keep the repository
manageable. Use `gzip -dk filename.gz` to unpack one locally. The large
uncompressed files are ignored by Git. The collection and screening scripts
reproduce the raw API cache and exports; see the catalogue README.

## Instrument Scraper extraction

`instrument-scraper/` contains the earlier 16-paper shortlist, nine method
drafts, benchmark-case drafts, source evidence and coverage reports. Historical
local-data paths in these reports describe the original inspection and do not
imply that the corresponding bulk files are redistributed here.
