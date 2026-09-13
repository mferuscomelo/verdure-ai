"""Label parsing, result normalising and the confidence gate.

These are the parts that stand between the model's raw output and a price
on the screen, so they're covered independently of the model itself.
"""
import numpy as np
import pytest

import produce_classifier
from produce_classifier import _extract_predictions, parse_label

FRAME = np.full((16, 16, 3), 200, dtype=np.uint8)


class _FakeBrick:
    def __init__(self, result, **kwargs):
        self.result = result
        self.kwargs = kwargs
        self.calls = []

    def classify(self, image_bytes, image_type="jpg", confidence=None):
        self.calls.append((image_bytes, image_type))
        return self.result


@pytest.fixture
def classify(arduino):
    """Build a classifier whose model returns whatever the test supplies."""
    def build(result, **kwargs):
        brick = _FakeBrick(result)
        arduino.image_classification_cls = lambda **kw: brick
        classifier = produce_classifier.ProduceClassifier(**kwargs)
        classifier.brick = brick
        return classifier
    return build


# --- label parsing --------------------------------------------------------

def test_parse_label_splits_type_from_grade():
    assert parse_label("apple_gradeA") == ("apple", "gradeA")
    assert parse_label("banana_reject") == ("banana", "reject")


def test_parse_label_rejects_an_unknown_produce_type():
    assert parse_label("dragonfruit_gradeA") is None


def test_parse_label_rejects_an_unknown_grade():
    assert parse_label("apple_gradeZ") is None


def test_parse_label_rejects_a_label_with_no_grade():
    assert parse_label("apple") is None


# --- result normalising ---------------------------------------------------

def test_extract_predictions_reads_a_label_to_score_mapping():
    assert sorted(_extract_predictions({"apple_gradeA": 0.9, "apple_gradeB": 0.1})) == [
        ("apple_gradeA", 0.9), ("apple_gradeB", 0.1),
    ]


def test_extract_predictions_reads_a_list_of_entries():
    result = [{"label": "apple_gradeA", "value": 0.8}, {"label": "apple_gradeC", "value": 0.2}]

    assert _extract_predictions(result) == [("apple_gradeA", 0.8), ("apple_gradeC", 0.2)]


def test_extract_predictions_reads_a_nested_list():
    result = {"results": [{"class": "banana_gradeB", "confidence": 0.7}]}

    assert _extract_predictions(result) == [("banana_gradeB", 0.7)]


def test_extract_predictions_survives_an_empty_or_missing_result():
    assert _extract_predictions(None) == []
    assert _extract_predictions({}) == []
    assert _extract_predictions([]) == []


# --- classification -------------------------------------------------------

def test_classify_returns_the_highest_scoring_label(classify):
    classifier = classify({"apple_gradeA": 0.2, "apple_gradeC": 0.75})

    graded = classifier.classify(FRAME)

    assert graded.produce_type == "apple"
    assert graded.tier == "gradeC"
    assert graded.confidence == 0.75
    assert graded.label == "apple_gradeC"


def test_classify_rejects_everything_below_the_confidence_threshold(classify):
    classifier = classify({"apple_gradeA": 0.4}, min_confidence=0.6)

    assert classifier.classify(FRAME) is None


def test_classify_ignores_a_label_it_cannot_map(classify):
    classifier = classify({"unmapped_thing": 0.99, "tomato_gradeB": 0.8})

    graded = classifier.classify(FRAME)

    assert graded.produce_type == "tomato"
    assert graded.tier == "gradeB"


def test_classify_returns_nothing_when_the_model_has_no_answer(classify):
    assert classify(None).classify(FRAME) is None


def test_classify_sends_the_frame_as_encoded_jpeg(classify):
    classifier = classify({"apple_gradeA": 0.9})

    classifier.classify(FRAME)

    image_bytes, image_type = classifier.brick.calls[0]
    assert image_type == "jpg"
    assert image_bytes[:2] == b"\xff\xd8"  # JPEG start-of-image marker
