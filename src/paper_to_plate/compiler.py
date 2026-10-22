import hashlib
import math

import yaml

from .models import Plan


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def split_strokes(volume_ul: float) -> list[float]:
    units = round(volume_ul * 10)
    if not math.isclose(volume_ul * 10, units, abs_tol=1e-7) or units < 50:
        raise ValueError("Picus 120 transfers require at least 5 uL and 0.1 uL increments; prepare a reviewed dilution for smaller amounts.")
    count = math.ceil(units / 1200)
    whole, remainder = divmod(units, count)
    return [(whole + (1 if i < remainder else 0)) / 10 for i in range(count)]


def compile_plan(raw: dict, setup: dict) -> dict:
    plan = Plan.model_validate(raw)
    if not plan.operations:
        raise ValueError("No supported liquid-handling operations were identified.")
    gantry = yaml.safe_load(setup["gantry_yaml"])
    if gantry.get("instruments", {}).get("pipette", {}).get("pipette_model") != "picus2_1ch_120":
        raise ValueError("The current generator compiler targets the Picus 2 single-channel 120 uL setup. Import a native protocol or add a supported compiler profile for another pipette.")
    deck = yaml.safe_load(setup["deck_yaml"])["labware"]
    rack_name = next((k for k, v in deck.items() if v.get("type") == "tip_rack"), None)
    waste = next((k for k in deck if "waste" in k.lower()), None)
    if not rack_name or not waste:
        raise ValueError("This compiler needs an identified tip rack and waste location.")
    rack = deck[rack_name]
    slots = [f"{chr(65 + r)}{c}" for r in range(rack.get("rows", 8)) for c in range(1, rack.get("columns", 12) + 1)]
    first = setup.get("first_tip", "A1")
    if first not in slots:
        raise ValueError("First tip is outside the supplied rack.")
    slots = [s for s in slots[slots.index(first):] if rack.get("tip_present", {}).get(s, True)]
    steps, trace = [], []
    tip_index = 0

    def add(command, args, operation_index, purpose):
        trace.append({"index": len(steps), "command": command, "args": args, "operation_index": operation_index, "summary": purpose})
        steps.append({command: args})

    def new_tip(index):
        nonlocal tip_index
        if tip_index >= len(slots):
            raise ValueError("The plan requires more fresh tips than the supplied setup has available.")
        add("pick_up_tip", {"position": f"{rack_name}.{slots[tip_index]}"}, index, "Pick up a fresh tip")
        tip_index += 1

    for index, operation in enumerate(plan.operations):
        for mixing in ([operation.volume_ul] if operation.action == "mix" else ([operation.mix_after_ul] if operation.mix_after_ul else [])):
            if mixing < 5 or mixing > 120 or not math.isclose(mixing * 10, round(mixing * 10), abs_tol=1e-7):
                raise ValueError("Mixing must stay within 5–120 uL in 0.1 uL increments.")
        for target in operation.destinations:
            if operation.action == "transfer":
                if not operation.source:
                    raise ValueError("Transfer source is missing.")
                # Integer 0.1-uL units preserve totals without an undersized remainder.
                strokes = split_strokes(operation.volume_ul)
                for stroke, volume in enumerate(strokes):
                    new_tip(index)
                    add("transfer", {"source": operation.source, "destination": target, "volume_ul": volume, "speed": 50.0, "source_height": operation.source_height, "destination_height": operation.destination_height}, index, operation.purpose)
                    if operation.mix_after_ul and stroke == len(strokes) - 1:
                        add("mix", {"position": target, "volume_ul": operation.mix_after_ul, "cycles": operation.mix_after_cycles, "speed": 50.0, "height": operation.destination_height}, index, "Mix the destination")
                    add("drop_tip", {"position": waste}, index, "Discard the used tip")
            else:
                new_tip(index)
                add("mix", {"position": target, "volume_ul": operation.volume_ul, "cycles": operation.cycles, "speed": 50.0, "height": operation.destination_height}, index, operation.purpose)
                add("drop_tip", {"position": waste}, index, "Discard the used tip")
    text = "# Generated draft. Offline validation is not physical validation.\n" + yaml.safe_dump({"protocol": steps}, sort_keys=False)
    return {"protocol_yaml": text, "protocol_hash": digest(text), "steps": trace, "tip_count": tip_index, "manual_interleaving": any(s.when == "between" for s in plan.manual_steps)}


def describe_yaml(text: str) -> list[dict]:
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict) or not isinstance(raw.get("protocol"), list) or not raw["protocol"]:
        raise ValueError("Expected a nonempty CubOS protocol list.")
    rows = []
    for index, step in enumerate(raw["protocol"]):
        if not isinstance(step, dict) or len(step) != 1:
            raise ValueError(f"Step {index + 1} must contain one command.")
        command, args = next(iter(step.items()))
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise ValueError(f"Step {index + 1} arguments must be a mapping.")
        rows.append({"index": index, "command": command, "args": args, "summary": f"{command.replace('_', ' ').capitalize()} {args.get('destination', args.get('position', ''))}".strip()})
    return rows
