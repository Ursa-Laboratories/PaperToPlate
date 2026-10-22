"""Supply native PDF hyperlinks missing from Artifact Tool's formula engine."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
ET.register_namespace('', MAIN)
ET.register_namespace('r', REL)
target = ROOT / 'ChemRxiv-workflow-catalogue.xlsx'
rows = [json.loads(x) for x in (ROOT / 'workflow_candidates_deduplicated.jsonl').read_text().splitlines()]
with ZipFile(target) as archive:
    content = {name: archive.read(name) for name in archive.namelist()}
sheet = ET.fromstring(content['xl/worksheets/sheet1.xml'])
relpath = 'xl/worksheets/_rels/sheet1.xml.rels'
rels = ET.fromstring(content[relpath]) if relpath in content else ET.Element(f'{{{PKG}}}Relationships')
links = ET.Element(f'{{{MAIN}}}hyperlinks')
for rownum, row in enumerate(rows, 2):
    if not row['pdf_url']:
        continue
    ident = f'pdfLink{rownum}'
    ET.SubElement(links, f'{{{MAIN}}}hyperlink', {'ref':f'D{rownum}', f'{{{REL}}}id':ident})
    ET.SubElement(rels, f'{{{PKG}}}Relationship', {'Id':ident, 'Type':REL+'/hyperlink', 'Target':row['pdf_url'], 'TargetMode':'External'})
# Native spreadsheet schema places hyperlinks before page/print/drawing/table parts.
before = {'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
position = next((i for i,child in enumerate(sheet) if child.tag.split('}')[-1] in before),len(sheet))
sheet.insert(position,links)
content['xl/worksheets/sheet1.xml'] = ET.tostring(sheet,encoding='utf-8',xml_declaration=True)
content[relpath] = ET.tostring(rels,encoding='utf-8',xml_declaration=True)
temp=target.with_suffix('.tmp.xlsx')
with ZipFile(temp,'w',ZIP_DEFLATED) as archive:
    for name,data in content.items():archive.writestr(name,data)
with ZipFile(temp) as archive:
    assert archive.testzip() is None
    assert len(ET.fromstring(archive.read('xl/worksheets/sheet1.xml')).find(f'{{{MAIN}}}hyperlinks')) == sum(bool(x['pdf_url']) for x in rows)
temp.replace(target)
print(f'Verified {len(links)} native PDF hyperlinks')
