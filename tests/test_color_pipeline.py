import asyncio
import io
import json
import time
from copy import deepcopy

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from paper_to_plate import color_pipeline, run_recording, station, store
from paper_to_plate.app import app
from paper_to_plate.compiler import compile_plan
from paper_to_plate.models import HandoffInput


def mock_run(setup):
    plan={'title':'Water fixture','summary':'Test','operations':[{'action':'transfer','source':'10_vial_holder.B5','destinations':['plate.A1'],'volume_ul':100,'purpose':'Water'}]}
    compiled=compile_plan(plan,setup)
    return store.create('runs',title='Fixture',paper_id='bradford-notes',setup_id='picus120',setup_snapshot=setup,plan=plan,
        **compiled,validation={'passed':True},validation_hash=compiled['protocol_hash'])


def test_run_record_starts_before_submission_and_never_replays(workspace,setup,monkeypatch):
    import paper_to_plate.app as module
    run=mock_run(setup);calls=[]
    async def valid(*a):calls.append('validate');return {'passed':True}
    async def record(value,request,station_id):
        calls.append('record')
        meta={'id':'a'*32,'status':'recording','started_at':time.time(),'limit_seconds':10,'cubos_run_id':station_id,'station_url':'http://fixture'}
        store.update_run(value['id'],execution_recording=meta)
        return meta
    async def send(*a):calls.append('submit');return {'run_id':'fixture','state':'queued','mock_mode':True}
    monkeypatch.setattr(module,'validate',valid)
    monkeypatch.setattr(run_recording,'start',record)
    monkeypatch.setattr(run_recording,'watch',lambda key:calls.append('watch'))
    monkeypatch.setattr(module.handoff,'send',send)
    with TestClient(app) as client:
        body={'expected_hash':run['protocol_hash'],'mock_mode':True,'record_execution':True}
        response=client.post(f"/api/runs/{run['id']}/handoff",json=body)
        assert response.status_code==200,response.text
        assert calls==['validate','record','watch','submit']
        assert client.post(f"/api/runs/{run['id']}/handoff",json=body).status_code==409


def test_failed_recording_blocks_hardware_submission(workspace,setup,monkeypatch):
    import paper_to_plate.app as module
    run=mock_run(setup);sent=[]
    async def valid(*a):return {'passed':True}
    async def record(*a):raise ValueError('Camera recording unavailable')
    async def send(*a):sent.append(True)
    monkeypatch.setattr(module,'validate',valid);monkeypatch.setattr(run_recording,'start',record);monkeypatch.setattr(module.handoff,'send',send)
    with TestClient(app) as client:
        response=client.post(f"/api/runs/{run['id']}/handoff",json={'expected_hash':run['protocol_hash'],'mock_mode':True,'record_execution':True})
        assert response.status_code==409
    assert not sent and not store.get('runs',run['id']).get('handoffs')


@pytest.mark.asyncio
async def test_observer_stops_recording_after_remote_terminal_event(workspace,setup,monkeypatch):
    run=mock_run(setup)
    store.update_run(run['id'],execution_recording={'id':'a'*32,'started_at':time.time(),'limit_seconds':30,'cubos_run_id':'station-run','station_url':'http://fixture','status':'recording'})
    requests=[]
    def handler(req):
        requests.append((req.method,req.url.path))
        if req.url.path.endswith('/stop'):return httpx.Response(200,json={'active':False})
        if req.url.path.endswith('/events'):return httpx.Response(200,json={'events':[{'sequence':1,'type':'step_completed','timestamp':123,'step_index':0}]})
        return httpx.Response(200,json={'state':'succeeded','started_at':120,'finished_at':124})
    original=httpx.AsyncClient
    monkeypatch.setattr(run_recording.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler)))
    await run_recording.observe(run['id'])
    final=store.get('runs',run['id'])['execution_recording']
    assert final['status']=='finished' and final['stop_reason']=='cubos_succeeded' and not final['active']
    assert ('POST','/recordings/'+'a'*32+'/stop') in requests
    rows=[json.loads(x) for x in (workspace/'execution_events'/f"{run['id']}.jsonl").read_text().splitlines()]
    assert rows[1]['event']['sequence']==1


