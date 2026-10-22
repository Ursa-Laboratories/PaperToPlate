from pathlib import Path
import json, zipfile
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'review-pack'
data=json.loads((OUT/'protocols.json').read_text())
for name in ['DM','DM-Semibold']:
    pdfmetrics.registerFont(TTFont(name,str(OUT/'assets/dm-sans.ttf')))
blue=colors.HexColor('#233C78');ink=colors.HexColor('#172137');muted=colors.HexColor('#58657A')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyDM',fontName='DM',fontSize=9.5,leading=14,textColor=ink,spaceAfter=7))
styles.add(ParagraphStyle(name='SmallDM',parent=styles['BodyDM'],fontSize=8,leading=11,textColor=muted,spaceAfter=5))
styles.add(ParagraphStyle(name='TitleDM',fontName='DM-Semibold',fontSize=30,leading=34,textColor=blue,spaceAfter=16))
styles.add(ParagraphStyle(name='H2DM',fontName='DM-Semibold',fontSize=15,leading=19,textColor=blue,spaceBefore=17,spaceAfter=9,keepWithNext=True))
styles.add(ParagraphStyle(name='H3DM',fontName='DM-Semibold',fontSize=10.5,leading=14,textColor=ink,spaceBefore=9,spaceAfter=5,keepWithNext=True))
styles.add(ParagraphStyle(name='QuoteDM',fontName='DM',fontSize=8,leading=11,textColor=muted,leftIndent=9,borderColor=colors.HexColor('#D7E1F2'),borderWidth=0.5,borderPadding=6,spaceBefore=2,spaceAfter=10))
translate=str.maketrans({'₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9','→':'to','−':'-','–':'-','—':'-','’':"'",'“':'"','”':'"','µ':'u','μ':'u','↗':''})
def text(s):return escape(str(s).translate(translate))
def P(s,style='BodyDM'):return Paragraph(text(s),styles[style])
def table(rows,widths,header=False):
    cells=[[P(cell,'SmallDM') for cell in row] for row in rows]
    t=Table(cells,colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
    config=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),0.4,colors.HexColor('#D5DAE0'))]
    if header:config.append(('BACKGROUND',(0,0),(-1,0),colors.HexColor('#D7E1F2')))
    t.setStyle(TableStyle(config));return t
path=OUT/'three-new-protocols.pdf'
doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=47,bottomMargin=47,title='Three new assay protocols - source extraction review',author='Paper to Plate',pageCompression=1)
story=[]
for index,p in enumerate(data['protocols'],1):
    if index>1:story.append(PageBreak())
    story.extend([P('PAPER TO PLATE / EXTRACTION %02d OF 03'%index,'SmallDM'),P(p['short_title'],'TitleDM'),P(p['paper_title']),P('Source: '+p['doi']+' | '+str(p['source_page_count'])+' PDF pages','SmallDM'),P('All page citations count from the first PDF page, including its cover.','SmallDM'),Spacer(1,7),table([p['summary']],[126.8]*4),Spacer(1,9),P('Extracted scope','H2DM'),P(p['scope']),P('Status: source extraction for review. Unresolved details are retained. No physical run or executable CubOS file is claimed.','SmallDM'),P('Materials and starting conditions','H2DM'),table([['Input','Reported conditions / unresolved details','PDF p.']]+p['materials'],[108,359,40],True),P('Ordered procedure','H2DM')])
    for s in p['steps']:
        pages=', '.join(str(n) for n in s['source_pages'])
        story.append(KeepTogether([P(s['id']+'  '+s['title'],'H3DM'),P(s['procedure']),P('Source: PDF page(s) '+pages+' | '+s['evidence_status'].replace('_',' '),'SmallDM'),P('Source excerpt: '+s['source_quote'],'QuoteDM')]))
    story.extend([P('Derived arithmetic - separate from source instructions','H2DM'),table([[r[0],r[1]+' '+r[2]] for r in p['derived']],[117,390]),P('Details to resolve before execution','H2DM')])
    for issue in p['issues']:
        story.extend([P(issue['title'],'H3DM'),P(issue['detail']),P('Source: PDF page(s) '+', '.join(str(x) for x in issue['source_pages']),'SmallDM')])
    story.extend([Spacer(1,9),P('Original file: '+p['filename'],'SmallDM'),P('Source SHA-256: '+p['source_sha256'],'SmallDM')])
story.extend([PageBreak(),P('Extraction record','TitleDM'),P(data['method']),P(data['screening']),P('The 28 source excerpts were checked against the text extracted from the cited PDF pages. Key Methods pages were visually inspected to verify numbers and units, including a missing volume prefix and conflicting concentration labels.'),P('Reported values, conditional interpretations, derived arithmetic and unresolved details are distinguished. A matching excerpt establishes traceability; it does not establish scientific validity.'),P('The review pack includes this PDF, an HTML review with source-page images, three individual protocol JSON files, a combined JSON file, the exact three original PDFs and verification.json.'),P('No original download or previously created protocol was overwritten. The original 100-paper ZIP and extracted collection remain available.'),P('For the HTML version, open index.html from the same review-pack folder.','SmallDM')])
def footer(c,doc):
    c.saveState();w,h=A4
    c.setStrokeColor(colors.HexColor('#CBD3DE'));c.line(44,33,w-44,33)
    c.setFont('DM',8);c.setFillColor(muted)
    c.drawString(44,20,'Paper to Plate | Source extraction review | 22 October 2026')
    c.drawRightString(w-44,20,str(doc.page));c.restoreState()
doc.build(story,onFirstPage=footer,onLaterPages=footer)
with zipfile.ZipFile(ROOT/'three-new-assay-protocols.zip','w',zipfile.ZIP_DEFLATED) as z:
    for file in sorted(OUT.rglob('*')):
        if file.is_file():z.write(file,arcname='three-new-assay-protocols/'+str(file.relative_to(OUT)))
print(path)
