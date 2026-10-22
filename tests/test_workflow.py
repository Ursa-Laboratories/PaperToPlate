import asyncio
import csv
import io
import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from paper_to_plate import handoff, pipeline, store
from paper_to_plate.analysis import analyze_bradford
from paper_to_plate.app import app
from paper_to_plate.compiler import compile_plan, digest
from paper_to_plate.models import HandoffInput
from paper_to_plate.validation import score, validate


def plan(volume=100):
    return {"title": "Water transfer", "summary": "A controlled test", "operations": [{"action": "transfer", "source": "10_vial_holder.B5", "destinations": ["plate.A1"], "volume_ul": volume, "purpose": "Transfer water", "citations": [{"page": 1, "quote": "Add water"}]}], "manual_steps": [], "assumptions": [], "unresolved": []}


def ready_run(setup):
    compiled = compile_plan(plan(), setup)
    return {"id": "test", "setup_snapshot": setup, **compiled, "validation": {"passed": True}, "validation_hash": compiled["protocol_hash"], "review": {"findings": []}, "review_hash": compiled["protocol_hash"], "plan": plan()}


def test_split_transfer_has_fresh_tip_per_stroke_and_preserves_volume(setup):
    compiled = compile_plan(plan(250), setup)
    steps = yaml.safe_load(compiled["protocol_yaml"])["protocol"]
    assert compiled["tip_count"] == 3
    assert sum(x["transfer"]["volume_ul"] for x in steps if "transfer" in x) == pytest.approx(250)
    assert [next(iter(x)) for x in steps] == ["pick_up_tip", "transfer", "drop_tip"] * 3
    assert len({x["pick_up_tip"]["position"] for x in steps if "pick_up_tip" in x}) == 3


def test_compiler_rejects_insufficient_tips_and_marks_interleaved_manual_steps(setup):
    setup["first_tip"] = "H12"
    with pytest.raises(ValueError, match="fresh tips"):
        compile_plan(plan(250), setup)
    raw = plan()
    raw["manual_steps"] = [{"when": "between", "instruction": "Swap a plate", "reason": "No robotic plate handler"}]
    assert compile_plan(raw, setup)["manual_interleaving"]


def test_compiler_does_not_invent_operations_or_assume_another_pipette_capacity(setup):
    empty=plan();empty['operations']=[];empty['unresolved']=['No usable method provided']
    with pytest.raises(ValueError,match='No supported'):compile_plan(empty,setup)
    gantry=yaml.safe_load(setup['gantry_yaml']);gantry['instruments']['pipette']['pipette_model']='another_pipette'
    setup['gantry_yaml']=yaml.safe_dump(gantry)
    with pytest.raises(ValueError,match='120 uL'):compile_plan(plan(),setup)


@pytest.mark.asyncio
async def test_native_validation_accepts_example_and_rejects_out_of_bounds(setup):
    example = store.get("runs", "bradford-example")
    result = await validate(setup, example["protocol_yaml"])
    assert result["passed"], result
    assert result["hardware_contacted"] is False
    bad = example["protocol_yaml"].replace('"destination_height": 0.0', '"destination_height": 500.0', 1)
    assert not (await validate(setup, bad))["passed"]


def test_physical_handoff_requires_current_review_validation_and_operator(setup):
    run = ready_run(setup)
    request = HandoffInput(mock_mode=False, expected_hash=run["protocol_hash"])
    with pytest.raises(ValueError, match="operator"):
        handoff.submission(run, request)
    request = request.model_copy(update={"operator_confirmed": True, "manual_steps_confirmed": True, "setup_confirmed": True})
    payload = handoff.submission(run, request)
    assert payload["mock_mode"] is False
    assert payload["state"]["initial_state"]["fluids"]["10_vial_holder.B5"]["volume_ul"] == 3000
    assert payload["run_id"] == handoff.submission(run, request)["run_id"]
    run["review_hash"] = None
    with pytest.raises(ValueError, match="Review"):
        handoff.submission(run, request)
    run["review_hash"] = run["protocol_hash"]
    run["protocol_yaml"] += "\n# edited\n"
    with pytest.raises(ValueError, match="changed"):
        handoff.submission(run, request)


