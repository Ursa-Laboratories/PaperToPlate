import time
from pathlib import Path

from . import store
from .config import ROOT
from .compiler import describe_yaml, digest


def seed():
    examples = ROOT / "examples"
    if not (examples / "gantry.yaml").exists():
        return
    try:
        store.get("setups", "picus120")
    except KeyError:
        store.save("setups", {"id": "picus120", "created_at": time.time(), "name": "Little Dipper · Picus 120 µL", "gantry_yaml": (examples / "gantry.yaml").read_text(), "deck_yaml": (examples / "deck.yaml").read_text(), "fluids_yaml": (examples / "prepared_fluids.yaml").read_text(), "first_tip": "A7", "materials": "10_vial_holder.A1: dilution water, 800 uL remaining. A2: BSA 0.1 mg/mL, 1500 uL. A3: Bradford reagent already diluted 2.5-fold, 3500 uL. A4/A5/B1: original unknowns (not used in assay stage). B2/B3/B4: prepared unknowns 1/2/3 at 1:10, 1000 uL each. B5: assay water, 3000 uL. plate: clean, empty 96-well plate. tips A7-G6 reserved for assay. Geometry is an operator-unverified supplied candidate. Reagent identity and reader availability are unconfirmed."})
    try:
        store.get("papers", "bradford-notes")
    except KeyError:
        notes = "Bradford plate-preparation reference notes\nThese are curated reference notes, not the uploaded full paper or an independently reviewed benchmark answer. Source: Ernst and Zor (2010), DOI 10.3791/1918.\nPrepare six BSA standards containing 0, 1, 2, 3, 4 and 5 micrograms per well from 0.1 mg/mL BSA; complement to 100 microliters with water. Prepare each in triplicate. Add 100 microliters of each prepared unknown to triplicate wells. Add 100 microliters of Bradford reagent that has been diluted 2.5-fold to standards and unknowns, giving 200 microliters per assay well. Prepare water-only optical blanks of 200 microliters. Read absorbance at 590 and 450 nm after 5 to 60 minutes. Subtract water blank at each wavelength before computing the ratio, retain the dye-only zero standard in regression, and apply the sample's prior dilution factor when estimating original concentration.\nLocal draft choices: three unknowns at 1:10, rows A/B/C as triplicates, standards columns 1-6, unknowns columns 7-9, optical blanks column 10. Reagent preparation, initial sample dilution and external-reader operation are separate operator tasks."
        store.save("papers", {"id": "bradford-notes", "created_at": time.time(), "title": "Linearized Bradford assay", "filename": "Bradford reference notes", "source_kind": "reference_notes", "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3164080/", "pages": [{"page": 1, "text": notes}], "page_count": 1, "characters": len(notes), "note": "Reference notes and existing draft. Upload the original paper for full-source review."})
    try:
        store.get("runs", "bradford-example")
    except KeyError:
        text = (examples / "bradford.yaml").read_text()
        store.save("runs", {"id": "bradford-example", "created_at": time.time(), "title": "Bradford · three samples in triplicate", "paper_id": "bradford-notes", "objective": "Prepare a Bradford assay plate with six standards, three already-diluted unknowns in triplicate and water-only blanks.", "setup_id": "picus120", "setup_snapshot": store.get("setups", "picus120"), "status": "example", "stage": "source", "example": True, "protocol_yaml": text, "protocol_hash": digest(text), "steps": describe_yaml(text), "review": None, "validation": None, "score": None, "events": [], "usage": [], "rubric": {"approved": False, "reviewer": "", "criteria": []}, "evidence": {"video_id": "demo", "offset_seconds": 0, "markers": [], "notes": "Existing Ursa demo footage. It is not a recording of this Bradford protocol."}, "manual_steps": [{"when": "before", "instruction": "Confirm source identities, calibration, liquid heights, tips and prepared 1:10 unknowns."}, {"when": "after", "instruction": "Incubate and read at 590/450 nm within the method's timing window."}]})
