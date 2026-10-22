"""User-requested colored-water analogue of the Bradford liquid workflow."""
import time

import yaml

from . import store
from .compiler import compile_plan
from .config import ROOT


def build_color_demo():
    base = ROOT / "examples/bradford-workflow"
    if not (base / "setup/picus120_fast_camera_20261014.yaml").exists():
        return None
    holder = "10_vial_holder."
    stock_definitions = [
        ("A1", "Red water · standard surrogate", "Prepared red stock, used as supplied (1× demo stock)", 1500,
         "Load 1.5 mL of your prepared red water. It represents the BSA standard for the liquid-handling demonstration; no protein concentration is assigned."),
        ("A2", "Yellow water · sample surrogate", "Prepared yellow stock, used as supplied (1× demo stock)", 1500,
         "Load 1.5 mL of your prepared yellow water. CubOS takes 100 µL into 900 µL water in A5, then uses that 1:10 dilution in three assay wells."),
        ("A3", "Blue water · working-reagent surrogate", "Prepared blue stock, used as supplied (1× demo stock)", 3000,
         "Load 3.0 mL of your prepared blue water. This represents the already-diluted Bradford working reagent. Do not apply the real reagent's 2.5-fold dilution to this demo stock."),
        ("A4", "Water · sample dilution", "Plain water", 1500,
         "Load 1.5 mL plain water. CubOS transfers 900 µL into empty A5 before adding the yellow sample."),
        ("B4", "Water · plate preparation", "Plain water", 3000,
         "Load 3.0 mL plain water for the red-volume series and water-only blanks."),
    ]
    stocks = [{"position": holder + p, "material": material, "concentration": concentration,
               "preparation": preparation, "load_volume_ul": load, "citations": []}
              for p, material, concentration, load, preparation in stock_definitions]
    colors = {1: "red", 2: "yellow", 3: "blue", 4: "water", 5: "empty"}
    layout = [{"position": holder + f"{row}{col}", "color": colors[col],
               "use": "dilution destination" if (row, col) == ("A", 5) else
                      "unused empty vial" if col == 5 else
                      "unused backup; contents not consumed" if row == "B" and col < 4 else "active source"}
              for row in "AB" for col in range(1, 6)]
    fluids = {s["position"]: {"volume_ul": s["load_volume_ul"], "composition": {s["material"]: s["load_volume_ul"]}}
              for s in stocks}
    # Do not invent the volume of unused user-loaded backup color vials.
    for p in [holder + "A5", holder + "B5", "waste"] + [f"plate.{r}{c}" for r in "ABC" for c in range(1, 9)]:
        fluids[p] = {"volume_ul": 0, "composition": {}}
    setup = {"id": "bradford-color-demo-setup", "name": "Color columns · red / yellow / blue / water / empty",
             "gantry_yaml": (base / "setup/picus120_fast_camera_20261014.yaml").read_text(),
             "deck_yaml": (base / "setup/cub_deck_xy_camera_20261021.yaml").read_text(),
             "fluids_yaml": yaml.safe_dump({"fluids": fluids}, sort_keys=False),
             "first_tip": "A1", "nominal_vial_capacity_ul": 5000,
             "materials": "Stock-holder columns, both rows: 1 red; 2 yellow; 3 blue; 4 water; 5 empty. "
                          "Active sources A1 red 1500 uL, A2 yellow 1500 uL, A3 blue 3000 uL, "
                          "A4 water 1500 uL, B4 water 3000 uL. A5/B5 initially empty. "
                          "B1/B2/B3 are untouched backups with unspecified volumes. "
                          "Colored-water demo only; no actual protein or Bradford reagent. "
                          "Supplied 4 mL configured working limit is retained despite 5 mL nominal vials."}
    operations = []

    def transfer(source, destinations, volume, purpose, mix=0, cycles=3):
        operations.append({"action": "transfer", "source": source, "destinations": destinations,
                           "volume_ul": volume, "purpose": purpose, "mix_after_ul": mix,
                           "mix_after_cycles": cycles, "citations": []})

    transfer(holder + "A4", [holder + "A5"], 900, "Add 900 µL water to empty A5")
    transfer(holder + "A2", [holder + "A5"], 100, "Make one 1:10 yellow sample dilution in A5", mix=100, cycles=10)
    for col in range(1, 7):
        transfer(holder + "B4", [f"plate.{r}{col}" for r in "ABC"], 100 - (col - 1) * 10,
                 f"Water for red-volume level {col - 1}, in triplicate")
    transfer(holder + "B4", [f"plate.{r}8" for r in "ABC"], 200, "Prepare three water-only blanks")
    for col in range(2, 7):
        transfer(holder + "A1", [f"plate.{r}{col}" for r in "ABC"], (col - 1) * 10,
                 f"Add {(col - 1) * 10} µL red standard surrogate, in triplicate")
    transfer(holder + "A5", [f"plate.{r}7" for r in "ABC"], 100, "Add diluted yellow sample to three wells")
    transfer(holder + "A3", [f"plate.{r}{c}" for c in range(1, 8) for r in "ABC"], 100,
             "Add blue working-reagent surrogate and pipette-mix", mix=80)
    manual = [
        {"when": "before", "instruction": "Match the stock-holder columns in both rows: 1 red, 2 yellow, 3 blue, 4 water, 5 empty. These are stock-holder columns, not assay-plate columns.", "reason": "User-specified physical arrangement."},
        {"when": "before", "instruction": "Verify the five active source loads below. Leave A5 and B5 empty. B1 red, B2 yellow and B3 blue stay in place as unused backups; this run never draws from them.", "reason": "No relocation or fabricated backup inventory is needed."},
        {"when": "before", "instruction": "Use a clean 96-well plate and fresh tips A1–F12. Confirm calibrated positions, liquid immersion, tip pickup and waste at the station before an operator starts the run.", "reason": "Only offline geometry and volume checks have been performed."},
        {"when": "after", "instruction": "Photograph or inspect the six red/blue mixture levels, the three matching yellow/blue sample wells and the three clear-water blanks. Compare replicate appearance and liquid levels.", "reason": "Visual evidence of a liquid-handling demonstration."},
        {"when": "after", "instruction": "No protein concentration is calculated. No absorbance reading, shaker or Bradford color-development wait is required for these colored-water stand-ins.", "reason": "The chemistry and quantitative readout of the paper are outside this demo."},
    ]
    plan = {"title": "Bradford · colored-water demo", "summary": "Your color columns mapped to Bradford's liquid-handling pattern: one yellow sample in triplicate, six red-volume levels and water blanks. No protein assay or absorbance readout.",
            "operations": operations, "stock_preparations": stocks, "manual_steps": manual,
            "assumptions": ["Colors are user-prepared aqueous stand-ins, not BSA or Bradford reagent.",
                            "One sample in triplicate replaces the earlier three-sample example.",
                            "Stock loads and mixing cycles are implementation choices; reserves do not establish reachable liquid depth.",
                            "Original gantry/deck geometry is retained and still requires operator verification."], "unresolved": []}
    compiled = compile_plan(plan, setup)
    plate_map = [{"well": f"{row}{col}", "role": "water blank" if col == 8 else "yellow sample surrogate" if col == 7 else "red standard surrogate",
                  "red_ul": (col - 1) * 10 if col <= 6 else 0,
                  "diluted_yellow_ul": 100 if col == 7 else 0,
                  "water_ul": 100 - (col - 1) * 10 if col <= 6 else 200 if col == 8 else 0,
                  "blue_ul": 100 if col <= 7 else 0, "final_volume_ul": 200}
                 for row in "ABC" for col in range(1, 9)]
    return {"id": "bradford-color-demo", "title": plan["title"], "paper_id": "bradford-color-demo-notes",
            "objective": "Demonstrate the Bradford pipetting structure using the user-loaded color columns; do not perform or report a protein assay.",
            "setup_id": setup["id"], "setup_snapshot": setup, "plan": plan, **compiled,
            "status": "example", "stage": "source", "example": True, "review_enabled": True,
            "review": None, "validation": None, "events": [], "usage": [],
            "demonstration": {"kind": "colored_water", "stock_layout": layout, "plate_map": plate_map},
            "execution_summary": ["A4 water → A5: 900 µL. A2 yellow → A5: 100 µL. Mix to make 1 mL at 1:10.",
                "Plate columns 1–6: 0, 10, 20, 30, 40 and 50 µL red, topped up to 100 µL with B4 water. Rows A/B/C are triplicates.",
                "Plate column 7: 100 µL diluted yellow from A5. Plate column 8: 200 µL water-only blanks.",
                "A3 blue → every well in plate columns 1–7: 100 µL, then pipette-mix. All 24 wells finish at 200 µL."],
            "evidence": {"markers": [], "offset_seconds": 0, "notes": "No physical demonstration recorded yet."},
            "rubric": {"approved": False, "reviewer": "", "criteria": []}}


