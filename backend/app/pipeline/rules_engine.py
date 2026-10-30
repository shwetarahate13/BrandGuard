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

    # 3. Structured facts: compare a value only in the same sentence as its subject.
    structured_facts = [fact for fact in facts if fact.get("subject") and fact.get("value")]
    subject_groups: dict[str, list[dict]] = {}
    for fact in structured_facts:
        subject_groups.setdefault(str(fact["subject"]).casefold().strip(), []).append(fact)

    for subject_key, subject_facts in subject_groups.items():
        subject = str(subject_facts[0]["subject"]).strip()
        subject_pattern = re.compile(r"(?<!\w)" + re.escape(subject) + r"(?!\w)", re.IGNORECASE)
        active_facts = [fact for fact in subject_facts if _is_active(fact)]
        active_values = {
            f"{_fact_value_signature(str(fact.get('value', '')).strip())}|{str(fact.get('unit') or '').strip().casefold()}"
            for fact in active_facts
        }
        conflict = len(active_values) > 1
        selected_fact = active_facts[0] if active_facts else max(subject_facts, key=lambda fact: str(fact.get("valid_to") or ""))

        for subject_match in subject_pattern.finditer(text):
            sentence_start = max((text.rfind(mark, 0, subject_match.start()) for mark in ".!?\n;"), default=-1) + 1
            sentence_end_candidates = [text.find(mark, subject_match.end()) for mark in ".!?\n;"]
            sentence_end_candidates = [pos for pos in sentence_end_candidates if pos >= 0]
            sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(text)
            sentence = text[sentence_start:sentence_end]
            local_values = [
                match for match in _FACT_VALUE_PATTERN.finditer(sentence)
                if not (sentence_start + match.start() < subject_match.end() and sentence_start + match.end() > subject_match.start())
            ]
            if not local_values:
                continue

            if conflict:
                findings.append(RuleFinding(
                    span_start=subject_match.start(),
                    span_end=subject_match.end(),
                    category="factual_accuracy",
                    issue=(
                        f"Conflicting active approved facts exist for '{subject}': "
                        + "; ".join(
                            f"{fact.get('value')} {fact.get('unit') or ''} — {fact.get('source_note') or 'source not recorded'}"
                            for fact in active_facts
                        )
                        + ". Send this value to a reviewer."
                    ),
                    source_type="approved_fact",
                    source_id=selected_fact.get("id"),
                    source_quote=selected_fact.get("statement"),
                    severity="major",
                    confidence="high",
                ))
                continue

            if not active_facts:
                if _is_expired(selected_fact) and any(
                    _fact_value_signature(match.group()) == _fact_value_signature(str(selected_fact.get("value", "")))
                    for match in local_values
                ):
                    expired_date = selected_fact.get("valid_to", "unknown")
                    findings.append(RuleFinding(
                        span_start=subject_match.start(),
                        span_end=subject_match.end(),
                        category="factual_accuracy",
                        issue=f"The approved value for '{subject}' expired on {expired_date}; send it to a reviewer because no active replacement exists.",
                        source_type="approved_fact",
                        source_id=selected_fact.get("id"),
                        source_quote=selected_fact.get("statement"),
                        severity="major",
                        confidence="high",
                    ))
                continue

            approved_value = str(selected_fact.get("value", "")).strip()
            unit = str(selected_fact.get("unit") or "").strip()
            expected_signature = _fact_value_signature(
                approved_value if unit.casefold() == "date" else f"{approved_value} {unit}"
            )
            mismatches = [
                (match, observed_unit, unit_end)
                for match in local_values
                for observed_unit, unit_end in [_unit_after_value(sentence, match.end(), facts)]
                if _fact_value_signature(match.group()) != expected_signature
                or (
                    observed_unit is not None
                    and _normalize_fact_unit(observed_unit) != _normalize_fact_unit(unit)
                )
            ]
            if not mismatches:
                continue

            # Multiple figures in the sentence cannot be safely mapped to a single fact.
            if len(local_values) != 1:
                continue

            match, observed_unit, unit_end = mismatches[0]
            unit_mismatch = (
                observed_unit is not None
                and _normalize_fact_unit(observed_unit) != _normalize_fact_unit(unit)
            )
            span_end_in_sentence = unit_end if unit_mismatch else match.end()
            span_start, span_end = sentence_start + match.start(), sentence_start + span_end_in_sentence
            original_value = sentence[match.start():span_end_in_sentence]
            source_note = str(selected_fact.get("source_note") or "").strip()
            approved_label = _fact_value_label(approved_value, unit)
            issue = f"Your text vs approved value — your text: '{original_value}'; approved value: '{approved_label}'."
            if source_note:
                issue += f" Source: {source_note}."
            replacement = _format_fact_value(approved_value, original_value)
            if _normalize_fact_unit(unit) == "%":
                replacement = _fact_value_label(replacement, unit)
            elif unit_mismatch and unit:
                replacement = _fact_value_label(replacement, unit)
            elif unit_mismatch:
                replacement = None
                issue += " No approved unit is recorded, so a reviewer must verify the quantity."
            findings.append(RuleFinding(
                span_start=span_start,
                span_end=span_end,
                category="factual_accuracy",
                issue=issue,
                source_type="approved_fact",
                source_id=selected_fact.get("id"),
                source_quote=selected_fact.get("statement"),
                severity="major",
                confidence="high",
                suggested_rewrite=replacement,
            ))

    # 3. Outdated facts
    for fact in facts:
        if fact.get("subject") and fact.get("value"):
            continue
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


