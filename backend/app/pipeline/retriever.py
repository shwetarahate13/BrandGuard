"""Approved-source retrieval with a neural encoder and automatic hash fallback."""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import HashingVectorizer
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models.models import ApprovedFact, Asset, GuidelineClause, Term

logger = logging.getLogger(__name__)

HASH_COLLECTION = "approved_sources_hash_v1"
NEURAL_COLLECTION = "approved_sources_minilm_v1"
COLLECTION_NAME = HASH_COLLECTION  # Compatibility for diagnostics and tests.

_client = None
_state_lock = threading.RLock()
_warmup_thread: threading.Thread | None = None
_hash_vectorizer = HashingVectorizer(
    n_features=384,
    stop_words="english",
    norm="l2",
    alternate_sign=False,
)
_embedding_model = None
_active_engine = "hash"
_active_collection_name = HASH_COLLECTION
_source_revision = 0
_retrieval_state = {
    "state": "not_started",
    "engine": "HashingVectorizer fallback",
    "detail": "The neural model has not started warming up.",
}


def _encode(texts: list[str], engine: str | None = None, model=None) -> list[list[float]]:
    engine = engine or _active_engine
    if engine == "minilm" and model is not None:
        vectors = model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vectors.astype("float32").tolist()
    matrix = _hash_vectorizer.transform([str(text or "") for text in texts])
    return matrix.toarray().astype("float32").tolist()


def get_chroma_client():
    global _client
    if _client is not None:
        return _client

    import chromadb
    from chromadb.config import Settings as ChromaSettings

    persist_dir = get_settings().CHROMA_PERSIST_DIR
    os.makedirs(persist_dir, exist_ok=True)
    _client = chromadb.PersistentClient(
        path=persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False, is_persistent=True),
    )
    return _client


def _collection(name: str):
    return get_chroma_client().get_or_create_collection(
        name=name,
        embedding_function=None,
        metadata={"hnsw:space": "cosine", "embedding_engine": name.rsplit("_", 1)[-1]},
    )


def get_collection():
    """Return the index currently serving requests."""
    with _state_lock:
        name = _active_collection_name
    return _collection(name)


def get_retrieval_status() -> dict[str, str]:
    with _state_lock:
        return dict(_retrieval_state)


def _read_sources(db: Session) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    ids: list[str] = []

    for clause in db.query(GuidelineClause).all():
        documents.append(f"{clause.code or ''} {clause.title or ''}: {clause.text}".strip())
        ids.append(f"clause_{clause.id}")
        metadatas.append({
            "source_type": "guideline_clause",
            "source_id": str(clause.id),
            "title": str(clause.title or clause.code or "Guideline Clause"),
            "doc_id": str(clause.doc_id),
        })

    for fact in db.query(ApprovedFact).all():
        documents.append(fact.statement)
        ids.append(f"fact_{fact.id}")
        metadatas.append({
            "source_type": "approved_fact",
            "source_id": str(fact.id),
            "title": "Approved Fact",
            "valid_to": fact.valid_to.isoformat() if fact.valid_to else "",
        })

    for term in db.query(Term).all():
        avoid = ", ".join(term.avoid) if isinstance(term.avoid, list) else str(term.avoid)
        documents.append(f"Preferred term: {term.preferred}. Avoid: {avoid}. Note: {term.note or ''}".strip())
        ids.append(f"term_{term.id}")
        metadatas.append({"source_type": "term", "source_id": str(term.id), "title": f"Term: {term.preferred}"})

    for asset in db.query(Asset).all():
        metadata_text = json.dumps(asset.metadata_ or {}, sort_keys=True)
        documents.append(f"Asset {asset.name} ({asset.kind.value}): {asset.file_path or ''}. Metadata: {metadata_text}".strip())
        ids.append(f"asset_{asset.id}")
        metadatas.append({"source_type": "asset", "source_id": str(asset.id), "title": f"Asset: {asset.name}"})

    return documents, metadatas, ids


def _write_index(
    db: Session,
    name: str,
    engine: str,
    model=None,
) -> int:
    documents, metadatas, ids = _read_sources(db)
    client = get_chroma_client()
    try:
        client.delete_collection(name=name)
    except Exception:
        pass
    collection = client.create_collection(
        name=name,
        embedding_function=None,
        metadata={"hnsw:space": "cosine", "embedding_engine": engine},
    )
    for start in range(0, len(documents), 100):
        batch_docs = documents[start : start + 100]
        collection.add(
            documents=batch_docs,
            embeddings=_encode(batch_docs, engine=engine, model=model),
            metadatas=metadatas[start : start + 100],
            ids=ids[start : start + 100],
        )
    logger.info("Indexed %s approved sources with %s", len(documents), engine)
    return len(documents)


def index_all_sources(db: Session) -> int:
    """Rebuild the active source index after approved sources change."""
    global _source_revision
    with _state_lock:
        _source_revision += 1
        engine = _active_engine
        name = _active_collection_name
        model = _embedding_model
        return _write_index(db, name, engine, model)


