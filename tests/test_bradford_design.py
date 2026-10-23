import json
from copy import deepcopy

import pytest
import yaml
from fastapi.testclient import TestClient

from paper_to_plate import bradford_design as bradford, design_api, store
from paper_to_plate.app import app
from paper_to_plate.config import ROOT
from paper_to_plate.preparation import build as loading_sheet
from paper_to_plate.validation import validate


@pytest.mark.parametrize('n,tips,commands', [(1,30,98),(2,51,168),(3,72,238)])
def test_replicate_counts_and_exact_plate_composition(workspace,n,tips,commands):
    original=store.get('setups','bradford-color-demo-setup');before=deepcopy(original)
    settings=bradford.BradfordSettings(replicates=n)
    plan,compiled,setup,extra=bradford.compile_bradford(settings,original)
    assert original==before
    assert compiled['tip_count']==tips and len(compiled['steps'])==commands
    assert len(bradford.build_design(settings)['wells'])==8*n
    balance={p:d['volume_ul'] for p,d in yaml.safe_load(setup['fluids_yaml'])['fluids'].items()}
    for step in compiled['steps']:
        if step['command']=='transfer':
            a=step['args'];balance[a['source']]-=a['volume_ul'];balance[a['destination']]+=a['volume_ul']
            assert balance[a['source']]>=-1e-8
    for r in 'ABC'[:n]:
        assert all(balance[f'plate.{r}{c}']==pytest.approx(200) for c in range(1,9))
    assert balance['10_vial_holder.A5']==1000-n*100
    assert balance['10_vial_holder.A1']==1500-150*n
    assert balance['10_vial_holder.A3']==3000-700*n
    assert extra['demonstration']['kind']=='colored_water'
    assert not loading_sheet({'plan':plan,'setup_snapshot':setup,**compiled})['issues']


def test_source_gate_is_specific_and_water_blank_is_distinct():
    assert bradford.supported_source([{'id':'20386536'}])
    assert not bradford.supported_source([{'id':'37747186','title':'RGBradford'}])
    d=bradford.build_design(bradford.BradfordSettings())
    zero=next(w for w in d['wells'] if w['well']=='A1')
    blank=next(w for w in d['wells'] if w['well']=='A8')
    assert zero['volumes_ul']['blue']==100 and zero['volumes_ul']['water']==100
    assert blank['volumes_ul']['blue']==0 and blank['volumes_ul']['water']==200
    sample=next(w for w in d['wells'] if w['well']=='A7')
    assert sample['volumes_ul']['diluted_yellow']==100
    assert sample['source_locator']=='Steps 5–6'


def test_mapping_capacity_and_tip_failure_do_not_change_geometry(workspace):
    setup=store.get('setups','bradford-color-demo-setup')
    with pytest.raises(ValueError,match='tips'):
        bradford.compile_bradford(bradford.BradfordSettings(first_tip='H12'),setup)
    deck=yaml.safe_load(setup['deck_yaml']);deck['labware']['10_vial_holder']['working_volume_ul']=500
    setup['deck_yaml']=yaml.safe_dump(deck)
    with pytest.raises(ValueError,match='capacity'):
        bradford.compile_bradford(bradford.BradfordSettings(),setup)


async def test_native_offline_validation_for_query_generated_bradford(workspace):
    plan,compiled,setup,_=bradford.compile_bradford(bradford.BradfordSettings(),store.get('setups','bradford-color-demo-setup'))
    result=await validate(setup,compiled['protocol_yaml'])
    assert result['passed'],result.get('errors')
    assert result['hardware_contacted'] is False


