import asyncio
import csv
import io
import json
import mimetypes
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

import httpx
import yaml
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader, PdfWriter

from . import handoff, pipeline, store, preparation
from .analysis import analyze_bradford
from .compiler import describe_yaml, digest
from .config import CUBOS_PYTHON, CUBOS_URL, DATA, MODEL, PORT, ROOT
from .models import AdjudicationInput, EvidenceInput, HandoffInput, ProtocolEdit, RubricInput, RunInput, SetupInput, PreparationEdit, LoadingConfirmation
from .review import fingerprint, human_clearance
from .seed import seed
from .validation import score, validate
from .vision_proxy import router as vision_router
from .bond import router as bond_router
from .design_api import router as design_router


def read(kind, key):
    try:
        return store.get(kind, key)
    except (KeyError, ValueError):
        raise HTTPException(404, "Artifact not found")


def present_run(value):
    return {**value, "preparation": preparation.build(value)}


@asynccontextmanager
async def lifespan(app):
    seed()
    for run in store.list_all("runs"):
        if run.get("status") in ("running", "queued"):
            store.update_run(run["id"], status="interrupted", error="The application restarted before this model run finished. No hardware was contacted.")
    yield
    tasks = list(pipeline.ACTIVE.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Ursa Paper to Plate", lifespan=lifespan)
app.include_router(vision_router)
app.include_router(bond_router)
app.include_router(design_router)
HANDOFF_LOCKS: dict[str, asyncio.Lock] = {}


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    allowed = {f"localhost:{PORT}", f"127.0.0.1:{PORT}", "testserver"}
    if request.headers.get("host", "") not in allowed:
        return JSONResponse({"detail": "Unrecognized application host"}, status_code=400)
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin and urlsplit(origin).netloc not in allowed:
            return JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/api/status")
def status():
    problem = pipeline.llm.configuration_error()
    return {"provider": "Ollama", "model": MODEL, "provider_configured": problem is None, "configuration_error": problem, "validator_available": bool(CUBOS_PYTHON and Path(CUBOS_PYTHON).is_file()), "cubos_url": CUBOS_URL, "active_runs": len(pipeline.ACTIVE), "morning_doc_url": os.getenv("PAPER_TO_PLATE_MORNING_DOC_URL", "")}


@app.get("/api/papers")
def papers():
    return [{k: v for k, v in p.items() if k != "pages"} for p in store.list_all("papers")]


@app.get("/api/papers/{paper_id}")
def paper(paper_id: str):
    return read("papers", paper_id)


@app.get("/api/papers/{paper_id}/file")
def paper_file(paper_id: str):
    value = read("papers", paper_id)
    if not value.get("file_path"):
        raise HTTPException(404, "This example contains reference notes, not an uploaded PDF.")
    return FileResponse(DATA / value["file_path"], media_type=value["mime_type"], filename=value["filename"], content_disposition_type="inline")


@app.post("/api/papers", status_code=201)
async def upload_paper(file: UploadFile = File(...)):
    content = await file.read(25 * 1024 * 1024 + 1)
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "Paper uploads are limited to 25 MB.")
    filename = Path(file.filename or "paper.pdf").name
    suffix = Path(filename).suffix.lower()
    if suffix not in (".pdf", ".txt", ".md"):
        raise HTTPException(400, "Upload a PDF, text or Markdown source.")
    try:
        if suffix == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise ValueError("The uploaded file is not a PDF.")
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 400:
                raise ValueError("Use an unencrypted PDF with at most 400 pages.")
            pages = [{"page": i + 1, "text": page.extract_text() or ""} for i, page in enumerate(reader.pages)]
            mime = "application/pdf"
        else:
            pages = [{"page": 1, "text": content.decode("utf-8")}]
            mime = "text/plain"
        characters = sum(len(p["text"]) for p in pages)
        if characters < 40:
            raise ValueError("No useful text was extracted. OCR the scanned paper first or upload its text.")
        if characters > 2000000:
            raise ValueError("The source text is too large; upload the relevant paper and methods separately.")
    except Exception as exc:
        raise HTTPException(400, str(exc) if isinstance(exc, ValueError) else "The PDF could not be read.") from exc
    key = uuid.uuid4().hex
    path = store.folder("uploads") / (key + suffix)
    path.write_bytes(content)
    value = store.save("papers", {"id": key, "created_at": time.time(), "title": filename.rsplit(".", 1)[0], "filename": filename, "source_kind": "uploaded_pdf" if suffix == ".pdf" else "uploaded_text", "mime_type": mime, "file_path": str(path.relative_to(DATA)), "pages": pages, "page_count": len(pages), "characters": characters, "sha256": __import__("hashlib").sha256(content).hexdigest()})
    return value


