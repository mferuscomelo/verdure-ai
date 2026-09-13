"""Produce identification and freshness grading.

Runs the captured frame through the `arduino:image_classification` brick,
which loads the Edge Impulse model and does inference in a sidecar
container on the board -- no cloud call at scan time.

The model is a single classifier over combined `<type>_<grade>` labels
(`apple_gradeA`, `banana_gradeC`, `tomato_reject`, ...) rather than one
model per fruit: the visual cues that separate a grade A apple from a grade
C one are the same cues that separate the fruits themselves, so one network
sees all of it and there is a single artefact to deploy and version.

A label is only accepted if it clears `PRODUCE_MIN_CONFIDENCE` and both
halves are known to config.py. Anything else comes back as None, and the
checkout asks for the item to be re-placed rather than inventing a price
for something it did not recognise.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from config import PRODUCE_DISCOUNT_BY_TIER, PRODUCE_MIN_CONFIDENCE, PRODUCE_PRICE_PER_KG

# Keys the brick may use for the label and the score in a prediction entry.
_LABEL_KEYS = ("label", "class", "name", "category")
_SCORE_KEYS = ("value", "confidence", "score", "probability")
# Keys a result dict may nest its prediction list under.
_LIST_KEYS = ("results", "predictions", "classification", "classifications", "labels")


@dataclass
class ProduceGrade:
    produce_type: str  # "apple", "banana", ...
    tier: str  # "gradeA" | "gradeB" | "gradeC" | "reject"
    confidence: float
    label: str  # the raw model label, e.g. "apple_gradeB"


def _score_of(entry: dict) -> float | None:
    for key in _SCORE_KEYS:
        if key in entry:
            try:
                return float(entry[key])
            except (TypeError, ValueError):
                return None
    return None


def _label_of(entry: dict) -> str | None:
    for key in _LABEL_KEYS:
        value = entry.get(key)
        if isinstance(value, str):
            return value
    return None


def _extract_predictions(result) -> list[tuple[str, float]]:
    """Normalise the brick's result into (label, score) pairs.

    Classification results come back either as a mapping of label to score
    or as a list of per-label entries, so both are flattened here and the
    rest of the module works in one shape.
    """
    if result is None:
        return []

    if isinstance(result, dict):
        for key in _LIST_KEYS:
            if isinstance(result.get(key), (list, tuple)):
                return _extract_predictions(result[key])
        pairs = []
        for label, score in result.items():
            if isinstance(label, str) and isinstance(score, (int, float)):
                pairs.append((label, float(score)))
        return pairs

    if isinstance(result, (list, tuple)):
        pairs = []
        for entry in result:
            if isinstance(entry, dict):
                label, score = _label_of(entry), _score_of(entry)
                if label is not None and score is not None:
                    pairs.append((label, score))
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                label, score = entry
                if isinstance(label, str) and isinstance(score, (int, float)):
                    pairs.append((label, float(score)))
        return pairs

    return []


def parse_label(label: str) -> tuple[str, str] | None:
    """Split `apple_gradeA` into ("apple", "gradeA").

    Split on the last underscore so multi-word produce types ("sweet_potato")
    keep working. Both halves must be known to config.py, which keeps an
    unexpected label out of the pricing path instead of raising a KeyError
    deeper in.
    """
    produce_type, separator, tier = label.rpartition("_")
    if not separator:
        return None
    if produce_type not in PRODUCE_PRICE_PER_KG or tier not in PRODUCE_DISCOUNT_BY_TIER:
        return None
    return produce_type, tier


class ProduceClassifier:
    def __init__(self, min_confidence: float = PRODUCE_MIN_CONFIDENCE):
        from arduino.app_bricks.image_classification import ImageClassification

        self._min_confidence = min_confidence
        self._classifier = ImageClassification(confidence=min_confidence)

    def classify(self, frame: np.ndarray) -> ProduceGrade | None:
        """Identify the produce and its condition, or None if unrecognised."""
        encoded, buffer = cv2.imencode(".jpg", frame)
        if not encoded:
            return None

        result = self._classifier.classify(buffer.tobytes(), image_type="jpg")
        return self._best_grade(_extract_predictions(result))

    def _best_grade(self, predictions: list[tuple[str, float]]) -> ProduceGrade | None:
        for label, score in sorted(predictions, key=lambda pair: pair[1], reverse=True):
            if score < self._min_confidence:
                return None  # sorted, so nothing below this clears it either
            parsed = parse_label(label)
            if parsed is not None:
                produce_type, tier = parsed
                return ProduceGrade(
                    produce_type=produce_type, tier=tier, confidence=score, label=label
                )
        return None


def get_produce_classifier() -> ProduceClassifier:
    return ProduceClassifier()
