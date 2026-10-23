"""Source-specific Bradford surrogate design, reusing the tested liquid plan."""
from copy import deepcopy
import math

import yaml
from pydantic import Field

from .bradford_color_demo import build_color_demo
from .compiler import compile_plan
from .experiment_design import check_position
from .models import StrictModel
from .preparation import build as loading_sheet

QUERY = "Linearization of the Bradford protein assay Ernst Zor 2010 microplate standard curve bovine serum albumin"
EXAMPLE_GOAL = ("Find a plate-based Bradford assay that measures protein in an unknown sample using a standard curve. "
    "Recreate its pipetting structure as a colored-water demonstration: red for standards, yellow for one unknown, "
    "blue for reagent, plus plain water. Include dilution, replicates and blanks. "
    "I have a 120 uL single-channel pipette and a camera, but no protein or absorbance reader.")
SOURCE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC3164080/"
REFERENCE = {"title": "Linearization of the Bradford Protein Assay — Ernst & Zor (2010)", "url": SOURCE_URL,
    "sections": "Detailed protocol, steps 1–11",
    "summary": "The paper quantifies unknown protein using BSA standards and the absorbance ratio A590/A450. This demo preserves the liquid-handling structure using colored water; it does not perform protein chemistry or quantify protein."}
SOURCE_FACTS = [
    {"origin": "reported", "locator": "Steps 1 and 4", "value": "BSA standard: 0.1 mg/mL. Add 0 and 10–50 µL; top up to 100 µL, in triplicate."},
    {"origin": "reported", "locator": "Steps 5 and 6", "value": "Unknown: 100 µL per well. Add 100 µL prepared reagent; final volume 200 µL."},
    {"origin": "reported", "locator": "Steps 8–11", "value": "Use a separate 200 µL water blank. Real quantification requires absorbance at 590 and 450 nm."},
    {"origin": "proposed", "locator": "Demo adaptation", "value": "Red/yellow/blue replace standard/unknown/reagent. One unknown is diluted 1:10. Plate layout, stock reserves and mixing cycles are local choices."},
    {"origin": "proposed", "locator": "Demo scope", "value": "Prepared blue represents working reagent. No extra reagent dilution, color-development wait or protein calculation is performed."},
]


class BradfordSettings(StrictModel):
    replicates: int = Field(default=3, ge=1, le=3)
    first_tip: str = Field(default="A1", pattern=r"^[A-H](?:[1-9]|1[0-2])$")


def supported_source(papers):
    return any(str(p.get("id", "")) == "20386536" or p.get("doi", "").lower().removeprefix("https://doi.org/") == "10.3791/1918" for p in papers)


def build_design(settings: BradfordSettings):
    wells = []
    for row in "ABC"[:settings.replicates]:
        for col in range(1, 9):
            role = "blank" if col == 8 else "sample" if col == 7 else "standard"
            label = "Water blank" if col == 8 else "Unknown · 1:10" if col == 7 else "Reagent-only zero" if col == 1 else f"Standard · {(col - 1) * 10} µL"
            volumes = {"red": (col - 1) * 10 if col <= 6 else 0,
                "diluted_yellow": 100 if col == 7 else 0,
                "water": 100 - (col - 1) * 10 if col <= 6 else 200 if col == 8 else 0,
                "blue": 100 if col <= 7 else 0}
            rationale = ("Background control: plain water, kept separate from the reagent-only zero." if col == 8 else
                "Represents an unknown sample; a 1:10 yellow dilution is prepared in stock-holder A5 before plating." if col == 7 else
                "The zero standard contains reagent; it is a calibration point, not the water blank." if col == 1 else
                "Represents a point on the published calibration series. Red-stock amount is a volume, not an assigned protein concentration.")
            wells.append({"well": f"{row}{col}", "label": label, "role": role, "volumes_ul": volumes,
                "total_ul": 200, "origin": "calculated", "rationale": rationale,
                "source_locator": "Step 8" if col == 8 else "Steps 5–6" if col == 7 else "Steps 4 and 6",
                "source_url": SOURCE_URL, "replicate_group": f"column-{col}"})
    return {"kind": "Bradford colored-water surrogate", "wells": wells, "well_count": len(wells), "columns": 8,
        "replicate_note": f"{settings.replicates} technical replicates per condition. Rows repeat the same eight conditions; no independent biological replicates are claimed.",
        "metric": "Camera RGB and within-condition spread only; no protein concentration, absorbance or assay-success inference.",
        "source_facts": SOURCE_FACTS, "preparation": "Stock A4 water 900 µL + stock A2 yellow 100 µL → empty A5; mix to prepare 1 mL of a 1:10 surrogate unknown."}


