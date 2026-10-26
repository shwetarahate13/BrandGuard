"""Calculate guideline dispute friction from persisted findings and decisions."""
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_session_factory
from backend.app.models.models import (
    Decision,
    DecisionAction,
    Finding,
    GuidelineClause,
    SourceType,
)

logger = logging.getLogger(__name__)

REASON_SIMILARITY_THRESHOLD = 0.35
MAX_CLUSTER_EXAMPLES = 3


def cluster_dispute_reasons(reasons: list[str]) -> list[dict]:
    """Group semantically similar dispute reasons using TF-IDF cosine similarity."""
    normalized = [reason.strip() for reason in reasons if reason and reason.strip()]
    if not normalized:
        return []

    frequencies = Counter(normalized)
    unique_reasons = list(frequencies)
    if len(unique_reasons) == 1:
        return [{"count": len(normalized), "examples": [unique_reasons[0]]}]

    try:
        vectors = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(unique_reasons)
        similarities = cosine_similarity(vectors)
    except ValueError:
        # Empty vocabularies can occur for short reasons made only of stop words.
        return [
            {"count": frequencies[reason], "examples": [reason]}
            for reason in unique_reasons
        ]

    parents = list(range(len(unique_reasons)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left in range(len(unique_reasons)):
        for right in range(left + 1, len(unique_reasons)):
            if similarities[left, right] >= REASON_SIMILARITY_THRESHOLD:
                union(left, right)

    clusters: dict[int, list[str]] = defaultdict(list)
    for index, reason in enumerate(unique_reasons):
        clusters[find(index)].append(reason)

    results = []
    for cluster in clusters.values():
        cluster.sort(key=lambda reason: (-frequencies[reason], reason.casefold()))
        results.append({
            "count": sum(frequencies[reason] for reason in cluster),
            "examples": cluster[:MAX_CLUSTER_EXAMPLES],
        })
    return sorted(results, key=lambda item: (-item["count"], item["examples"][0].casefold()))


def collect_clause_dispute_metrics(db: Session) -> dict[str, dict]:
    """Aggregate total and disputed findings, plus grouped reasons, per cited clause."""
    total_rows = (
        db.query(Finding.source_id, func.count(func.distinct(Finding.id)))
        .filter(Finding.source_type == SourceType.guideline_clause)
        .group_by(Finding.source_id)
        .all()
    )
    totals = {clause_id: count for clause_id, count in total_rows if clause_id}

    disputed_rows = (
        db.query(Finding.source_id, Finding.id, Decision.reason)
        .join(Decision, Decision.finding_id == Finding.id)
        .filter(
            Finding.source_type == SourceType.guideline_clause,
            Decision.action == DecisionAction.dispute,
        )
        .all()
    )
    disputed_ids: dict[str, set[str]] = defaultdict(set)
    reasons: dict[str, list[str]] = defaultdict(list)
    for clause_id, finding_id, reason in disputed_rows:
        if not clause_id:
            continue
        disputed_ids[clause_id].add(finding_id)
        if reason and reason.strip():
            reasons[clause_id].append(reason.strip())

    all_clause_ids = set(totals) | set(disputed_ids)
    return {
        clause_id: {
            "total_findings": totals.get(clause_id, 0),
            "disputed_findings": len(disputed_ids.get(clause_id, set())),
            "dispute_clusters": cluster_dispute_reasons(reasons.get(clause_id, [])),
        }
        for clause_id in all_clause_ids
    }


def update_dispute_friction_index(db: Session) -> int:
    """Recalculate and persist DFI for every guideline clause."""
    metrics = collect_clause_dispute_metrics(db)
    clauses = db.query(GuidelineClause).all()
    computed_at = datetime.now(timezone.utc)
    for clause in clauses:
        row = metrics.get(clause.id, {})
        total_findings = row.get("total_findings", 0)
        disputed_findings = row.get("disputed_findings", 0)
        clause.dispute_friction_index = round(
            (disputed_findings / total_findings) * 100.0,
            2,
        ) if total_findings else 0.0
        clause.dfi_computed_at = computed_at
    db.commit()
    logger.info("Updated dispute friction index for %d guideline clauses", len(clauses))
    return len(clauses)


def dfi_scores_are_stale(db: Session, max_age: timedelta = timedelta(hours=24)) -> bool:
    """Return whether any persisted clause score is missing or older than max_age."""
    clauses = db.query(GuidelineClause)
    if clauses.count() == 0:
        return False
    if clauses.filter(GuidelineClause.dfi_computed_at.is_(None)).first() is not None:
        return True
    oldest = db.query(func.min(GuidelineClause.dfi_computed_at)).scalar()
    if oldest is None:
        return True
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    return oldest < datetime.now(timezone.utc) - max_age


def run_dfi_worker(session_or_factory=None) -> int | None:
    """Run with a supplied Session or an owned scheduled session.

    Failures are logged and returned as ``None`` so they never stop the app.
    """
    db = None
    owns_session = not isinstance(session_or_factory, Session)
    try:
        if owns_session:
            session_factory = session_or_factory or get_session_factory()
            db = session_factory()
        else:
            db = session_or_factory
        return update_dispute_friction_index(db)
    except Exception:
        if db is not None:
            db.rollback()
        logger.exception("Guideline DFI worker failed")
        return None
    finally:
        if db is not None and owns_session:
            db.close()