def seed_color_demo():
    try:
        store.get("runs", "bradford-color-demo")
        return
    except KeyError:
        pass
    run = build_color_demo()
    if run is None:
        return
    now = time.time()
    notes = ("User-requested colored-water demonstration. This is an adaptation of the liquid-handling structure of Ernst and Zor, DOI 10.3791/1918, not the published protein assay. "
             "Stock-holder columns in both rows: 1 red, 2 yellow, 3 blue, 4 water, 5 empty. Use A1 red as standard surrogate, A2 yellow as one sample surrogate, A3 blue as already-prepared working-reagent surrogate. "
             "Make 100 uL yellow plus 900 uL A4 water in empty A5. Prepare six red levels (0,10,20,30,40,50 uL) topped to 100 uL with B4 water in plate columns 1–6, rows A/B/C. "
             "Place 100 uL of diluted yellow in plate column 7, rows A/B/C. Add 100 uL blue to columns 1–7 and pipette-mix. Plate column 8 contains 200 uL water-only blanks, rows A/B/C. "
             "No protein concentration, absorbance measurement, incubation or shaker is part of this visual demo. B1/B2/B3 backups remain untouched; B5 remains empty. "
             "Sample count, color substitution, loading reserves, mixing and plate layout are local choices, not published assay facts.")
    store.save("papers", {"id": run["paper_id"], "created_at": now, "title": "Bradford colored-water demonstration · adaptation notes",
        "filename": "Color-demo adaptation notes", "source_kind": "reference_notes", "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3164080/",
        "pages": [{"page": 1, "text": notes}], "page_count": 1, "characters": len(notes),
        "note": "User-defined surrogate workflow; the original Bradford assay is preserved separately."})
    run["created_at"] = now
    run["setup_snapshot"]["created_at"] = now
    store.save("setups", run["setup_snapshot"])
    store.save("runs", run)
