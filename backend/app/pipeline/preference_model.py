"""Online preference learning from reviewer acceptance and edit decisions."""
from __future__ import annotations

import logging
import pickle
import re
import numpy as np
import textstat
from sklearn.linear_model import SGDClassifier
from sqlalchemy.orm import Session

from backend.app.models.models import Decision, DecisionAction, PreferenceModelState

logger = logging.getLogger(__name__)
MODEL_STATE_ID = "workspace-default"

FORMAL_MARKERS = {
    "accordingly", "additionally", "demonstrate", "ensure", "furthermore", "maintain",
    "provide", "therefore", "within", "require", "recommend", "appropriate",
}
INFORMAL_MARKERS = {
    "awesome", "cool", "gonna", "gotta", "kinda", "stuff", "super", "wanna",
    "yeah", "yep", "totally", "awesome",
}
CONTRACTION_PATTERN = re.compile(r"\b\w+(?:n't|'re|'ve|'ll|'d|'m)\b", re.I)


def _sentence_length(text: str) -> float:
    words = max(0, int(textstat.lexicon_count(text, removepunct=True)))
    sentences = max(1, int(textstat.sentence_count(text))) if text.strip() else 0
    return words / sentences if sentences else 0.0


def _formality_score(text: str) -> float:
    words = re.findall(r"[A-Za-z']+", text.lower())
    if not words:
        return 0.0
    formal = sum(word in FORMAL_MARKERS for word in words)
    informal = sum(word in INFORMAL_MARKERS for word in words)
    contraction_count = len(CONTRACTION_PATTERN.findall(text))
    return float(np.clip((formal - informal - contraction_count) / len(words), -1.0, 1.0))


def feature_vector(original_span: str, rewrite: str) -> np.ndarray:
    """Return normalized length, Flesch readability, and formality deltas."""
    original = original_span or ""
    candidate = rewrite or ""
    try:
        sentence_delta = _sentence_length(candidate) - _sentence_length(original)
        flesch_delta = float(textstat.flesch_reading_ease(candidate)) - float(textstat.flesch_reading_ease(original))
    except Exception:
        logger.exception("Could not calculate rewrite readability features")
        sentence_delta = 0.0
        flesch_delta = 0.0
    formality_delta = _formality_score(candidate) - _formality_score(original)
    return np.asarray([
        np.clip(sentence_delta / 20.0, -1.0, 1.0),
        np.clip(flesch_delta / 100.0, -1.0, 1.0),
        np.clip(formality_delta, -1.0, 1.0),
    ], dtype=np.float64)


def _load_classifier(db: Session, lock: bool = False) -> tuple[SGDClassifier | None, PreferenceModelState | None]:
    query = db.query(PreferenceModelState).filter(PreferenceModelState.id == MODEL_STATE_ID)
    if lock:
        query = query.with_for_update()
    state = query.first()
    if not state:
        return None, None
    try:
        model = pickle.loads(state.model_blob)
        if not isinstance(model, SGDClassifier):
            raise TypeError("Persisted preference model has an unexpected type")
        return model, state
    except Exception:
        logger.exception("Persisted preference model could not be loaded")
        return None, state


def score_acceptance(db: Session, original_span: str, rewrite: str | None) -> float | None:
    """Predict reviewer acceptance probability; return neutral before feedback exists."""
    if not rewrite or not rewrite.strip():
        return None
    model, state = _load_classifier(db)
    if model is None or state is None or state.sample_count == 0:
        return 0.5
    try:
        probability = float(model.predict_proba([feature_vector(original_span, rewrite)])[0][1])
        return float(np.clip(probability, 0.0, 1.0))
    except Exception:
        logger.exception("Preference model scoring failed")
        return 0.5


def partial_fit(db: Session, decision: Decision) -> int:
    """Update the online classifier and persist its weights in the current transaction."""
    action = decision.action.value if isinstance(decision.action, DecisionAction) else str(decision.action)
    original_span = decision.original_span or ""
    suggested = (decision.suggested_rewrite or "").strip()
    human_edit = (decision.human_edited_text or decision.edited_text or "").strip()
    examples: list[tuple[str, int]] = []

    if suggested and action in {"accept", "edit", "dispute"}:
        examples.append((suggested, 1 if action == "accept" else 0))
    if human_edit and action == "edit":
        # A reviewer-selected edit is a positive example of the preferred style.
        examples.append((human_edit, 1))
    if not examples:
        return 0

    model, state = _load_classifier(db, lock=True)
    if model is None:
        model = SGDClassifier(loss="log_loss", alpha=0.001, random_state=42, learning_rate="optimal")
    features = np.vstack([feature_vector(original_span, rewrite) for rewrite, _ in examples])
    labels = np.asarray([label for _, label in examples], dtype=np.int64)
    model.partial_fit(features, labels, classes=np.asarray([0, 1], dtype=np.int64))

    if state is None:
        state = PreferenceModelState(id=MODEL_STATE_ID, model_blob=b"", sample_count=0)
        db.add(state)
    state.model_blob = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
    state.sample_count = (state.sample_count or 0) + len(examples)
    db.flush()
    return len(examples)
