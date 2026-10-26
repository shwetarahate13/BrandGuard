"""ChromaDB retrieval over approved sources with TF-IDF / Hashing embeddings."""
import os
import logging
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import HashingVectorizer
from chromadb.api.types import Documents, EmbeddingFunction

from backend.app.config import get_settings
from backend.app.models.models import GuidelineClause, ApprovedFact, Term, Asset

logger = logging.getLogger(__name__)

# Collection name for all approved brand sources
COLLECTION_NAME = "approved_sources"


class LightweightEmbeddingFunction(EmbeddingFunction[Documents]):
    """Stateless hashing vectorizer for 512MB RAM budget.
    Implements Chroma's EmbeddingFunction interface without heavy neural models.
    """
    def __init__(self, n_features: int = 256):
        self.n_features = n_features
        self.vectorizer = HashingVectorizer(
            n_features=n_features,
            stop_words="english",
            norm="l2",
            alternate_sign=False,
        )

    @staticmethod
    def name() -> str:
        return "lightweight_tfidf"

    @staticmethod
    def build_from_config(config: dict) -> "LightweightEmbeddingFunction":
        return LightweightEmbeddingFunction(n_features=int(config.get("n_features", 256)))

    def is_legacy(self) -> bool:
        return False

    def supported_spaces(self) -> List[str]:
        return ["cosine"]

    def get_config(self) -> dict:
        return {"n_features": self.n_features}

    def embed_query(self, input: str) -> List[float]:
        res = self([input])
        return res[0] if res else []

    def embed_documents(self, input: List[str]) -> List[List[float]]:
        return self(input)

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not input:
            return []
        # Ensure all items are strings
        cleaned = [str(t) if t else "" for t in input]
        matrix = self.vectorizer.transform(cleaned)
        return matrix.toarray().astype(float).tolist()


_chroma_client = None
_embedding_fn = None


def get_embedding_function():
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = LightweightEmbeddingFunction(n_features=256)
    return _embedding_fn


def get_chroma_client():
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    import chromadb
    from chromadb.config import Settings as ChromaSettings

    settings = get_settings()
    persist_dir = settings.CHROMA_PERSIST_DIR
    os.makedirs(persist_dir, exist_ok=True)

    _chroma_client = chromadb.PersistentClient(
        path=persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False, is_persistent=True)
    )
    return _chroma_client


def get_collection():
    client = get_chroma_client()
    fn = get_embedding_function()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=fn,
        metadata={"hnsw:space": "cosine"},
    )


def index_all_sources(db: Session) -> int:
    """Index or re-index all approved guidelines, facts, terms, and assets from Postgres into Chroma."""
    client = get_chroma_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass

    collection = get_collection()

    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []

    # 1. Guideline clauses
    clauses = db.query(GuidelineClause).all()
    for c in clauses:
        doc_text = f"{c.code or ''} {c.title or ''}: {c.text}".strip()
        documents.append(doc_text)
        ids.append(f"clause_{c.id}")
        metadatas.append({
            "source_type": "guideline_clause",
            "source_id": str(c.id),
            "title": str(c.title or c.code or "Guideline Clause"),
            "doc_id": str(c.doc_id),
        })

    # 2. Approved facts
    facts = db.query(ApprovedFact).all()
    for f in facts:
        documents.append(f.statement)
        ids.append(f"fact_{f.id}")
        metadatas.append({
            "source_type": "approved_fact",
            "source_id": str(f.id),
            "title": "Approved Fact",
            "valid_to": f.valid_to.isoformat() if f.valid_to else "",
        })

    # 3. Approved terms
    terms = db.query(Term).all()
    for t in terms:
        avoid_str = ", ".join(t.avoid) if isinstance(t.avoid, list) else str(t.avoid)
        doc_text = f"Preferred term: {t.preferred}. Avoid: {avoid_str}. Note: {t.note or ''}".strip()
        documents.append(doc_text)
        ids.append(f"term_{t.id}")
        metadatas.append({
            "source_type": "term",
            "source_id": str(t.id),
            "title": f"Term: {t.preferred}",
        })

    # 4. Assets
    assets = db.query(Asset).all()
    for a in assets:
        metadata_text = json.dumps(a.metadata_ or {}, sort_keys=True)
        doc_text = f"Asset {a.name} ({a.kind.value}): {a.file_path or ''}. Metadata: {metadata_text}".strip()
        documents.append(doc_text)
        ids.append(f"asset_{a.id}")
        metadatas.append({
            "source_type": "asset",
            "source_id": str(a.id),
            "title": f"Asset: {a.name}",
        })

    if documents:
        # Chroma add in batches if needed
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            collection.add(
                documents=documents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
                ids=ids[i:i + batch_size],
            )
        logger.info(f"Indexed {len(documents)} approved sources into ChromaDB")

    return len(documents)


def reindex_if_empty(db: Session) -> int:
    """If Chroma collection is empty, re-index all sources from Postgres."""
    try:
        collection = get_collection()
        count = collection.count()
        if count == 0:
            logger.info("ChromaDB collection empty. Running re-index from Postgres...")
            return index_all_sources(db)
        return count
    except Exception as e:
        logger.warning(f"Error checking Chroma count, attempting full reindex: {e}")
        return index_all_sources(db)


def retrieve_sources(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Retrieve top-k relevant approved sources for a query span."""
    if not query or not query.strip():
        return []

    try:
        collection = get_collection()
        count = collection.count()
        if count == 0:
            return []

        actual_k = min(top_k, count)
        emb_fn = get_embedding_function()
        query_emb = emb_fn([query])

        results = collection.query(
            query_embeddings=query_emb,
            n_results=actual_k,
            include=["documents", "metadatas", "distances"],
        )

        sources = []
        if results and results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, distances):
                # Cosine distance to similarity: similarity = 1 - distance
                similarity = max(0.0, 1.0 - float(dist)) if dist is not None else 0.5
                sources.append({
                    "id": meta.get("source_id"),
                    "type": meta.get("source_type"),
                    "title": meta.get("title"),
                    "text": doc,
                    "similarity": round(similarity, 3),
                })
        return sources
    except Exception as e:
        logger.error(f"Error retrieving sources from Chroma: {e}")
        return []