def compile_bradford(settings: BradfordSettings, supplied_setup: dict):
    template = build_color_demo()
    if template is None:
        raise ValueError("The reviewed Bradford demo template is unavailable.")
    plan, setup = deepcopy(template["plan"]), deepcopy(supplied_setup)
    rows = "ABC"[:settings.replicates]
    for op in plan["operations"]:
        op["destinations"] = [p for p in op["destinations"] if not p.startswith("plate.") or p.split(".")[1][0] in rows]
        op["purpose"] = op["purpose"].replace("in triplicate", f"in {settings.replicates} technical replicates").replace("three wells", f"{settings.replicates} wells").replace("three water-only blanks", f"{settings.replicates} water-only blanks")
    setup["first_tip"] = settings.first_tip
    setup["materials"] = template["setup_snapshot"]["materials"]
    fluids = yaml.safe_load(template["setup_snapshot"]["fluids_yaml"])["fluids"]
    fluids = {p: v for p, v in fluids.items() if not p.startswith("plate.") or p.split(".")[1][0] in rows}
    deck = yaml.safe_load(setup["deck_yaml"])
    for p, v in fluids.items():
        if p == "waste":
            continue
        capacity = check_position(deck, p)
        needed = 1000 if p == "10_vial_holder.A5" else 200 if p.startswith("plate.") else v["volume_ul"]
        if needed > capacity:
            raise ValueError(f"{p}: planned {needed:g} µL exceeds the configured working capacity.")
    setup["fluids_yaml"] = yaml.safe_dump({"fluids": fluids}, sort_keys=False)
    plan["summary"] = f"Six standard-volume levels, one diluted unknown and a water blank × {settings.replicates} replicates. {8 * settings.replicates} wells at 200 µL. Colored-water demonstration only."
    compiled = compile_plan(plan, setup)
    tips = [s["args"]["position"] for s in compiled["steps"] if s["command"] == "pick_up_tip"]
    for step in plan["manual_steps"]:
        step["instruction"] = step["instruction"].replace("fresh tips A1–F12", f"{len(tips)} fresh tips ({tips[0]} through {tips[-1]})").replace("three matching yellow/blue sample wells", f"{settings.replicates} matching yellow/blue sample wells").replace("three clear-water blanks", f"{settings.replicates} clear-water blanks")
    check = loading_sheet({"setup_snapshot": setup, "plan": plan, **compiled})
    if check["issues"]:
        raise ValueError("; ".join(check["issues"]))
    extra = {"demonstration": {**template["demonstration"], "plate_map": [w for w in template["demonstration"]["plate_map"] if w["well"][0] in rows]},
        "execution_summary": [
            "Prepare 1:10 yellow in A5: 900 µL water from A4 + 100 µL yellow from A2, then mix.",
            f"Rows {', '.join(rows)}, plate columns 1–6: red 0, 10, 20, 30, 40, 50 µL; B4 water tops each to 100 µL.",
            "Column 7: 100 µL diluted yellow. Column 8: 200 µL water-only blanks.",
            "Add 100 µL blue to columns 1–7 and mix. All used plate wells finish at 200 µL."]}
    return plan, compiled, setup, extra


def summarize_colors(design, measurements):
    expected = {w["well"]: w for w in design["wells"]}
    seen, groups, rows = set(), {}, []
    for m in measurements:
        if m["well"] not in expected or m["well"] in seen:
            raise ValueError("Measurements must name unique wells from this design.")
        seen.add(m["well"])
        well = expected[m["well"]]
        rows.append({**m, "label": well["label"]})
        groups.setdefault(well["replicate_group"], []).append(m["rgb"])
    summary = []
    for key, values in groups.items():
        mean = [sum(v[c] for v in values) / len(values) for c in range(3)]
        spread = sum(math.dist(v, mean) for v in values) / len(values) if len(values) > 1 else None
        summary.append({"group": key, "label": next(w["label"] for w in expected.values() if w["replicate_group"] == key),
            "n": len(values), "mean_rgb": [round(v, 2) for v in mean], "mean_rgb_distance": round(spread, 3) if spread is not None else None})
    return {"ranked": sorted(rows, key=lambda r: r["well"]), "best": None, "groups": summary,
        "complete": len(seen) == len(expected), "measured_wells": len(seen), "expected_wells": len(expected),
        "note": "Colored-water visual observations only. Replicate RGB spread is not pipetting accuracy, a standard-curve fit or protein concentration."}
