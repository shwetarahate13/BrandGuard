from backend.app.pipeline.writing_assistant import analyze_writing
from backend.app.pipeline.suggestion_safety import prepare_suggestions
from backend.app.pipeline.confidence import verify_intent_preserved
from scripts.eval import evaluate_writing_assistant_fixtures
import time


STYLE = {
    "id": "clause-style-1",
    "code": "STYLE-1",
    "text": "Content must be free of spelling and grammar errors.",
}


def test_spelling_and_grammar_findings_cite_style_and_quote_exact_spans():
    text = "Teh patrons is more faster"
    findings = analyze_writing(text, STYLE)
    assert {finding.category for finding in findings} == {"spelling", "grammar"}
    for finding in findings:
        assert text[finding.span_start: finding.span_end]
        assert finding.source_id == STYLE["id"]
        assert finding.source_quote == STYLE["text"]
        assert finding.issue.startswith(("SPELL-", "GRAM-"))


def test_brand_allowlist_and_protected_tokens_are_not_flagged():
    text = "Golden Oat Elixir accomodate https://example.com/a and hello@example.com @Aurelia #GoldenOat `teh` <b>the</b> 😀"
    findings = analyze_writing(text, STYLE, ["accomodate", "Golden Oat Elixir"])
    assert not findings


def test_known_spelling_is_detected_but_unknown_brand_word_is_left_alone():
    text = "AureliaFoods accomodate the launch."
    findings = analyze_writing(text, STYLE, ["AureliaFoods"])
    spelling = [finding for finding in findings if finding.category == "spelling"]
    assert len(spelling) == 1
    assert text[spelling[0].span_start:spelling[0].span_end] == "accomodate"
    assert spelling[0].suggested_rewrite == "accommodate"


def test_requested_sample_gets_concrete_grammar_and_spelling_replacements():
    text = "Their is a new Bright Desk plan, it help teams finish reports more faster. We guarentee 100% accuracy and its the best tool in the world."
    findings = analyze_writing(text, STYLE, ["Bright Desk"])
    replacements = {
        (text[item.span_start:item.span_end], item.suggested_rewrite)
        for item in findings
        if item.suggested_rewrite
    }

    assert ("Their is", "There is") in replacements
    assert ("it help", "it helps") in replacements
    assert ("more faster", "faster") in replacements
    assert ("guarentee", "guarantee") in replacements
    assert ("its the", "it's the") in replacements
    assert all(item.source_quote == STYLE["text"] for item in findings)


def test_empty_or_unseeded_clause_disables_writing_findings():
    assert analyze_writing("teh", None) == []


def test_claim_rewrite_without_approved_fact_is_withheld_and_routed():
    finding = {
        "span_start": 0, "span_end": 10, "category": "unsupported_claim",
        "issue": "Unsupported claim.", "source_type": "guideline_clause",
        "source_id": "claim-clause", "suggested_rewrite": "clinically supported",
    }
    prepare_suggestions([finding], "guaranteed", "describe the product", [], [], [
        {"id": "claim-clause", "code": "CLAIM-1", "text": "Claims require approved evidence."},
    ])
    assert finding["suggested_rewrite"] is None
    assert finding["needs_human"] is True
    assert "route this claim to the reviewer" in finding["issue"]
    assert "Guideline CLAIM-1" in finding["issue"]


def test_overlapping_terminology_edit_precedes_spelling_edit():
    findings = [
        {"span_start": 0, "span_end": 6, "category": "spelling", "issue": "typo", "source_type": "guideline_clause", "suggested_rewrite": "clients"},
        {"span_start": 0, "span_end": 6, "category": "terminology", "issue": "use patrons", "source_type": "term", "suggested_rewrite": "patrons"},
    ]
    prepare_suggestions(findings, "client", "refer to our audience", [], [], [])
    assert findings[1]["suggested_rewrite"] == "patrons"
    assert findings[0]["suggested_rewrite"] is None
    assert "queued" in findings[0]["issue"]


def test_rewrite_that_adds_unsupported_claim_is_withheld():
    finding = {
        "span_start": 0, "span_end": 7, "category": "terminology",
        "issue": "Use preferred wording.", "source_type": "term",
        "suggested_rewrite": "guaranteed",
    }
    clauses = [{"id": "claim-clause", "code": "CLAIM-1", "text": "Claims need approved evidence."}]
    prepare_suggestions([finding], "patrons", "describe our audience", [], [], clauses)
    assert finding["suggested_rewrite"] is None
    assert finding["needs_human"] is True
    assert "new high-severity issue" in finding["issue"]


def test_all_planted_fixtures_detected_and_clean_brand_copy_has_no_false_flags():
    result = evaluate_writing_assistant_fixtures()
    for values in result["metrics"].values():
        assert values["fn"] == 0
        assert values["fp"] == 0
        assert values["precision"] == 1
        assert values["recall"] == 1
    assert result["clean_brand_copy_controls"] >= 3
    assert result["clean_brand_copy_false_flags"] == 0


def test_markup_and_unicode_offsets_preserve_surrounding_content():
    text = "**Accomodate** 😀"
    finding = next(item for item in analyze_writing(text, STYLE) if item.category == "spelling")
    corrected = text[:finding.span_start] + finding.suggested_rewrite + text[finding.span_end:]
    assert corrected == "**Accommodate** 😀"


def test_non_english_copy_is_not_flagged():
    assert analyze_writing("El producto es bueno para los clientes", STYLE) == []
    assert analyze_writing("नमस्ते दुनिया", STYLE) == []


def test_intent_verification_keeps_aligned_rewrites_and_drops_divergent_ones():
    assert verify_intent_preserved("customers", "patrons", "speak to our audience", "term") == "patrons"
    assert verify_intent_preserved("organic oat drink", "cures cancer", "promote a healthy breakfast") is None


def test_offline_check_of_one_thousand_words_is_bounded():
    text = "Golden Oat Elixir is ready for our patrons. " * 125
    started = time.perf_counter()
    analyze_writing(text, STYLE)
    assert time.perf_counter() - started < 2.0
