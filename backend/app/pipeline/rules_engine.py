"""Deterministic rules engine - no LLM needed.

Checks terminology, promotional claims, tone, accessibility, facts.
Each finding includes a source citation.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field, asdict
from backend.app.pipeline.writing_assistant import analyze_writing

logger = logging.getLogger(__name__)

# Forbidden promotional phrases that need evidence
FORBIDDEN_PHRASES = [
    "guaranteed", "best in the world", "100% safe", "cure", "cures",
    "clinically proven", "scientifically proven", "miracle",
    "risk-free", "no side effects", "#1", "number one",
    "world's best", "industry leading", "unmatched", "unbeatable",
]

# Accessibility: vague link text patterns
VAGUE_LINK_PATTERNS = [
    r'\[click\s+here\]',
    r'\[here\]',
    r'\[read\s+more\]',
    r'\[link\]',
    r'<a[^>]*>click\s+here</a>',
    r'<a[^>]*>here</a>',
    r'<a[^>]*>read\s+more</a>',
    r'<a[^>]*>link</a>',
]

# Markdown/HTML images without alt text
IMG_NO_ALT_PATTERNS = [
    r'!\[\]\(',           # ![](url) - empty alt
    r'<img(?![^>]*alt=)', # <img without alt attribute
    r'<img[^>]*alt=""',   # <img alt="" - empty alt
    r"<img[^>]*alt=''",   # <img alt='' - empty alt
]


@dataclass
class RuleFinding:
    span_start: int
    span_end: int
    category: str
    issue: str
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_quote: Optional[str] = None
    severity: str = "minor"
    confidence: str = "high"
    suggested_rewrite: Optional[str] = None


def count_syllables(word: str) -> int:
    """Simple syllable counter for Flesch-Kincaid."""
    word = word.lower().strip(".,!?;:'\"")
    if not word:
        return 0
    count = 0
    vowels = "aeiouy"
    prev_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def flesch_kincaid_grade(text: str) -> float:
    """Compute FK grade level."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0
    words = text.split()
    if not words:
        return 0.0
    total_syllables = sum(count_syllables(w) for w in words)
    avg_words_per_sentence = len(words) / len(sentences)
    avg_syllables_per_word = total_syllables / len(words)
    return 0.39 * avg_words_per_sentence + 11.8 * avg_syllables_per_word - 15.59


