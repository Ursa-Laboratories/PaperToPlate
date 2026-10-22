from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")

from paper_to_plate.vision_models import _nms, _predict_head_proba


def test_dino_head_probability_path_is_finite_without_blas_warnings():
    head = SimpleNamespace(
        coef_=np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, -1.0]], dtype=np.float64),
        intercept_=np.zeros(3, dtype=np.float64),
    )
    result = _predict_head_proba(head, np.array([[1.0, 2.0], [0.0, -1.0]], dtype=np.float32))
    assert result.shape == (2, 3)
    assert np.isfinite(result).all()
    np.testing.assert_allclose(result.sum(axis=1), 1.0)


def test_dino_head_rejects_nonfinite_features():
    head = SimpleNamespace(coef_=np.zeros((3, 2)), intercept_=np.zeros(3))
    with pytest.raises(RuntimeError, match="non-finite"):
        _predict_head_proba(head, np.array([[np.nan, 0.0]]))


def test_dense_candidates_do_not_require_paired_channels():
    candidate = {"label": "tip", "confidence": 0.8, "box": [10.0, 20.0, 30.0, 100.0]}
    assert _nms([candidate]) == [candidate]


def test_overlapping_tiles_keep_complete_tip_over_clipped_fragment():
    torch = pytest.importorskip('torch')
    from PIL import Image
    from paper_to_plate.vision_models import CameraTipDetector

    class FakeModel:
        def predict(self, crops, **kwargs):
            # 1280x1080 generates three columns and two rows. The lower tile
            # sees a high-confidence clipped fragment of the same full tip.
            output = []
            for index in range(len(crops)):
                boxes, scores = ([], [])
                if index == 0:
                    boxes, scores = ([[100, 300, 130, 500]], [.8])
                elif index == 3:
                    boxes, scores = ([[100, 0, 130, 60]], [.99])
                output.append(SimpleNamespace(boxes=SimpleNamespace(xyxy=torch.tensor(boxes), conf=torch.tensor(scores))))
            return output

    detector = CameraTipDetector.__new__(CameraTipDetector)
    detector.device = 'cpu'
    detector.model = FakeModel()
    detector.liquid = SimpleNamespace(predict=lambda image: [])
    output = detector.predict(Image.new('RGB', (1280,1080)))
    assert len(output) == 1
    assert output[0]['box'] == [100.,300.,130.,500.]
