import asyncio
import json
import os
import tempfile
from pathlib import Path

import yaml

from .config import CUBOS_PYTHON


async def validate(setup: dict, protocol_yaml: str) -> dict:
    if not CUBOS_PYTHON or not Path(CUBOS_PYTHON).is_file():
        return {"passed": False, "available": False, "errors": ["Configure a Python interpreter with the compatible installed CubOS package."], "output": "", "hardware_contacted": False}
    with tempfile.TemporaryDirectory(prefix="paper-to-plate-validation-") as temp:
        directory = Path(temp)
        paths = []
        for name, data in (("gantry", setup["gantry_yaml"]), ("deck", setup["deck_yaml"]), ("protocol", protocol_yaml), ("fluids", setup.get("fluids_yaml", ""))):
            if not data:
                continue
            path = directory / f"{name}.yaml"
            path.write_text(data)
            paths.append(str(path))
        process = await asyncio.create_subprocess_exec(CUBOS_PYTHON, str(Path(__file__).with_name("validation_worker.py")), *paths, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env={k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "TMPDIR", "LANG", "SYSTEMROOT")})
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=90)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return {"passed": False, "available": True, "errors": ["CubOS offline validation exceeded its time limit."], "output": "", "hardware_contacted": False}
        if process.returncode:
            return {"passed": False, "available": True, "errors": ["The configured CubOS validator could not complete. Check runtime compatibility."], "output": stderr.decode(errors="replace")[-6000:], "hardware_contacted": False}
        try:
            return {**json.loads(stdout), "available": True, "fluids_checked": bool(setup.get("fluids_yaml"))}
        except ValueError:
            return {"passed": False, "available": True, "errors": ["CubOS validator returned an unreadable result."], "output": "", "hardware_contacted": False}


def score(run: dict, setup: dict, paper: dict | None = None) -> dict:
    protocol = yaml.safe_load(run.get("protocol_yaml", "")) or {}
    fluids = (yaml.safe_load(setup.get("fluids_yaml", "")) or {}).get("fluids", {})
    volumes = {key: float(value.get("volume_ul", 0)) for key, value in fluids.items()}
    transfers, moved, tips = 0, 0.0, []
    for step in protocol.get("protocol", []):
        if "transfer" in step:
            args = step["transfer"]
            volume = float(args.get("volume_ul", 0))
            volumes[args["source"]] = volumes.get(args["source"], 0) - volume
            volumes[args["destination"]] = volumes.get(args["destination"], 0) + volume
            transfers += 1
            moved += volume
        if "pick_up_tip" in step:
            tips.append(step["pick_up_tip"]["position"])
    criteria = []
    rubric = run.get("rubric", {})
    for rule in rubric.get("criteria", []):
        if rule.get("type") == "final_volume":
            observed = volumes.get(rule.get("target"))
            expected = rule.get("expected_ul")
            passed = observed is not None and isinstance(expected, (int, float)) and abs(observed - expected) <= float(rule.get("tolerance_ul", 0.01))
            criteria.append({"label": rule.get("label", rule.get("target", "Final volume")), "passed": passed, "observed": observed, "expected": expected})
        else:
            criteria.append({"label": rule.get("label", "Unsupported criterion"), "passed": None, "reason": "This criterion requires human review or an independent measurement."})
    citations = [c for op in run.get("plan", {}).get("operations", []) for c in op.get("citations", [])]
    verified_citations = 0
    if paper:
        pages = {x["page"]: " ".join(x["text"].split()).casefold() for x in paper.get("pages", [])}
        for citation in citations:
            quote = " ".join(citation.get("quote", "").split()).casefold()
            if quote and quote in pages.get(citation.get("page"), ""):
                verified_citations += 1
    return {"transfer_count": transfers, "transferred_ul": round(moved, 3), "tips": len(tips), "unique_tips": len(set(tips)), "final_volumes": volumes, "criteria": criteria, "rubric_approved": bool(rubric.get("approved")), "rubric_reviewer": rubric.get("reviewer", ""), "citations": len(citations), "citations_text_verified": verified_citations, "physical_outcome": "Not measured", "note": "Text matches establish citation presence, not scientific correctness. Physical outcomes require independent measurements."}
