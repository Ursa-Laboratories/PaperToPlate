"""Local observation-only vision worker. Camera acquisition stays in CubOS.

Run with the project's ML environment; the main app proxies this local service.
No movement, protocol or recovery commands are implemented here.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / 'vision'
CAMERA_URL = 'http://127.0.0.1:8090'
PORT = 8793


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False))
    temp.replace(path)


def clean_detections(items, width, height):
    """Bound model output and associate liquid regions with visible tips."""
    cleaned = []
    for item in items:
        try:
            label = str(item['label']).lower()
            confidence = float(item['confidence'])
            x1, y1, x2, y2 = map(float, item['box'])
            if label not in ('tip', 'liquid') or not np.isfinite([confidence, x1, y1, x2, y2]).all():
                continue
            if confidence < .25 or confidence > 1:
                continue
            box = [max(0., min(width, x1)), max(0., min(height, y1)), max(0., min(width, x2)), max(0., min(height, y2))]
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            cleaned.append({'label': label, 'confidence': confidence, 'box': box})
        except (KeyError, TypeError, ValueError):
            continue
    tips = [d for d in cleaned if d['label'] == 'tip']
    result = list(tips)
    for liquid in (d for d in cleaned if d['label'] == 'liquid'):
        a, b, c, d = liquid['box']
        area = (c-a)*(d-b)
        if any(max(0, min(c, t['box'][2])-max(a, t['box'][0])) * max(0, min(d, t['box'][3])-max(b, t['box'][1])) / area >= .5 for t in tips):
            result.append(liquid)
    return result[:100]


def render(image, detections, caption):
    canvas = image.copy().convert('RGB')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=max(12, min(22, canvas.width//80)))
    for d in detections:
        color = '#51dba6' if d['label'] == 'liquid' else '#78b6ff'
        draw.rectangle(d['box'], outline=color, width=3)
        x, y = d['box'][:2]
        label = f"{'T' if d['label'] == 'tip' else 'L'}{d['confidence']*100:.0f}"
        bounds = draw.textbbox((0, 0), label, font=font)
        label_width = bounds[2]+6
        draw.rectangle((x, max(0, y-22), min(canvas.width, x+label_width), max(0, y-22)+22), fill='#102236')
        draw.text((x+3, max(0, y-20)), label, fill=color, font=font)
    draw.rectangle((0, canvas.height-28, canvas.width, canvas.height), fill='#102236')
    draw.text((10, canvas.height-24), caption[:170], fill='white', font=font)
    out = io.BytesIO()
    canvas.save(out, format='JPEG', quality=85)
    return out.getvalue()


class Vision:
    def __init__(self, data=DATA):
        self.data = Path(data)
        self.lock = threading.RLock()
        self.model_lock = threading.Lock()
        self.stop = threading.Event()
        self.threads = []
        self.raw = None
        self.jpeg = None
        self.frame_id = 0
        self.received_at = 0.
        self.changed_at = 0.
        self.frame_hash = ''
        self.capture_error = None
        self.model_error = None
        self.model_id = 'yolo'
        self.loaded_id = None
        self.detector = None
        self.model_fingerprint = None
        self.model_components = {}
        self.result = {}
        self.result_id = 0
        self.session_id = uuid.uuid4().hex
        self.started_at = time.time()
        self.unique_frames = 0
        self.camera_status = {}
        self.recording = None

    def start(self):
        self.stop.clear()
        for target in (self.capture_loop, self.inference_loop):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self.threads.append(thread)

    def close(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(timeout=3)

    def models(self):
        # The model adapter owns checkpoint discovery; do not assume available weights.
        try:
            from .vision_models import available_models
            return available_models(self.data)
        except (ImportError, AttributeError):
            return [{'id': 'yolo', 'label': 'YOLO · trained detector', 'available': False, 'detail': 'Training/checkpoint setup pending'}, {'id': 'dino', 'label': 'DINO · region classifier', 'available': False, 'detail': 'Training/checkpoint setup pending'}]

    def status(self):
        with self.lock:
            now = time.time()
            age = now-self.received_at if self.received_at else None
            repeated = bool(self.changed_at and now-self.changed_at > 3)
            state = 'live'
            warning = 'Research model: source-data evaluation does not establish accuracy on this camera. Liquid regions are not volume measurements.'
            if self.raw is None or self.capture_error:
                state = 'camera_unavailable'
                warning = self.capture_error or 'Waiting for CubOS camera frames.'
            elif age is None or age > 3 or repeated:
                state = 'stale'
                warning = 'Camera frames are missing or repeating. Current tip/liquid state is unknown.'
            elif self.model_error:
                state = 'model_error'
                warning = self.model_error
            elif self.loaded_id != self.model_id:
                state = 'loading_model'
            elif not self.result or now-self.result.get('captured_at', 0) > 3:
                state = 'waiting_for_inference'
            valid = state == 'live' and self.result.get('model') == self.model_id
            detections = self.result.get('detections', []) if valid else []
            result_age = now-self.result['captured_at'] if self.result else None
            return {'state': state, 'camera': 'MX Brio · CubOS camera bridge', 'model': self.model_id,
                    'frame_id': self.result.get('frame_id'), 'capture_frame_id': self.frame_id,
                    'captured_at': self.result.get('captured_at'), 'frame_age_s': result_age, 'capture_age_s': age,
                    'result_age_s': result_age, 'source_repeating': repeated,
                    'inference_ms': self.result.get('inference_ms'),
                    'fps': self.camera_status.get('fps', self.unique_frames/max(1, now-self.started_at)),
                    'detections': detections, 'counts': {'tip': sum(x['label']=='tip' for x in detections), 'liquid': sum(x['label']=='liquid' for x in detections)} if valid else {'tip': None, 'liquid': None},
                    'warning': warning, 'models': self.models(), 'session_id': self.session_id,
                    'timing_basis': 'CubOS bridge frame receipt; not sensor exposure or synchronized protocol time',
                    'recording': self.recording_status(),
                    'training': self.report()}

    def recording_status(self):
        if not self.recording:
            return None
        remaining = max(0., self.recording['ends_at']-time.time())
        return {'id': self.recording['id'], 'active': remaining > 0,
                'frames': self.recording['frames'], 'seconds_remaining': round(remaining, 1)}

    def start_recording(self, duration):
        with self.lock:
            if self.recording_status() and self.recording_status()['active']:
                raise ValueError('A recording is already active.')
            key = uuid.uuid4().hex
            folder = self.data/'recordings'/key
            folder.mkdir(parents=True)
            self.recording = {'id': key, 'ends_at': time.time()+duration, 'frames': 0, 'last_saved': 0.}
            atomic_json(folder/'session.json', {'id': key, 'started_at': time.time(), 'duration_seconds': duration, 'session_id': self.session_id, 'camera': 'MX Brio', 'model': self.model_id, 'protocol_alignment': None, 'label_source': 'model_predictions_unreviewed', 'target_domain_validated': False})
            return self.recording_status()

    def record_observation(self, image, value):
        with self.lock:
            recording = self.recording
            if not recording or time.time() >= recording['ends_at'] or time.time()-recording['last_saved'] < .5:
                return
            if recording['frames'] >= 120:
                return
            folder = self.data/'recordings'/recording['id']
            filename = f"frame-{recording['frames']:04d}.jpg"
            image.save(folder/filename, format='JPEG', quality=88)
            row = {**value, 'image': filename, 'image_sha256': hashlib.sha256((folder/filename).read_bytes()).hexdigest(), 'label_source': 'model_prediction', 'reviewed': False}
            with (folder/'observations.jsonl').open('a') as handle:
                handle.write(json.dumps(row, allow_nan=False)+'\n')
            recording['frames'] += 1
            recording['last_saved'] = time.time()

    def report(self):
        try:
            result = json.loads((self.data/'training-report.json').read_text())
            local = self.data/'local-tip-report.json'
            if local.is_file():
                result['local_tip_calibration'] = json.loads(local.read_text())
            liquid = self.data/'local-liquid-report.json'
            if liquid.is_file():
                result['local_liquid_replay'] = json.loads(liquid.read_text())
            return result
        except (OSError, ValueError):
            return {'status': 'pending', 'target_domain_validated': False}

    def capture_loop(self):
        with httpx.Client(timeout=3, trust_env=False) as client:
            while not self.stop.is_set():
                try:
                    response = client.get(CAMERA_URL+'/frame.jpg')
                    response.raise_for_status()
                    content = response.content
                    if len(content) > 10_000_000:
                        raise ValueError('Camera frame exceeds 10 MB')
                    image = Image.open(io.BytesIO(content)).convert('RGB')
                    digest = hashlib.sha256(content).hexdigest()
                    now = time.time()
                    captured_at = float(response.headers.get('X-Captured-At', now))
                    if not np.isfinite(captured_at) or captured_at > now+5:
                        raise ValueError('Invalid camera timestamp')
                    with self.lock:
                        if digest != self.frame_hash:
                            self.changed_at = now
                            self.unique_frames += 1
                        self.frame_hash = digest
                        self.raw = image
                        self.frame_id += 1
                        self.received_at = captured_at
                        self.capture_error = None
                    if self.frame_id % 10 == 0:
                        r = client.get(CAMERA_URL+'/status')
                        if r.status_code == 200:
                            self.camera_status = r.json()
                except Exception as exc:
                    with self.lock:
                        self.capture_error = f'CubOS camera unavailable: {type(exc).__name__}: {exc}'
                self.stop.wait(.15)

    def load(self, model_id):
        from .vision_models import load_detector
        detector = load_detector(model_id, self.data)
        path = Path(detector.weights) if hasattr(detector, 'weights') else self.data/'models'/'dino-v2-vits14-head.joblib'
        paths = getattr(detector, 'checkpoint_paths', [path])
        components = {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
        fingerprint = hashlib.sha256(json.dumps(components, sort_keys=True).encode()).hexdigest()
        with self.lock:
            self.detector = detector
            self.loaded_id = model_id
            self.model_fingerprint = fingerprint
            self.model_components = components
            self.model_error = None

    def inference_loop(self):
        seen = None
        while not self.stop.is_set():
            with self.lock:
                image = self.raw.copy() if self.raw is not None else None
                frame_id, timestamp, model_id = self.frame_id, self.received_at, self.model_id
                digest = self.frame_hash
            if image is None:
                self.stop.wait(.3)
                continue
            try:
                with self.model_lock:
                    if self.loaded_id != model_id or self.detector is None:
                        self.load(model_id)
                    if seen == (digest, model_id):
                        self.stop.wait(.15)
                        continue
                    start = time.monotonic()
                    items = self.detector.predict(np.array(image))
                    detections = clean_detections(items, *image.size)
                    elapsed = (time.monotonic()-start)*1000
                value = {'frame_id': frame_id, 'captured_at': timestamp, 'model': model_id, 'model_bundle_sha256': self.model_fingerprint, 'model_components': self.model_components, 'source_frame_sha256': digest, 'inference_ms': elapsed, 'detections': detections}
                annotated = render(image, detections, f'{model_id.upper()} | frame {frame_id} | {elapsed:.0f} ms | Research prediction - volume unverified')
                with self.lock:
                    self.result = value
                    self.jpeg = annotated
                    self.result_id += 1
                    self.model_error = None
                seen = (digest, model_id)
                atomic_json(self.data/'latest-observation.json', value)
                self.record_observation(image, value)
            except Exception as exc:
                with self.lock:
                    self.model_error = f'{type(exc).__name__}: {exc}'
                self.stop.wait(3)
            self.stop.wait(.05)

    def image(self):
        state = self.status()['state']
        with self.lock:
            if state == 'live' and self.jpeg:
                return self.jpeg
            base = self.raw.copy() if self.raw is not None else Image.new('RGB', (1280, 720), '#102236')
        return render(base, [], f'{state.replace("_", " ").upper()} | No current validated observation')

    def capture(self, context=None):
        if self.status()['state'] in ('camera_unavailable', 'stale'):
            raise ValueError('A fresh camera frame is required for a review capture.')
        with self.lock:
            key = uuid.uuid4().hex
            image = self.raw.copy()
            timestamp, frame_id = self.received_at, self.frame_id
        folder = self.data/'captures'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder/f'{key}.jpg'
        image.save(path, quality=95)
        value = {'id': key, 'session_id': self.session_id, 'captured_at': timestamp, 'source_frame_id': frame_id, 'image_path': str(path), 'width': image.width, 'height': image.height, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'reviewed': False}
        value['context'] = context or {}
        atomic_json(folder/f'{key}.json', value)
        value['image_url'] = f'/api/vision/captures/{key}/image'
        return value

    def examples(self):
        try:
            return json.loads((self.data/'examples.json').read_text())
        except (OSError, ValueError):
            return []


vision = Vision()


@asynccontextmanager
async def lifespan(app):
    vision.start()
    yield
    vision.close()


app = FastAPI(title='Paper to Plate local vision worker', lifespan=lifespan)


@app.middleware('http')
async def boundary(request: Request, call_next):
    if request.headers.get('host') not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}', 'testserver'):
        return JSONResponse({'detail': 'Local service only'}, status_code=400)
    if request.method != 'GET' and request.headers.get('origin'):
        return JSONResponse({'detail': 'Use the Paper to Plate same-origin API'}, status_code=403)
    result = await call_next(request)
    result.headers['Cache-Control'] = 'no-store'
    return result


@app.get('/status')
def status():
    return vision.status()


class ModelInput(BaseModel):
    model: str = Field(pattern='^(yolo|yolo_source|dino)$')


@app.post('/model')
def select_model(body: ModelInput):
    if not any(m['id'] == body.model and m['available'] for m in vision.models()):
        raise HTTPException(409, 'Model weights are not available; see the training report.')
    with vision.lock:
        vision.model_id = body.model
        vision.model_error = None
    return vision.status()


@app.get('/frame.jpg')
def frame():
    return Response(vision.image(), media_type='image/jpeg')


@app.get('/stream')
async def stream(request: Request):
    async def frames():
        while not await request.is_disconnected():
            data = await asyncio.to_thread(vision.image)
            yield b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data+b'\r\n'
            await asyncio.sleep(.25)
    return StreamingResponse(frames(), media_type='multipart/x-mixed-replace; boundary=frame')


class CaptureInput(BaseModel):
    context: dict[str, str | None] = Field(default_factory=dict)


@app.post('/capture')
def capture(body: CaptureInput | None = None):
    try:
        return vision.capture(body.context if body else None)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


class RecordingInput(BaseModel):
    duration_seconds: int = Field(default=30, ge=5, le=60)


@app.post('/recording')
def record(body: RecordingInput):
    if vision.status()['state'] != 'live':
        raise HTTPException(409, 'Recording requires a fresh camera and working detector.')
    try:
        return vision.start_recording(body.duration_seconds)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get('/recordings/{key}/archive')
def recording_archive(key: str):
    if len(key) != 32 or any(c not in '0123456789abcdef' for c in key):
        raise HTTPException(404)
    folder = vision.data/'recordings'/key
    if not (folder/'session.json').is_file():
        raise HTTPException(404)
    if vision.recording and vision.recording['id'] == key and vision.recording_status()['active']:
        raise HTTPException(409, 'Wait for the recording to finish.')
    output = io.BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix in ('.json', '.jsonl', '.jpg'):
                archive.write(path, path.name)
    return Response(output.getvalue(), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="vision-{key}.zip"'})


@app.get('/captures/{key}/image')
def captured_image(key: str):
    if len(key) != 32 or any(c not in '0123456789abcdef' for c in key):
        raise HTTPException(404)
    path = vision.data/'captures'/f'{key}.jpg'
    if not path.is_file():
        raise HTTPException(404)
    return Response(path.read_bytes(), media_type='image/jpeg')


class BoxInput(BaseModel):
    label: str = Field(pattern='^(tip|liquid)$')
    box: list[float] = Field(min_length=4, max_length=4)


class AnnotationInput(BaseModel):
    frame_id: str = Field(pattern='^[a-f0-9]{32}$')
    boxes: list[BoxInput] = Field(max_length=100)
    reviewed: bool


@app.post('/annotations')
def annotate(body: AnnotationInput):
    path = vision.data/'captures'/f'{body.frame_id}.json'
    if not path.is_file():
        raise HTTPException(404, 'Capture not found')
    value = json.loads(path.read_text())
    for item in body.boxes:
        x1, y1, x2, y2 = item.box
        if not np.isfinite(item.box).all() or not (0 <= x1 < x2 <= value['width'] and 0 <= y1 < y2 <= value['height']):
            raise HTTPException(422, 'Boxes must be finite and inside the original frame.')
    value.update(frame_id=body.frame_id, boxes=[x.model_dump() for x in body.boxes], reviewed=body.reviewed, annotated_at=time.time(), label_source='human_review', purpose='target-domain adaptation; split by capture session')
    atomic_json(vision.data/'annotations'/f'{body.frame_id}.json', value)
    return {'id': body.frame_id, 'reviewed': body.reviewed, 'boxes': len(body.boxes)}


@app.get('/examples')
def examples():
    return [{'id': x['id'], 'label': x['label']} for x in vision.examples()]


@app.get('/examples/{key}/image')
def example_image(key: str):
    item = next((x for x in vision.examples() if x['id'] == key), None)
    if item is None:
        raise HTTPException(404)
    image = Image.open(item['image_path']).convert('RGB')
    try:
        with vision.model_lock:
            if vision.loaded_id != vision.model_id:
                vision.load(vision.model_id)
            detections = clean_detections(vision.detector.predict(np.array(image)), *image.size)
    except Exception as exc:
        raise HTTPException(503, f'Model not ready: {type(exc).__name__}') from exc
    return Response(render(image, detections, 'RECORDED OT-2 VALIDATION EXAMPLE | Not the live camera | Research prediction'), media_type='image/jpeg')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=PORT)
