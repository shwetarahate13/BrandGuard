"""Confidence routing and intent-preserving rewrite verification."""
import difflib
import logging
import re
from collections import Counter, defaultdict
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models.models import Decision, DecisionAction, Finding, SourceType, SubmissionVersion
from backend.app.pipeline.preference_model import score_acceptance

logger = logging.getLogger(__name__)


def compute_confidence_and_routing(
    finding: Dict[str, Any],
    source_similarity: float = 0.8,
    is_rule_based: bool = False,
    is_ambiguous: bool = False,
    acceptance_probability: float | None = None,
) -> Dict[str, Any]:
    """Label finding confidence as High / Medium / Low.
    
    Low confidence or ambiguous findings are flagged with needs_human=True.
    """
    if acceptance_probability is not None:
        finding["acceptance_probability"] = acceptance_probability

    if is_ambiguous:
        finding["confidence"] = "low"
        finding["needs_human"] = True
        return finding

    if is_rule_based:
        # Direct rule violations (exact term, strict regex, expired fact)
        finding["confidence"] = "high"
        finding["needs_human"] = False
    elif source_similarity >= 0.70:
        finding["confidence"] = "high"
        finding["needs_human"] = False
    elif source_similarity >= 0.45:
        finding["confidence"] = "medium"
        finding["needs_human"] = False
    else:
        # Low similarity to cited source - route to human reviewer
        finding["confidence"] = "low"
        finding["needs_human"] = True

    return finding


def _normalize_span(span: str) -> str:
    return re.sub(r"\s+", " ", span).strip().casefold()


def _dismissed_pattern_groups(db: Session) -> dict[tuple[str, str], dict[str, set[str]]]:
    """Group distinct disputed findings by clause/span across the workspace."""
    dismissed = (
        db.query(
            Decision.original_span,
            Finding.source_id,
            Finding.category,
            Finding.span_start,
            Finding.span_end,
            SubmissionVersion.text,
            Decision.finding_id,
        )
        .join(Finding, Finding.id == Decision.finding_id)
        .join(SubmissionVersion, SubmissionVersion.id == Finding.version_id)
        .filter(
            Decision.action == DecisionAction.dispute,
            Finding.source_type == SourceType.guideline_clause,
            Finding.source_id.isnot(None),
        )
        .all()
    )
    groups: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(
        lambda: {"finding_ids": set(), "categories": set()}
    )
    for original_span, clause_id, category, span_start, span_end, version_text, finding_id in dismissed:
        span = original_span
        if not span and span_start is not None and span_end is not None:
            span = version_text[max(0, span_start):max(span_start, span_end)]
        normalized = _normalize_span(span or "")
        if normalized:
            category_name = category.value if hasattr(category, "value") else str(category)
            group = groups[(str(clause_id), normalized)]
            group["finding_ids"].add(str(finding_id))
            group["categories"].add(category_name)
    return groups


def suppressed_span_combinations(db: Session, threshold: int = 3) -> set[tuple[str, str]]:
    """Find guideline/span pairs disputed repeatedly in this single-brand workspace."""
    groups = _dismissed_pattern_groups(db)
    return {
        key for key, group in groups.items()
        if len(group["finding_ids"]) >= threshold
    }


def suppressed_counts_by_category(db: Session, threshold: int = 3) -> Counter[str]:
    groups = _dismissed_pattern_groups(db)
    return Counter(
        category
        for group in groups.values()
        if len(group["finding_ids"]) >= threshold
        for category in group["categories"]
    )


def should_suppress_finding(
    finding: Dict[str, Any],
    original_span: str,
    suppressed: set[tuple[str, str]],
) -> bool:
    source_type = finding.get("source_type")
    source_type = source_type.value if hasattr(source_type, "value") else source_type
    if source_type != SourceType.guideline_clause.value:
        return False
    source_id = str(finding.get("source_id") or "")
    normalized = _normalize_span(original_span)
    return bool(source_id and normalized and (source_id, normalized) in suppressed)


def rank_findings_by_acceptance(db: Session, findings: list[Dict[str, Any]], source_text: str) -> list[Dict[str, Any]]:
    """Attach learned acceptance probabilities and return highest-ranked rewrites first."""
    for finding in findings:
        start = finding.get("span_start")
        end = finding.get("span_end")
        original = source_text[max(0, start):min(len(source_text), end)] if start is not None and end is not None else ""
        finding["acceptance_probability"] = score_acceptance(db, original, finding.get("suggested_rewrite"))
    return sorted(
        findings,
        key=lambda item: item.get("acceptance_probability") if item.get("acceptance_probability") is not None else 0.5,
        reverse=True,
    )


def verify_intent_preserved(
    original_span: str,
    suggested_rewrite: Optional[str],
    intent: Optional[str],
    source_type: SourceType | str | None = None,
) -> Optional[str]:
    """Verify that a suggested rewrite preserves the creator's stated intent.
    
    If intent is provided and the suggested rewrite diverts too drastically
    or empties the core message, return None instead of a bad suggestion.
    """
    if not suggested_rewrite or not suggested_rewrite.strip():
        return None

    orig_clean = original_span.strip().lower()
    rewrite_clean = suggested_rewrite.strip().lower()

    # If identical, no need for rewrite
    if orig_clean == rewrite_clean:
        return None

    # A terminology rule is an approved, organization-owned replacement for
    # the exact term in the span. Its wording may not share lexical roots with
    # the campaign intent (for example, "cheap" -> "accessible pricing"),
    # so the generic intent heuristic must not hide that deterministic fix.
    if source_type in (SourceType.term, SourceType.term.value, SourceType.approved_fact, SourceType.approved_fact.value):
        return suggested_rewrite.strip()

    # If creator provided no intent, accept sensible rewrite
    if not intent or not intent.strip():
        return suggested_rewrite.strip()

    intent_lower = intent.lower()

    # Direct word stem / root matching
    def get_roots(words):
        roots = set()
        for w in words:
            clean_w = "".join(c for c in w if c.isalnum())
            if len(clean_w) >= 4:
                roots.add(clean_w[:4])
            elif clean_w:
                roots.add(clean_w)
        return roots

    orig_roots = get_roots(orig_clean.split())
    rewrite_roots = get_roots(rewrite_clean.split())
    intent_roots = get_roots(intent_lower.split())

    shared_roots = rewrite_roots.intersection(orig_roots.union(intent_roots))

    # Also compute string similarity ratio
    ratio_orig = difflib.SequenceMatcher(None, orig_clean, rewrite_clean).ratio()
    ratio_intent = difflib.SequenceMatcher(None, intent_lower, rewrite_clean).ratio()

    # If there are shared roots between rewrite and original/intent, keep the rewrite
    if shared_roots:
        return suggested_rewrite.strip()

    logger.info("Dropping suggested rewrite: divergent from original span and intent anchors")
    return None
