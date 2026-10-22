"""Proposed human loading instructions derived from the exact protocol artifact.

This is a planning calculation, not live inventory. CubOS remains authoritative
for labware resolution, fluid validation, collision planning and execution.
"""
from copy import deepcopy
import hashlib
import json
import math

import yaml

from .models import StockPreparation
from .review import human_clearance


def fingerprint(run: dict) -> str:
    plan = run.get("plan") or {}
    value = {"protocol": run.get("protocol_yaml", ""), "setup": run.get("setup_snapshot", {}),
             "stocks": plan.get("stock_preparations", []),
             "manual_steps": plan.get("manual_steps", run.get("manual_steps", [])),
             "manual_interleaving": run.get("manual_interleaving", False)}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _steps(text):
    raw = yaml.safe_load(text) or {}
    steps = raw.get("protocol", [])
    if not isinstance(steps, list):
        raise ValueError("Protocol must contain a list of steps.")
    return steps


def _capacity(deck, position):
    labware = deck.get("labware", {})
    name, _, well = position.partition(".")
    item = labware.get(name, {})
    override = item.get("well_attributes", {}).get(well, {})
    limits = [override.get(key, item.get(key)) for key in ("capacity_ul", "working_volume_ul")]
    limits = [float(x) for x in limits if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0]
    # Do not invent a capacity for unresolved load names/nested geometry.
    return min(limits) if limits else None


def demand(protocol_yaml):
    balance, minimum, touched = {}, {}, set()
    for step in _steps(protocol_yaml):
        if "transfer" in step:
            args = step["transfer"]
            source, dest, volume = args["source"], args["destination"], float(args["volume_ul"])
            if not math.isfinite(volume) or volume <= 0:
                raise ValueError("Transfer volume must be positive and finite.")
            touched.update((source, dest))
            balance[source] = balance.get(source, 0) - volume
            minimum[source] = min(minimum.get(source, 0), balance[source])
            balance[dest] = balance.get(dest, 0) + volume
        elif "mix" in step:
            args = step["mix"]
            position, volume = args["position"], float(args["volume_ul"])
            touched.add(position)
            minimum[position] = min(minimum.get(position, 0), balance.get(position, 0) - volume)
    return {p: round(-v, 6) for p, v in minimum.items() if v < -1e-8}, touched


def apply_stock_preparations(raw_stocks, setup, protocol_yaml):
    """Produce a new proposed fluid seed; never writes to CubOS state."""
    specs = [StockPreparation.model_validate(x) for x in raw_stocks]
    positions = [s.position for s in specs]
    if len(set(positions)) != len(positions):
        raise ValueError("Each stock position must appear only once.")
    needed, touched = demand(protocol_yaml)
    fluids = deepcopy((yaml.safe_load(setup.get("fluids_yaml", "")) or {}).get("fluids", {}))
    deck = yaml.safe_load(setup["deck_yaml"])
    nominal = float(setup.get("nominal_vial_capacity_ul", 5000))
    for spec in specs:
        if spec.position not in needed:
            raise ValueError(f"{spec.position} is not an initially required source in this protocol.")
        capacity = _capacity(deck, spec.position)
        if capacity is None:
            raise ValueError(f"No explicit capacity is available for {spec.position}; supply the resolved deck configuration.")
        capacity = min(capacity, nominal)
        # Preparation reserve is an estimate, not a measured dead-volume floor.
        load = spec.load_volume_ul
        if load is None:
            load = math.ceil((needed[spec.position] + max(200, needed[spec.position] * .1)) / 50) * 50
        if load > capacity:
            raise ValueError(f"{spec.position}: proposed {load:g} uL exceeds the configured/nominal {capacity:g} uL limit. Split the stock across mapped vials or reduce the run.")
        if load < needed[spec.position]:
            raise ValueError(f"{spec.position}: {load:g} uL cannot supply the required {needed[spec.position]:g} uL.")
        fluids[spec.position] = {"volume_ul": load, "composition": {spec.material: load}}
    for position in touched:
        fluids.setdefault(position, {"volume_ul": 0, "composition": {}})
    updated = deepcopy(setup)
    updated["fluids_yaml"] = yaml.safe_dump({"fluids": fluids}, sort_keys=False)
    return updated


