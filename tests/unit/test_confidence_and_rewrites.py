"""Unit tests for confidence routing and intent-preserving rewrite verification."""
from backend.app.pipeline.confidence import compute_confidence_and_routing, verify_intent_preserved


def test_confidence_routing_rules_and_similarity():
    # Rule based -> high confidence, needs_human=False
    f1 = {"issue": "Term issue"}
    res1 = compute_confidence_and_routing(f1, is_rule_based=True)
    assert res1["confidence"] == "high"
    assert res1["needs_human"] is False

    # Ambiguous -> low confidence, needs_human=True
    f2 = {"issue": "Ambiguous natural claim"}
    res2 = compute_confidence_and_routing(f2, is_ambiguous=True)
    assert res2["confidence"] == "low"
    assert res2["needs_human"] is True

    # Low similarity -> routed to human
    f3 = {"issue": "Distant match"}
    res3 = compute_confidence_and_routing(f3, source_similarity=0.3)
    assert res3["confidence"] == "low"
    assert res3["needs_human"] is True


def test_intent_preserved_verifies_context():
    orig = "cheap bread"
    rewrite = "accessible artisan sourdough"
    intent = "highlight fairly priced artisan bread"

    res = verify_intent_preserved(orig, rewrite, intent)
    assert res == rewrite


def test_intent_preserved_rejects_divergent_suggestion():
    orig = "Golden Oat Elixir cures morning fatigue"
    divergent_rewrite = "Buy our plastic water bottles now"
    intent = "Introduce organic oat milk"

    res = verify_intent_preserved(orig, divergent_rewrite, intent)
    # Divergent rewrite lacking common anchors with intent should be withheld
    assert res is None
