"""Guard, ground, and de-conflict human-reviewed writing suggestions."""
from __future__ import annotations

import re
from typing import Any

from backend.app.pipeline.confidence import verify_intent_preserved
from backend.app.pipeline.rules_engine import run_rules_engine


PRIORITY = {
    "unsupported_claim": 0,
    "factual_accuracy": 0,
    "terminology": 1,
    "tone": 2,
    "accessibility": 3,
    "grammar": 4,
    "spelling": 4,
    "messaging": 5,
}
HIGH_CATEGORIES = {"unsupported_claim", "factual_accuracy"}
CLAUSE_FOR_CATEGORY = {
    "spelling": "STYLE-1", "grammar": "STYLE-1", "terminology": "TERM-1",
    "tone": "VOICE-1", "accessibility": "A11Y-1",
    "unsupported_claim": "CLAIM-1", "factual_accuracy": "CLAIM-1",
    "messaging": "CLAIM-1",
}


def _key(candidate: dict[str, Any]) -> tuple[str, str]:
    return (str(candidate.get("category", "")), re.sub(r"\s+", " ", str(candidate.get("issue", "")).casefold()).strip())


def _apply(text: str, edits: list[dict[str, Any]]) -> str:
    result = text
    for item in sorted(edits, key=lambda value: value["span_start"], reverse=True):
        start, end = item["span_start"], item["span_end"]
        result = result[:start] + item["suggested_rewrite"] + result[end:]
    return result


def ground_issue(candidate: dict[str, Any], clauses: list[dict[str, Any]]) -> None:
    """Add the policy code and a literal clause quote to the plain-language reason."""
    code = CLAUSE_FOR_CATEGORY.get(str(candidate.get("category", "")))
    clause = next((item for item in clauses if code and item.get("code") == code), None)
    if clause is None and candidate.get("source_type") == "guideline_clause":
        clause = next((item for item in clauses if str(item.get("id")) == str(candidate.get("source_id"))), None)
    if clause:
        quote = str(clause.get("text", "")).strip()
        if quote and "Guideline " not in str(candidate.get("issue", "")):
            candidate["issue"] = f"{candidate.get('issue', 'Review this passage.')} Guideline {clause.get('code') or clause.get('title')}: ‘{quote}’"
    elif candidate.get("source_quote") and "Cited source:" not in str(candidate.get("issue", "")):
        quote = str(candidate["source_quote"]).strip()
        candidate["issue"] = f"{candidate.get('issue', 'Review this passage.')} Cited source: ‘{quote}’"


def prepare_suggestions(
    candidates: list[dict[str, Any]],
    text: str,
    intent: str,
    terms: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    clauses: list[dict[str, Any]],
    brand_words: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Verify intent and evidence, run a full deterministic-rule safety pass, then resolve overlaps."""
    for candidate in candidates:
        category = str(candidate.get("category", ""))
        original = ""
        if candidate.get("span_start") is not None and candidate.get("span_end") is not None:
            original = text[max(0, candidate["span_start"]):min(len(text), candidate["span_end"])]
        rewrite = verify_intent_preserved(original, candidate.get("suggested_rewrite"), intent, candidate.get("source_type"))

        # Claims/facts may only use exact wording from an approved fact. Otherwise
        # leave the rewrite for a reviewer instead of paraphrasing evidence.
        if category in HIGH_CATEGORIES:
            cited_fact = next((fact for fact in facts if str(fact.get("id")) == str(candidate.get("source_id"))), None)
            approved_wording = str(cited_fact.get("statement", "")) if cited_fact else ""
            if candidate.get("source_type") != "approved_fact" or not rewrite or rewrite not in approved_wording:
                rewrite = None
                candidate["needs_human"] = True

        candidate["suggested_rewrite"] = rewrite
        if not rewrite:
            candidate["needs_human"] = bool(candidate.get("needs_human")) or category in HIGH_CATEGORIES
            if category in HIGH_CATEGORIES:
                note = "No safe replacement is supported by an approved fact; route this claim to the reviewer."
                if note not in str(candidate.get("issue", "")):
                    candidate["issue"] = f"{candidate.get('issue', '')} {note}"
        ground_issue(candidate, clauses)

    # Resolve suggested edits by risk priority. Findings remain visible; the
    # lower-priority overlapping suggestion is queued for later review.
    accepted: list[dict[str, Any]] = []
    with_rewrite = sorted(
        (item for item in candidates if item.get("suggested_rewrite") is not None),
        key=lambda item: (PRIORITY.get(str(item.get("category")), 5), item.get("span_start") or 0, -(item.get("span_end") or 0)),
    )
    for candidate in with_rewrite:
        start, end = candidate.get("span_start"), candidate.get("span_end")
        if start is None or end is None:
            continue
        if any(start < other.get("span_end", 0) and end > other.get("span_start", 0) for other in accepted):
            candidate["suggested_rewrite"] = None
            candidate["issue"] = f"{candidate.get('issue', '')} This overlapping edit is queued behind a higher-priority finding."
        else:
            accepted.append(candidate)

    # Re-run the deterministic compliance rules on the proposed result. If any
    # edit introduces a new high-severity category/issue, withhold the batch.
    safe_edits = [item for item in accepted if item.get("suggested_rewrite") is not None]
    if safe_edits:
        baseline = run_rules_engine(text, terms, facts, clauses, brand_words=brand_words)
        proposal = _apply(text, safe_edits)
        proposed_findings = run_rules_engine(proposal, terms, facts, clauses, brand_words=brand_words)
        baseline_high = {(finding.category, re.sub(r"\s+", " ", finding.issue.casefold()).strip()) for finding in baseline if finding.severity in {"major", "critical"}}
        introduced = [finding for finding in proposed_findings if finding.severity in {"major", "critical"} and (finding.category, re.sub(r"\s+", " ", finding.issue.casefold()).strip()) not in baseline_high]
        if introduced:
            for candidate in safe_edits:
                candidate["suggested_rewrite"] = None
                candidate["issue"] = f"{candidate.get('issue', '')} The proposed edit was withheld because a safety check detected a new high-severity issue."
                candidate["needs_human"] = True
    return candidates
