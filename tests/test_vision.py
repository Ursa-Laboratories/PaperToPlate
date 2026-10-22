import json
import time

import pytest

pytest.importorskip('numpy')
from fastapi.testclient import TestClient
from PIL import Image
from paper_to_plate import vision_service as service


def test_unassociated_liquid_and_invalid_predictions_are_not_reported():
    raw = [
        {'label': 'tip', 'confidence': .8, 'box': [10, 10, 30, 80]},
        {'label': 'liquid', 'confidence': .7, 'box': [11, 30, 29, 60]},
        {'label': 'liquid', 'confidence': .9, 'box': [100, 100, 120, 130]},
        {'label': 'tip', 'confidence': float('nan'), 'box': [1, 1, 20, 20]},
        {'label': 'tip', 'confidence': .9, 'box': [10, 10, 3, 4]},
    ]
    result = service.clean_detections(raw, 200, 200)
    assert [x['label'] for x in result] == ['tip', 'liquid']


def test_stale_camera_invalidates_previous_success(tmp_path):
    worker = service.Vision(tmp_path)
    worker.raw = Image.new('RGB', (200, 200))
    worker.received_at = time.time()
    worker.changed_at = time.time()-10
    worker.loaded_id = 'yolo'
    worker.result = {'model': 'yolo', 'captured_at': time.time(), 'detections': [{'label': 'tip'}]}
    state = worker.status()
    assert state['state'] == 'stale'
    assert state['detections'] == []
    assert state['counts']['tip'] is None
    with pytest.raises(ValueError, match='fresh'):
        worker.capture()


def test_model_switch_invalidates_old_result(tmp_path):
    worker = service.Vision(tmp_path)
    worker.raw = Image.new('RGB', (200, 200))
    worker.received_at = worker.changed_at = time.time()
    worker.loaded_id = 'yolo'
    worker.model_id = 'dino'
    worker.result = {'model': 'yolo', 'captured_at': time.time(), 'detections': [{'label': 'tip'}]}
    assert worker.status()['state'] == 'loading_model'
    assert worker.status()['detections'] == []


def test_annotation_roundtrip_and_bounds(tmp_path, monkeypatch):
    worker = service.Vision(tmp_path)
    worker.raw = Image.new('RGB', (200, 100))
    worker.received_at = worker.changed_at = time.time()
    monkeypatch.setattr(service, 'vision', worker)
    client = TestClient(service.app)
    capture = client.post('/capture').json()
    assert client.get('/captures/'+capture['id']+'/image').status_code == 200
    bad = {'frame_id': capture['id'], 'reviewed': True, 'boxes': [{'label': 'liquid', 'box': [0, 0, 201, 50]}]}
    assert client.post('/annotations', json=bad).status_code == 422
    good = {**bad, 'boxes': []}
    assert client.post('/annotations', json=good).status_code == 200
    annotation = json.loads((tmp_path/'annotations'/f"{capture['id']}.json").read_text())
    assert annotation['label_source'] == 'human_review'
    assert annotation['session_id'] == worker.session_id
    assert annotation['boxes'] == []
    assert annotation['sha256']


def test_worker_rejects_remote_hosts_and_cross_origin_writes():
    client = TestClient(service.app)
    assert client.get('/status', headers={'host': 'evil.example'}).status_code == 400
    assert client.post('/model', json={'model': 'yolo'}, headers={'origin': 'https://evil.example'}).status_code == 403
    assert client.get('/captures/../../.env/image').status_code == 404


def test_pending_weights_do_not_suggest_available_models(tmp_path):
    worker = service.Vision(tmp_path)
    assert all(not item['available'] for item in worker.models())


def test_recording_keeps_prediction_provenance_and_enforces_single_session(tmp_path, monkeypatch):
    worker = service.Vision(tmp_path)
    monkeypatch.setattr(service, 'vision', worker)
    worker.raw = Image.new('RGB', (200, 100))
    worker.received_at = worker.changed_at = time.time()
    worker.loaded_id = 'yolo'
    worker.result = {'model': 'yolo', 'captured_at': time.time(), 'detections': []}
    client = TestClient(service.app)
    response = client.post('/recording', json={'duration_seconds': 5})
    assert response.status_code == 200
    key = response.json()['id']
    assert client.post('/recording', json={'duration_seconds': 5}).status_code == 409
    worker.record_observation(worker.raw, {'frame_id': 1, 'captured_at': time.time(), 'detections': []})
    row = json.loads((tmp_path/'recordings'/key/'observations.jsonl').read_text())
    assert row['reviewed'] is False
    assert row['label_source'] == 'model_prediction'
    assert client.get(f'/recordings/{key}/archive').status_code == 409
    worker.recording['ends_at'] = time.time()-1
    archive = client.get(f'/recordings/{key}/archive')
    assert archive.status_code == 200
    assert archive.content.startswith(b'PK')


def test_capture_links_paper_and_protocol_revision(workspace, monkeypatch):
    import httpx
    from paper_to_plate import store, vision_proxy
    from paper_to_plate.app import app as workbench
    real_client = httpx.AsyncClient
    run = store.get('runs', 'bradford-example')
    received = []

    def handle(request):
        context = json.loads(request.content)['context']
        received.append(context)
        return httpx.Response(200, json={'id': 'a'*32, 'session_id': 'b'*32, 'captured_at': 123., 'sha256': 'c'*64, 'context': context})

    monkeypatch.setattr(vision_proxy.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handle)))
    client = TestClient(workbench)
    response = client.post('/api/vision/capture', json={'run_id': run['id']})
    assert response.status_code == 200
    assert received[0]['paper_id'] == run['paper_id']
    assert received[0]['protocol_hash'] == run.get('protocol_hash', '')
    saved = store.get('runs', run['id'])
    assert saved['vision_captures'][0]['id'] == 'a'*32
    assert 'no step alignment' in saved['vision_captures'][0]['context']['alignment_method']
    assert client.post('/api/vision/capture', json={'run_id': 'nonexistent'}).status_code == 400
