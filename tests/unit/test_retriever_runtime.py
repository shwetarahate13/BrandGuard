from pathlib import Path

import numpy as np

from backend.app.pipeline import retriever


class _DummySession:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _FakeSentenceTransformer:
    def __init__(self, path, **kwargs):
        self.path = path
        self.kwargs = kwargs

    def encode(self, _texts, **_kwargs):
        return np.asarray([[1.0, 0.0]], dtype="float32")


def _reset_retrieval_state():
    retriever._active_engine = "hash"
    retriever._active_collection_name = retriever.HASH_COLLECTION
    retriever._embedding_model = None
    retriever._retrieval_state.update({
        "state": "not_started",
        "engine": "HashingVectorizer fallback",
        "detail": "The neural model has not started warming up.",
    })


def test_embedding_warmup_uses_local_neural_model_and_reports_ready(tmp_path, monkeypatch):
    model_dir = tmp_path / "all-MiniLM-L6-v2"
    model_dir.mkdir()
    (model_dir / "modules.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(retriever, "get_settings", lambda: type("Settings", (), {"EMBEDDING_MODEL_PATH": str(model_dir)})())
    monkeypatch.setattr(retriever, "reindex_if_empty", lambda _db: 0)
    written = []
    monkeypatch.setattr(retriever, "_write_index", lambda _db, name, engine, model: written.append((name, engine, model)) or 1)
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", type("Module", (), {"SentenceTransformer": _FakeSentenceTransformer})())
    _reset_retrieval_state()

    retriever._warm_embedding_model(lambda: _DummySession())

    assert retriever._active_engine == "minilm"
    assert retriever._active_collection_name == retriever.NEURAL_COLLECTION
    assert retriever.get_retrieval_status()["state"] == "ready"
    assert retriever._encode(["test"], model=retriever._embedding_model)[0] == [1.0, 0.0]
    assert written and written[0][1] == "minilm"
    _reset_retrieval_state()


def test_missing_neural_model_keeps_hash_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(retriever, "get_settings", lambda: type("Settings", (), {"EMBEDDING_MODEL_PATH": str(tmp_path / "missing")})())
    monkeypatch.setattr(retriever, "reindex_if_empty", lambda _db: 0)
    _reset_retrieval_state()

    retriever._warm_embedding_model(lambda: _DummySession())

    assert retriever._active_engine == "hash"
    assert retriever.get_retrieval_status()["state"] == "fallback"
    assert retriever._encode(["test"])[0]
    _reset_retrieval_state()