@pytest.mark.asyncio
async def test_station_config_drift_prevents_handoff(setup,monkeypatch):
    setup=deepcopy(setup)
    setup['station_source']={'url':station.CUBOS_URL,'gantry_file':station.GANTRY_FILE,'deck_file':station.DECK_FILE,'gantry_sha256':'old','deck_sha256':'old'}
    original=httpx.AsyncClient
    monkeypatch.setattr(station.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'content':'changed config'}))))
    with pytest.raises(ValueError,match='changed'):
        await station.verify_setup({'setup_snapshot':setup})


@pytest.mark.asyncio
async def test_full_paper_retrieval_uses_retrieved_id_and_retains_digest(workspace,monkeypatch):
    writer=PdfWriter();writer.add_blank_page(width=300,height=300);output=io.BytesIO();writer.write(output)
    original=httpx.AsyncClient
    monkeypatch.setattr(color_pipeline.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=output.getvalue()))))
    design={'id':'paper-fixture','bond':{'result':{'papers':[{'id':'2310.00510v1','title':'Color matching','url':'https://arxiv.org/abs/2310.00510'}]}}}
    paper=await color_pipeline.retrieve_paper(design)
    assert paper['page_count']==1 and len(paper['sha256'])==64
    assert (workspace/paper['file_path']).read_bytes().startswith(b'%PDF')
    design['bond']['result']['papers']=[]
    with pytest.raises(ValueError,match='not the reviewed'):
        await color_pipeline.retrieve_paper(design)


def test_declared_loading_does_not_fit_silently(workspace):
    from paper_to_plate.experiment_design import MixtureSettings,design_mixtures,compile_design
    from paper_to_plate.preparation import apply_stock_preparations
    setup=store.get('setups','picus120')
    settings=MixtureSettings()
    plan,compiled,prepared=compile_design(settings,setup,design_mixtures(settings))
    for stock in plan['stock_preparations']:stock['load_volume_ul']=4500
    with pytest.raises(ValueError,match='4000'):
        apply_stock_preparations(plan['stock_preparations'],prepared,compiled['protocol_yaml'])


@pytest.mark.asyncio
async def test_final_camera_frame_is_attached_to_the_design(workspace,setup):
    run=mock_run(setup)
    design=store.create('designs',title='Camera fixture')
    store.update_run(run['id'],color_design_id=design['id'])
    def handler(req):
        if req.method=='POST':
            context=json.loads(req.content)['context']
            assert context['protocol_hash']==run['protocol_hash']
            return httpx.Response(200,json={'id':'a'*32,'context':context})
        return httpx.Response(200,content=b'jpeg-fixture')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await run_recording.capture_final(run['id'],client)
    final=store.get('designs',design['id'])['result_image']
    assert (workspace/'design_images'/final['id']).read_bytes()==b'jpeg-fixture'
    assert store.get('runs',run['id'])['final_plate_image']['id']==final['id']


def test_model_quotes_are_bounded_literal_excerpts():
    from paper_to_plate.design_api import Claim
    source=' '.join(['A sufficiently long experimental abstract describes colored liquid mixtures and camera measurements.']*5)
    claim=Claim(paper_id='paper',quote=source,implication='A proposed adaptation')
    assert len(claim.quote.split())<=16 and len(claim.quote)<=200
    assert source.startswith(claim.quote)


