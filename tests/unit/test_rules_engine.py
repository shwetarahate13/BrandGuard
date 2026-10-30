"""Unit tests for deterministic rules engine."""
from dataclasses import asdict
from backend.app.pipeline.rules_engine import run_rules_engine, flesch_kincaid_grade
from backend.app.pipeline.suggestion_safety import prepare_suggestions


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


def test_structured_fact_mismatch_has_exact_replacement_and_source_comparison():
    facts = [{
        "id": "fact-price",
        "statement": "Bright Desk plan costs $39 per month.",
        "subject": "Bright Desk plan",
        "value": "$39",
        "unit": "per month",
        "source_note": "Approved pricing sheet, 2026-01",
    }]
    text = "The Bright Desk plan costs $29 per month."

    findings = run_rules_engine(text, [], facts, [])

    assert len(findings) == 1
    finding = findings[0]
    assert text[finding.span_start:finding.span_end] == "$29"
    assert finding.category == "factual_accuracy"
    assert finding.suggested_rewrite == "$39"
    assert "your text: '$29'; approved value: '$39 per month'" in finding.issue
    assert "Source: Approved pricing sheet" in finding.issue
    assert finding.source_quote == facts[0]["statement"]


def test_structured_fact_correction_survives_safety_validation():
    facts = [{
        "id": "fact-price",
        "statement": "Artisan Pantry Subscription box costs $34 per month.",
        "subject": "Artisan Pantry Subscription box",
        "value": "$34",
        "unit": "per month",
        "source_note": "Approved pricing sheet",
    }]
    text = "Artisan Pantry Subscription box costs $28 per month."
    finding = asdict(run_rules_engine(text, [], facts, [])[0])

    prepare_suggestions([finding], text, "Describe the monthly subscription offer.", [], facts, [])

    assert finding["suggested_rewrite"] == "$34"


def test_structured_fact_conflicts_never_suggest_a_replacement():
    facts = [
        {"id": "old", "statement": "Bright Desk plan is $39.", "subject": "Bright Desk plan", "value": "$39"},
        {"id": "new", "statement": "Bright Desk plan is $49.", "subject": "Bright Desk plan", "value": "$49"},
    ]

    findings = run_rules_engine("Bright Desk plan costs $29 per month.", [], facts, [])

    assert len(findings) == 1
    assert "Conflicting active approved facts" in findings[0].issue
    assert findings[0].suggested_rewrite is None


def test_expired_structured_fact_is_routed_to_reviewer_without_rewrite():
    facts = [{
        "id": "expired",
        "statement": "Bright Desk plan was $29 per month.",
        "subject": "Bright Desk plan",
        "value": "$29",
        "valid_to": "2020-01-01T00:00:00+00:00",
    }]

    findings = run_rules_engine("Bright Desk plan costs $29 per month.", [], facts, [])

    assert len(findings) == 1
    assert "expired" in findings[0].issue
    assert findings[0].suggested_rewrite is None


def test_structured_fact_compares_dates_without_suggesting_expired_values():
    facts = [{
        "id": "launch-date",
        "statement": "The launch date is March 15, 2026.",
        "subject": "launch date",
        "value": "2026-03-15",
        "unit": "date",
        "source_note": "Approved launch calendar",
    }]

    findings = run_rules_engine("The launch date is March 14, 2026.", [], facts, [])

    assert len(findings) == 1
    finding = findings[0]
    assert "March 14, 2026" == "The launch date is March 14, 2026."[finding.span_start:finding.span_end]
    assert finding.suggested_rewrite == "March 15, 2026"
