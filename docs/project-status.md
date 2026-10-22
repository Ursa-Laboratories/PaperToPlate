# Project status

Snapshot: October 22, 2026.

The local prototype supports PDF/text upload, page-linked AI extraction,
typed protocol generation, separate model review, native CubOS offline
validation, transparent scoring, manual video alignment, independent Bradford
ratio analysis and operator-controlled CubOS handoff. Hosted Ollama access was
tested using a private local configuration. No key is included in this repo.

The previous build passed 21 application tests and a production frontend build.
A real RotiQuant source completed the model pipeline in 16.23 seconds with native
validation passing. The AI reviewer made false-positive claims; its findings
remain visible and a revision-bound human review can resolve them. These are
software checks, not scientific or hardware validation.

The native Bradford package contains separate 1:10 stock-dilution and assay
preparation protocols for three unknowns in triplicate, plus water commissioning
drafts. Six offline tests passed in a compatible installed CubOS environment.
The supplied deck and gantry snapshots remain physically unverified.

Three new papers were selected from a user-provided 100-PDF collection: peroxide
quantification, chloride transport and nucleoside-kinase activity. Their review
pack contains 28 page-linked steps, source excerpts, source images, JSON, PDF and
HTML reports. Each excerpt was checked against its cited source; original PDF
hashes match. Missing values and source conflicts remain explicit. These extracts
have not been compiled into runnable CubOS protocols.

The ChemRxiv catalogue was harvested from Crossref and contains 57,658 DOI
records, 2,625 conservatively deduplicated candidates and 57,604 PDF URLs.
Metadata screening does not verify that every candidate has a usable pipetting
recipe. Valency's `list_sources` later succeeded with nine enabled sources,
including ChemRxiv. Search access did not remove direct PDF access restrictions.

Still required for a physical benchmark: independent scientific review, an
approved assay and readout, actual station connectivity, calibrated positions
and liquid heights, supervised volume checks, a reference assay, repeated
measurements and synchronized run/video/reader evidence. No hardware has been
operated by this work.

Publication excludes `.env`, private document URLs in default app settings,
runtime uploads/model outputs, logs, dependency environments and the bulk PDF
collections. The three CC-BY papers supporting the new extraction review are
included with attribution. Generated full catalogue exports are compressed;
raw API response caches can be regenerated with the collection script.