@pytest.mark.parametrize("change", ["critical", "unresolved", "manual"])
def test_physical_handoff_blocks_scientific_and_workflow_gaps(setup, change):
    run = ready_run(setup)
    if change == "critical":run["review"]["findings"] = [{"severity": "critical"}]
    if change == "unresolved":run["plan"]["unresolved"] = ["Unknown stock"]
    if change == "manual":run["manual_interleaving"] = True
    request = HandoffInput(mock_mode=False, expected_hash=run["protocol_hash"], operator_confirmed=True, manual_steps_confirmed=True, setup_confirmed=True)
    with pytest.raises(ValueError):handoff.submission(run, request)


def reader_csv():
    return "well,role,protein_ug,a590,a450,sample_id,dilution_factor,sample_volume_ul,expected_ug_ml\nA10,blank,,0.1,0.2,,,,\nA1,standard,0,0.3,1.2,,,,\nA2,standard,1,0.8,1.2,,,,\nA3,standard,2,1.3,1.2,,,,\nA7,sample,,0.8,1.2,test,10,100,100\nB7,sample,,0.8,1.2,test,10,100,100\n"


def test_bradford_uses_water_blanks_nonzero_intercept_and_dilution():
    result = analyze_bradford(reader_csv())
    assert result["slope"] == pytest.approx(0.5)
    assert result["intercept"] == pytest.approx(0.2)
    assert result["samples"][0]["original_ug_ml"] == pytest.approx(100)
    assert result["samples"][0]["recovery_percent"] == pytest.approx(100)
    assert result["groups"][0]["cv_percent"] == 0


@pytest.mark.parametrize("text", [reader_csv().replace('test,10,100','test,0,100'),reader_csv().replace('A7,sample,,0.8,1.2','A7,sample,,0.8,0.2'),reader_csv().replace('A10,blank','A1,blank')])
def test_reader_rejects_invalid_dilution_denominator_and_duplicate_wells(text):
    with pytest.raises(ValueError):analyze_bradford(text)


def test_score_does_not_promote_reviewer_or_reference_notes_to_physical_success(setup):
    run = ready_run(setup)
    run["rubric"] = {"approved": False, "criteria": [{"type": "final_volume", "target": "plate.A1", "expected_ul": 100}]}
    result = score(run, setup, {"pages": [{"page": 1, "text": "Add water"}]})
    assert result["criteria"][0]["passed"]
    assert not result["rubric_approved"]
    assert result["physical_outcome"] == "Not measured"
    assert result["citations_text_verified"] == 1


def test_upload_edit_and_origin_boundary(workspace, monkeypatch):
    monkeypatch.setattr("paper_to_plate.app.DATA", workspace)
    with TestClient(app) as client:
        response = client.post('/api/papers', files={'file': ('paper.txt', b'Add water to the assay plate. Record the pipetting step and the final volume.','text/plain')})
        assert response.status_code == 201
        assert response.json()['source_kind'] == 'uploaded_text'
        assert client.post('/api/papers', files={'file': ('paper.pdf', b'not a pdf','application/pdf')}).status_code == 400
        assert client.post('/api/papers',headers={'Origin':'https://unrelated.example'},files={'file':('p.txt',b'hello')}).status_code == 403
        assert client.get('/api/status',headers={'Host':'unrelated.example'}).status_code == 400
        original = client.get('/api/runs/bradford-example').json()
        updated = client.put('/api/runs/bradford-example/protocol',json={'protocol_yaml':original['protocol_yaml']+'\n# revision'}).json()
        assert updated['validation'] is None and updated['review'] is None
        assert updated['protocol_hash'] != original['protocol_hash']


