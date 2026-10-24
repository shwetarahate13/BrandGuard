"""Content normalizer and sentence segmenter."""
import re
import unicodedata
from dataclasses import dataclass


@dataclass
class Span:
    text: str
    start: int
    end: int


def normalize_text(text: str) -> str:
    """Normalize text: unicode NFKC, normalize whitespace, strip."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def segment_into_spans(text: str) -> list[Span]:
    """Split text into sentence-level spans with character offsets.
    
    Uses regex-based splitting to avoid heavy NLTK dependency.
    """
    normalized = normalize_text(text)
    if not normalized:
        return []

    # Split on sentence boundaries: period/question/exclamation followed by space and capital
    # But preserve the delimiter
    sentence_pattern = re.compile(
        r'(?<=[.!?])\s+(?=[A-Z\u201c\u2018"\'(])|(?<=\n)\s*(?=\S)'
    )

    spans = []
    last_end = 0

    for match in sentence_pattern.finditer(normalized):
        start = last_end
        end = match.start()
        chunk = normalized[start:end].strip()
        if chunk:
            # Find actual position in normalized text
            actual_start = normalized.index(chunk, start)
            spans.append(Span(text=chunk, start=actual_start, end=actual_start + len(chunk)))
        last_end = match.end()

    # Last segment
    remaining = normalized[last_end:].strip()
    if remaining:
        actual_start = normalized.index(remaining, last_end)
        spans.append(Span(text=remaining, start=actual_start, end=actual_start + len(remaining)))

    # If no splits occurred, return the whole text as one span
    if not spans and normalized:
        spans.append(Span(text=normalized, start=0, end=len(normalized)))

    return spans
