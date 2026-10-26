"""Offline feature extraction and online SGD persistence tests."""
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Decision, DecisionAction, PreferenceModelState
from backend.app.pipeline.confidence import rank_findings_by_acceptance
from backend.app.pipeline.preference_model import (
    MODEL_STATE_ID,
    _load_classifier,
    feature_vector,
    partial_fit,
    score_acceptance,
)


def test_feature_vector_uses_offline_textstat_counts():
    features = feature_vector(
        "Simple claim.",
        "Additionally, we provide a clear and helpful explanation to every customer.",
    )

    assert features.shape == (3,)
    assert np.isfinite(features).all()
    assert features[0] > 0


def test_accept_edit_and_dispute_train_and_persist_online_model():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        decisions = [
            Decision(
                id="decision-accept",
                finding_id="finding-accept",
                user_id="creator",
                action=DecisionAction.accept,
                original_span="A much longer claim with several extra words.",
                suggested_rewrite="A short claim.",
            ),
            Decision(
                id="decision-edit",
                finding_id="finding-edit",
                user_id="creator",
                action=DecisionAction.edit,
                original_span="Make this copy clearer for our customers.",
                suggested_rewrite="Use concise promotional language.",
                human_edited_text="Say it simply and honestly.",
            ),
            Decision(
                id="decision-dispute",
                finding_id="finding-dispute",
                user_id="creator",
                action=DecisionAction.dispute,
                original_span="This product works well.",
                suggested_rewrite="This product may work well.",
                reason="The guideline does not require a hedge.",
            ),
        ]
        for decision in decisions:
            db.add(decision)
            db.flush()
            partial_fit(db, decision)
        db.commit()

        state = db.get(PreferenceModelState, MODEL_STATE_ID)
        model, loaded_state = _load_classifier(db)
        assert state is not None
        assert state.sample_count == 4
        assert loaded_state is state
        assert model is not None
        assert model.classes_.tolist() == [0, 1]
        assert 0.0 <= score_acceptance(db, "A much longer claim with several extra words.", "A short claim.") <= 1.0

    engine.dispose()


def test_rank_findings_uses_predicted_acceptance_probability(monkeypatch):
    from backend.app.pipeline import confidence

    probabilities = {
        "Rewrite A": 0.2,
        "Rewrite B": 0.9,
    }
    monkeypatch.setattr(
        confidence,
        "score_acceptance",
        lambda _db, _original, rewrite: probabilities[rewrite],
    )
    candidates = [
        {"span_start": 0, "span_end": 5, "suggested_rewrite": "Rewrite A"},
        {"span_start": 6, "span_end": 11, "suggested_rewrite": "Rewrite B"},
    ]

    ranked = rank_findings_by_acceptance(None, candidates, "First Second")

    assert [item["suggested_rewrite"] for item in ranked] == ["Rewrite B", "Rewrite A"]
    assert [item["acceptance_probability"] for item in ranked] == [0.9, 0.2]
