from copy import deepcopy

import pytest
import yaml
from fastapi.testclient import TestClient

from paper_to_plate import handoff, preparation, store
from paper_to_plate.app import app
from paper_to_plate.compiler import split_strokes
from paper_to_plate.models import HandoffInput, Plan
from paper_to_plate.validation import validate


def example():
    return store.get("runs", "bradford-load-and-run")


def confirmed(run):
    sheet = preparation.build(run)
    run["loading_confirmation"] = {"fingerprint": sheet["fingerprint"],
        "loaded_positions": [s["position"] for s in sheet["stocks"]], "human_steps_confirmed": True}
    return sheet


def request(run):
    return HandoffInput(mock_mode=False, expected_hash=run["protocol_hash"],
        preparation_hash=preparation.fingerprint(run), operator_confirmed=True,
        manual_steps_confirmed=True, setup_confirmed=True)


def review_fixture(run):
    run["plan"]["unresolved"] = []
    run.update(review={"verdict": "needs_operator_review", "findings": []},
               review_hash=run["protocol_hash"], validation={"passed": True},
               validation_hash=run["protocol_hash"])


def test_bradford_sheet_matches_source_volumes_and_separates_empty_intermediates(workspace):
    run = example()
    Plan.model_validate(run["plan"])
    sheet = preparation.build(run)
    assert sheet["issues"] == []
    assert len(sheet["stocks"]) == 7
    assert sheet["nominal_vial_capacity_ul"] == 5000
    assert all(s["effective_capacity_ul"] == 4000 for s in sheet["stocks"])
    assert sheet["well_peak_ul"] == 200 and sheet["well_capacity_ul"] == 300
    assert sheet["tip_count"] == 78
    assert "10_vial_holder.B2" in sheet["empty_locations"]
    assert not any(s["position"] == "10_vial_holder.B2" for s in sheet["stocks"])
    stocks = {s["position"]: s for s in sheet["stocks"]}
    assert stocks["10_vial_holder.A1"]["consumed_ul"] == 2700
    assert stocks["10_vial_holder.A1"]["remaining_ul"] == 800
    assert stocks["10_vial_holder.A2"]["concentration"] == "0.1 mg/mL BSA"
    assert stocks["10_vial_holder.A3"]["load_volume_ul"] == 3500
    assert stocks["10_vial_holder.A3"]["consumed_ul"] == 2700
    assert len(sheet["human_before"]) == 3 and len(sheet["human_after"]) == 2
    assert not sheet["confirmed"]


@pytest.mark.asyncio
async def test_combined_dilution_and_assay_pass_native_cubos_offline(workspace):
    run = example()
    result = await validate(run["setup_snapshot"], run["protocol_yaml"])
    assert result["passed"], result
    assert not result["hardware_contacted"]


@pytest.mark.parametrize("total", [5, 120, 120.1, 121, 125, 200, 249.9, 900, 5000])
def test_capacity_splitting_preserves_volume_and_device_increment(total):
    strokes = split_strokes(total)
    assert sum(strokes) == pytest.approx(total)
    assert all(5 <= v <= 120 and v * 10 == pytest.approx(round(v * 10)) for v in strokes)


@pytest.mark.parametrize("total", [.5, 4.9, 10.05])
def test_below_minimum_and_unrepresentable_transfers_require_a_dilution(total):
    with pytest.raises(ValueError):
        split_strokes(total)


def test_stock_plan_respects_smaller_capacity_and_refuses_insufficient_load(workspace):
    run = example()
    stocks = deepcopy(run["plan"]["stock_preparations"])
    stocks[0]["load_volume_ul"] = 4500
    with pytest.raises(ValueError, match="4000"):
        preparation.apply_stock_preparations(stocks, run["setup_snapshot"], run["protocol_yaml"])
    stocks[0]["load_volume_ul"] = 1000
    with pytest.raises(ValueError, match="required 2700"):
        preparation.apply_stock_preparations(stocks, run["setup_snapshot"], run["protocol_yaml"])
    stocks[0]["load_volume_ul"] = None
    changed = preparation.apply_stock_preparations(stocks, run["setup_snapshot"], run["protocol_yaml"])
    assert yaml.safe_load(changed["fluids_yaml"])["fluids"]["10_vial_holder.A1"]["volume_ul"] == 3000
    assert changed["deck_yaml"] == run["setup_snapshot"]["deck_yaml"]