_FACT_VALUE_PATTERN = re.compile(
    r"(?<!\w)(?:"
    r"\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}"
    r"|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?"
    r"|(?:[$€£]\s*)?\d[\d,]*(?:\.\d+)?\s*%?"
    r")(?!\w)",
    re.IGNORECASE,
)

_COMMON_FACT_UNITS = (
    "per month", "per year", "per week", "per day", "per hour", "per user",
    "percentage", "percent", "users", "user", "seats", "seat", "licenses", "license",
    "employees", "locations", "location", "kwh", "mwh", "kg", "mg", "lbs", "lb",
    "miles", "km", "meters", "metres", "hours", "days", "years", "months", "items", "units",
)


def _normalize_fact_unit(unit: str) -> str:
    normalized = " ".join(unit.casefold().split())
    if normalized in {"percentage", "percent"}:
        return "%"
    return normalized


def _unit_after_value(text: str, end: int, facts: list[dict]) -> tuple[str | None, int]:
    candidates = {
        str(fact.get("unit") or "").strip()
        for fact in facts
        if str(fact.get("unit") or "").strip().casefold() not in {"date", "%", "percent", "percentage"}
    }
    candidates.update(_COMMON_FACT_UNITS)
    for candidate in sorted(candidates, key=len, reverse=True):
        match = re.match(r"\s+(" + re.escape(candidate) + r")(?!\w)", text[end:], re.IGNORECASE)
        if match:
            return " ".join(match.group(1).split()), end + match.end()
    return None, end


def _fact_value_label(value: str, unit: str) -> str:
    if not unit or unit.casefold() == "date":
        return value
    if _normalize_fact_unit(unit) == "%":
        return value if _fact_value_signature(value).endswith("%") else f"{value}%"
    return f"{value} {unit}".strip()


def _fact_value_signature(value: str) -> str:
    stripped = value.strip()
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y", "%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y"):
        try:
            parsed = datetime.strptime(stripped, date_format)
            return f"date:{parsed.month:02d}-{parsed.day:02d}-{parsed.year:04d}"
        except ValueError:
            pass
    symbol = next((char for char in "$€£" if char in stripped), "")
    percent = "%" if "%" in stripped or re.search(r"\bpercent\b", stripped, re.IGNORECASE) else ""
    match = re.search(r"\d[\d,]*(?:\.\d+)?", value)
    if not match:
        return value.casefold().strip()
    try:
        number = float(match.group().replace(",", ""))
    except ValueError:
        return value.casefold().strip()
    normalized_number = str(int(number)) if number.is_integer() else str(number)
    return f"{symbol}{normalized_number}{percent}"


def _format_fact_value(approved_value: str, original: str) -> str:
    try:
        approved_date = datetime.fromisoformat(approved_value.strip())
    except ValueError:
        return approved_value
    if re.match(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", original, re.IGNORECASE):
        month_format = "%b" if len(original.split()[0]) == 3 else "%B"
        return f"{approved_date.strftime(month_format)} {approved_date.day}, {approved_date.year}"
    if re.match(r"^\d{1,2}/", original):
        return approved_date.strftime("%m/%d/%Y")
    return approved_date.strftime("%Y-%m-%d")


def _is_active(fact: dict) -> bool:
    if _is_expired(fact):
        return False
    valid_from = fact.get("valid_from")
    if not valid_from:
        return True
    if isinstance(valid_from, str):
        try:
            valid_from = datetime.fromisoformat(valid_from)
        except (ValueError, TypeError):
            return True
    if not isinstance(valid_from, datetime):
        return True
    if valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=timezone.utc)
    return valid_from <= datetime.now(timezone.utc)
