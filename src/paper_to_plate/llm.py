import json
import os
import time
import re
import uuid

import httpx
from pydantic import BaseModel

from .config import DATA, MODEL, OLLAMA_URL


class ModelError(RuntimeError):
    pass


async def complete(schema: type[BaseModel], system: str, user: str, max_tokens: int = 9000, _format_retry: bool = False) -> tuple[dict, dict]:
    key = os.getenv("OLLAMA_API_KEY", "")
    if OLLAMA_URL == "https://ollama.com" and not key:
        raise ModelError("Ollama is not configured on the server.")
    contract = schema.model_json_schema()
    started = time.monotonic()
    payload = {
        "model": MODEL, "stream": False, "think": "low", "format": contract,
        "options": {"temperature": 0, "num_predict": max_tokens},
        "messages": [
            {"role": "system", "content": system + "\nReturn one JSON object matching this schema. No markdown or extra text.\n" + json.dumps(contract)},
            {"role": "user", "content": user},
        ],
    }
    async with httpx.AsyncClient(timeout=300, follow_redirects=False, trust_env=False) as client:
        try:
            response = await client.post(OLLAMA_URL + "/api/chat", json=payload, headers={"Authorization": "Bearer " + key} if key else {})
        except httpx.HTTPError as exc:
            raise ModelError(f"Ollama connection failed ({type(exc).__name__}).") from exc
    if response.status_code != 200:
        raise ModelError(f"Ollama returned HTTP {response.status_code}. Check account access or usage limits.")
    body = response.json()
    content = body.get("message", {}).get("content", "").strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        try:
            value = json.loads(content)
        except ValueError:
            # Allow explanatory prose around a single valid object; never eval it.
            start = content.find("{")
            if start < 0:
                raise ValueError("No JSON object was returned")
            value, _ = json.JSONDecoder().raw_decode(content[start:])
        parsed = schema.model_validate(value).model_dump()
    except (ValueError, TypeError) as exc:
        errors = [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()] if hasattr(exc, "errors") else [{"message": "Response was not a complete JSON object"}]
        debug = DATA / "model_debug"
        debug.mkdir(parents=True, exist_ok=True)
        path = debug / (uuid.uuid4().hex + ".json")
        path.write_text(json.dumps({"schema": schema.__name__, "done_reason": body.get("done_reason"), "errors": errors, "response_content": content}, ensure_ascii=False))
        path.chmod(0o600)
        if not _format_retry:
            correction = "\nFORMAT CORRECTION: The previous response did not satisfy the schema. Return concise valid JSON with every required field. Do not include explanations outside the object. Use only the declared enum values. Errors: " + json.dumps(errors[:8])
            parsed, retry_usage = await complete(schema, system + correction, user, min(max_tokens * 2, 16000), _format_retry=True)
            retry_usage["format_retries"] = 1
            retry_usage["duration_seconds"] = round(time.monotonic() - started, 2)
            for field, count in (("input_tokens", "prompt_eval_count"), ("output_tokens", "eval_count")):
                retry_usage[field] = (retry_usage.get(field) or 0) + (body.get(count) or 0)
            return parsed, retry_usage
        raise ModelError("The model returned invalid structured data after one format correction. The result was not accepted; try a smaller objective.") from exc
    usage = {"model": MODEL, "duration_seconds": round(time.monotonic() - started, 2), "input_tokens": body.get("prompt_eval_count"), "output_tokens": body.get("eval_count"), "done_reason": body.get("done_reason")}
    return parsed, usage
