"""Valency Bond connection, independent of the assistant's own credentials."""
import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from . import store
from .config import PORT

router = APIRouter(prefix="/api/bond", tags=["Valency Bond"])
ENDPOINT = "https://mcp.valency.io/"
AUTH = "https://oauth.valency.io"
RESOURCE = "https://mcp.valency.io"
PENDING: dict[str, dict] = {}
LOCK = asyncio.Lock()


class BondError(RuntimeError):
    pass


def credentials():
    path = store.folder("private") / "bond.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_credentials(value):
    path = store.folder("private") / "bond.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream)
    path.chmod(0o600)


@router.get("/status")
def status():
    saved = credentials()
    return {"connected": bool(os.getenv("VALENCY_ACCESS_TOKEN") or saved.get("access_token")),
            "provider": "Valency Bond", "endpoint": ENDPOINT}


@router.post("/connect")
async def connect():
    callback = f"http://127.0.0.1:{PORT}/api/bond/callback"
    # Fixed official endpoints: no user-controlled auth destination or redirect.
    async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
        try:
            response = await client.post(AUTH + "/register", json={
                "client_name": "Ursa Paper to Plate", "redirect_uris": [callback],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"], "token_endpoint_auth_method": "none"})
            response.raise_for_status()
            registration = response.json()
            client_id = registration["client_id"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise HTTPException(502, "Bond sign-in could not start. Try again when Valency is reachable.") from exc
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    for key in list(PENDING):
        if PENDING[key]["expires"] < time.time():
            PENDING.pop(key)
    PENDING[state] = {"client_id": client_id, "verifier": verifier, "callback": callback, "expires": time.time() + 600}
    return {"url": AUTH + "/authorize?" + urlencode({"response_type": "code", "client_id": client_id,
        "redirect_uri": callback, "scope": "email profile offline_access", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256", "resource": RESOURCE})}


@router.get("/callback")
async def callback(state: str = "", code: str = "", error: str = ""):
    pending = PENDING.pop(state, None)
    if not pending or pending["expires"] < time.time() or not code or error:
        raise HTTPException(400, "Bond sign-in expired or was declined. Start Connect Bond again.")
    async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
        try:
            result = await client.post(AUTH + "/token", data={"grant_type": "authorization_code", "code": code,
                "redirect_uri": pending["callback"], "client_id": pending["client_id"],
                "code_verifier": pending["verifier"], "resource": RESOURCE})
            result.raise_for_status()
            token = result.json()
            if not token.get("access_token"):
                raise ValueError("Missing token")
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(502, "Bond could not complete sign-in. No credentials were exposed.") from exc
    save_credentials({**token, "client_id": pending["client_id"], "expires_at": time.time() + token.get("expires_in", 3600)})
    return RedirectResponse("/?design=1&bond=connected", status_code=303)


async def access_token():
    if os.getenv("VALENCY_ACCESS_TOKEN"):
        return os.environ["VALENCY_ACCESS_TOKEN"]
    async with LOCK:
        saved = credentials()
        if not saved.get("access_token"):
            raise BondError("Connect Valency Bond to search live literature, or open the recorded dye example.")
        if saved.get("expires_at", 0) > time.time() + 60:
            return saved["access_token"]
        if not saved.get("refresh_token"):
            raise BondError("Bond sign-in expired. Connect Bond again.")
        async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
            response = await client.post(AUTH + "/token", data={"grant_type": "refresh_token",
                "client_id": saved["client_id"], "refresh_token": saved["refresh_token"], "resource": RESOURCE})
            if response.status_code != 200:
                raise BondError("Bond sign-in expired. Connect Bond again.")
            token = response.json()
        if not token.get("access_token"):
            raise BondError("Bond returned no access token. Connect Bond again.")
        save_credentials({**saved, **token, "expires_at": time.time() + token.get("expires_in", 3600)})
        return token["access_token"]


def rpc_result(response):
    if response.status_code in (401, 403):
        raise BondError("Bond access expired or was denied. Connect Bond again.")
    if response.status_code == 429:
        raise BondError("Bond's usage limit was reached. Retry after your allowance resets.")
    response.raise_for_status()
    if "text/event-stream" in response.headers.get("content-type", ""):
        messages = [json.loads(line[5:].strip()) for line in response.text.splitlines() if line.startswith("data:") and line[5:].strip()]
        value = next((m for m in messages if "result" in m or "error" in m), {})
    else:
        value = response.json()
    if "error" in value or "result" not in value:
        raise BondError("Bond could not complete the literature request.")
    return value["result"]


async def search(query: str):
    token = await access_token()
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    async with httpx.AsyncClient(timeout=60, trust_env=False, follow_redirects=False) as client:
        initial = await client.post(ENDPOINT, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "paper-to-plate", "version": "0.1.0"}}})
        initialized = rpc_result(initial)
        headers["MCP-Protocol-Version"] = initialized.get("protocolVersion", "2025-03-26")
        if initial.headers.get("mcp-session-id"):
            headers["Mcp-Session-Id"] = initial.headers["mcp-session-id"]
        notification = await client.post(ENDPOINT, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        notification.raise_for_status()
        result = rpc_result(await client.post(ENDPOINT, headers=headers, json={"jsonrpc": "2.0", "id": 2,
            "method": "tools/call", "params": {"name": "semantic_search_papers", "arguments": {
                "query": query[:5000], "limit": 6, "max_authors": 3, "enrich_citations": False}}}))
    if result.get("isError"):
        raise BondError("Bond returned a search error. No evidence was fabricated.")
    content = result.get("structuredContent")
    if not content:
        content = json.loads(next(c["text"] for c in result.get("content", []) if c.get("type") == "text"))
    return {"query": query, "result": content, "retrieved_at": time.time(), "mode": "live"}