def build(run):
    setup = run.get("setup_snapshot") or {}
    plan = run.get("plan") or {}
    issues = []
    result = {"fingerprint": fingerprint(run), "stocks": [], "empty_locations": [],
              "issues": issues, "confirmed": False, "can_confirm": False,
              "nominal_vial_capacity_ul": setup.get("nominal_vial_capacity_ul", 5000),
              "pipette_min_ul": 5, "pipette_max_ul": 120,
              "human_before": [], "human_after": [], "human_between": [], "robot_operations": [],
              "well_peak_ul": 0, "well_capacity_ul": None, "tip_count": 0,
              "note": "Proposed initial loading. This is not a reading of live inventory. Reserves do not establish reachable liquid depth."}
    review = run.get("review") or {}
    current_hash = hashlib.sha256(run.get("protocol_yaml", "").encode()).hexdigest()
    result["validation_ready"] = bool((run.get("validation") or {}).get("passed") and run.get("validation_hash") == current_hash)
    scientific_gaps = bool(plan.get("unresolved")) or review.get("verdict") == "changes_required" or any(f.get("severity") == "critical" for f in review.get("findings", []))
    result["review_ready"] = bool(review and run.get("review_hash") == current_hash and (not scientific_gaps or human_clearance(run)))
    manual = plan.get("manual_steps", run.get("manual_steps", []))
    for step in manual:
        key = "human_" + step.get("when", "before")
        if key in result:
            result[key].append(step.get("instruction", ""))
    result["robot_operations"] = [] if run.get("protocol_edited") else [op.get("purpose", op.get("action", "")) for op in plan.get("operations", [])]
    if not run.get("protocol_yaml"):
        issues.append("Generate a protocol to calculate the loading plan.")
        return result
    try:
        steps = _steps(run["protocol_yaml"])
        needed, touched = demand(run["protocol_yaml"])
        deck = yaml.safe_load(setup["deck_yaml"])
        fluids = (yaml.safe_load(setup.get("fluids_yaml", "")) or {}).get("fluids", {})
        initial = {p: float(v.get("volume_ul", 0)) for p, v in fluids.items()}
        if any(not math.isfinite(v) or v < 0 for v in initial.values()):
            raise ValueError("Initial volumes must be finite and nonnegative.")
        current, peaks = dict(initial), dict(initial)
        gantry = yaml.safe_load(setup["gantry_yaml"])
        if gantry.get("instruments", {}).get("pipette", {}).get("pipette_model") != "picus2_1ch_120":
            issues.append("This loading planner supports the Picus 2 single-channel 5–120 uL profile.")
        outgoing = {}
        for step in steps:
            command, args = next(iter(step.items()))
            if command in ("transfer", "mix"):
                volume = float(args["volume_ul"])
                if not math.isfinite(volume) or not 5 <= volume <= 120 or not math.isclose(volume * 10, round(volume * 10), abs_tol=1e-7):
                    issues.append(f"{command}: {volume:g} uL is outside 5–120 uL in 0.1 uL increments.")
            if command == "transfer":
                source, dest = args["source"], args["destination"]
                outgoing[source] = outgoing.get(source, 0) + volume
                current[source] = current.get(source, 0) - volume
                if current[source] < -1e-7:
                    issues.append(f"{source} runs out before the protocol completes.")
                current[dest] = current.get(dest, 0) + volume
                peaks[dest] = max(peaks.get(dest, 0), current[dest])
            elif command == "mix" and volume > current.get(args["position"], 0):
                issues.append(f"{args['position']}: mixing volume exceeds the liquid present.")
            elif command == "pick_up_tip":
                result["tip_count"] += 1
        specs = {s["position"]: s for s in plan.get("stock_preparations", [])}
        nominal = float(result["nominal_vial_capacity_ul"])
        for position in sorted(touched):
            capacity = _capacity(deck, position)
            peak = peaks.get(position, 0)
            if capacity is None:
                issues.append(f"{position}: capacity unavailable in the supplied deck; use a resolved setup.")
            elif peak > capacity + 1e-7:
                issues.append(f"{position}: peak {peak:g} uL exceeds its {capacity:g} uL working limit.")
            if position not in needed and initial.get(position, 0) == 0:
                result["empty_locations"].append(position)
            if position.startswith("plate."):
                result["well_peak_ul"] = max(result["well_peak_ul"], peak)
                if capacity is not None:
                    result["well_capacity_ul"] = min(result["well_capacity_ul"] or capacity, capacity)
        # Include all initially loaded, used containers, even if the protocol
        # could technically run without their initial contents.
        external = sorted(set(needed) | {p for p in touched if initial.get(p, 0) > 0})
        for position in external:
            spec = specs.get(position, {})
            capacity = _capacity(deck, position)
            effective = min(capacity, nominal) if capacity is not None else None
            load = initial.get(position, 0)
            composition = (fluids.get(position) or {}).get("composition", {})
            material = spec.get("material") or ", ".join(composition) or "Unspecified stock"
            concentration, preparation = spec.get("concentration", "").strip(), spec.get("preparation", "").strip()
            if not concentration or not preparation:
                issues.append(f"{position}: enter the stock concentration and preparation instructions.")
            if effective is not None and load > effective:
                issues.append(f"{position}: load {load:g} uL exceeds its {effective:g} uL source limit.")
            if load < needed.get(position, 0):
                issues.append(f"{position}: load at least {needed[position]:g} uL plus a verified reserve.")
            result["stocks"].append({"position": position, "material": material,
                "concentration": concentration, "preparation": preparation,
                "load_volume_ul": load, "minimum_required_ul": needed.get(position, 0),
                "consumed_ul": outgoing.get(position, 0), "remaining_ul": current.get(position, 0),
                "capacity_ul": capacity, "effective_capacity_ul": effective,
                "citations": spec.get("citations", [])})
        if not result["stocks"]:
            issues.append("No prepared source stocks could be identified.")
        if run.get("manual_interleaving") or result["human_between"]:
            issues.append("Human actions interrupt the robot sequence. Split this into separate runs before using Run.")
    except (ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError, StopIteration) as exc:
        issues.append(f"Loading calculation could not complete: {type(exc).__name__}: {exc}")
    result["issues"] = list(dict.fromkeys(issues))
    result["can_confirm"] = not result["issues"]
    confirmation = run.get("loading_confirmation") or {}
    required = {s["position"] for s in result["stocks"]}
    result["confirmed"] = bool(result["can_confirm"] and confirmation.get("fingerprint") == result["fingerprint"]
        and set(confirmation.get("loaded_positions", [])) == required and confirmation.get("human_steps_confirmed"))
    result["confirmed_at"] = confirmation.get("at") if result["confirmed"] else None
    return result
