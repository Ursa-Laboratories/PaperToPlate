from copy import deepcopy

import pytest
import yaml
from fastapi.testclient import TestClient

from paper_to_plate import preparation, store
from paper_to_plate.app import app
from paper_to_plate.bradford_color_demo import build_color_demo, seed_color_demo
from paper_to_plate.validation import validate


def simulate(run):
    state = deepcopy(yaml.safe_load(run["setup_snapshot"]["fluids_yaml"])["fluids"])
    tips = []
    attached = None
    for step in yaml.safe_load(run["protocol_yaml"])["protocol"]:
        command, args = next(iter(step.items()))
        if command == "pick_up_tip":
            assert attached is None and args["position"] not in tips
            attached = args["position"]; tips.append(attached)
        elif command == "drop_tip":
            assert attached is not None
            attached = None
        elif command == "transfer":
            assert attached
            assert 5 <= args["volume_ul"] <= 120
            src, dst, amount = state[args["source"]], state[args["destination"]], args["volume_ul"]
            assert src["volume_ul"] >= amount
            for key, quantity in list(src["composition"].items()):
                moved = quantity * amount / src["volume_ul"]
                src["composition"][key] -= moved
                dst["composition"][key] = dst["composition"].get(key, 0) + moved
            src["volume_ul"] -= amount; dst["volume_ul"] += amount
        elif command == "mix":
            assert attached and args["volume_ul"] <= min(120, state[args["position"]]["volume_ul"])
        else:
            pytest.fail(f"Unexpected non-liquid demo action: {command}")
    assert attached is None
    return state, tips


def test_color_column_mapping_and_mass_balance():
    run = build_color_demo()
    state, tips = simulate(run)
    assert len(tips) == 72 and tips[-1] == "tips.F12"
    assert {s["position"] for s in preparation.build(run)["stocks"]} == {
        "10_vial_holder.A1", "10_vial_holder.A2", "10_vial_holder.A3", "10_vial_holder.A4", "10_vial_holder.B4"}
    assert preparation.build(run)["issues"] == []
    initial = yaml.safe_load(run["setup_snapshot"]["fluids_yaml"])["fluids"]
    assert all(f"10_vial_holder.B{c}" not in initial for c in (1,2,3))
    assert state["10_vial_holder.A5"]["volume_ul"] == 700
    assert state["10_vial_holder.B5"]["volume_ul"] == 0
    for row in "ABC":
        for col in range(1,9):
            well = state[f"plate.{row}{col}"]
            assert well["volume_ul"] == 200
            comp = well["composition"]
            if col <= 6:
                assert comp.get("Red water · standard surrogate",0) == pytest.approx((col-1)*10)
                assert comp["Blue water · working-reagent surrogate"] == pytest.approx(100)
            elif col == 7:
                assert comp["Yellow water · sample surrogate"] == pytest.approx(10)
                assert comp["Water · sample dilution"] == pytest.approx(90)
                assert comp["Blue water · working-reagent surrogate"] == pytest.approx(100)
            else:
                assert comp == {"Water · plate preparation": 200}
    for item in run["demonstration"]["stock_layout"]:
        col = int(item["position"][-1])
        assert item["color"] == {1:"red",2:"yellow",3:"blue",4:"water",5:"empty"}[col]


@pytest.mark.asyncio
async def test_color_demo_passes_native_validation_without_hardware():
    run = build_color_demo()
    result = await validate(run["setup_snapshot"], run["protocol_yaml"])
    assert result["passed"], result
    assert result["hardware_contacted"] is False


def test_seed_preserves_original_and_never_resets_an_existing_demo(workspace):
    original = store.get("runs", "bradford-load-and-run")
    color = store.get("runs", "bradford-color-demo")
    color["operator_note"] = "Preserve my edits"
    store.save("runs",color)
    seed_color_demo()
    assert store.get("runs", "bradford-load-and-run") == original
    assert store.get("runs", "bradford-color-demo")["operator_note"] == "Preserve my edits"


def test_demo_copy_keeps_visual_only_scope_and_rejects_protein_readings(workspace):
    with TestClient(app) as client:
        response = client.post('/api/runs/bradford-color-demo/measurements',files={'file':('test.csv',b'not protein data','text/csv')})
        assert response.status_code == 400 and 'colored-water' in response.json()['detail']
        copied = client.post('/api/runs/bradford-color-demo/copy').json()
        assert copied['demonstration']['kind'] == 'colored_water'
        assert copied['execution_summary']
        assert not copied.get('loading_confirmation')
