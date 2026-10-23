import hashlib
from copy import deepcopy
import httpx
import pytest
from fastapi.testclient import TestClient
from paper_to_plate import exploration,store
from paper_to_plate.app import app
from paper_to_plate.models import HandoffInput
from paper_to_plate.handoff import submission

STOCKS=[{'color':c,'position':f'10_vial_holder.A{i+1}','description':c+' stock'} for i,c in enumerate(exploration.COLORS)]

@pytest.mark.asyncio
async def test_discovery_preserves_sources_and_does_not_generate_protocol(workspace,monkeypatch):
    calls=[]
    papers=[{'id':'2310.00510','title':'Color benchmark','url':'https://arxiv.org/abs/2310.00510','abstract':'Liquid dye camera mixtures','source':'arxiv'}, {'id':'led','title':'LED experiment','url':'https://example.org/paper','abstract':'LEDs and a light sensor','source':'journal'}]
    async def search(q):calls.append(q);return {'mode':'live','query':q,'result':{'papers':papers},'retrieved_at':1}
    async def model(*args,**kwargs):return {'answer':'Two approaches to compare.','ideas':[{'paper_id':'led','summary':'Uses light sources.','experiment_title':'Light mixing','experiment':'Compare sources.','steps':['Mix LED intensities.'],'readout':'Light sensor','extra_materials':['LEDs'],'fit':'needs_equipment'},{'paper_id':'invented','summary':'Fake','experiment_title':'Fake','experiment':'Fake','steps':['Fake'],'readout':'Fake','extra_materials':[],'fit':'fits_stocks'}]}, {'model':'fixture'}
    monkeypatch.setattr(exploration.bond,'search',search);monkeypatch.setattr(exploration.llm,'complete',model)
    before=len(store.list_all('runs'))
    result=await exploration.research(exploration.Question(question='What can these stocks tell us?',stocks=STOCKS))
    assert len(calls)==2 and len(result['papers'])==2 and len(store.list_all('runs'))==before
    assert result['selected'] is None and result['papers'][0]['supported_method']
    assert result['papers'][1]['extra_materials']==['LEDs'] and not result['papers'][1]['can_prepare']
    assert all(p['id']!='invented' for p in result['papers'])

@pytest.mark.asyncio
async def test_abstract_only_selection_cannot_compile(workspace):
    p=exploration.paper_card({'id':'led','title':'LED','url':'https://example.org','abstract':'lights'})
    value=store.create('explorations',papers=[p],selected=None)
    selected=await exploration.select(value['id'],exploration.Selection(paper_id='led'))
    assert selected['selected']['status']=='methods_needed'
    from paper_to_plate.experiment_design import MixtureSettings
    with pytest.raises(Exception) as e:await exploration.prepare(value['id'],exploration.Prepare(settings=MixtureSettings()))
    assert e.value.status_code==409

@pytest.mark.asyncio
async def test_offline_deck_is_labeled_recorded_not_live(workspace,setup,monkeypatch):
    async def preview(s):return {'labware':[{'key':'plate','positions':{'A1':{'x':10,'y':80,'z':42}}}]}
    monkeypatch.setattr(exploration,'saved_setup',lambda:setup);monkeypatch.setattr(exploration,'native_preview',preview)
    original=httpx.AsyncClient
    def fail(req):raise httpx.ConnectError('offline',request=req)
    monkeypatch.setattr(exploration.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(fail)))
    view=await exploration.deck_view()
    assert view['mode']=='recorded' and not view['station']['connected'] and view['inventory_id'] is None
    assert view['containers']==[] and view['tips']==[]


def test_water_is_required_and_recorded_setup_cannot_run_hardware(workspace,setup):
    with TestClient(app) as c:
        response=c.post('/api/explore/research',json={'question':'What can I test?','stocks':[STOCKS[0]]*4})
        assert response.status_code==400
    from paper_to_plate.compiler import compile_plan
    compiled=compile_plan({'title':'fixture','summary':'fixture','operations':[{'action':'transfer','source':'10_vial_holder.A1','destinations':['plate.A1'],'volume_ul':60,'purpose':'test'}]},setup)
    run={'id':'fixture',**compiled,'validation_hash':compiled['protocol_hash'],'validation':{'passed':True},'requires_station_refresh':True}
    with pytest.raises(ValueError,match='recorded setup'):
        submission(run,HandoffInput(mock_mode=False,expected_hash=compiled['protocol_hash']))


def test_bounded_recipe_checks_reject_changed_well_totals(setup):
    from paper_to_plate.experiment_design import MixtureSettings,compile_design,design_mixtures
    import yaml
    settings=MixtureSettings();_,compiled,_=compile_design(settings,setup,design_mixtures(settings))
    selected={'paper_id':'2310.00510','paper':{'supported_method':True},'source':{'sha256':'a'*64,'pages':[{'text':'method'}]}}
    assert not exploration.recipe_checks(selected,settings,compiled,{'passed':True})['findings']
    commands=yaml.safe_load(compiled['protocol_yaml']);commands['protocol'][1]['transfer']['volume_ul']=5
    compiled['protocol_yaml']=yaml.safe_dump(commands)
    assert exploration.recipe_checks(selected,settings,compiled,{'passed':True})['verdict']=='changes_required'


def test_recipe_checks_reject_wrong_stock_even_when_total_is_unchanged(setup):
    import yaml
    from paper_to_plate.experiment_design import MixtureSettings,compile_design,design_mixtures
    settings=MixtureSettings();_,compiled,_=compile_design(settings,setup,design_mixtures(settings))
    selected={'paper_id':'2310.00510','paper':{'supported_method':True},'source':{'sha256':'a'*64,'pages':[{'text':'method'}]}}
    commands=yaml.safe_load(compiled['protocol_yaml']);commands['protocol'][1]['transfer']['source']='10_vial_holder.B5'
    compiled['protocol_yaml']=yaml.safe_dump(commands)
    assert exploration.recipe_checks(selected,settings,compiled,{'passed':True})['verdict']=='changes_required'


@pytest.mark.asyncio
async def test_larger_design_preserves_the_operator_working_reserve(workspace,setup,monkeypatch):
    from paper_to_plate.experiment_design import MixtureSettings
    async def valid(*a):return {'passed':True,'errors':[]}
    monkeypatch.setattr(exploration,'validate',valid)
    selected={'status':'proposed','paper_id':'2310.00510','paper':{'supported_method':True,'title':'Fixture method','url':'https://arxiv.org/abs/2310.00510'},'depth_known':True,'setup':setup,'deck_mode':'recorded','proposal':{'title':'Larger fixture'},'source':{'page_count':1,'sha256':'a'*64,'pages':[{'page':1,'text':'Synthetic source fixture'}],'file_path':'fixture.pdf'}}
    value=store.create('explorations',question='Fixture question',stocks=STOCKS,selected=selected,usage=[])
    run=await exploration.prepare(value['id'],exploration.Prepare(settings=MixtureSettings(blocks=2)))
    loads={s['material']:s['load_volume_ul'] for s in run['plan']['stock_preparations']}
    assert loads['water']==2200 and loads['red working dye']==1700
    assert run['requires_station_refresh'] and not run.get('handoff')
