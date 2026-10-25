"""Review pipeline runner orchestrating all stages:

1. Normalize and segment content into reviewable spans
2. Deterministic rules engine (terminology, forbidden claims, outdated facts, accessibility, tone)
3. Retrieval of top-k relevant sources from ChromaDB
4. LLM check (or offline deterministic mock mode)
5. Citation validator (strict verification of source_id, presence in retrieved set, and quote match)
6. Confidence routing (High / Medium / Low; Low -> needs_human=True)
7. Intent-preserving rewrite verification
8. Persist findings to database for the given version
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models.models import (
    Submission, SubmissionVersion, Finding,
    FindingCategory, FindingSeverity, FindingConfidence, FindingStatus, SourceType,
    GuidelineClause, ApprovedFact, Term
)
from backend.app.pipeline.segmenter import segment_into_spans
from backend.app.pipeline.rules_engine import run_rules_engine, RuleFinding
from backend.app.pipeline.retriever import retrieve_sources, reindex_if_empty
from backend.app.pipeline.citation_validator import validate_citations
from backend.app.pipeline.confidence import compute_confidence_and_routing, verify_intent_preserved
from backend.app.llm.client import get_llm_client, check_content_with_llm, MockProvider

logger = logging.getLogger(__name__)


def _mock_llm_check(
    text: str,
    spans: list,
    intent: Optional[str],
    retrieved_sources: list[dict],
    terms: list[dict],
    clauses: list[dict],
    facts: list[dict],
) -> list[dict]:
    """Deterministic mock check for offline demo mode with zero API keys.
    Generates realistic, explainable findings by matching against guidelines and facts.
    """
    mock_findings = []

    # Check for ambiguous phrasing (e.g., 'all-natural') that needs human reviewer
    text_lower = text.lower()
    if "all-natural" in text_lower or "100% natural" in text_lower:
        # Find matching clause on natural claims or ingredient transparency
        nat_clause = None
        for c in clauses:
            if "natural" in c.get("text", "").lower() or "ingredient" in c.get("text", "").lower():
                nat_clause = c
                break
        
        idx = text_lower.find("all-natural") if "all-natural" in text_lower else text_lower.find("100% natural")
        match_len = len("all-natural") if "all-natural" in text_lower else len("100% natural")
        
        if nat_clause:
            mock_findings.append({
                "span_start": idx,
                "span_end": idx + match_len,
                "category": "messaging",
                "issue": "Claim 'all-natural' is ambiguous without certification or qualification. Requires reviewer verification.",
                "source_type": "guideline_clause",
                "source_id": str(nat_clause["id"]),
                "source_quote": nat_clause["text"][:180],
                "severity": "minor",
                "confidence": "low",
                "needs_human": True,
                "suggested_rewrite": "made with natural ingredients",
            })

    # Check for unsupported superlatives (e.g. 'purest', 'revolutionary')
    superlatives = [
        ("purest", "Claims of absolute purity require batch lab testing citation."),
        ("revolutionary", "Superlative marketing terms must be tempered to brand voice tone."),
    ]
    for sup, reason in superlatives:
        if sup in text_lower:
            idx = text_lower.find(sup)
            # Find guideline clause on tone/voice or claims
            target_clause = None
            for c in clauses:
                if any(w in c.get("text", "").lower() for w in ["tone", "claim", "voice", "honest"]):
                    target_clause = c
                    break
            if target_clause:
                mock_findings.append({
                    "span_start": idx,
                    "span_end": idx + len(sup),
                    "category": "tone",
                    "issue": f"{reason} ({sup})",
                    "source_type": "guideline_clause",
                    "source_id": str(target_clause["id"]),
                    "source_quote": target_clause["text"][:180],
                    "severity": "minor",
                    "confidence": "medium",
                    "needs_human": False,
                    "suggested_rewrite": "premium",
                })

    return mock_findings


def run_pipeline(
    submission: Submission,
    version: SubmissionVersion,
    db: Session,
) -> List[Finding]:
    """Execute the full BrandGuard review pipeline on a submission version."""
    settings = get_settings()
    text = version.text
    intent = submission.intent or ""

    if not text or not text.strip():
        logger.info(f"Submission {submission.id} version {version.version_no} has empty text")
        return []

    # Ensure Chroma is populated
    reindex_if_empty(db)

    # 1. Fetch all approved sources for rules engine and citations
    clauses = [
        {"id": str(c.id), "text": c.text, "title": c.title, "code": c.code}
        for c in db.query(GuidelineClause).all()
    ]
    facts = [
        {"id": str(f.id), "statement": f.statement, "valid_to": f.valid_to}
        for f in db.query(ApprovedFact).all()
    ]
    terms = [
        {"id": str(t.id), "preferred": t.preferred, "avoid": t.avoid or [], "note": t.note}
        for t in db.query(Term).all()
    ]

    # If accessibility rules exist in guidelines, attach source to accessibility findings
    access_clause = next(
        (c for c in clauses if any(w in c.get("text", "").lower() for w in ["accessib", "alt", "link", "readab"])),
        None
    )

    # 2. Segment text
    spans = segment_into_spans(text)

    # 3. Retrieve relevant sources per span and globally
    all_retrieved_sources: List[Dict[str, Any]] = []
    seen_source_ids = set()

    for span in spans:
        span_sources = retrieve_sources(span.text, top_k=3)
        for s in span_sources:
            s_id = str(s["id"])
            if s_id not in seen_source_ids:
                seen_source_ids.add(s_id)
                all_retrieved_sources.append(s)

    # Also retrieve for whole text / title
    global_sources = retrieve_sources(f"{submission.title} {text[:200]}", top_k=5)
    for s in global_sources:
        s_id = str(s["id"])
        if s_id not in seen_source_ids:
            seen_source_ids.add(s_id)
            all_retrieved_sources.append(s)

    # 4. Deterministic rules engine
    rule_results: List[RuleFinding] = run_rules_engine(text, terms, facts, clauses)

    # Convert rule findings to dicts
    candidate_findings: List[Dict[str, Any]] = []
    for rf in rule_results:
        f_dict = {
            "span_start": rf.span_start,
            "span_end": rf.span_end,
            "category": rf.category,
            "issue": rf.issue,
            "source_type": rf.source_type,
            "source_id": rf.source_id,
            "source_quote": rf.source_quote,
            "severity": rf.severity,
            "confidence": rf.confidence,
            "suggested_rewrite": rf.suggested_rewrite,
            "needs_human": False,
            "is_rule": True,
        }
        # If accessibility finding lacks source, bind to accessibility guideline clause if available
        if rf.category == "accessibility" and not f_dict["source_id"] and access_clause:
            f_dict["source_type"] = "guideline_clause"
            f_dict["source_id"] = access_clause["id"]
            f_dict["source_quote"] = access_clause["text"][:150]

        candidate_findings.append(f_dict)

    # 5. LLM or Mock check
    llm_client = get_llm_client()
    if isinstance(llm_client, MockProvider) or not settings.llm_available:
        mock_results = _mock_llm_check(
            text, spans, intent, all_retrieved_sources, terms, clauses, facts
        )
        for mf in mock_results:
            mf["is_rule"] = False
            candidate_findings.append(mf)
    else:
        # Call LLM on spans with retrieved sources
        source_ids = [str(s["id"]) for s in all_retrieved_sources]
        for span in spans:
            llm_results = check_content_with_llm(
                span_text=span.text,
                intent=intent,
                sources=all_retrieved_sources,
                source_ids=source_ids,
            )
            for lf in llm_results:
                # Adjust span offsets relative to full text
                start = lf.get("span_start", 0) + span.start
                end = lf.get("span_end", len(span.text)) + span.start
                lf["span_start"] = min(start, len(text))
                lf["span_end"] = min(end, len(text))
                lf["is_rule"] = False
                candidate_findings.append(lf)

    # 6. Non-negotiable Citation Validator
    validated_findings, dropped_count = validate_citations(
        candidate_findings, all_retrieved_sources, db
    )

    # 7. Confidence routing and intent-preserving rewrite verification
    final_db_findings: List[Finding] = []

    for f_data in validated_findings:
        is_rule = f_data.get("is_rule", False)
        needs_human = f_data.get("needs_human", False)
        source_sim = 0.85 if is_rule else 0.65

        # Compute confidence and routing
        f_routed = compute_confidence_and_routing(
            finding=f_data,
            source_similarity=source_sim,
            is_rule_based=is_rule,
            is_ambiguous=needs_human,
        )

        # Verify rewrite keeps intent
        orig_span_text = ""
        if f_routed.get("span_start") is not None and f_routed.get("span_end") is not None:
            s_start = max(0, f_routed["span_start"])
            s_end = min(len(text), f_routed["span_end"])
            orig_span_text = text[s_start:s_end]

        verified_rewrite = verify_intent_preserved(
            original_span=orig_span_text,
            suggested_rewrite=f_routed.get("suggested_rewrite"),
            intent=intent,
        )

        # Map string enums safely
        cat_str = f_routed.get("category", "messaging")
        try:
            cat_enum = FindingCategory(cat_str)
        except ValueError:
            cat_enum = FindingCategory.messaging

        sev_str = f_routed.get("severity", "minor")
        # Enforce rule: unsupported promotional claims and factual errors are at least 'major'
        if cat_enum in (FindingCategory.unsupported_claim, FindingCategory.factual_accuracy):
            if sev_str in ("minor", "info"):
                sev_str = "major"
        try:
            sev_enum = FindingSeverity(sev_str)
        except ValueError:
            sev_enum = FindingSeverity.minor

        conf_str = f_routed.get("confidence", "high")
        try:
            conf_enum = FindingConfidence(conf_str)
        except ValueError:
            conf_enum = FindingConfidence.high

        source_type_str = f_routed.get("source_type")
        source_type_enum = None
        if source_type_str:
            try:
                source_type_enum = SourceType(source_type_str)
            except ValueError:
                source_type_enum = None

        db_finding = Finding(
            submission_id=submission.id,
            version_id=version.id,
            span_start=f_routed.get("span_start"),
            span_end=f_routed.get("span_end"),
            category=cat_enum,
            issue=f_routed.get("issue", ""),
            source_type=source_type_enum,
            source_id=f_routed.get("source_id"),
            source_quote=f_routed.get("source_quote"),
            severity=sev_enum,
            confidence=conf_enum,
            suggested_rewrite=verified_rewrite,
            needs_human=f_routed.get("needs_human", False),
            status=FindingStatus.open,
        )
        db.add(db_finding)
        final_db_findings.append(db_finding)

    db.commit()
    logger.info(f"Pipeline completed: {len(final_db_findings)} findings saved for submission {submission.id}")
    return final_db_findings
