from pathlib import Path
import pytest
from paper_to_plate import store
from paper_to_plate.seed import seed


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    seed()
    return tmp_path


@pytest.fixture
def setup(workspace):
    return store.get("setups", "picus120")
