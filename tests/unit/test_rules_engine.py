"""Unit tests for deterministic rules engine."""
from backend.app.pipeline.rules_engine import run_rules_engine, flesch_kincaid_grade


def test_forbidden_promotional_phrases():
    clauses = [{"id": "c1", "text": "All claims must be substantiated with evidence."}]
    terms = []
    facts = []

    text = "Our formula is clinically proven and guaranteed to improve health."
    findings = run_rules_engine(text, terms, facts, clauses)

    issues = [f.issue for f in findings]
    assert any("clinically proven" in i for i in issues)
    assert any("guaranteed" in i for i in issues)
    assert all(f.category == "unsupported_claim" for f in findings if "guaranteed" in f.issue)
    assert all(f.severity == "major" for f in findings if f.category == "unsupported_claim")


def test_terminology_avoided_terms():
    clauses = []
    terms = [
        {"id": "t1", "preferred": "accessible pricing", "avoid": ["cheap"]},
        {"id": "t2", "preferred": "patrons", "avoid": ["users", "consumers"]},
    ]
    facts = []

    text = "We offer cheap options for our users."
    findings = run_rules_engine(text, terms, facts, clauses)

    assert len(findings) == 2
    assert findings[0].suggested_rewrite == "accessible pricing"
    assert findings[1].suggested_rewrite == "patrons"
    assert all(f.category == "terminology" for f in findings)


def test_accessibility_vague_links_and_missing_alt():
    clauses = []
    terms = []
    facts = []

    text = "Check our catalog! [click here](https://brand.com) and ![](https://brand.com/img.png)"
    findings = run_rules_engine(text, terms, facts, clauses)

    cats = [f.category for f in findings]
    assert "accessibility" in cats
    assert any("Vague link text" in f.issue for f in findings)
    assert any("alt text" in f.issue for f in findings)


def test_accessibility_all_caps_blocks():
    clauses = []
    terms = []
    facts = []

    text = "Welcome to our store. BUY NOW AND GET FREE shipping today."
    findings = run_rules_engine(text, terms, facts, clauses)

    caps_findings = [f for f in findings if "all-caps" in f.issue.lower()]
    assert len(caps_findings) >= 1
    assert caps_findings[0].category == "accessibility"


def test_clean_text_no_false_positives():
    clauses = [{"id": "c1", "text": "Tone must be grounded and friendly."}]
    terms = [{"id": "t1", "preferred": "patrons", "avoid": ["consumers"]}]
    facts = [{"id": "f1", "statement": "We ship to 50 states.", "valid_to": None}]

    text = "Our artisan sourdough is baked daily using stone-ground einkorn flour."
    findings = run_rules_engine(text, terms, facts, clauses)
    assert len(findings) == 0
