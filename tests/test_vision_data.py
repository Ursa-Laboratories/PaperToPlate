import importlib.util
from pathlib import Path

import pytest
pytest.importorskip('PIL')

spec = importlib.util.spec_from_file_location('vision_prepare', Path(__file__).parents[1]/'scripts'/'vision_prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def test_capture_family_is_never_split_by_frame_number():
    assert prepare.group_name('tipsWaterRed_1') == prepare.group_name('tipsWaterRed_13')
    assert prepare.SPLIT_BY_GROUP[prepare.group_name('tipsWaterRed_1')] == 'test'


def test_dataset_generation_cannot_delete_unowned_directory(tmp_path):
    source = tmp_path/'raw'
    output = tmp_path/'valuable'
    source.mkdir()
    output.mkdir()
    original = output/'notes.txt'
    original.write_text('keep')
    with pytest.raises(ValueError, match='Refusing'):
        prepare.prepare(source, output)
    assert original.read_text() == 'keep'
    with pytest.raises(ValueError, match='source'):
        prepare.prepare(source, tmp_path)


def test_nonfinite_and_zero_area_labels_rejected(tmp_path):
    labels = tmp_path/'labels.txt'
    for value in ['0 nan .5 .2 .2', '1 .5 .5 0 .2']:
        labels.write_text(value)
        with pytest.raises(ValueError):
            prepare.parse_labels(labels)
