import os

import httpx
import yaml

from .compiler import digest
from .config import CUBOS_URL
from .models import HandoffInput
from .review import human_clearance
from .preparation import build as build_preparation


def submission(run: dict, request: HandoffInput) -> dict:
    current_hash = digest(run["protocol_yaml"])
    if request.expected_hash != current_hash or run.get("validation_hash") != current_hash:
        raise ValueError("The protocol changed after validation. Validate and review the current version first.")
    if not (run.get("validation") or {}).get("passed"):
        raise ValueError("CubOS offline validation must pass before handoff.")
    if run.get("manual_interleaving"):
        raise ValueError("This procedure has manual actions between robot steps. Split it into separately reviewed runs first.")
    if not request.mock_mode:
        if run.get("requires_station_refresh"):
            raise ValueError("This draft uses a recorded setup. Reconnect CubOS and prepare it again with current inventory before a physical run.")
        if not all((request.operator_confirmed, request.manual_steps_confirmed, request.setup_confirmed)):
            raise ValueError("The operator must confirm the reviewed procedure, physical setup and manual steps.")
        if not run.get("review") or run.get("review_hash") != current_hash:
            raise ValueError("Review the current protocol before physical handoff.")
        cleared = human_clearance(run)
        if any(f["severity"] == "critical" for f in run["review"].get("findings", [])) and not cleared:
            raise ValueError("Resolve critical reviewer findings before physical handoff.")
        if run["review"].get("verdict") == "changes_required" and not cleared:
            raise ValueError("The reviewer requested changes; resolve them before physical handoff.")
        if run.get("plan", {}).get("unresolved") and not cleared:
            raise ValueError("The generated plan still has unresolved scientific questions.")
        loading = build_preparation(run)
        if not loading["confirmed"] or request.preparation_hash != loading["fingerprint"]:
            raise ValueError("Confirm every stock on the current preparation sheet before a physical Run.")
    setup = run["setup_snapshot"]
    payload = {"run_id": f"paper-{run['id'][:32]}-{'mock' if request.mock_mode else 'hardware'}-{current_hash[:12]}", "gantry_config": setup["gantry_yaml"], "deck_config": setup["deck_yaml"], "protocol_yaml": run["protocol_yaml"], "mock_mode": request.mock_mode, "metadata": {"source": "ursa-paper-to-plate", "benchmark_run_id": run["id"], "protocol_hash": current_hash}}
    if setup.get("station_fluid_state_id") and not request.mock_mode:
        payload["state"] = {"fluid_state_id": setup["station_fluid_state_id"]}
    elif setup.get("fluids_yaml") and not request.mock_mode:
        initial = yaml.safe_load(setup["fluids_yaml"])
        payload["state"] = {"initial_state": {"label": "Paper to Plate operator-verified setup", "fluids": initial["fluids"]}}
    return payload


async def send(run: dict, request: HandoffInput) -> dict:
    payload = submission(run, request)
    token = os.getenv("CUBOS_API_TOKEN", "")
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.post(CUBOS_URL + "/api/v1/runs", json=payload, headers={"Authorization": "Bearer " + token} if token else {})
    if response.status_code != 202:
        detail = response.json().get("detail", "CubOS did not accept the run.") if "application/json" in response.headers.get("content-type", "") else "CubOS did not accept the run."
        raise ValueError(f"CubOS returned HTTP {response.status_code}: {str(detail)[:1000]}")
    return response.json()
