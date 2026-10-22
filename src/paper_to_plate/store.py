import json
import re
import threading
import time
import uuid
from pathlib import Path

from .config import DATA

LOCK = threading.RLock()
ID = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def folder(kind: str) -> Path:
    target = DATA / kind
    target.mkdir(parents=True, exist_ok=True)
    return target


def identifier(value: str) -> str:
    if not ID.fullmatch(value):
        raise ValueError("Invalid artifact identifier")
    return value


def get(kind: str, key: str) -> dict:
    path = folder(kind) / f"{identifier(key)}.json"
    if not path.exists():
        raise KeyError(key)
    return json.loads(path.read_text())


def save(kind: str, obj: dict) -> dict:
    with LOCK:
        obj["updated_at"] = time.time()
        path = folder(kind) / f"{identifier(obj['id'])}.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
        temp.replace(path)
    return obj


def create(kind: str, **fields) -> dict:
    return save(kind, {"id": uuid.uuid4().hex, "created_at": time.time(), **fields})


def list_all(kind: str) -> list[dict]:
    rows = [json.loads(path.read_text()) for path in folder(kind).glob("*.json")]
    return sorted(rows, key=lambda x: x.get("created_at", 0), reverse=True)


def update_run(key: str, **fields) -> dict:
    with LOCK:
        run = get("runs", key)
        run.update(fields)
        return save("runs", run)


def event(key: str, stage: str, status: str, message: str) -> None:
    with LOCK:
        run = get("runs", key)
        run.setdefault("events", []).append({"stage": stage, "status": status, "message": message, "at": time.time()})
        run["stage"] = stage
        save("runs", run)