@app.get("/api/setups")
def setups():
    return store.list_all("setups")


@app.get("/api/library")
def library():
    path = ROOT / "examples" / "review-library.json"
    items = json.loads(path.read_text()) if path.exists() else []
    for item in items:
        item["documents"] = [doc for doc in item.get("documents", []) if (ROOT / "examples" / "library" / doc["filename"]).is_file()]
    return items


def library_item(rank: int):
    item = next((x for x in library() if x["rank"] == rank), None)
    if item is None:
        raise HTTPException(404, "Library paper not found")
    return item


@app.get("/api/library/{rank}/pdf/{index}")
def library_pdf(rank: int, index: int):
    item = library_item(rank)
    if not 0 <= index < len(item["documents"]):
        raise HTTPException(404, "This document is not available locally")
    path = ROOT / "examples" / "library" / item["documents"][index]["filename"]
    if not path.is_file():
        raise HTTPException(404, "This document is not available locally")
    return FileResponse(path, media_type="application/pdf", content_disposition_type="inline")


@app.post("/api/library/{rank}/use")
async def use_library(rank: int):
    item = library_item(rank)
    for paper in store.list_all("papers"):
        if paper.get("library_rank") == rank:
            return paper
    document = next((d for d in item["documents"] if d["role"] == "main_article"), None)
    if not document:
        raise HTTPException(404, "This is a metadata lead. Retrieve its paper before using it as a protocol source.")
    documents = sorted(item["documents"], key=lambda d: d["role"] != "main_article")
    writer, page_map = PdfWriter(), []
    for doc in documents:
        path = ROOT / "examples" / "library" / doc["filename"]
        source = PdfReader(path)
        for index, page in enumerate(source.pages):
            writer.add_page(page)
            page_map.append({"document": doc["role"], "original_page": index + 1})
    stream = io.BytesIO()
    writer.write(stream)
    stream.seek(0)
    paper = await upload_paper(UploadFile(filename=f"library-paper-{rank}.pdf", file=stream))
    for page, mapping in zip(paper["pages"], page_map):
        page.update(mapping)
    paper.update(title=item["title"], source_url=item["publication_url"], library_rank=rank, source_doi=item["doi"])
    paper["source_documents"] = documents
    return store.save("papers", paper)


