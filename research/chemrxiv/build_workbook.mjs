import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.dirname(fileURLToPath(import.meta.url));
const rows = (await fs.readFile(path.join(root, 'workflow_candidates_deduplicated.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
const stats = JSON.parse(await fs.readFile(path.join(root, 'catalogue_manifest.json'), 'utf8'));
const wb = Workbook.create();
const sheet = wb.worksheets.add('Workflow candidates');
const coverage = wb.worksheets.add('Coverage and method');
sheet.showGridLines = false;
coverage.showGridLines = false;
const columns = ['Paper title', 'Metadata evidence', 'Posted date', 'PDF', 'DOI', 'Matched terms', 'Evidence excerpt', 'First author', 'Other title clue', 'DOI records in group', 'PDF URL', 'Source metadata'];
sheet.getRangeByIndexes(0, 0, 1, columns.length).values = [columns];
const safe = value => typeof value === 'string' && /^[=+@-]/.test(value) ? `'${value}` : value;
const dateSerial = value => /^\d{4}-\d{2}-\d{2}$/.test(value) ? (Date.parse(value + 'T00:00:00Z') - Date.UTC(1899, 11, 30)) / 86400000 : value;
const values = rows.map(r => [r.title,
  r.screening_band === 'Assay / liquid-handling metadata match' ? 'Assay / liquid handling' : r.screening_band === 'Earlier-version metadata match' ? 'Earlier version only' : 'Broader experimental method',
  dateSerial(r.published_date), r.pdf_url ? 'PDF' : 'Missing', r.doi, r.matched_terms.join('; '), r.evidence_excerpt,
  r.authors[0] || '', r.review_or_analysis_title ? 'Review / analysis title' : '',
  r.all_version_dois.length, r.pdf_url || 'No deposited PDF link', r.crossref_record_url].map(safe));
sheet.getRangeByIndexes(1, 0, rows.length, columns.length).values = values;
sheet.getRange(`A1:L${rows.length + 1}`).format.font = { name: 'Arial', size: 10, color: '#202C39' };
sheet.getRange(`A2:L${rows.length + 1}`).format.wrapText = true;
sheet.getRange(`A2:L${rows.length + 1}`).format.verticalAlignment = 'center';
sheet.getRange('A1:L1').format = { fill: '#233C50', font: {name:'Arial',size:10,bold:true,color:'#FFFFFF'}, wrapText:true, horizontalAlignment:'center', verticalAlignment:'center', rowHeight:32 };
const widths = [73, 28, 12, 8, 43, 38, 72, 25, 24, 17, 80, 80];
for(let c=0;c<widths.length;c++) sheet.getRangeByIndexes(0,c,rows.length+1,1).format.columnWidth=widths[c];
sheet.getRange(`C2:C${rows.length+1}`).setNumberFormat('yyyy-mm-dd');
sheet.getRange(`D2:D${rows.length+1}`).format.font.color='#1268B3';
sheet.getRange(`J2:J${rows.length+1}`).setNumberFormat('0');
for(let i=0;i<values.length;i++) {
  const maxLines = Math.max(...values[i].map((v,c)=>Math.ceil(String(v).length / (widths[c] * 0.95))));
  sheet.getRangeByIndexes(i+1,0,1,columns.length).format.rowHeight=Math.max(42, maxLines*15+8);
}
sheet.tables.add(`A1:L${rows.length+1}`,true,'ChemRxivWorkflowCandidates');
sheet.freezePanes.freezeRows(1);
sheet.freezePanes.freezeColumns(1);
sheet.tabColor='#233C50';

const notes = [
 ['ChemRxiv workflow catalogue', 'Snapshot: 2026-10-21'],
 ['Evidence level', 'Metadata screening only. Methods and supporting information have not been verified.'],
 ['Retrieved DOI records', stats.chemrxiv_doi_records],
 ['Crossref reported DOI records', stats.raw_records],
 ['DOI families after version grouping', stats.doi_families],
 ['Direct assay/liquid-handling matching families', stats.direct_assay_or_liquid_handling_families],
 ['All matching DOI families', stats.workflow_candidate_families],
 ['Candidate entries after exact-title/author grouping', stats.deduplicated_workflow_candidates],
 ['Candidate PDF links, all versions', stats.workflow_pdf_urls_all_versions],
 ['All corpus PDF links', stats.all_pdf_urls],
 ['DOI records missing deposited PDF links', stats.records_missing_pdf_url],
 ['DOI records missing abstracts', stats.records_missing_abstract],
 ['DOI families with a repeated normalized title', stats.families_with_duplicate_title],
 ['Collection source', 'https://api.crossref.org/prefixes/10.26434/works'],
 ['Date filter', 'type:posted-content,until-pub-date:2026-10-21'],
 ['Version grouping', 'Strip terminal .vN, /vN or -vN. Preserve every DOI and PDF link in the exports.'],
 ['Migration-alias grouping', 'Group only exact normalized titles with identical complete ordered author lists. Three additional families grouped.'],
 ['Remaining duplicates', '507 DOI families share normalized titles. Different author metadata may prevent safe merging; inspect flagged entries.'],
 ['Direct matches', 'Assay/bioassay terms, named assays, pipetting/liquid handling, or plate/reader terminology in any version title or abstract.'],
 ['Broader matches', 'Experimental screening/sample preparation terms, or readout terms together with method/measurement context.'],
 ['Not a completeness claim for protocols', 'Full-text-only or supplement-only workflows can be missed. Broad matches can describe reviews, devices or analyses rather than runnable protocols.'],
 ['PDF access', '3 ChemRxiv requests returned HTTP 403. Further requests to the host were skipped. No PDFs downloaded.'],
 ['Valency connection', 'Configured at https://mcp.valency.io/; OAuth failed because the callback omitted required issuer https://oauth.valency.io. No list_sources verification.'],
 ['Companion exports', 'workflow_candidates_deduplicated.csv; all_paper_families.csv; all_doi_records.jsonl; workflow_pdf_links.txt; all_pdf_links.txt'],
 ['Reproducibility', 'Raw paginated responses, exact regex rules, collection scripts and retrieval manifests accompany the catalogue.'],
];
coverage.getRangeByIndexes(0,0,notes.length,2).values=notes;
coverage.getRange(`A1:B${notes.length}`).format.font={name:'Arial',size:11,color:'#202C39'};
coverage.getRange(`A1:A${notes.length}`).format.columnWidth=53;
coverage.getRange(`B1:B${notes.length}`).format.columnWidth=110;
coverage.getRange(`A1:B${notes.length}`).format.wrapText=true;
coverage.getRange(`A1:B${notes.length}`).format.verticalAlignment='center';
coverage.getRange('A1:B1').format.font={name:'Arial',size:15,bold:true,color:'#233C50'};
for(let i=0;i<notes.length;i++) coverage.getRangeByIndexes(i,0,1,2).format.rowHeight=Math.max(30,Math.ceil(String(notes[i][1]).length/115)*16+10);
coverage.getRange('B3:B13').setNumberFormat('#,##0');
coverage.tabColor='#A9B8C3';
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Workflow candidates!A1:F4',include:'values,formulas',tableMaxRows:4,tableMaxCols:6,maxChars:2200})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#SPILL!',options:{useRegex:true,maxResults:10},maxChars:1500})).ndjson);
for(const [name,range,file] of [['Workflow candidates','A1:D8','preview_candidates.png'],['Coverage and method','A1:B13','preview_coverage.png']]) {
 const preview=await wb.render({sheetName:name,range,scale:1.3,format:'png'});
 await fs.writeFile(path.join(root,file),new Uint8Array(await preview.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(root,'ChemRxiv-workflow-catalogue.xlsx'));
// Artifact Tool's formula engine does not implement HYPERLINK. Add native
// XLSX hyperlink relationships after authoring instead of shipping error caches.
console.log(execFileSync(process.env.PYTHON || 'python3', [path.join(root,'add_hyperlinks.py')], {encoding:'utf8'}));
console.log(`EXPORTED ${rows.length} candidate rows`);
