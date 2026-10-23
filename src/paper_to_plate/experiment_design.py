"""Deterministic mixture design. Recipes are proposals, not paper facts."""
import math
import random
from copy import deepcopy

import yaml
from pydantic import Field

from .compiler import compile_plan
from .models import StrictModel
from .preparation import apply_stock_preparations

COLORS = ("red", "yellow", "blue")


class MixtureSettings(StrictModel):
    total_ul: int = Field(default=120, ge=30, le=240, multiple_of=6)
    dye_percent: int = Field(default=50, ge=10, le=90, multiple_of=10)
    blocks: int = Field(default=1, ge=1, le=2)
    seed: int = Field(default=42, ge=0, le=1000000)
    target_hex: str = Field(default="#4a956f", pattern=r"^#[0-9a-fA-F]{6}$")
    red_source: str = Field(default="10_vial_holder.A1", max_length=100)
    yellow_source: str = Field(default="10_vial_holder.A2", max_length=100)
    blue_source: str = Field(default="10_vial_holder.A3", max_length=100)
    water_source: str = Field(default="10_vial_holder.A4", max_length=100)
    source_height_mm: float = Field(default=0,ge=-100,le=0,allow_inf_nan=False)
    start_row: str = Field(default="A", pattern=r"^[A-H]$")
    first_tip: str = Field(default="A1", pattern=r"^[A-H](?:[1-9]|1[0-2])$")


