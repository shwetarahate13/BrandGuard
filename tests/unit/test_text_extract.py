"""Unit tests for text extraction from PDF, DOCX, and TXT files."""
from pathlib import Path
from backend.app.utils.text_extract import extract_pdf_text_with_layout, extract_text
from backend.app.pipeline.runner import _map_finding_location

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


def test_pdf_extraction_returns_line_boxes_and_finding_locations():
    pdf_path = FIXTURES_DIR / "sample_with_errors.pdf"
    text, layout = extract_pdf_text_with_layout(pdf_path.read_bytes())

    assert text
    assert layout["pages"]
    assert layout["regions"]
    first_region = layout["regions"][0]
    assert len(first_region["bbox"]) == 4
    assert first_region["page"] == 1
    mapped = _map_finding_location(
        first_region["start"],
        first_region["end"],
        layout,
        "application/pdf",
    )
    assert mapped == {"page": 1, "bbox": first_region["bbox"]}
    fallback = _map_finding_location(None, None, layout, "application/pdf")
    assert fallback["page"] == 1
    assert len(fallback["bbox"]) == 4
