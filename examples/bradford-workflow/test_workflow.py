"""Offline scientific and inventory contracts for the Bradford YAML workflow."""

from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from cubos.protocol_engine.setup_validator import run_setup_validation


ROOT = Path(__file__).resolve().parent


def read(name):
    return yaml.safe_load((ROOT / name).read_text())


def simulate(name, initial):
    state = deepcopy(initial)
    picked = []
    attached = None
    visited = set()
    for step in read(name)["protocol"]:
        command, args = next(iter(step.items()))
        if command == "pick_up_tip":
            assert attached is None
            attached = args["position"]
            assert attached not in picked
            picked.append(attached)
            visited = set()
        elif command == "drop_tip":
            assert attached is not None
            attached = None
        elif command == "transfer":
            assert attached is not None
            source, dest = args["source"], args["destination"]
            volume = args["volume_ul"]
            assert 10 <= volume <= 100
            assert len(visited | {dest}) == 1  # one destination per tip
            visited.add(dest)
            src, dst = state[source], state[dest]
            assert src["volume_ul"] >= volume
            for substance, amount in list(src["composition"].items()):
                moved = amount * volume / src["volume_ul"]
                src["composition"][substance] -= moved
                dst["composition"][substance] = dst["composition"].get(substance, 0) + moved
            src["volume_ul"] -= volume
            dst["volume_ul"] += volume
            assert dst["volume_ul"] <= (300 if dest.startswith("plate.") else 4000)
        elif command == "mix":
            assert attached is not None
            assert args["position"] in visited
            assert 0 < args["volume_ul"] <= min(120, state[args["position"]]["volume_ul"])
            assert args["cycles"] > 0
        else:
            pytest.fail(f"Unexpected command in routing-only protocol: {command}")
    assert attached is None
    return state, picked


@pytest.mark.parametrize("protocol, seed", [
    ("00_water_commissioning.yaml", "00_water_fluids.yaml"),
    ("01_dilute_samples_1_in_10.yaml", "01_initial_fluids.yaml"),
    ("02_bradford_assay.yaml", "02_prepared_fluids.yaml"),
])
def test_exact_supplied_setup_routes_and_volumes(protocol, seed):
    result = run_setup_validation(
        ROOT / "setup/picus120_fast_camera_20261014.yaml",
        ROOT / "setup/cub_deck_xy_camera_20261021.yaml",
        ROOT / protocol,
        ROOT / seed,
    )
    assert result.passed, result.output


def test_stock_dilution_and_handoff_are_exact():
    state, tips = simulate("01_dilute_samples_1_in_10.yaml", read("01_initial_fluids.yaml")["fluids"])
    for number, well in enumerate(("B2", "B3", "B4"), 1):
        tube = state[f"10_vial_holder.{well}"]
        assert tube["volume_ul"] == 1000
        assert tube["composition"] == {"deionized_water": 900, f"unknown_{number}_neat": 100}
    assert state == read("02_prepared_fluids.yaml")["fluids"]
    assert tips == [f"tips.A{i}" for i in range(1, 7)]


def test_assay_mass_balance_blanks_and_tip_allocation():
    initial = read("01_initial_fluids.yaml")["fluids"]
    prepared, dilution_tips = simulate("01_dilute_samples_1_in_10.yaml", initial)
    final, assay_tips = simulate("02_bradford_assay.yaml", prepared)
    assert len(assay_tips) == 72
    assert len(set(dilution_tips + assay_tips)) == 78
    assert assay_tips[0] == "tips.A7" and assay_tips[-1] == "tips.G6"
    for row in "ABC":
        for col in range(1, 7):
            well = final[f"plate.{row}{col}"]
            assert well["volume_ul"] == 200
            assert well["composition"]["bradford_2_5_fold_diluted"] == 100
            # 0.1 mg/mL = 0.1 ug/uL; six levels must be 0,1,2,3,4,5 ug.
            assert well["composition"].get("bsa_0_1_mg_ml", 0) * 0.1 == col - 1
        for col in (7, 8, 9):
            well = final[f"plate.{row}{col}"]
            assert well["volume_ul"] == 200
            assert well["composition"] == {
                "deionized_water": pytest.approx(90),
                f"unknown_{col - 6}_neat": pytest.approx(10),
                "bradford_2_5_fold_diluted": 100,
            }
        assert final[f"plate.{row}10"] == {"volume_ul": 200, "composition": {"deionized_water": 200}}
    assert sum(v["volume_ul"] for k, v in final.items() if k.startswith("plate.")) == 6000
    assert sum(v["volume_ul"] for v in final.values()) == sum(v["volume_ul"] for v in initial.values())
    for well, expected in {"A1": 800, "A2": 1050, "A3": 800, "A4": 1400, "A5": 1400, "B1": 1400, "B2": 700, "B3": 700, "B4": 700, "B5": 1050}.items():
        assert final[f"10_vial_holder.{well}"]["volume_ul"] == expected
    assert final == read("expected_final_fluids.yaml")["fluids"]


def test_dye_is_added_last_and_each_tip_is_discarded_after_mix():
    steps = read("02_bradford_assay.yaml")["protocol"]
    dye_started = False
    destinations = []
    for index, step in enumerate(steps):
        if "transfer" not in step:
            continue
        args = step["transfer"]
        if args["source"] == "10_vial_holder.A3":
            dye_started = True
            destinations.append(args["destination"])
            assert "pick_up_tip" in steps[index - 1]
            assert steps[index + 1]["mix"]["position"] == args["destination"]
            assert "drop_tip" in steps[index + 2]
        else:
            assert not dye_started
    assert Counter(destinations) == Counter(f"plate.{r}{c}" for c in range(1, 10) for r in "ABC")