@pytest.mark.asyncio
async def test_pipeline_runs_generator_reviewer_validator_and_score(setup, monkeypatch):
    calls = []
    async def complete(schema, *args, **kwargs):
        calls.append(schema.__name__)
        if schema.__name__ == 'Extraction':value={'title':'Test','summary':'Test method','assay':'water','materials':['water'],'steps':[],'unknowns':[],'readout':'manual'}
        elif schema.__name__ == 'Plan':value=plan()
        else:value={'summary':'No issues found in fixture','verdict':'needs_operator_review','findings':[],'questions':[]}
        return schema.model_validate(value).model_dump(),{'model':'test-double','duration_seconds':0}
    monkeypatch.setattr(pipeline.llm,'complete',complete)
    async def offline(*args):return {'passed':True,'errors':[],'hardware_contacted':False}
    monkeypatch.setattr(pipeline,'validate',offline)
    value=store.create('runs',paper_id='bradford-notes',setup_snapshot=setup,objective='Transfer 100 uL water',review_enabled=True,events=[],status='queued')
    await pipeline.execute(value['id'])
    final=store.get('runs',value['id'])
    assert calls == ['Extraction','Plan','Review']
    assert final['status']=='ready'
    assert final['review_hash']==final['protocol_hash']==final['validation_hash']
    assert final['score']['physical_outcome']=='Not measured'
    events = [(e['stage'], e['status']) for e in final['events']]
    assert ('generate', 'complete') in events
    assert ('review', 'running') in events
    assert ('validate', 'complete') in events


def test_duplicate_submission_is_not_replayed_and_copy_clears_execution_evidence(workspace, setup, monkeypatch):
    import paper_to_plate.app as api_module
    monkeypatch.setattr(api_module, 'DATA', workspace)
    r = ready_run(setup)
    r.update(id='handoff-test', title='Water', paper_id='bradford-notes', setup_id='picus120', objective='Water test', evidence={'video_id':'demo','offset_seconds':0,'markers':[{'step_index':0,'seconds':1}]})
    store.save('runs', r)
    sent = []
    async def fake_send(value, request):
        sent.append(handoff.submission(value, request))
        return {'run_id':'mock-resource','state':'queued','mock_mode':True}
    async def fake_validate(*args):return {'passed':True}
    monkeypatch.setattr(api_module.handoff,'send',fake_send)
    monkeypatch.setattr(api_module,'validate',fake_validate)
    with TestClient(app) as client:
        payload={'mock_mode':True,'expected_hash':r['protocol_hash']}
        assert client.post('/api/runs/handoff-test/handoff',json=payload).status_code == 200
        assert client.post('/api/runs/handoff-test/handoff',json=payload).status_code == 409
        assert len(sent)==1 and sent[0]['mock_mode'] is True
        copied=client.post('/api/runs/handoff-test/copy').json()
        assert copied['id'] != r['id']
        assert 'handoffs' not in copied
        assert copied['validation'] is None and copied['review'] is None
        assert copied['evidence']['markers']==[]


def test_protocol_edit_clears_old_video_alignment(workspace, setup):
    r=store.get('runs','bradford-example')
    r['evidence']['markers']=[{'step_index':0,'seconds':2}]
    store.save('runs',r)
    with TestClient(app) as client:
        updated=client.put('/api/runs/bradford-example/protocol',json={'protocol_yaml':r['protocol_yaml']+'\n# changed'}).json()
        assert updated['evidence']['markers']==[]
        assert updated['evidence_history'][0]['markers'][0]['seconds']==2


