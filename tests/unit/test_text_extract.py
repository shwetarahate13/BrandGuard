"""Unit tests for text extraction from PDF, DOCX, and TXT files."""
from pathlib import Path
from backend.app.utils.text_extract import extract_text

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_extract_docx():
    docx_path = FIXTURES_DIR / "sample_with_errors.docx"
    assert docx_path.exists()

    with open(docx_path, "rb") as f:
        text = extract_text(f.read(), "sample_with_errors.docx")

    assert "Golden Oat Elixir" in text
    assert "$28" in text
    assert len(text) > 50


def test_extract_pdf():
    pdf_path = FIXTURES_DIR / "sample_with_errors.pdf"
    assert pdf_path.exists()

    with open(pdf_path, "rb") as f:
        text = extract_text(f.read(), "sample_with_errors.pdf")

    assert "Aurelia Foods" in text or "sourdough" in text.lower()
    assert len(text) > 20
