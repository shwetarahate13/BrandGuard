"""Script to generate evaluation fixtures: PDF, DOCX, TXT, and ground-truth JSON."""
import os
import json
from pathlib import Path
from docx import Document

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def generate_docx():
    docx_path = FIXTURES_DIR / "sample_with_errors.docx"
    doc = Document()
    doc.add_heading("Aurelia Foods Q4 Pantry Announcement", 0)
    doc.add_paragraph(
        "Golden Oat Elixir is the world's best oat beverage, clinically proven to eliminate morning fatigue. "
        "Our formula guarantees 100% safe results for all users."
    )
    doc.add_paragraph(
        "Subscribe to our monthly pantry box for only $28 per month. Baked in our regional factories. "
        "Visit our site [click here](https://aureliafoods.com) to view our seasonal sourdough selection."
    )
    doc.save(str(docx_path))
    print(f"Generated DOCX fixture: {docx_path}")


def generate_pdf():
    pdf_path = FIXTURES_DIR / "sample_with_errors.pdf"
    
    # Minimal valid single-page PDF with stream text
    text_lines = [
        "Aurelia Foods Sourdough Launch Document",
        "Our cheap sourdough loaves offer unbeatable taste for consumers.",
        "Golden Oat Elixir cures fatigue with guaranteed 100% safe organic ingredients.",
        "Visit our Portland factories or check our website [click here] for more info."
    ]
    
    # Build simple PDF structure
    content_stream = "BT\n/F1 12 Tf\n50 750 Td\n16 TL\n"
    for line in text_lines:
        safe_line = line.replace("(", "\\(").replace(")", "\\)")
        content_stream += f"({safe_line}) '\n"
    content_stream += "ET\n"
    
    stream_len = len(content_stream.encode('latin1'))
    
    pdf_content = (
        "%PDF-1.4\n"
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        f"4 0 obj\n<< /Length {stream_len} >>\nstream\n{content_stream}endstream\nendobj\n"
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        "xref\n0 6\n"
        "0000000000 65535 f \n"
        "0000000010 00000 n \n"
        "0000000060 00000 n \n"
        "0000000117 00000 n \n"
        f"0000000234 00000 n \n"
        f"{234 + stream_len + 45:010d} 00000 n \n"
        "trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        f"{320 + stream_len:d}\n%%EOF\n"
    )
    
    with open(pdf_path, "wb") as f:
        f.write(pdf_content.encode("latin1"))
    print(f"Generated PDF fixture: {pdf_path}")


def generate_expected_fixtures():
    fixtures_data = [
        {
            "id": "fixture_1_unsupported_claim",
            "text": "Golden Oat Elixir is the world's best oat beverage, clinically proven to boost vitality and guaranteed to rejuvenate your morning routine. Our revolutionary formula cures morning fatigue with 100% safe organic ingredients.",
            "intent": "Introduce Golden Oat Elixir product benefits",
            "expected_categories": ["unsupported_claim", "tone"],
            "expected_errors": ["world's best", "clinically proven", "guaranteed", "cures", "100% safe"],
        },
        {
            "id": "fixture_2_outdated_facts",
            "text": "Subscribe to our monthly artisan pantry box for only $28 per month. Our Portland production facility operates with 50% solar energy as we continue reducing our emissions.",
            "intent": "Subscription pricing and sustainability update",
            "expected_categories": ["factual_accuracy"],
            "expected_errors": ["$28", "50%"],
        },
        {
            "id": "fixture_3_off_brand_tone",
            "text": "Hey guys! We are gonna throw a super cool party this weekend. BUY NOW AND GET FREE SHIPPING on all orders! You will totally love these crazy good snacks.",
            "intent": "Announce weekend harvest event",
            "expected_categories": ["tone", "accessibility"],
            "expected_errors": ["gonna", "super cool", "BUY NOW AND GET FREE SHIPPING"],
        },
        {
            "id": "fixture_4_banned_terms",
            "text": "Our cheap sourdough loaves offer great taste for our users. Every loaf is baked in our modern factories using traditional wild yeast starters.",
            "intent": "Showcase artisan sourdough baking",
            "expected_categories": ["terminology"],
            "expected_errors": ["cheap", "users", "factories"],
        },
        {
            "id": "fixture_5_accessibility",
            "text": "Explore our harvest sourdough pairings! [click here](https://aureliafoods.com/recipes) to view the recipe.\n\n![](https://aureliafoods.com/images/loaf.jpg)",
            "intent": "Share sourdough recipe guide",
            "expected_categories": ["accessibility"],
            "expected_errors": ["[click here]", "![]("],
        },
        {
            "id": "fixture_6_clean_sample",
            "text": "Stone-Ground Einkorn Flour is sourced exclusively from certified organic family farms in Idaho. Aurelia Foods distributes to over 450 independent grocery stores across the Pacific Northwest. We thank our patrons for supporting sustainable regional agriculture.",
            "intent": "Explain grain sourcing and celebrate farm partnerships",
            "expected_categories": [],
            "expected_errors": [],
        },
        {
            "id": "fixture_7_ambiguous_case",
            "text": "Our new Wildflower Honey Infusion is crafted with all-natural botanical botanicals harvested from Willamette Valley apiaries.",
            "intent": "Introduce herbal botanical blend",
            "expected_categories": ["messaging"],
            "expected_errors": ["all-natural"],
        }
    ]

    expected_path = FIXTURES_DIR / "expected_findings.json"
    with open(expected_path, "w") as f:
        json.dump(fixtures_data, f, indent=2)
    print(f"Generated ground-truth fixtures: {expected_path}")


if __name__ == "__main__":
    generate_docx()
    generate_pdf()
    generate_expected_fixtures()
