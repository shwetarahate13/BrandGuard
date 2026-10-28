"""Small, deterministic English copy-editing rules with source-grounded findings.

The bundled correction map is intentionally conservative: unknown words are not
called misspellings. Protected markup and identifiers are excluded before rules run.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class WritingFinding:
    span_start: int
    span_end: int
    category: str
    issue: str
    source_type: str
    source_id: str
    source_quote: str
    severity: str
    confidence: str
    suggested_rewrite: str | None


# A bundled, reviewed correction dictionary. Unknown words remain untouched.
SPELLING: dict[str, str] = {
    "accomodate": "accommodate", "acheive": "achieve", "agian": "again",
    "alwasy": "always", "beleive": "believe", "calender": "calendar",
    "definately": "definitely", "enviroment": "environment", "goverment": "government",
    "grammer": "grammar", "imediately": "immediately", "independant": "independent",
    "maintainance": "maintenance", "seperate": "separate", "recieve": "receive",
    "occured": "occurred", "adress": "address", "begining": "beginning",
    "businesseses": "businesses", "comming": "coming", "concious": "conscious",
    "definetly": "definitely", "existance": "existence", "finaly": "finally",
    "freind": "friend", "goverment": "government", "happend": "happened",
    "knowlege": "knowledge", "langauge": "language", "neccessary": "necessary",
    "occassion": "occasion", "perserverance": "perseverance", "responsibile": "responsible",
    "succesful": "successful", "tommorow": "tomorrow", "untill": "until",
    "wich": "which", "wierd": "weird", "writting": "writing", "thier": "their",
    "teh": "the", "severly": "severely", "truely": "truly",
}

TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
PROTECTED_PATTERNS = (
    re.compile(r"```[\s\S]*?```|~~~[\s\S]*?~~~"),
    re.compile(r"`[^`\n]*`"),
    re.compile(r"<[^>]*>"),
    re.compile(r"(?:https?://|www\.)[^\s<>]+", re.I),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?<!\w)[@#][\w-]+"),
)
NON_ENGLISH_MARKERS = {
    "el", "la", "los", "las", "un", "una", "y", "de", "del", "que", "para", "con", "por", "es", "en", "muy", "pero", "son", "está",
    "le", "les", "des", "une", "et", "est", "du", "dans", "avec", "pour", "der", "die", "das", "ein", "eine", "und", "ist", "zu", "mit", "von", "für",
    "o", "os", "as", "um", "uma", "e", "do", "da", "com", "em",
}


def _protected(text: str) -> list[tuple[int, int]]:
    spans = sorted((m.start(), m.end()) for pattern in PROTECTED_PATTERNS for m in pattern.finditer(text))
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _is_protected(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < right and end > left for left, right in spans)


def _looks_non_english(text: str) -> bool:
    words = {word.casefold() for word in TOKEN_RE.findall(text)}
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    non_latin = 0
    for char in letters:
        decomposed = unicodedata.normalize("NFKD", char)
        if not any("a" <= part.lower() <= "z" for part in decomposed):
            non_latin += 1
    if non_latin / len(letters) > 0.05:
        return True
    other_hits = len(words & NON_ENGLISH_MARKERS)
    return other_hits >= 2


def analyze_writing(text: str, clause: dict | None, brand_words: list[str] | None = None) -> list[WritingFinding]:
    """Return conservative grammar/spelling findings; all spans index the original text."""
    if not text or _looks_non_english(text) or not clause or not clause.get("id") or not clause.get("text"):
        return []
    protected = _protected(text)
    allow = {word.casefold() for word in (brand_words or []) if word.strip()}
    findings: list[WritingFinding] = []
    seen: set[tuple[int, int, str]] = set()

    def add(start: int, end: int, category: str, rule_id: str, confidence: str, replacement: str | None, reason: str):
        key = (start, end, rule_id)
        if key in seen or start < 0 or end <= start or end > len(text) or _is_protected(start, end, protected):
            return
        seen.add(key)
        findings.append(WritingFinding(
            start, end, category, f"{rule_id}: {reason}", "guideline_clause", str(clause["id"]),
            str(clause["text"]), "minor", confidence, replacement,
        ))

    # Spelling corrections only flag exact, reviewed dictionary entries.
    for match in TOKEN_RE.finditer(text):
        word = match.group()
        correction = SPELLING.get(word.casefold())
        if correction and word.casefold() not in allow and not _is_protected(match.start(), match.end(), protected):
            if word[:1].isupper():
                correction = correction[:1].upper() + correction[1:]
            add(match.start(), match.end(), "spelling", "SPELL-1", "high", correction,
                f"Possible spelling error: replace {word!r} with {correction!r}.")

    # Repeated adjacent words, except intentional repeated tokens in markup/URLs.
    for match in re.finditer(r"\b([A-Za-z][A-Za-z’']*)\s+\1\b", text, re.I):
        add(match.start(), match.end(), "grammar", "GRAM-1", "high", match.group(1), "Repeated adjacent word.")

    # High-confidence local grammar patterns.
    for pattern, replacement_fn, rule, reason in [
        (re.compile(r"\ba\s+([aeiou][A-Za-z-]*)\b", re.I), lambda m: "an " + m.group(1), "GRAM-2", "Use 'an' before a vowel sound in this simple case."),
        (re.compile(r"\ban\s+([bcdfghjklmnpqrstvwxyz][A-Za-z-]*)\b", re.I), lambda m: "a " + m.group(1), "GRAM-2", "Use 'a' before a consonant sound in this simple case."),
        (re.compile(r"\b(he|she|it|this|that)\s+are\b", re.I), lambda m: m.group(1) + " is", "GRAM-3", "Singular subject takes 'is' in this simple construction."),
        (re.compile(r"\b(they|we|you|these|those)\s+is\b", re.I), lambda m: m.group(1) + " are", "GRAM-3", "Plural subject takes 'are' in this simple construction."),
        (re.compile(r"\b(they|we|you)\s+was\b", re.I), lambda m: m.group(1) + " were", "GRAM-3", "Plural subject takes 'were' in this simple construction."),
        (re.compile(r"\b(more|most)\s+(faster|slower|easier|better|quicker|stronger)\b", re.I), lambda m: m.group(2), "GRAM-4", "Avoid a double comparative."),
        (re.compile(r"\b(their|there)\s+(going|coming|doing|being|ready|happy|available)\b", re.I), lambda m: "they're " + m.group(2), "GRAM-5", "Use 'they're' for 'they are' in this construction."),
        (re.compile(r"\b(its)\s+(a|an|the|not|very|really)\b", re.I), lambda m: "it's " + m.group(2), "GRAM-6", "Use 'it's' for 'it is' in this construction."),
    ]:
        for match in pattern.finditer(text):
            replacement = replacement_fn(match)
            add(match.start(), match.end(), "grammar", rule, "high", replacement, reason)

    for match in re.finditer(r" {2,}", text):
        add(match.start(), match.end(), "grammar", "GRAM-7", "high", " ", "Use a single space between words.")
    for match in re.finditer(r"([.!?,;:])([A-Za-z])", text):
        add(match.start(2), match.end(2), "grammar", "GRAM-8", "high", " " + match.group(2), "Add a space after punctuation.")
    for match in re.finditer(r"(?:^|[.!?]\s+)([a-z])", text):
        add(match.start(1), match.end(1), "grammar", "GRAM-9", "high", match.group(1).upper(), "Capitalize the start of this sentence.")
    for match in re.finditer(r"\b(\w+)\s*,\s+(I|you|we|they|he|she|it|the|a|an)\s+\w+\s+\w+", text, re.I):
        add(match.start(), match.end(), "grammar", "GRAM-10", "medium", None, "Possible comma splice or run-on sentence; review the sentence boundary.")

    # Missing final punctuation is flagged for review; no punctuation is invented automatically.
    trimmed_text = text.rstrip()
    final_word_char = re.search(r"([A-Za-z0-9])(?=[^\w]*$)", trimmed_text)
    punctuation_after_word = bool(final_word_char and re.search(r"[.!?]", trimmed_text[final_word_char.end():]))
    if final_word_char and not punctuation_after_word:
        last = final_word_char.start(1)
        end = last + 1
        if not _is_protected(last, end, protected):
            add(last, end, "grammar", "GRAM-11", "medium", text[last] + ".", "Add final sentence punctuation if this is a complete sentence.")

    return sorted(findings, key=lambda item: (item.span_start, item.span_end, item.category))
