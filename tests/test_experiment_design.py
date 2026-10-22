import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from paper_to_plate import bond, store
from paper_to_plate.app import app
from paper_to_plate.experiment_design import MixtureSettings, compile_design, design_mixtures, rank_colors


def test_mixture_screen_preserves_totals_and_reference_controls():
    design = design_mixtures(MixtureSettings())
    assert len(design['wells']) == 10
    assert len({w['well'] for w in design['wells']}) == 10
    for row in design['wells']:
        assert sum(row['volumes_ul'].values()) == 120
        assert all(v == 0 or v >= 5 for v in row['volumes_ul'].values())
        if row['role'] != 'blank':
            assert sum(row['volumes_ul'][c] for c in ('red','yellow','blue')) == 60
    assert sum(w['role']=='technical_repeat' for w in design['wells']) == 3
    assert sum(w['role']=='blank' for w in design['wells']) == 1
    assert design == design_mixtures(MixtureSettings())
    assert design['wells'] != design_mixtures(MixtureSettings(seed=7))['wells']


def test_compilation_is_a_proposed_snapshot_and_clears_old_assay_fluids(setup):
    original = deepcopy(setup)
    settings = MixtureSettings()
    plan, compiled, prepared = compile_design(settings, setup, design_mixtures(settings))
    assert setup == original
    assert compiled['tip_count'] == 28
    assert len(compiled['steps']) == 94
    assert 'BSA' not in prepared['fluids_yaml']
    assert 'Bradford' not in prepared['fluids_yaml']
    assert all(not op['citations'] for op in plan['operations'])
    assert plan['assumptions']


@pytest.mark.parametrize('settings', [MixtureSettings(total_ul=30,dye_percent=10),MixtureSettings(total_ul=42,dye_percent=30)])
def test_unrepresentable_or_undersized_transfers_fail(settings):
    with pytest.raises(ValueError):
        design_mixtures(settings)


@pytest.mark.parametrize('change', [{'red_source':'plate.A1'}, {'red_source':'10_vial_holder.Z99'}, {'red_source':'10_vial_holder.A2'}, {'first_tip':'H12'}])
def test_setup_mapping_and_tip_limits(setup, change):
    s=MixtureSettings(**change)
    with pytest.raises(ValueError):
        compile_design(s,setup,design_mixtures(s))


def test_color_ranking_uses_observations_and_excludes_blank():
    design=design_mixtures(MixtureSettings())
    blank=next(w['well'] for w in design['wells'] if w['role']=='blank')
    well=next(w['well'] for w in design['wells'] if w['role']=='mixture')
    result=rank_colors(design,[{'well':blank,'rgb':[100,100,100]},{'well':well,'rgb':[101,100,100]}],[100,100,100])
    assert result['best']['well']==well
    assert result['best']['distance']==1
    assert not result['complete']
    with pytest.raises(ValueError):
        rank_colors(design,[{'well':'Z99','rgb':[0,0,0]}],[0,0,0])


def test_recorded_example_protocol_and_origin_boundary(workspace, monkeypatch):
    import paper_to_plate.design_api as design_api
    async def offline(*args):return {'passed':True,'hardware_contacted':False,'errors':[]}
    monkeypatch.setattr(design_api,'validate',offline)
    with TestClient(app) as client:
        request={'goal':'Find a dye mixture closest to green','evidence_mode':'recorded_demo'}
        result=client.post('/api/designs',json=request)
        assert result.status_code==201,result.text
        value=result.json()
        assert value['bond']['mode']=='recorded_demo'
        assert value['bond']['result']['_meta']['request_id']
        assert value['preview']['tip_count']==28
        assert not value['blockers']
        generated=client.post('/api/designs/'+value['id']+'/protocol')
        assert generated.status_code==201,generated.text
        run=generated.json()
        assert run['status']=='needs_attention' and run['review'] is None
        assert run['design_id']==value['id']
        assert run['validation']['hardware_contacted'] is False
        assert not run.get('handoffs')
        assert client.post('/api/designs',json=request,headers={'Origin':'https://untrusted.example'}).status_code==403
        bad=client.post('/api/designs',json={**request,'kind':'research_brief'})
        assert bad.status_code==400


