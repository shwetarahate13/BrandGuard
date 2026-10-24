"""Confidence routing and intent-preserving rewrite verification."""
import difflib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def compute_confidence_and_routing(
    finding: Dict[str, Any],
    source_similarity: float = 0.8,
    is_rule_based: bool = False,
    is_ambiguous: bool = False,
) -> Dict[str, Any]:
    """Label finding confidence as High / Medium / Low.
    
    Low confidence or ambiguous findings are flagged with needs_human=True.
    """
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


def verify_intent_preserved(
    original_span: str,
    suggested_rewrite: Optional[str],
    intent: Optional[str],
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
