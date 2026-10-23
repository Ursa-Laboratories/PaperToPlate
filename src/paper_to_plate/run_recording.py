"""Record execution evidence; CubOS is the sole owner of live run state."""
import asyncio
import json
import time
import uuid

import httpx

from . import store
from .config import CUBOS_URL
from .vision_proxy import WORKER

WATCHERS = {}
TERMINAL = {'succeeded', 'failed', 'cancelled'}


async def capture_final(run_id, client):
    run=store.get('runs',run_id)
    design_id=run.get('color_design_id')
    if not design_id:
        return
    try:
        response=await client.post(WORKER+'/capture',json={'context':{
            'run_id':run_id,'protocol_hash':run['protocol_hash'],'purpose':'post-run frame; operator must verify plate visibility'}})
        response.raise_for_status();capture=response.json()
        image=await client.get(WORKER+f"/captures/{capture['id']}/image")
        image.raise_for_status()
        key=uuid.uuid4().hex
        (store.folder('design_images')/key).write_bytes(image.content)
        store.save('design_image_records',{'id':key,'design_id':design_id,'mime':'image/jpeg','source':'post-run camera','capture':capture})
        value={'id':key,'url':f'/api/designs/{design_id}/images/{key}','capture':capture}
        design=store.get('designs',design_id);design['result_image']=value;store.save('designs',design)
        store.update_run(run_id,final_plate_image=value)
    except (httpx.HTTPError,ValueError,KeyError,OSError):
        store.update_run(run_id,final_plate_image_error='Post-run camera image unavailable. Capture or upload a plate image manually.')


async def start(run, request, station_run_id):
    context = {'run_id': run['id'], 'protocol_hash': run['protocol_hash'],
               'cubos_run_id': station_run_id, 'mock_mode': str(request.mock_mode).lower()}
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.post(WORKER+'/recording', json={
                'duration_seconds': request.recording_limit_seconds, 'context': context, 'video': True})
            if response.status_code != 200:
                raise ValueError('Recording could not start. No robot run was submitted. Check the camera and recorder.')
            recording = response.json()
    except httpx.HTTPError as exc:
        raise ValueError('Recorder did not confirm startup. No robot run was submitted; inspect the camera service.') from exc
    if not recording.get('active') or not recording.get('video_healthy'):
        raise ValueError('Recorder did not confirm a working video stream. No robot run was submitted.')
    value = {**recording, 'started_at': time.time(), 'limit_seconds': request.recording_limit_seconds,
             'station_url': CUBOS_URL, 'cubos_run_id': station_run_id, 'status': 'recording',
             'timing_basis': 'local timestamps and separately recorded CubOS events; clock offset not calibrated'}
    store.update_run(run['id'], execution_recording=value)
    return value


async def stop(run_id, reason):
    run = store.get('runs', run_id)
    recording = run.get('execution_recording')
    if not recording:
        return
    stopped = False
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            response = await client.post(WORKER+f"/recordings/{recording['id']}/stop")
        stopped = response.status_code == 200
    except httpx.HTTPError:
        pass
    value = {**recording, 'active': not stopped, 'status': 'finished' if stopped else 'stop_unconfirmed',
             'stop_reason': reason, 'finished_at': time.time()}
    store.update_run(run_id, execution_recording=value)


async def observe(run_id):
    run = store.get('runs', run_id)
    recording = run['execution_recording']
    station_id, station_url = recording['cubos_run_id'], recording['station_url']
    deadline = recording['started_at']+recording['limit_seconds']
    cursor = int(recording.get('event_cursor', 0))
    log = store.folder('execution_events') / f'{run_id}.jsonl'
    try:
        async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
            while time.time() < deadline:
                try:
                    before = time.time()
                    response = await client.get(station_url+f'/api/v1/runs/{station_id}')
                    after = time.time()
                    if response.status_code == 200:
                        state = response.json()
                        events = await client.get(station_url+f'/api/v1/runs/{station_id}/events', params={'after':cursor})
                        rows = events.json().get('events', []) if events.status_code == 200 else []
                        with log.open('a') as output:
                            output.write(json.dumps({'type':'run_observation','request_started_at':before,'received_at':after,
                                'station_run_id':station_id,'state':state.get('state'),'started_at':state.get('started_at'),
                                'finished_at':state.get('finished_at'),'error':state.get('error')})+'\n')
                            for event in rows:
                                output.write(json.dumps({'type':'cubos_event','received_at':time.time(),'event':event})+'\n')
                                cursor = max(cursor, event.get('sequence', cursor))
                        current = store.get('runs',run_id)['execution_recording']
                        store.update_run(run_id, execution_recording={**current, 'event_cursor':cursor})
                        if state.get('state') in TERMINAL:
                            await asyncio.sleep(2)  # retain a short view of the completed plate
                            if state.get('state')=='succeeded':
                                await capture_final(run_id,client)
                            await stop(run_id, 'cubos_'+state['state'])
                            return
                except (httpx.HTTPError, ValueError, KeyError):
                    # Record loss of visibility; never retry a run submission.
                    with log.open('a') as output:
                        output.write(json.dumps({'type':'station_observation_unavailable','at':time.time()})+'\n')
                await asyncio.sleep(2)
        await stop(run_id, 'recording_duration_limit')
    finally:
        WATCHERS.pop(run_id, None)


def watch(run_id):
    if run_id not in WATCHERS:
        WATCHERS[run_id] = asyncio.create_task(observe(run_id))


async def shutdown():
    tasks = list(WATCHERS.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def live_status(run):
    handed = (run.get('handoff') or {}).get('response', {})
    recording = run.get('execution_recording')
    station_id = handed.get('run_id') or (recording or {}).get('cubos_run_id')
    result = {'run': None, 'recording': recording, 'reachable': False, 'station_url': (recording or {}).get('station_url', CUBOS_URL)}
    if not station_id:
        return result
    url = (recording or {}).get('station_url', CUBOS_URL)
    async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
        try:
            response = await client.get(url+f'/api/v1/runs/{station_id}')
            result.update(reachable=response.status_code==200, run=response.json() if response.status_code==200 else None)
            if recording and recording.get('status')=='recording':
                status = await client.get(WORKER+'/status')
                active = status.json().get('recording', {}) if status.status_code==200 else {}
                if active and active.get('id')==recording['id']:
                    result['recording'] = {**recording, **active}
        except (httpx.HTTPError, ValueError):
            pass
    return result