def test_peak_capacity_is_checked_even_if_well_is_later_drained(workspace):
    run = example()
    run["protocol_yaml"] = yaml.safe_dump({"protocol":[
        {"transfer":{"source":"10_vial_holder.B5","destination":"plate.A1","volume_ul":100}},
        {"transfer":{"source":"10_vial_holder.B5","destination":"plate.A1","volume_ul":100}},
        {"transfer":{"source":"10_vial_holder.B5","destination":"plate.A1","volume_ul":100}},
        {"transfer":{"source":"10_vial_holder.B5","destination":"plate.A1","volume_ul":100}},
        {"transfer":{"source":"plate.A1","destination":"10_vial_holder.B2","volume_ul":100}},
    ]})
    sheet = preparation.build(run)
    assert not sheet["can_confirm"]
    assert any("peak 400" in issue for issue in sheet["issues"])


@pytest.mark.parametrize("changed", ["recipe", "load", "geometry", "manual", "protocol"])
def test_confirmation_becomes_stale_after_any_material_revision(workspace, changed):
    run = example()
    confirmed(run)
    assert preparation.build(run)["confirmed"]
    if changed == "recipe":run["plan"]["stock_preparations"][0]["preparation"] += " Revised."
    if changed == "load":run["setup_snapshot"]["fluids_yaml"] += "\n# revised load"
    if changed == "geometry":run["setup_snapshot"]["deck_yaml"] += "\n# revised geometry"
    if changed == "manual":run["plan"]["manual_steps"][0]["instruction"] += " Revised."
    if changed == "protocol":run["protocol_yaml"] += "\n# revised"
    assert not preparation.build(run)["confirmed"]


def test_api_loading_confirmation_and_stock_edit_invalidate_review(workspace):
    with TestClient(app) as client:
        run = client.get('/api/runs/bradford-load-and-run').json()
        sheet = run["preparation"]
        body = {"expected_preparation_hash":sheet["fingerprint"],"loaded_positions":[],"human_steps_confirmed":True}
        assert client.post('/api/runs/bradford-load-and-run/preparation/confirm',json=body).status_code == 400
        body["loaded_positions"] = [s["position"] for s in sheet["stocks"]]
        saved = client.post('/api/runs/bradford-load-and-run/preparation/confirm',json=body)
        assert saved.status_code == 200 and saved.json()["preparation"]["confirmed"]
        stocks = run["plan"]["stock_preparations"]
        stocks[0]["preparation"] += " Reviewed against the source."
        edited = client.put('/api/runs/bradford-load-and-run/preparation',json={"expected_hash":sheet["fingerprint"],"stocks":stocks})
        assert edited.status_code == 200
        assert edited.json()["review"] is None and edited.json()["validation"] is None
        assert not edited.json()["preparation"]["confirmed"]
        assert client.post('/api/runs/bradford-load-and-run/preparation/confirm',json=body).status_code == 409


def test_server_physical_handoff_requires_current_complete_loading(workspace):
    run = example()
    review_fixture(run)
    with pytest.raises(ValueError, match="stock"):
        handoff.submission(run, request(run))
    confirmed(run)
    payload = handoff.submission(run, request(run))
    assert payload["state"]["initial_state"]["fluids"]["10_vial_holder.A3"]["volume_ul"] == 3500
    run["plan"]["stock_preparations"][0]["concentration"] = ""
    with pytest.raises(ValueError, match="stock"):
        handoff.submission(run, request(run))


def test_stock_revision_during_handoff_never_reaches_cubos(workspace, monkeypatch):
    import paper_to_plate.app as api_module
    run = example(); review_fixture(run); confirmed(run); store.save("runs",run)
    sent=[]
    async def changed_validation(*args):
        current=example();current["plan"]["stock_preparations"][0]["preparation"] += " changed"
        store.save("runs",current)
        return {"passed":True}
    async def forbidden_send(*args):sent.append(True)
    monkeypatch.setattr(api_module,'validate',changed_validation)
    monkeypatch.setattr(api_module.handoff,'send',forbidden_send)
    with TestClient(app) as client:
        response=client.post('/api/runs/bradford-load-and-run/handoff',json=request(run).model_dump())
        assert response.status_code == 409
    assert sent == []