def test_confirmed_row_and_tip_are_used_without_touching_previous_wells(setup):
    from paper_to_plate.experiment_design import MixtureSettings, design_mixtures, compile_design
    settings=MixtureSettings(start_row='F',first_tip='C5')
    design=design_mixtures(settings)
    plan,compiled,prepared=compile_design(settings,setup,design)
    commands=yaml.safe_load(compiled['protocol_yaml'])['protocol']
    assert {s['transfer']['destination'] for s in commands if 'transfer' in s}=={f'plate.F{i}' for i in range(1,11)}
    assert [s['pick_up_tip']['position'] for s in commands if 'pick_up_tip' in s][0]=='tips.C5'
    assert [s['pick_up_tip']['position'] for s in commands if 'pick_up_tip' in s][-1]=='tips.E8'
    with pytest.raises(ValueError,match='exceed'):
        design_mixtures(MixtureSettings(start_row='H',blocks=2))


@pytest.mark.asyncio
async def test_live_inventory_blocks_occupied_destinations(setup,monkeypatch):
    import hashlib
    setup=deepcopy(setup)
    setup['station_fluid_state_id']=15
    setup['station_source']={'url':station.CUBOS_URL,'gantry_file':'g','deck_file':'d',
        'gantry_sha256':hashlib.sha256(b'g').hexdigest(),'deck_sha256':hashlib.sha256(b'd').hexdigest()}
    setup['fluids_yaml']='fluids:\n  10_vial_holder.B5:\n    volume_ul: 1500\n    composition: {water: 1500}\n'
    plan={'title':'fixture','summary':'fixture','operations':[{'action':'transfer','source':'10_vial_holder.B5','destinations':['plate.F1'],'volume_ul':100,'purpose':'test'}]}
    run={'setup_snapshot':setup,**compile_plan(plan,setup)}
    def handler(req):
        if '/configs/' in req.url.path:return httpx.Response(200,json={'content':req.url.path.split('/')[-2]})
        if req.url.path.endswith('/status'):return httpx.Response(200,json={'connected':True})
        return httpx.Response(200,json={'containers':[
            {'labware_key':'10_vial_holder','location_id':'B5','current_volume_ul':1500,'composition':{'water':1500}},
            {'labware_key':'plate','location_id':'F1','current_volume_ul':100,'composition':{'water':100}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(station.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError,match='occupied'):
        await station.verify_setup(run)


def test_unreachable_tips_can_be_excluded_without_changing_calibration(setup):
    from paper_to_plate.experiment_design import MixtureSettings,design_mixtures,compile_design
    setup=deepcopy(setup); original=setup['deck_yaml'];setup['excluded_tips']=['C12','D12']
    settings=MixtureSettings(start_row='F',first_tip='C5')
    _,compiled,prepared=compile_design(settings,setup,design_mixtures(settings))
    tips=[s['pick_up_tip']['position'] for s in yaml.safe_load(compiled['protocol_yaml'])['protocol'] if 'pick_up_tip' in s]
    assert len(tips)==28 and tips[0]=='tips.C5' and tips[-1]=='tips.E10'
    assert 'tips.C12' not in tips and 'tips.D12' not in tips
    assert prepared['deck_yaml']==original


def test_stock_depth_is_applied_to_every_source_but_not_plate_mixing(setup):
    from paper_to_plate.experiment_design import MixtureSettings,design_mixtures,compile_design
    setup=deepcopy(setup);setup['excluded_tips']=['C12','D12']
    settings=MixtureSettings(first_tip='C6',source_height_mm=-40)
    plan,compiled,_=compile_design(settings,setup,design_mixtures(settings))
    steps=yaml.safe_load(compiled['protocol_yaml'])['protocol']
    assert len([s for s in steps if 'transfer' in s])==28
    assert all(s['transfer']['source_height']==-40 and s['transfer']['destination_height']==0 for s in steps if 'transfer' in s)
    assert all(s['mix']['height']==0 for s in steps if 'mix' in s)
    assert steps[0]['pick_up_tip']['position']=='tips.C6'
    assert [s['pick_up_tip']['position'] for s in steps if 'pick_up_tip' in s][-1]=='tips.E11'
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        color_pipeline.ColorResearch()
