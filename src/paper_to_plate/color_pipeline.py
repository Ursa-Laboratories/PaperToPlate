"""A focused live-literature entry point for the three-stock color screen."""
import hashlib
import io

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import Field
from pypdf import PdfReader

from . import design_api, station, store
from .experiment_design import MixtureSettings, compile_design
from .models import StrictModel
from .preparation import apply_stock_preparations
from .validation import validate
from . import pipeline, llm

router = APIRouter(prefix='/api/color', tags=['Color matching'])
PAPER_ID = '2310.00510'
PAPER_PDF = 'https://arxiv.org/pdf/2310.00510v1'


class ColorResearch(StrictModel):
    goal: str = Field(default='I have red, yellow and blue aqueous dye stocks. Find a liquid-handling method to sample their mixture space and identify the closest observed mixture to my target green.', min_length=10,max_length=4000)
    target_hex: str = Field(default='#4a956f',pattern=r'^#[0-9a-fA-F]{6}$')
    red_stock: str = Field(default='Prepared red aqueous dye, used as loaded',min_length=1,max_length=400)
    yellow_stock: str = Field(default='Prepared yellow aqueous dye, used as loaded',min_length=1,max_length=400)
    blue_stock: str = Field(default='Prepared blue aqueous dye, used as loaded',min_length=1,max_length=400)
    stock_load_ul: float = Field(default=1500,ge=300,le=5000)
    blocks: int = Field(default=1,ge=1,le=2)
    source_height_mm: float = Field(ge=-100,le=0,allow_inf_nan=False)
    start_row: str = Field(default="A",pattern=r"^[A-H]$")
    excluded_tips: list[str] = Field(default_factory=list,max_length=96)
    fluid_state_id: int | None = Field(default=None,ge=1)
    first_tip: str = Field(default='A1',pattern=r'^[A-H](?:[1-9]|1[0-2])$')


async def retrieve_paper(design):
    paper = next((p for p in design['bond']['result'].get('papers',[]) if str(p.get('id','')).startswith(PAPER_ID)),None)
    if not paper:
        raise ValueError('Bond returned literature leads but not the reviewed liquid-dye benchmark. Inspect the results before choosing an executable method.')
    # The retrieved ID selects a fixed reviewed public source, never an arbitrary URL.
    async with httpx.AsyncClient(timeout=45,trust_env=False,follow_redirects=True) as client:
        async with client.stream('GET',PAPER_PDF) as response:
            response.raise_for_status()
            chunks=[]; size=0
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>20*1024*1024:
                    raise ValueError('Source PDF exceeds 20 MB.')
                chunks.append(chunk)
    content=b''.join(chunks)
    if not content.startswith(b'%PDF'):
        raise ValueError('The paper host did not return a PDF; no full-text source was claimed.')
    pdf=PdfReader(io.BytesIO(content))
    if len(pdf.pages)>100:
        raise ValueError('Source PDF exceeds 100 pages.')
    pages=[{'page':i+1,'text':p.extract_text() or ''} for i,p in enumerate(pdf.pages)]
    path=store.folder('design_sources')/(design['id']+'.pdf')
    path.write_bytes(content)
    return {'paper_id':paper['id'],'title':paper['title'],'url':paper['url'],
        'pdf_source':PAPER_PDF,'file_path':'design_sources/'+path.name,'sha256':hashlib.sha256(content).hexdigest(),
        'pages':pages,'page_count':len(pages), 'method_sections':['2.1 Application','2.4 Image Processing','2.5 Color Picking Solvers'],
        'adaptation':'The source uses CMYK dyes and iterative solvers. This first RYB screen uses vertices, edge mixtures, repeated center and a blank; its volumes are local design choices.'}


@router.post('/research',status_code=201)
async def research(body:ColorResearch):
    try:
        setup=await station.import_setup()
        setup['excluded_tips']=body.excluded_tips
        store.save('setups',setup)
        if body.fluid_state_id:
            setup['station_fluid_state_id']=body.fluid_state_id
            store.save('setups',setup)
        settings=MixtureSettings(target_hex=body.target_hex,blocks=body.blocks,first_tip=body.first_tip,start_row=body.start_row,source_height_mm=body.source_height_mm)
        design=await design_api.create(design_api.DesignInput(goal=body.goal,setup_id=setup['id'],kind='color_mixture',evidence_mode='live',settings=settings))
        design['declared_stocks']=body.model_dump()
        try:
            design['paper_document']=await retrieve_paper(design)
        except (httpx.HTTPError,ValueError) as exc:
            design['blockers'].append(str(exc) if isinstance(exc,ValueError) else 'The selected full paper could not be downloaded. Retry source retrieval before creating the run.')
        return store.save('designs',design)
    except (httpx.HTTPError,ValueError,KeyError) as exc:
        raise HTTPException(409, str(exc) if isinstance(exc,ValueError) else 'Could not read the station setup or complete live research.') from exc


@router.get('/{design_id}/paper')
def paper(design_id:str):
    value=design_api.get_design(design_id)
    doc=value.get('paper_document')
    if not doc:
        raise HTTPException(404,'No full paper downloaded.')
    return FileResponse(store.folder('design_sources')/(design_id+'.pdf'),media_type='application/pdf',filename='color-matching-paper.pdf')


@router.post('/{design_id}/protocol',status_code=201)
async def protocol(design_id:str):
    design=design_api.get_design(design_id)
    if not design.get('paper_document') or design.get('blockers'):
        raise HTTPException(409,'Resolve source/design blockers before creating the protocol.')
    declared=design['declared_stocks']
    setup=store.get('setups',design['setup_id'])
    proposed, compiled, prepared=compile_design(MixtureSettings.model_validate(design['settings']),setup,design['design'])
    stocks=proposed['stock_preparations']
    for spec,color in zip(stocks,('red','yellow','blue','water')):
        spec['load_volume_ul']=declared['stock_load_ul']
        if color!='water':
            spec['concentration']=declared[color+'_stock']
            spec['preparation']=f"Load {declared['stock_load_ul']/1000:g} mL of this same prepared {color} stock: {declared[color+'_stock']}."
    try:
        prepared=apply_stock_preparations(stocks,prepared,compiled['protocol_yaml'])
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    run=await design_api.protocol(design_id)
    run['plan']['stock_preparations']=stocks
    run['setup_snapshot']=prepared
    run['validation']=await validate(run['setup_snapshot'],run['protocol_yaml'])
    run['recording_recommended']=True
    run['color_design_id']=design_id
    run['execution_summary']=['Prepare the three single-color references.','Mix the three binary blends and three center repeats.','Add the water blank.','Pipette-mix each well; photograph the finished plate.']
    source=store.get('papers',run['paper_id'])
    doc=design['paper_document']
    source['pages'] += [{'page':i+2,'text':p['text'],'document':'retrieved_paper','original_page':p['page']} for i,p in enumerate(doc['pages'])]
    source.update(page_count=len(source['pages']),characters=sum(len(p['text']) for p in source['pages']),file_path=doc['file_path'],source_url=doc['url'])
    store.save('papers',source)
    try:
        review, usage = await pipeline.review_run(source,run['setup_snapshot'],run)
        run.update(review=review,review_hash=run['protocol_hash'])
        run.setdefault('usage',[]).append({'stage':'review',**usage})
    except llm.ModelError as exc:
        run['error']=str(exc)
    run['status']=pipeline.readiness(run)
    design['latest_run_id']=run['id']
    store.save('designs',design)
    return store.save('runs',run)