def run_rules_engine(
    text: str,
    terms: list[dict],
    facts: list[dict],
    clauses: list[dict],
    brand_words: list[str] | None = None,
) -> list[RuleFinding]:
    """Run all deterministic rules. Returns findings with source citations."""
    findings: list[RuleFinding] = []

    style_clause = next(
        (c for c in clauses if c.get("code") == "STYLE-1"),
        next((c for c in clauses if "free of spelling and grammar errors" in c.get("text", "").lower()), None),
    )
    findings.extend(RuleFinding(**finding.__dict__) for finding in analyze_writing(text, style_clause, brand_words))

    # 1. Terminology checks
    for term in terms:
        preferred = term.get("preferred", "")
        avoid_list = term.get("avoid", [])
        term_id = term.get("id", "")

        for avoided in avoid_list:
            if not avoided:
                continue
            pattern = re.compile(r'\b' + re.escape(avoided) + r'\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                findings.append(RuleFinding(
                    span_start=match.start(),
                    span_end=match.end(),
                    category="terminology",
                    issue=f"Use '{preferred}' instead of '{avoided}'.",
                    source_type="term",
                    source_id=term_id,
                    source_quote=f"Preferred: '{preferred}'. Avoid: '{avoided}'.",
                    severity="minor",
                    confidence="high",
                    suggested_rewrite=preferred,
                ))

    # 2. Forbidden promotional phrases
    claim_clause = None
    for c in clauses:
        ctext = c.get("text", "").lower()
        if any(kw in ctext for kw in ["claim", "promotional", "evidence", "substantiat"]):
            claim_clause = c
            break

    for phrase in FORBIDDEN_PHRASES:
        pattern = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
        for match in pattern.finditer(text):
            # Check if any approved fact supports this claim
            matched_text = text[max(0, match.start()-50):min(len(text), match.end()+50)]
            fact_supports = False
            for fact in facts:
                stmt = fact.get("statement", "").lower()
                if phrase.lower() in stmt and not _is_expired(fact):
                    fact_supports = True
                    break

            if not fact_supports:
                source_id = claim_clause["id"] if claim_clause else None
                source_quote = claim_clause["text"][:200] if claim_clause else None
                source_type = "guideline_clause" if claim_clause else None

                findings.append(RuleFinding(
                    span_start=match.start(),
                    span_end=match.end(),
                    category="unsupported_claim",
                    issue=f"Unsupported promotional claim: '{match.group()}'. This requires evidence from an approved source.",
                    source_type=source_type,
                    source_id=source_id,
                    source_quote=source_quote,
                    severity="major",
                    confidence="high",
                    suggested_rewrite=None,
                ))

    # 3. Outdated facts
    for fact in facts:
        if not _is_expired(fact):
            continue
        stmt = fact.get("statement", "")
        # Extract key numbers/percentages with word boundary
        numbers = re.findall(r'\b\d[\d,.]*%?\b', stmt)
        for num in numbers:
            # Avoid single digit false alarms
            if len(num) < 2 and not num.endswith("%"):
                continue
            pattern = re.compile(r'\b' + re.escape(num) + r'\b')
            match = pattern.search(text)
            if match:
                findings.append(RuleFinding(
                    span_start=match.start(),
                    span_end=match.end(),
                    category="factual_accuracy",
                    issue=f"This statistic may be outdated. The approved fact '{stmt[:100]}...' expired on {fact.get('valid_to', 'unknown')}.",
                    source_type="approved_fact",
                    source_id=fact.get("id"),
                    source_quote=stmt[:200],
                    severity="major",
                    confidence="medium",
                    suggested_rewrite=None,
                ))

    # 4. All-caps blocks (accessibility)
    caps_pattern = re.compile(r'\b([A-Z]{2,}\s+){3,}[A-Z]{2,}\b')
    for match in caps_pattern.finditer(text):
        findings.append(RuleFinding(
            span_start=match.start(),
            span_end=match.end(),
            category="accessibility",
            issue="Long all-caps block detected. Screen readers may interpret this as an acronym. Use sentence case for readability.",
            severity="minor",
            confidence="high",
            suggested_rewrite=match.group().capitalize(),
        ))

    # 5. Vague link text (accessibility)
    for pattern_str in VAGUE_LINK_PATTERNS:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        for match in pattern.finditer(text):
            findings.append(RuleFinding(
                span_start=match.start(),
                span_end=match.end(),
                category="accessibility",
                issue="Vague link text detected. Use descriptive link text instead of 'click here' or 'read more'.",
                severity="minor",
                confidence="high",
                suggested_rewrite=None,
            ))

    # 6. Images without alt text (accessibility)
    for pattern_str in IMG_NO_ALT_PATTERNS:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        for match in pattern.finditer(text):
            findings.append(RuleFinding(
                span_start=match.start(),
                span_end=match.end(),
                category="accessibility",
                issue="Image without alt text. Add descriptive alt text for accessibility.",
                severity="major",
                confidence="high",
                suggested_rewrite=None,
            ))

    # 7. Overly complex sentences (accessibility)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    pos = 0
    for sentence in sentences:
        idx = text.find(sentence, pos)
        if idx == -1:
            idx = pos
        word_count = len(sentence.split())
        if word_count > 40:
            findings.append(RuleFinding(
                span_start=idx,
                span_end=idx + len(sentence),
                category="accessibility",
                issue=f"Overly complex sentence ({word_count} words). Consider breaking into shorter sentences for readability.",
                severity="minor",
                confidence="high",
                suggested_rewrite=None,
            ))
        pos = idx + len(sentence)

    # 8. Tone/readability check (evaluate on texts with at least 40 words)
    grade = flesch_kincaid_grade(text)
    tone_clause = None
    for c in clauses:
        ctext = c.get("text", "").lower()
        if any(kw in ctext for kw in ["tone", "voice", "readab", "grade", "plain language"]):
            tone_clause = c
            break

    if grade > 14 and len(text.split()) >= 40 and tone_clause:
        findings.append(RuleFinding(
            span_start=0,
            span_end=min(len(text), 100),
            category="tone",
            issue=f"Content readability is at grade level {grade:.1f}. Brand guidelines recommend accessible, plain language.",
            source_type="guideline_clause",
            source_id=tone_clause["id"],
            source_quote=tone_clause["text"][:200],
            severity="minor",
            confidence="medium",
            suggested_rewrite=None,
        ))

    return findings


def _is_expired(fact: dict) -> bool:
    """Check if a fact has expired."""
    valid_to = fact.get("valid_to")
    if not valid_to:
        return False
    if isinstance(valid_to, str):
        try:
            valid_to = datetime.fromisoformat(valid_to)
        except (ValueError, TypeError):
            return False
    if isinstance(valid_to, datetime):
        now = datetime.now(timezone.utc)
        if valid_to.tzinfo is None:
            valid_to = valid_to.replace(tzinfo=timezone.utc)
        return valid_to < now
    return False
