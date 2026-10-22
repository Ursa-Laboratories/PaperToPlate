"""Fixed localhost proxy; camera frames and models never leave this machine."""
import asyncio
import json

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from . import store

router = APIRouter(prefix='/api/vision')
WORKER = 'http://127.0.0.1:8793'
ALLOWED = {'status', 'model', 'stream', 'frame.jpg', 'capture', 'annotations', 'examples', 'recording'}


@router.api_route('/{path:path}', methods=['GET', 'POST'])
async def proxy(path: str, request: Request):
    parts = path.split('/')
    valid = path in ALLOWED or (len(parts) == 3 and ((parts[0] in ('captures', 'examples') and parts[2] == 'image') or (parts[0] == 'recordings' and parts[2] == 'archive')) and parts[1].replace('-', '').isalnum())
    if not valid:
        return JSONResponse({'detail': 'Unknown vision endpoint'}, status_code=404)
    if path == 'stream' and request.method == 'GET':
        async def stream():
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(5, read=None), trust_env=False) as client:
                    async with client.stream('GET', WORKER+'/stream') as upstream:
                        upstream.raise_for_status()
                        async for chunk in upstream.aiter_bytes():
                            if await request.is_disconnected():
                                return
                            yield chunk
            except (httpx.HTTPError, asyncio.CancelledError):
                return
        return StreamingResponse(stream(), media_type='multipart/x-mixed-replace; boundary=frame', headers={'Cache-Control': 'no-store'})
    try:
        content = await request.body()
        if len(content) > 100_000:
            return JSONResponse({'detail': 'Request too large'}, status_code=413)
        linked_run = None
        if path == 'capture' and request.method == 'POST':
            try:
                body = json.loads(content or '{}')
                run_id = body.get('run_id')
                if run_id:
                    linked_run = store.get('runs', run_id)
                context = {'run_id': linked_run['id'], 'paper_id': linked_run['paper_id'], 'protocol_hash': linked_run.get('protocol_hash', ''), 'alignment_method': 'manual experiment association; no step alignment verified'} if linked_run else {}
                content = json.dumps({'context': context}).encode()
            except (ValueError, KeyError, TypeError, AttributeError):
                return JSONResponse({'detail': 'Unknown experiment or invalid capture request'}, status_code=400)
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.request(request.method, WORKER+'/'+path, content=content, headers={'Content-Type': 'application/json'})
        if linked_run and response.status_code == 200:
            capture = response.json()
            current = store.get('runs', linked_run['id'])
            current.setdefault('vision_captures', []).append({k: capture[k] for k in ('id', 'session_id', 'captured_at', 'sha256', 'context')})
            store.save('runs', current)
        headers = {'Cache-Control': 'no-store'}
        if 'content-disposition' in response.headers:
            headers['Content-Disposition'] = response.headers['content-disposition']
        return Response(response.content, status_code=response.status_code, media_type=response.headers.get('content-type', 'application/json'), headers=headers)
    except httpx.HTTPError:
        if path == 'status':
            return JSONResponse({'state': 'worker_offline', 'warning': 'Vision worker is not running. Start it with ./start-vision.sh.', 'models': [{'id': 'yolo', 'label': 'YOLO', 'available': False}, {'id': 'dino', 'label': 'DINO', 'available': False}], 'counts': {'tip': None, 'liquid': None}, 'detections': []})
        return JSONResponse({'detail': 'Vision worker is unavailable'}, status_code=503)
