"""Unit tests for citation validator."""
from backend.app.pipeline.citation_validator import validate_citations, quote_exists_in_source
from backend.app.database import get_session_factory
from backend.app.seed import run_seed
from backend.app.models.models import GuidelineClause, ApprovedFact


def test_quote_exists_exact_and_fuzzy():
    source = "All nutritional claims must be backed by approved clinical testing."
    assert quote_exists_in_source("clinical testing", source)
    assert quote_exists_in_source("All nutritional claims", source)
    assert not quote_exists_in_source("alien technology from mars", source)


def test_validator_drops_nonexistent_source():
    db = get_session_factory()()
    run_seed(db)

    findings = [
        {
            "span_start": 0,
            "span_end": 10,
            "category": "tone",
            "issue": "Fake issue with fake source",
            "source_id": "non_existent_uuid_12345",
            "source_quote": "Some fake quote",
            "severity": "minor",
        }
    ]
    retrieved = []

    validated, dropped = validate_citations(findings, retrieved, db)
    assert len(validated) == 0
    assert dropped == 1
    db.close()


def test_validator_drops_hallucinated_quote():
    db = get_session_factory()()
    run_seed(db)

    clause = db.query(GuidelineClause).first()
    findings = [
        {
            "span_start": 0,
            "span_end": 10,
            "category": "tone",
            "issue": "Real source but hallucinated quote",
            "source_id": str(clause.id),
            "source_quote": "A completely invented quote that never appeared in the text.",
            "severity": "minor",
        }
    ]
    retrieved = [{"id": str(clause.id), "text": clause.text}]

    validated, dropped = validate_citations(findings, retrieved, db)
    assert len(validated) == 0
    assert dropped == 1
    db.close()


def test_validator_keeps_valid_citation():
    db = get_session_factory()()
    run_seed(db)

    clause = db.query(GuidelineClause).first()
    quote = clause.text[:40]

    findings = [
        {
            "span_start": 0,
            "span_end": 10,
            "category": "tone",
            "issue": "Valid finding with real quote",
            "source_id": str(clause.id),
            "source_quote": quote,
            "severity": "minor",
        }
    ]
    retrieved = [{"id": str(clause.id), "text": clause.text}]

    validated, dropped = validate_citations(findings, retrieved, db)
    assert len(validated) == 1
    assert dropped == 0
    assert validated[0]["source_id"] == str(clause.id)
    db.close()