def design_mixtures(settings: MixtureSettings):
    dye_units = settings.total_ul * settings.dye_percent // 10  # 0.1-uL units
    total_units = settings.total_ul * 10
    if dye_units % 6:
        raise ValueError("Choose volumes that split exactly into halves and thirds in 0.1 uL increments.")
    if dye_units // 3 < 50 or total_units - dye_units < 50:
        raise ValueError("Every nonzero dye and water transfer must be at least 5 uL. Increase total volume or dye fraction.")
    recipes = [("Red reference", (1, 0, 0), 1, "reference"), ("Yellow reference", (0, 1, 0), 1, "reference"),
        ("Blue reference", (0, 0, 1), 1, "reference"), ("Red + yellow", (1, 1, 0), 2, "mixture"),
        ("Red + blue", (1, 0, 1), 2, "mixture"), ("Yellow + blue", (0, 1, 1), 2, "mixture")]
    recipes += [(f"Center repeat {i + 1}", (1, 1, 1), 3, "technical_repeat") for i in range(3)]
    recipes += [("Water blank", (0, 0, 0), 1, "blank")]
    if ord(settings.start_row) - 65 + settings.blocks > 8:
        raise ValueError("The requested rows exceed the 96-well plate.")
    rows = []
    for block in range(settings.blocks):
        shuffled = list(recipes)
        random.Random(settings.seed + block).shuffle(shuffled)
        for column, (label, weights, divisor, role) in enumerate(shuffled, 1):
            volumes = {c: dye_units * w // divisor / 10 for c, w in zip(COLORS, weights)}
            volumes["water"] = round(settings.total_ul - sum(volumes.values()), 1)
            rows.append({"well": f"{chr(ord(settings.start_row) + block)}{column}", "block": block + 1, "label": label, "role": role,
                         "volumes_ul": volumes, "total_ul": settings.total_ul, "origin": "calculated",
                         "rationale": "Water background" if role == "blank" else "Center repeatability" if role == "technical_repeat" else "Sample the constrained red/yellow/blue mixture space"})
    return {"kind": "three-component mixture screen", "wells": rows, "seed": settings.seed,
        "well_count": len(rows), "target_hex": settings.target_hex,
        "replicate_note": "Center wells are technical repeats from the same stocks, not independent biological replicates.",
        "metric": "Euclidean distance in camera RGB; uncalibrated and comparable only within a fixed imaging setup.",
        "limitations": ["This is a first-round screen, not a guarantee of reaching the target or a fitted optimization model.",
            "Dye proportions sum to a fixed total. This is a mixture design, not independent factorial dosing.",
            "Swatches identify ingredients and the target; mixed colors must be measured, not predicted by averaging RGB."]}


def check_position(deck, position):
    try:
        name, well = position.rsplit(".", 1)
        labware = deck["labware"][name]
        row, col = ord(well[0]) - 65, int(well[1:]) - 1
        if not 0 <= row < labware["rows"] or not 0 <= col < labware["columns"]:
            raise ValueError()
        limits = [labware[k] for k in ("capacity_ul", "working_volume_ul") if k in labware]
        if not limits:
            raise ValueError()
        return min(limits)
    except (KeyError, ValueError, IndexError, TypeError) as exc:
        raise ValueError(f"{position}: select a valid mapped well with an explicit capacity in this setup.") from exc


def compile_design(settings: MixtureSettings, setup: dict, design: dict):
    setup = deepcopy(setup)
    deck = yaml.safe_load(setup["deck_yaml"])
    sources = {c: getattr(settings, c + "_source") for c in (*COLORS, "water")}
    if len(set(sources.values())) != 4:
        raise ValueError("Each dye and water needs a distinct source position.")
    targets = {"plate." + row["well"] for row in design["wells"]}
    if targets & set(sources.values()):
        raise ValueError("Sources must be separate from the experiment wells.")
    for position in sources.values():
        check_position(deck, position)
    for target in targets:
        if settings.total_ul > check_position(deck, target):
            raise ValueError(f"{target}: total volume exceeds the configured working capacity.")
    setup["first_tip"] = settings.first_tip
    setup["fluids_yaml"] = "fluids: {}\n"  # An explicit proposed empty-plate loading plan, never live state.
    setup["materials"] = "; ".join(f"{pos}: {color} working stock" for color, pos in sources.items())
    operations = []
    for row in design["wells"]:
        parts = [(c, row["volumes_ul"][c]) for c in ("water", *COLORS) if row["volumes_ul"][c] > 0]
        for index, (color, volume) in enumerate(parts):
            operations.append({"action": "transfer", "source": sources[color], "destinations": ["plate." + row["well"]],
                "volume_ul": volume, "source_height": settings.source_height_mm, "mix_after_ul": min(60, settings.total_ul / 2) if index == len(parts) - 1 else 0,
                "mix_after_cycles": 3, "purpose": f"{row['well']} · {row['label']}: add {volume:g} uL {color}", "citations": []})
    stocks = [{"position": pos, "material": color + (" working dye" if color != "water" else ""),
        "concentration": "Water, no added dye" if color == "water" else "User-provided working stock; absolute dye concentration unmeasured",
        "preparation": "Load clean water." if color == "water" else f"Use the same well-mixed {color} working stock throughout. Record product and dilution. Pilot for visible, unsaturated camera response before this screen.",
        "load_volume_ul": None, "citations": []} for color, pos in sources.items()]
    plan = {"title": "Find the closest color · RYB mixture screen", "summary": f"{len(design['wells'])} wells at {settings.total_ul} µL, with a water blank and repeated center recipe.",
        "operations": operations, "stock_preparations": stocks,
        "manual_steps": [{"when": "before", "instruction": "Confirm source identities, source row, stock depths, empty destination wells, fresh tips and physical calibration in CubOS. Load the proposed amounts only after review.", "reason": "The setup is a draft snapshot, not live inventory."},
            {"when": "before", "instruction": "Use diffuse fixed lighting, a white reference and fixed camera exposure/white balance. Prefer a physical target viewed beside the plate.", "reason": "Camera RGB depends on illumination and imaging settings."},
            {"when": "after", "instruction": "Image all wells after mixing and bubbles settle. Measure central well regions, avoiding glare; record RGB and image reference for each well.", "reason": "Compare observed colors with the target under the same imaging conditions."}],
        "assumptions": ["Proposed adaptation from a CMYK literature workflow to the user's red/yellow/blue dyes.",
            "Total volume, dye dilution, mixture levels, repeat count and mixing settings are local design choices, not reported paper parameters."],
        "unresolved": []}
    compiled = compile_plan(plan, setup)
    setup = apply_stock_preparations(stocks, setup, compiled["protocol_yaml"])
    return plan, compiled, setup


def rank_colors(design, measurements, target):
    expected = {w["well"]: w for w in design["wells"]}
    seen, ranked = set(), []
    for row in measurements:
        if row["well"] not in expected or row["well"] in seen:
            raise ValueError("Measurements must name unique wells from this design.")
        seen.add(row["well"])
        rgb = row["rgb"]
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb, target)))
        ranked.append({**row, "distance": round(distance, 3), "label": expected[row["well"]]["label"],
                       "role": expected[row["well"]]["role"]})
    ranked.sort(key=lambda x: x["distance"])
    candidates = [r for r in ranked if r["role"] != "blank"]
    return {"ranked": ranked, "best": candidates[0] if candidates else None,
            "measured_wells": len(seen), "expected_wells": len(expected), "complete": len(seen) == len(expected),
            "note": "Observed camera-RGB distance only. No calibrated absorbance, physical accuracy, or global optimum is established."}
