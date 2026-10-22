"""Upload-to-result integration checks; no model service or hardware required."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from paper_to_plate import llm, pipeline, store
from paper_to_plate.app import app


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setattr(llm, 'OLLAMA_URL', 'https://ollama.com')
    monkeypatch.setenv('OLLAMA_API_KEY', 'test-only-secret')


def test_missing_key_is_visible_and_does_not_create_run(workspace, hosted, monkeypatch):
    monkeypatch.delenv('OLLAMA_API_KEY')
    with TestClient(app) as client:
        status = client.get('/api/status').json()
        assert not status['provider_configured']
        assert 'OLLAMA_API_KEY' in status['configuration_error']
        before = len(store.list_all('runs'))
        response = client.post('/api/runs', json={'paper_id': 'bradford-notes', 'objective': 'Prepare the assay'})
        assert response.status_code == 503
        assert len(store.list_all('runs')) == before


def test_local_ollama_does_not_require_cloud_key(hosted, monkeypatch):
    monkeypatch.delenv('OLLAMA_API_KEY')
    monkeypatch.setattr(llm, 'OLLAMA_URL', 'http://127.0.0.1:11434')
    assert llm.configuration_error() is None


@pytest.mark.parametrize('code, expected', [(401, 'API key'), (403, 'API key'), (429, 'usage limit'), (404, 'model or endpoint'), (500, 'HTTP 500')])
async def test_provider_errors_are_actionable_and_do_not_leak_body(hosted, monkeypatch, code, expected):
    class Result(BaseModel):
        ready: bool
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            return httpx.Response(code, text='private provider response test-only-secret')
    monkeypatch.setattr(llm.httpx, 'AsyncClient', Client)
    with pytest.raises(llm.ModelError, match=expected) as error:
        await llm.complete(Result, 'system', 'user')
    assert 'test-only-secret' not in str(error.value)
    assert 'private provider' not in str(error.value)


async def test_upload_to_ollama_to_frontend_contract(workspace, setup, hosted, monkeypatch):
    import paper_to_plate.app as api_module
    monkeypatch.setattr(api_module, 'DATA', workspace)
    calls = []
    responses = [
        {'title': 'Water method', 'summary': 'Transfer water', 'assay': 'Water', 'materials': ['Water'],
         'steps': [{'title': 'Transfer', 'instruction': 'Transfer 100 uL water.', 'citations': [{'page': 1, 'quote': 'Transfer 100 uL water'}]}],
         'unknowns': [], 'readout': 'Manual inspection'},
        {'title': 'Water method', 'summary': 'Transfer water', 'operations': [{'action': 'transfer', 'source': '10_vial_holder.B5',
         'destinations': ['plate.A1'], 'volume_ul': 100, 'purpose': 'Transfer water', 'citations': [{'page': 1, 'quote': 'Transfer 100 uL water'}]}]},
        {'summary': 'Inspect before use', 'verdict': 'needs_operator_review', 'findings': [], 'questions': []},
    ]
    def model_response(request):
        assert str(request.url) == 'https://ollama.com/api/chat'
        assert request.headers['Authorization'] == 'Bearer test-only-secret'
        payload = json.loads(request.content)
        calls.append(payload['format']['title'])
        assert '[PAGE 1]' in payload['messages'][1]['content']
        assert 'test-only-secret' not in request.content.decode()
        return httpx.Response(200, json={'message': {'content': json.dumps(responses.pop(0))}, 'done_reason': 'stop', 'eval_count': 10})
    real_client = httpx.AsyncClient
    def provider_client(**kwargs):
        return real_client(transport=httpx.MockTransport(model_response), **kwargs)
    monkeypatch.setattr(llm.httpx, 'AsyncClient', provider_client)
    async def validate(*args):
        return {'passed': True, 'errors': [], 'hardware_contacted': False}
    monkeypatch.setattr(pipeline, 'validate', validate)
    monkeypatch.setattr(pipeline, 'SEMAPHORE', asyncio.Semaphore(1))
    transport = httpx.ASGITransport(app=app)
    async with real_client(transport=transport, base_url='http://testserver') as client:
        uploaded = await client.post('/api/papers', files={'file': ('method.txt', b'Transfer 100 uL water to the assay plate. Record the final volume.', 'text/plain')})
        assert uploaded.status_code == 201
        created = await client.post('/api/runs', json={'paper_id': uploaded.json()['id'], 'setup_id': setup['id'], 'objective': 'Transfer 100 uL water into A1'})
        assert created.status_code == 202
        run_id = created.json()['id']
        task = pipeline.ACTIVE.get(run_id)
        if task is not None:
            await asyncio.wait_for(task, timeout=5)
        response = await client.get('/api/runs/' + run_id)
        result = response.json()
        assert result['status'] == 'ready', result.get('error')
        assert calls == ['Extraction', 'Plan', 'Review']
        assert result['extraction']['steps'][0]['citations'][0]['page'] == 1
        assert 'transfer:' in result['protocol_yaml']
        assert len(result['steps']) == 3
        assert result['validation']['hardware_contacted'] is False
        assert result['score']['physical_outcome'] == 'Not measured'
        assert result['preparation']
        assert result['usage'][0]['stage'] == 'extract'
        assert 'test-only-secret' not in response.text
        assert not result.get('handoffs')
