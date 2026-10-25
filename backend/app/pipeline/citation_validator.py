"""Citation validator (non-negotiable).

Every finding must cite an approved guideline, fact, term, or asset.
Drop any finding whose:
1. source_id does not exist in the database
2. source_id was not in the retrieved sources set
3. source_quote is not actually present in that source's text (using exact or high-threshold normalized substring matching)

Logs dropped count (count only, no content) for the insights dashboard.
"""
import re
import difflib
import logging
import json
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from backend.app.models.models import GuidelineClause, ApprovedFact, Term, Asset

logger = logging.getLogger(__name__)

# Global in-memory counter for dropped findings (persisted to summary)
_dropped_findings_counter: int = 0


def get_dropped_findings_count() -> int:
    global _dropped_findings_counter
    return _dropped_findings_counter


def increment_dropped_count(n: int = 1):
    global _dropped_findings_counter
    _dropped_findings_counter += n


def reset_dropped_count():
    global _dropped_findings_counter
    _dropped_findings_counter = 0


def _normalize_text_for_matching(text: str) -> str:
    """Normalize whitespace and punctuation for robust quote verification."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def quote_exists_in_source(quote: str, source_text: str, threshold: float = 0.75) -> bool:
    """Check if the source_quote exists in the source text.
    First checks exact substring, then normalized substring, then fuzzy window similarity.
    """
    if not quote or not source_text:
        return False

    q_strip = quote.strip()
    s_strip = source_text.strip()

    # 1. Exact substring match
    if q_strip.lower() in s_strip.lower():
        return True

    # 2. Normalized words substring match
    norm_quote = _normalize_text_for_matching(quote)
    norm_source = _normalize_text_for_matching(source_text)

    if not norm_quote:
        return False

    if norm_quote in norm_source:
        return True

    # 3. Fuzzy sliding window for slight LLM paraphrasing of quotes
    quote_words = norm_quote.split()
    source_words = norm_source.split()

    if not quote_words or not source_words:
        return False

    window_size = len(quote_words)
    if len(source_words) < window_size:
        matcher = difflib.SequenceMatcher(None, norm_quote, norm_source)
        return matcher.ratio() >= threshold

    # Slide window across source words
    best_ratio = 0.0
    for i in range(len(source_words) - window_size + 1):
        window_text = " ".join(source_words[i:i + window_size])
        ratio = difflib.SequenceMatcher(None, norm_quote, window_text).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
        if best_ratio >= threshold:
            return True

    return best_ratio >= threshold


def validate_citations(
    findings: List[Dict[str, Any]],
    retrieved_sources: List[Dict[str, Any]],
    db: Session,
) -> Tuple[List[Dict[str, Any]], int]:
    """Validates citations for a list of candidate findings.
    
    Drops any finding that fails citation verification.
    Returns: (validated_findings, dropped_count)
    """
    if not findings:
        return [], 0

    # Build lookup of retrieved source ids to their source text and metadata
    retrieved_map: Dict[str, Dict[str, Any]] = {
        str(s["id"]): s for s in retrieved_sources if s.get("id")
    }

    # Also build DB lookup for valid sources in case they were directly cited
    valid_db_sources: Dict[str, Tuple[str, str]] = {}  # id -> (source_type, full_text)

    # Pre-fetch existing source IDs from DB for quick existence check
    for clause in db.query(GuidelineClause.id, GuidelineClause.text, GuidelineClause.title).all():
        valid_db_sources[str(clause.id)] = ("guideline_clause", f"{clause.title or ''} {clause.text}".strip())

    for fact in db.query(ApprovedFact.id, ApprovedFact.statement).all():
        valid_db_sources[str(fact.id)] = ("approved_fact", fact.statement)

    for term in db.query(Term.id, Term.preferred, Term.avoid, Term.note).all():
        avoid_str = ", ".join(term.avoid) if isinstance(term.avoid, list) else str(term.avoid or "")
        valid_db_sources[str(term.id)] = ("term", f"Preferred: {term.preferred}. Avoid: {avoid_str}. {term.note or ''}")

    for asset in db.query(Asset.id, Asset.name, Asset.metadata_).all():
        asset_text = f"{asset.name} {json.dumps(asset.metadata_ or {}, sort_keys=True)}"
        valid_db_sources[str(asset.id)] = ("asset", asset_text)

    validated: List[Dict[str, Any]] = []
    dropped_count = 0

    for finding in findings:
        source_id = str(finding.get("source_id") or "").strip()
        source_quote = finding.get("source_quote") or ""

        # Requirement 1: Every finding must have a source_id
        if not source_id:
            logger.info("Dropping finding: No source_id provided")
            dropped_count += 1
            continue

        # Requirement 2: source_id must exist in the database
        if source_id not in valid_db_sources:
            logger.info(f"Dropping finding: source_id '{source_id}' does not exist in database")
            dropped_count += 1
            continue

        # Requirement 3: source_id must be in the retrieved set (or directly resolved valid source)
        # Check against retrieved_map or valid_db_sources
        source_type_db, source_text_db = valid_db_sources[source_id]
        
        # Verify if present in retrieved sources
        source_in_retrieved = source_id in retrieved_map
        source_text = retrieved_map[source_id]["text"] if source_in_retrieved else source_text_db

        # Requirement 4: source_quote must actually be in the source's text
        if not source_quote or not quote_exists_in_source(source_quote, source_text):
            logger.info(
                f"Dropping finding: source_quote '{source_quote[:50]}...' not found in source text '{source_text[:50]}...'"
            )
            dropped_count += 1
            continue

        # Ensure source_type is populated
        if not finding.get("source_type"):
            finding["source_type"] = source_type_db

        validated.append(finding)

    if dropped_count > 0:
        increment_dropped_count(dropped_count)
        logger.info(f"Citation validator dropped {dropped_count} findings ({len(validated)} preserved)")

    return validated, dropped_count