def test_oauth_callback_rejects_invalid_state_and_status_hides_tokens(workspace):
    bond.save_credentials({'access_token':'private-token','refresh_token':'refresh-secret'})
    with TestClient(app) as client:
        response=client.get('/api/bond/status')
        assert response.json()['connected']
        assert 'private-token' not in response.text and 'refresh-secret' not in response.text
        assert client.get('/api/bond/callback?state=wrong&code=x').status_code==400


async def test_mcp_json_and_sse_transport(workspace, monkeypatch):
    monkeypatch.setenv('VALENCY_ACCESS_TOKEN','fixture-token')
    requests=[]
    def handler(request):
        data=json.loads(request.content);requests.append(data)
        assert request.headers['Authorization']=='Bearer fixture-token'
        if data['method']=='initialize':return httpx.Response(200,json={'jsonrpc':'2.0','id':1,'result':{'protocolVersion':'2025-03-26'}},headers={'Mcp-Session-Id':'session'})
        assert request.headers['Mcp-Session-Id']=='session'
        if data['method']=='notifications/initialized':return httpx.Response(202)
        assert data['params']['name']=='semantic_search_papers'
        return httpx.Response(200,text='event: message\ndata: '+json.dumps({'jsonrpc':'2.0','id':2,'result':{'structuredContent':{'papers':[]}}})+'\n\n',headers={'content-type':'text/event-stream'})
    client=httpx.AsyncClient
    monkeypatch.setattr(bond.httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(handler),**kw))
    result=await bond.search('red yellow blue mixture')
    assert result['mode']=='live' and len(requests)==3


def test_live_brief_filters_fabricated_quotes_and_blocks_incompatible_design(workspace, monkeypatch):
    import paper_to_plate.design_api as module
    async def search(query):
        return {'mode':'live','query':query,'retrieved_at':1,'result':{'papers':[{'id':'paper-1','title':'Dye experiment','url':'https://example.org/paper','abstract':'Camera measurements can compare dye mixtures.'}]}}
    async def complete(*args,**kwargs):
        return {'title':'Unsupported goal','hypothesis':'Test an incompatible goal','claims':[{'paper_id':'paper-1','quote':'An invented quotation','implication':'Not supported'}],
                'proposed_choices':[],'unresolved':[],'compatible_with_design':False},{}
    monkeypatch.setattr(module.bond,'search',search)
    monkeypatch.setattr(module.llm,'complete',complete)
    with TestClient(app) as client:
        r=client.post('/api/designs',json={'goal':'Measure an unrelated reaction mechanism','evidence_mode':'live'})
        assert r.status_code==201
        value=r.json()
        assert value['brief']['claims']==[]
        assert any('removed' in q for q in value['brief']['unresolved'])
        assert value['blockers']
        assert client.post('/api/designs/'+value['id']+'/protocol').status_code==409


def test_measurements_require_matching_image_and_valid_channels(workspace):
    import base64
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD4sAAAAASUVORK5CYII=')
    with TestClient(app) as client:
        value=client.post('/api/designs',json={'goal':'Find a red yellow blue mixture','evidence_mode':'recorded_demo'}).json()
        path='/api/designs/'+value['id']
        image=client.post(path+'/images',files={'file':('fixture.png',png,'image/png')}).json()
        assert client.get(image['url']).content==png
        body={'rows':[{'well':'A1','rgb':[30,50,60]}],'target_rgb':[30,50,60],'image_id':image['id']}
        result=client.post(path+'/measurements',json=body)
        assert result.status_code==200
        assert result.json()['measurements']['best']['distance']==0
        assert not result.json()['measurements']['complete']
        body['rows'][0]['rgb']=[500,0,0]
        assert client.post(path+'/measurements',json=body).status_code==400
