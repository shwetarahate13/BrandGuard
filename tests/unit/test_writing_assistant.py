from backend.app.pipeline.writing_assistant import analyze_writing


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


def test_empty_or_unseeded_clause_disables_writing_findings():
    assert analyze_writing("teh", None) == []