@app.post("/api/setups", status_code=201)
def create_setup(body: SetupInput):
    try:
        for key in ("gantry_yaml", "deck_yaml"):
            if not isinstance(yaml.safe_load(getattr(body, key)), dict):
                raise ValueError("Gantry and deck inputs must be YAML mappings.")
        if body.fluids_yaml and not isinstance(yaml.safe_load(body.fluids_yaml), dict):
            raise ValueError("Initial fluids must be a YAML mapping.")
    except (yaml.YAMLError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return store.create("setups", **body.model_dump())


@app.get("/api/runs")
def runs():
    return [{k: v for k, v in r.items() if k not in ("setup_snapshot", "protocol_yaml", "steps", "attempts", "extraction")} for r in store.list_all("runs")]


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    return present_run(read("runs", run_id))


@app.put("/api/runs/{run_id}/preparation")
def edit_preparation(run_id: str, body: PreparationEdit):
    value = read("runs", run_id)
    if run_id in pipeline.ACTIVE or value.get("handoffs"):
        raise HTTPException(409, "Copy a submitted experiment, or wait for generation to finish, before changing stocks.")
    if body.expected_hash != preparation.fingerprint(value):
        raise HTTPException(409, "The preparation changed. Reload its current version.")
    try:
        stocks = [s.model_dump() for s in body.stocks]
        setup = preparation.apply_stock_preparations(stocks, value["setup_snapshot"], value["protocol_yaml"])
    except (ValueError, KeyError, yaml.YAMLError) as exc:
        raise HTTPException(400, str(exc)) from exc
    value.setdefault("plan", {})["stock_preparations"] = stocks
    value.update(setup_snapshot=setup, loading_confirmation=None, validation=None,
                 validation_hash=None, review=None, review_hash=None, score=None,
                 status="needs_attention", edited_at=time.time())
    if value.get("adjudication"):
        value.setdefault("adjudication_history", []).append(value["adjudication"])
        value["adjudication"] = None
    return present_run(store.save("runs", value))


@app.post("/api/runs/{run_id}/preparation/confirm")
def confirm_loading(run_id: str, body: LoadingConfirmation):
    value = read("runs", run_id)
    if run_id in pipeline.ACTIVE or value.get("handoffs"):
        raise HTTPException(409, "Loading cannot be confirmed during generation or after a submission attempt.")
    sheet = preparation.build(value)
    if body.expected_preparation_hash != sheet["fingerprint"]:
        raise HTTPException(409, "The stocks or protocol changed; review the current loading sheet.")
    if not sheet["can_confirm"]:
        raise HTTPException(409, "; ".join(sheet["issues"]))
    if set(body.loaded_positions) != {s["position"] for s in sheet["stocks"]} or not body.human_steps_confirmed:
        raise HTTPException(400, "Confirm every listed stock and the human preparation steps.")
    value["loading_confirmation"] = {"fingerprint": sheet["fingerprint"],
        "loaded_positions": body.loaded_positions, "human_steps_confirmed": True, "at": time.time()}
    return present_run(store.save("runs", value))


@app.post("/api/runs", status_code=202)
async def new_run(body: RunInput):
    problem = pipeline.llm.configuration_error()
    if problem:
        raise HTTPException(503, problem)
    if len(pipeline.ACTIVE) >= 4:
        raise HTTPException(429, "Four model runs are already queued.")
    source, setup = read("papers", body.paper_id), read("setups", body.setup_id)
    value = store.create("runs", **body.model_dump(), title=source["title"], setup_snapshot=setup, status="queued", stage="extract", events=[], usage=[], evidence={"markers": [], "offset_seconds": 0}, rubric={"approved": False, "reviewer": "", "criteria": []})
    pipeline.start(value["id"])
    return value


@app.post("/api/runs/{run_id}/cancel")
async def cancel_generation(run_id: str):
    value = read("runs", run_id)
    task = pipeline.ACTIVE.get(run_id)
    if task is None:
        raise HTTPException(409, "There is no active generation job. Control any physical run directly in CubOS.")
    store.update_run(run_id, cancel_requested=True, status="cancelled", error="Generation was stopped by the user.")
    task.cancel()
    return read("runs", run_id)


@app.put("/api/runs/{run_id}/protocol")
def edit_protocol(run_id: str, body: ProtocolEdit):
    value = read("runs", run_id)
    if run_id in pipeline.ACTIVE:
        raise HTTPException(409, "Wait for the current model run before editing.")
    if value.get("handoffs"):
        raise HTTPException(409, "A submission attempt already exists. Copy this experiment before editing so the submitted artifact stays intact.")
    try:
        steps = describe_yaml(body.protocol_yaml)
    except (ValueError, yaml.YAMLError) as exc:
        raise HTTPException(400, str(exc)) from exc
    value.update(protocol_yaml=body.protocol_yaml, protocol_hash=digest(body.protocol_yaml), steps=steps, validation=None, validation_hash=None, review=None, review_hash=None, loading_confirmation=None, score=None, status="needs_attention", edited_at=time.time())
    value.pop("execution_summary", None)
    value["protocol_edited"] = True
    if value.get("adjudication"):
        value.setdefault("adjudication_history", []).append(value["adjudication"])
        value["adjudication"] = None
    if value.get("evidence", {}).get("markers"):
        value.setdefault("evidence_history", []).append(value["evidence"])
        value["evidence"] = {**value["evidence"], "markers": [], "notes": value["evidence"].get("notes", "") + " Protocol edited: previous step markers require realignment."}
    return present_run(store.save("runs", value))


@app.post("/api/runs/{run_id}/copy", status_code=201)
def copy_run(run_id: str):
    import copy
    source = read("runs", run_id)
    if run_id in pipeline.ACTIVE:
        raise HTTPException(409, "Wait for the model workflow to finish before copying.")
    fields = {key: copy.deepcopy(source[key]) for key in ("title", "paper_id", "objective", "setup_id", "setup_snapshot", "protocol_yaml", "protocol_hash", "steps", "plan", "manual_steps", "manual_interleaving", "extraction", "demonstration", "execution_summary") if key in source}
    fields["title"] = fields["title"] + " · copy"
    return store.create("runs", **fields, copied_from=run_id, status="needs_attention", stage="source", review=None, validation=None, score=None, events=[], usage=[], evidence={"offset_seconds": 0, "markers": []}, rubric=copy.deepcopy(source.get("rubric", {"approved": False, "reviewer": "", "criteria": []})))


@app.post("/api/runs/{run_id}/validate")
async def validate_run(run_id: str):
    if run_id in pipeline.ACTIVE:
        raise HTTPException(409, "Wait for the model workflow to finish before running a separate validation.")
    value = read("runs", run_id)
    if not value.get("protocol_yaml"):
        raise HTTPException(400, "Generate or import a protocol first.")
    protocol_hash = digest(value["protocol_yaml"])
    setup_version = preparation.fingerprint(value)
    result = await validate(value["setup_snapshot"], value["protocol_yaml"])
    current = read("runs", run_id)
    if digest(current.get("protocol_yaml", "")) != protocol_hash or preparation.fingerprint(current) != setup_version:
        raise HTTPException(409, "The protocol changed while validation was running.")
    current.update(validation=result, validation_hash=protocol_hash)
    try:
        current["score"] = score(current, current["setup_snapshot"], read("papers", current["paper_id"]))
    except (ValueError, KeyError, TypeError):
        current["score"] = {"physical_outcome": "Not measured", "note": "Resolve protocol validation errors before scoring."}
    current["status"] = pipeline.readiness(current)
    return present_run(store.save("runs", current))


@app.post("/api/runs/{run_id}/review")
async def review(run_id: str):
    if run_id in pipeline.ACTIVE:
        raise HTTPException(409, "Wait for the model workflow to finish before starting another review.")
    value = read("runs", run_id)
    if not value.get("protocol_yaml"):
        raise HTTPException(400, "Generate a protocol first.")
    version = digest(value["protocol_yaml"])
    setup_version = preparation.fingerprint(value)
    try:
        result, usage = await pipeline.review_run(read("papers", value["paper_id"]), value["setup_snapshot"], value)
    except Exception as exc:
        raise HTTPException(502, str(exc) if isinstance(exc, pipeline.llm.ModelError) else "The model review did not complete.") from exc
    current = read("runs", run_id)
    if digest(current.get("protocol_yaml", "")) != version or preparation.fingerprint(current) != setup_version:
        raise HTTPException(409, "The protocol changed during review.")
    current.update(review=result, review_hash=version)
    if current.get("adjudication"):
        current.setdefault("adjudication_history", []).append(current["adjudication"])
        current["adjudication"] = None
    current.setdefault("usage", []).append({"stage": "review", **usage})
    current["status"] = pipeline.readiness(current)
    current["error"] = None
    return present_run(store.save("runs", current))


@app.post("/api/runs/{run_id}/adjudication")
def adjudicate(run_id: str, body: AdjudicationInput):
    value = read("runs", run_id)
    if run_id in pipeline.ACTIVE or not value.get("review"):
        raise HTTPException(409, "Complete the model review before recording a human decision.")
    if body.expected_hash != value.get("protocol_hash") or value.get("review_hash") != body.expected_hash:
        raise HTTPException(409, "Review the current protocol revision first.")
    decision = {**body.model_dump(exclude={"expected_hash"}), "at": time.time(), "protocol_hash": body.expected_hash, "review_fingerprint": fingerprint(value["review"]), "review_snapshot": value["review"]}
    value["adjudication"] = decision
    if body.approved and not human_clearance(value):
        raise HTTPException(400, "Provide a substantive response to every critical finding and unresolved plan question before approving.")
    value["status"] = pipeline.readiness(value)
    value["error"] = None
    return present_run(store.save("runs", value))


@app.put("/api/runs/{run_id}/rubric")
def rubric(run_id: str, body: RubricInput):
    value = read("runs", run_id)
    if body.approved and not body.reviewer.strip():
        raise HTTPException(400, "Name the independent reviewer before approving a rubric.")
    value["rubric"] = body.model_dump()
    value["score"] = score(value, value["setup_snapshot"], read("papers", value["paper_id"]))
    return present_run(store.save("runs", value))


@app.put("/api/runs/{run_id}/evidence")
def evidence(run_id: str, body: EvidenceInput):
    value = read("runs", run_id)
    if body.video_id and body.video_id != "demo":
        read("videos", body.video_id)
    for marker in body.markers:
        if not isinstance(marker.get("step_index"), int) or not 0 <= marker["step_index"] < len(value.get("steps", [])):
            raise HTTPException(400, "A marker references an unknown step.")
        seconds = marker.get("seconds")
        if not isinstance(seconds, (int, float)) or not __import__("math").isfinite(seconds) or seconds < 0:
            raise HTTPException(400, "Marker times must be finite and nonnegative.")
    value["evidence"] = {**body.model_dump(), "alignment_method": "manual", "updated_at": time.time()}
    return present_run(store.save("runs", value))


@app.post("/api/videos", status_code=201)
async def upload_video(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".mp4", ".webm", ".mov"):
        raise HTTPException(400, "Upload MP4, WebM or MOV video.")
    key = uuid.uuid4().hex
    path = store.folder("uploads") / (key + suffix)
    total = 0
    try:
        with path.open("wb") as stream:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > 250 * 1024 * 1024:
                    raise HTTPException(413, "Video uploads are limited to 250 MB.")
                stream.write(chunk)
        return store.save("videos", {"id": key, "created_at": time.time(), "filename": Path(file.filename).name, "file_path": str(path.relative_to(DATA)), "bytes": total, "mime_type": mimetypes.guess_type(str(path))[0] or "video/mp4"})
    except BaseException:
        path.unlink(missing_ok=True)
        raise


@app.get("/api/videos/{video_id}")
def video(video_id: str):
    if video_id == "demo":
        path = ROOT / "frontend" / "public" / "assets" / "demo.mp4"
        return FileResponse(path, media_type="video/mp4")
    value = read("videos", video_id)
    return FileResponse(DATA / value["file_path"], media_type=value["mime_type"])


@app.post("/api/runs/{run_id}/measurements")
async def measurements(run_id: str, file: UploadFile = File(...)):
    value = read("runs", run_id)
    if value.get("demonstration", {}).get("kind") == "colored_water":
        raise HTTPException(400, "This is a colored-water demonstration; Bradford protein-concentration analysis does not apply. Attach visual evidence instead.")
    content = await file.read(1024 * 1024 + 1)
    if len(content) > 1024 * 1024:
        raise HTTPException(413, "Measurement CSV is too large.")
    try:
        result = analyze_bradford(content.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    value["measurements"] = result
    value["measurement_csv"] = content.decode("utf-8-sig")
    value["measurement_imported_at"] = time.time()
    return present_run(store.save("runs", value))


@app.get("/api/measurements/template")
def measurements_template():
    text = "well,role,protein_ug,a590,a450,sample_id,dilution_factor,sample_volume_ul,expected_ug_ml\nA10,blank,,,,,,,\nA1,standard,0,,,,,,\nA2,standard,1,,,,,,\nA3,standard,2,,,,,,\nA7,sample,,,,unknown_1,10,100,\n"
    return Response(text, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="bradford-reader-template.csv"'})


@app.get("/api/runs/{run_id}/export")
def export_run(run_id: str):
    value = read("runs", run_id)
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("protocol.yaml", value.get("protocol_yaml", ""))
        for key, filename in (("gantry_yaml", "gantry.yaml"), ("deck_yaml", "deck.yaml"), ("fluids_yaml", "initial_fluids.yaml")):
            archive.writestr(filename, value["setup_snapshot"].get(key, ""))
        archive.writestr("evaluation.json", json.dumps(value, indent=2))
        archive.writestr("preparation.json", json.dumps(preparation.build(value), indent=2))
        for capture in value.get('vision_captures', []):
            key = capture.get('id', '')
            if len(key) == 32 and all(c in '0123456789abcdef' for c in key):
                image = ROOT / 'data' / 'vision' / 'captures' / f'{key}.jpg'
                if image.is_file():
                    archive.write(image, f'vision/{key}.jpg')
        source = read("papers", value["paper_id"])
        archive.writestr("source/metadata.json", json.dumps(source, ensure_ascii=False, indent=2))
        if source.get("file_path"):
            original = DATA / source["file_path"]
            archive.write(original, "source/original" + original.suffix)
        else:
            archive.writestr("source/reference-notes.txt", "\n\n".join(p["text"] for p in source.get("pages", [])))
        archive.writestr("READ-ME.txt", "Generated or imported research draft. Offline checks do not establish physical validity. Review source facts, unresolved questions, setup calibration, manual steps and readout equipment before an operator runs this in CubOS.\n")
    return Response(output.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="paper-to-plate-{run_id[:8]}.zip"'})


@app.get("/api/cubos/status")
async def cubos_status():
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            response = await client.get(CUBOS_URL + "/api/v1/protocol/run-status")
        return {"reachable": response.status_code == 200, "url": CUBOS_URL, "run_status": response.json() if response.status_code == 200 else None}
    except (httpx.HTTPError, ValueError):
        return {"reachable": False, "url": CUBOS_URL}


@app.post("/api/runs/{run_id}/handoff")
async def send_to_cubos(run_id: str, body: HandoffInput):
    async with HANDOFF_LOCKS.setdefault(run_id, asyncio.Lock()):
        value = read("runs", run_id)
        key = "mock" if body.mock_mode else "hardware"
        existing = value.get("handoffs", {}).get(key)
        if existing:
            raise HTTPException(409, "This experiment already has a submission attempt in that mode. Inspect CubOS; do not replay it from here.")
        # The app never calls this route during generation or validation.
        try:
            handoff.submission(value, body)
            fresh = await validate(value["setup_snapshot"], value["protocol_yaml"])
            if not fresh["passed"]:
                raise ValueError("Current offline validation failed; the run was not submitted.")
            current = read("runs", run_id)
            if preparation.fingerprint(current) != preparation.fingerprint(value):
                raise ValueError("The protocol or loading plan changed during handoff checks.")
            handoff.submission(current, body)
            value = current
            value.setdefault("handoffs", {})[key] = {"status": "submitting", "at": time.time()}
            store.save("runs", value)
            result = await handoff.send(value, body)
        except (ValueError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, "CubOS did not return a confirmed result. Inspect Operator before any retry; the submission may have been accepted.") from exc
        value["handoff"] = {"at": time.time(), "mock_mode": body.mock_mode, "response": result}
        value["handoffs"][key] = {"status": "accepted", **value["handoff"]}
        store.save("runs", value)
        return result


dist = ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="workbench")
