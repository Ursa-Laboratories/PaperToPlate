"""Curated Bradford loading example; source files and geometry are unchanged."""
import time
import yaml

from . import store
from .compiler import describe_yaml, digest
from .config import ROOT


def seed_loading_example():
    try:
        store.get("runs", "bradford-load-and-run")
        return
    except KeyError:
        pass
    base = ROOT / "examples/bradford-workflow"
    if not (base / "01_dilute_samples_1_in_10.yaml").exists():
        return
    steps = []
    for name in ("01_dilute_samples_1_in_10.yaml", "02_bradford_assay.yaml"):
        steps.extend(yaml.safe_load((base / name).read_text())["protocol"])
    text = "# Bradford: three 1:10 tube dilutions, then assay plate preparation.\n# Human incubation and 590/450 nm reading follow the last dye addition.\n" + yaml.safe_dump({"protocol": steps}, sort_keys=False)
    stocks = [
        {"position": "10_vial_holder.A1", "material": "Deionized water · sample dilution", "concentration": "Pure deionized water", "preparation": "Load 3.5 mL deionized water. CubOS uses 900 µL for each of the three sample dilutions.", "load_volume_ul": 3500},
        {"position": "10_vial_holder.A2", "material": "BSA standard", "concentration": "0.1 mg/mL BSA", "preparation": "Prepare 1.5 mL at 0.1 mg/mL. If your verified parent stock is 1 mg/mL, combine 150 µL stock with 1,350 µL water. For another parent concentration, recalculate C1×V1=C2×V2; do not use those volumes unchanged.", "load_volume_ul": 1500},
        {"position": "10_vial_holder.A3", "material": "Bradford working reagent", "concentration": "Bio-Rad reagent diluted 2.5-fold (40% of supplied stock)", "preparation": "For the Bio-Rad reagent specified by the JoVE method: mix 1.4 mL supplied reagent with 2.1 mL deionized water; load 3.5 mL. Confirm reagent identity before using this dilution; it is not an instruction for a ready-to-use alternative.", "load_volume_ul": 3500},
        *[{"position": "10_vial_holder." + position, "material": f"Unknown sample {number} · original", "concentration": "Unknown protein concentration · original sample", "preparation": f"Load 1.5 mL of original sample {number}. CubOS transfers 100 µL into 900 µL water in {destination}, creating its 1:10 dilution. The extra source volume is an unvalidated immersion reserve.", "load_volume_ul": 1500} for number, position, destination in [(1, "A4", "B2"), (2, "A5", "B3"), (3, "B1", "B4")]],
        {"position": "10_vial_holder.B5", "material": "Deionized water · assay", "concentration": "Pure deionized water", "preparation": "Load 3.0 mL deionized water for standards and water-only optical blanks.", "load_volume_ul": 3000},
    ]
    # Reconstruct aggregate transfer/mix intents from the existing exact YAML.
    operations = []
    for step in steps:
        if "transfer" in step:
            a = step["transfer"]
            prev = operations[-1] if operations else {}
            if prev.get("action") == "transfer" and prev.get("source") == a["source"] and prev.get("destinations") == [a["destination"]] and not prev.get("mix_after_ul"):
                prev["volume_ul"] += a["volume_ul"]
            else:
                operations.append({"action": "transfer", "source": a["source"], "destinations": [a["destination"]], "volume_ul": a["volume_ul"], "purpose": f"Transfer to {a['destination']}", "citations": []})
        elif "mix" in step:
            a = step["mix"]
            prev = operations[-1]
            if prev["destinations"] == [a["position"]]:
                prev.update(mix_after_ul=a["volume_ul"], mix_after_cycles=a["cycles"])
    manual = [
        {"when": "before", "instruction": "Prepare and load the seven liquids listed in the table; leave stock tubes B2, B3 and B4 empty for CubOS to make the dilutions.", "reason": "Stock preparation and loading are human tasks."},
        {"when": "before", "instruction": "Place a clean compatible 96-well plate, fresh tips A1–G6 and a verified waste container. Confirm calibration and reachable liquid heights on the actual station.", "reason": "Physical setup is operator-owned."},
        {"when": "before", "instruction": "Confirm the Bio-Rad reagent identity and a reader supporting 590 and 450 nm. Have a timer ready for the first dye addition.", "reason": "This method requires the specified dye preparation and an external reader."},
        {"when": "after", "instruction": "Wait at least 5 minutes after the last dye addition; complete both readings within 60 minutes of the first dye addition. These timers are not enforced by the liquid-handling YAML.", "reason": "Color development and reader acquisition are manual."},
        {"when": "after", "instruction": "Read 590 and 450 nm using 200 µL water-only blanks, calculate the blank-corrected ratio, retain the zero-protein dye standard in the fit and apply the 1:10 sample dilution correction.", "reason": "The camera does not measure absorbance."},
    ]
    setup = {"id": "bradford-full-setup", "name": "Bradford · full dilution and assay", "created_at": time.time(),
        "gantry_yaml": (base / "setup/picus120_fast_camera_20261014.yaml").read_text(),
        "deck_yaml": (base / "setup/cub_deck_xy_camera_20261021.yaml").read_text(),
        "fluids_yaml": (base / "01_initial_fluids.yaml").read_text(), "first_tip": "A1", "nominal_vial_capacity_ul": 5000,
        "materials": "\n".join(f"{s['position']}: {s['material']}, {s['concentration']}, load {s['load_volume_ul']} uL." for s in stocks) + "\nB2/B3/B4 start empty. plate starts empty. Supplied geometry requires physical confirmation."}
    store.save("setups", setup)
    store.save("runs", {"id": "bradford-load-and-run", "created_at": time.time(), "title": "Bradford · prepare, load & run",
        "paper_id": "bradford-notes", "objective": "Dilute three original samples 1:10 in stock tubes, then prepare Bradford standards, samples and water blanks in triplicate.",
        "setup_id": setup["id"], "setup_snapshot": setup, "status": "example", "stage": "source", "example": True,
        "protocol_yaml": text, "protocol_hash": digest(text), "steps": describe_yaml(text), "tip_count": 78,
        "manual_interleaving": False, "review_enabled": True, "review": None, "validation": None, "events": [], "usage": [],
        "execution_summary": ["Make three 1:10 dilutions in B2–B4: 100 µL original sample + 900 µL water.",
            "Prepare six BSA levels (0–5 µg/well) in triplicate, topped up to 100 µL.",
            "Dispense diluted unknowns into columns 7–9, and water-only blanks into column 10.",
            "Add 100 µL Bradford working reagent to each assay well and pipette-mix. Final well volume: 200 µL."],
        "plan": {"title": "Bradford · prepare, load & run", "summary": "You prepare the stocks. CubOS makes the sample dilutions and assay plate. You handle incubation and the absorbance reader.",
            "operations": operations, "manual_steps": manual, "stock_preparations": stocks,
            "assumptions": ["Three unknowns in triplicate; 1:10 dilution is a local choice.", "Mixing cycles and loading reserves are unvalidated implementation choices."],
            "unresolved": ["Confirm that the supplied Bradford reagent is the Bio-Rad formulation intended for 2.5-fold dilution, and that the external reader supports 590/450 nm."]},
        "evidence": {"markers": [], "offset_seconds": 0}, "rubric": {"approved": False, "reviewer": "", "criteria": []}})