@pytest.mark.asyncio
async def test_structured_output_gets_one_bounded_format_correction(workspace, monkeypatch):
    import httpx
    from pydantic import BaseModel
    from paper_to_plate import llm
    class Result(BaseModel):ready:bool
    replies=iter(['not json','{"ready": true}'])
    calls=[]
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            calls.append(kwargs['json'])
            return httpx.Response(200,json={'message':{'content':next(replies)},'eval_count':2,'prompt_eval_count':5,'done_reason':'stop'})
    monkeypatch.setattr(llm,'DATA',workspace)
    monkeypatch.setattr(llm.httpx,'AsyncClient',Client)
    monkeypatch.setenv('OLLAMA_API_KEY','test-only-key')
    result,usage=await llm.complete(Result,'system','user',max_tokens=100)
    assert result=={'ready':True}
    assert len(calls)==2 and usage['format_retries']==1
    assert usage['input_tokens']==10
    assert 'test-only-key' not in str(calls)


def test_library_has_available_sources_without_treating_metadata_as_pdf(workspace, monkeypatch):
    import paper_to_plate.app as api_module
    from paper_to_plate.config import ROOT
    examples = workspace / 'examples'
    (examples / 'library').mkdir(parents=True)
    (examples / 'library' / 'fixture.pdf').write_bytes((ROOT / 'examples' / 'water-workflow-test.pdf').read_bytes())
    (examples / 'review-library.json').write_text(json.dumps([
        {'rank': 1, 'documents': [{'role': 'main_article', 'filename': 'fixture.pdf'}]},
        {'rank': 2, 'documents': [{'role': 'main_article', 'filename': 'not-downloaded.pdf'}]},
    ]))
    monkeypatch.setattr(api_module, 'ROOT', workspace)
    with TestClient(app) as client:
        rows=client.get('/api/library').json()
        assert len(rows)==2
        missing=next(row for row in rows if not row['documents'])
        assert client.post(f"/api/library/{missing['rank']}/use").status_code==404
        assert client.get('/api/library/2/pdf/0').status_code==404
        assert client.get('/api/library/1/pdf/0').content.startswith(b'%PDF-')


def test_reader_upload_and_export_keep_source_evidence(workspace, monkeypatch):
    import paper_to_plate.app as api_module
    from zipfile import ZipFile
    monkeypatch.setattr(api_module,'DATA',workspace)
    with TestClient(app) as client:
        result=client.post('/api/runs/bradford-example/measurements',files={'file':('synthetic-test.csv',reader_csv().encode(),'text/csv')})
        assert result.status_code == 200
        assert result.json()['measurements']['groups'][0]['mean_original_ug_ml']==pytest.approx(100)
        exported=client.get('/api/runs/bradford-example/export')
        with ZipFile(io.BytesIO(exported.content)) as z:
            assert 'source/metadata.json' in z.namelist()
            assert 'source/reference-notes.txt' in z.namelist()
            assert 'initial_fluids.yaml' in z.namelist()
            assert not any(name.endswith('.env') for name in z.namelist())


def test_human_adjudication_is_specific_to_review_and_never_overrides_native_failure(setup):
    from paper_to_plate.review import fingerprint,human_clearance
    r=ready_run(setup)
    r['review']={'verdict':'changes_required','findings':[{'severity':'critical','title':'A model mistake'}]}
    r['plan']['unresolved']=['Stock identity']
    r['adjudication']={'approved':True,'reviewer':'Test reviewer','notes':'An isolated test records a substantive independent explanation.','protocol_hash':r['protocol_hash'],'review_fingerprint':fingerprint(r['review']),'finding_responses':{'0':'The fixture has the verified expected final volume.'},'question_responses':{'0':'The fixture source is explicitly deionized water.'}}
    assert human_clearance(r)
    request=HandoffInput(mock_mode=False,expected_hash=r['protocol_hash'],operator_confirmed=True,manual_steps_confirmed=True,setup_confirmed=True)
    assert handoff.submission(r,request)['mock_mode'] is False
    r['validation']['passed']=False
    with pytest.raises(ValueError,match='validation'):handoff.submission(r,request)
    r['review']['findings'][0]['title']='A changed review finding'
    assert not human_clearance(r)