def reindex_if_empty(db: Session) -> int:
    """Build the active index if it has no sources."""
    try:
        collection = get_collection()
        count = collection.count()
        if count == 0:
            return index_all_sources(db)
        return count
    except Exception:
        logger.exception("Could not read the approved-source index; rebuilding it")
        return index_all_sources(db)


def _warm_embedding_model(session_factory) -> None:
    global _active_engine, _active_collection_name, _embedding_model
    settings = get_settings()
    model_path = Path(settings.EMBEDDING_MODEL_PATH).expanduser()
    try:
        with session_factory() as db:
            reindex_if_empty(db)
    except Exception:
        logger.exception("Initial approved-source hash index could not be prepared")
    try:
        from sentence_transformers import SentenceTransformer

        if not model_path.is_dir():
            raise FileNotFoundError(f"Embedding model not found at {model_path}; run scripts/setup_local.py")
        model = SentenceTransformer(str(model_path), local_files_only=True, device="cpu")
        # Initialize model weights before indexing, keeping model load failures
        # out of the first user request.
        model.encode(["BrandGuard retrieval warm-up"], show_progress_bar=False, convert_to_numpy=True)
    except Exception as exc:
        with _state_lock:
            _retrieval_state.update({
                "state": "fallback",
                "engine": "HashingVectorizer fallback",
                "detail": f"Neural retrieval unavailable; using the local hashing fallback ({type(exc).__name__}).",
            })
        logger.warning("Neural retrieval unavailable; retaining hashing fallback: %s", exc)
        return

    with _state_lock:
        _retrieval_state.update({"state": "reindexing", "engine": "all-MiniLM-L6-v2", "detail": "Rebuilding approved-source vectors."})

    try:
        while True:
            with _state_lock:
                revision = _source_revision
            with session_factory() as db:
                _write_index(db, NEURAL_COLLECTION, "minilm", model)
            with _state_lock:
                if revision != _source_revision:
                    continue
                _embedding_model = model
                _active_engine = "minilm"
                _active_collection_name = NEURAL_COLLECTION
                _retrieval_state.update({"state": "ready", "engine": "all-MiniLM-L6-v2", "detail": "Neural source retrieval is ready."})
                return
    except Exception as exc:
        with _state_lock:
            _retrieval_state.update({
                "state": "fallback",
                "engine": "HashingVectorizer fallback",
                "detail": f"Neural index build failed; using the local hashing fallback ({type(exc).__name__}).",
            })
        logger.exception("Neural retrieval index failed; retaining hashing fallback")


def start_embedding_warmup(session_factory) -> None:
    """Warm the optional neural model in the background without delaying startup."""
    global _warmup_thread
    with _state_lock:
        if _warmup_thread and _warmup_thread.is_alive():
            return
        _retrieval_state.update({"state": "warming_up", "engine": "HashingVectorizer fallback", "detail": "Loading the neural model in the background."})
        _warmup_thread = threading.Thread(
            target=_warm_embedding_model,
            args=(session_factory,),
            name="brandguard-embedding-warmup",
            daemon=True,
        )
        _warmup_thread.start()


def initialize_retrieval_worker(session_factory) -> str:
    """Select the configured neural engine inside an isolated job process."""
    global _active_engine, _active_collection_name, _embedding_model
    settings = get_settings()
    model_path = Path(settings.EMBEDDING_MODEL_PATH).expanduser()
    try:
        from sentence_transformers import SentenceTransformer

        if not model_path.is_dir():
            raise FileNotFoundError("local embedding model is missing")
        model = SentenceTransformer(str(model_path), local_files_only=True, device="cpu")
        model.encode(["BrandGuard worker warm-up"], show_progress_bar=False, convert_to_numpy=True)
        collection = _collection(NEURAL_COLLECTION)
        if collection.count() == 0:
            with session_factory() as db:
                _write_index(db, NEURAL_COLLECTION, "minilm", model)
        _embedding_model = model
        _active_engine = "minilm"
        _active_collection_name = NEURAL_COLLECTION
        return "all-MiniLM-L6-v2"
    except Exception as exc:
        _embedding_model = None
        _active_engine = "hash"
        _active_collection_name = HASH_COLLECTION
        logger.warning("Worker neural retrieval unavailable; using hash fallback: %s", exc)
        return "HashingVectorizer fallback"


def retrieve_sources(query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    """Retrieve source records using whichever vector engine is ready."""
    if not query or not query.strip():
        return []

    with _state_lock:
        try:
            collection = _collection(_active_collection_name)
            count = collection.count()
            if count == 0:
                return []
            amount = min(top_k or get_settings().RETRIEVAL_TOP_K, count)
            vectors = _encode([query], engine=_active_engine, model=_embedding_model)
            results = collection.query(
                query_embeddings=vectors,
                n_results=amount,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            logger.exception("Approved-source retrieval failed")
            return []

    sources = []
    if results and results.get("documents") and results["documents"][0]:
        docs = results["documents"][0]
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
        for doc, meta, distance in zip(docs, metas, distances):
            similarity = max(0.0, 1.0 - float(distance)) if distance is not None else 0.5
            sources.append({
                "id": meta.get("source_id"),
                "type": meta.get("source_type"),
                "title": meta.get("title"),
                "text": doc,
                "similarity": round(similarity, 3),
            })
    return sources