def test_live_question_to_bradford_draft_preserves_surrogate_scope(workspace,monkeypatch):
    receipt=json.loads((ROOT/'examples/bond-bradford-search.json').read_text())
    calls=[]
    async def search(query):calls.append(query);return deepcopy(receipt)
    async def complete(*args,**kwargs):
        return {'title':'Bradford protein assay represented in colored water','hypothesis':'Demonstrate the pipetting structure',
            'claims':[],'proposed_choices':[],'unresolved':[],'compatible_with_design':True},{'model':'test-double'}
    async def offline(*args):return {'passed':True,'errors':[],'hardware_contacted':False}
    monkeypatch.setattr(design_api.bond,'search',search);monkeypatch.setattr(design_api.llm,'complete',complete);monkeypatch.setattr(design_api,'validate',offline)
    with TestClient(app) as client:
        response=client.post('/api/designs',json={'goal':bradford.EXAMPLE_GOAL,'kind':'auto','setup_id':'bradford-color-demo-setup'})
        assert response.status_code==201,response.text
        design=response.json()
        assert design['kind']=='bradford_demo' and design['requested_kind']=='auto'
        assert calls[0]==bradford.EXAMPLE_GOAL and calls[1]==bradford.QUERY
        assert design['preview']['tip_count']==72 and not design['blockers']
        run=client.post(f"/api/designs/{design['id']}/protocol").json()
        assert run['demonstration']['kind']=='colored_water'
        assert run['review'] is None and run['status']=='needs_attention'
        assert not run.get('handoffs') and not run.get('loading_confirmation')
        response=client.post(f"/api/runs/{run['id']}/measurements",files={'file':('protein.csv',b'fake','text/csv')})
        assert response.status_code==400 and 'colored-water' in response.text
        copy=client.post(f"/api/runs/{run['id']}/copy").json()
        assert copy['demonstration']['kind']=='colored_water'


def test_camera_observations_never_fit_protein_or_choose_a_winner():
    d=bradford.build_design(bradford.BradfordSettings())
    result=bradford.summarize_colors(d,[{'well':'A2','rgb':[100,100,100]},{'well':'B2','rgb':[102,100,100]}])
    assert result['best'] is None
    assert result['groups'][0]['mean_rgb_distance']==1
    assert not result['complete']
    assert 'concentration' not in result
    with pytest.raises(ValueError):bradford.summarize_colors(d,[{'well':'Z99','rgb':[1,2,3]}])


async def test_surrogate_review_receipt_uses_compiled_volume_and_capacity(workspace, monkeypatch):
    from paper_to_plate import pipeline
    run=store.get('runs','bradford-color-demo')
    captured={}
    async def complete(schema, system, user, **kwargs):
        captured.update(json.loads(user))
        return {'summary':'Check physical setup','verdict':'needs_operator_review','findings':[],'questions':[]},{}
    monkeypatch.setattr(pipeline.llm,'complete',complete)
    await pipeline.review_run(store.get('papers',run['paper_id']),run['setup_snapshot'],run)
    receipt=captured['compiled_receipt']
    assert receipt['initial_ul']['10_vial_holder.A5']==0
    assert receipt['peak_ul']['10_vial_holder.A5']==1000
    assert receipt['final_ul']['10_vial_holder.A5']==700
    assert receipt['labware_limits']['10_vial_holder']['working_volume_ul']==4000
    assert receipt['pipette_min_ul']==5 and receipt['smallest_transfer_ul']==10
    assert receipt['tip_pickups']==receipt['tip_discards']==72
    assert receipt['loading_sheet']['human_before']
    assert 'gantry_yaml' not in captured and 'source' not in captured


def test_review_preserves_previous_findings(workspace, monkeypatch):
    from paper_to_plate import pipeline
    run=store.get('runs','bradford-color-demo')
    old={'summary':'Original review','verdict':'changes_required','findings':[],'questions':[]}
    run.update(review=old,review_hash=run['protocol_hash'])
    store.save('runs',run)
    async def replacement(*args):
        return {'summary':'Updated review','verdict':'needs_operator_review','findings':[],'questions':[]},{}
    monkeypatch.setattr(pipeline,'review_run',replacement)
    with TestClient(app) as client:
        result=client.post('/api/runs/bradford-color-demo/review').json()
        assert result['review']['summary']=='Updated review'
        assert result['review_history'][0]['review']==old
        assert not result.get('adjudication') and not result.get('loading_confirmation')
