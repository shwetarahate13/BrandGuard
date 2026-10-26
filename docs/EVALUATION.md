# BrandGuard Pipeline Evaluation Report

## Executive Summary

The BrandGuard review engine was evaluated across structured test fixtures containing planted brand compliance errors, factual discrepancies, banned terminology, tone inconsistencies, accessibility violations, and clean controls.

- **Precision**: 93.33%
- **Recall**: 87.50%
- **F1 Score**: 90.32%
- **Clean Sample Over-flagging**: 0 flags across 1 clean control(s)
- **Citation Validator Dropped Count**: 0 invalid candidate findings dropped

---

## Detailed Metric Breakdown

| Metric | Score | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Precision** | **93.3%** | >= 85% | Pass |
| **Recall** | **87.5%** | >= 85% | Pass |
| **F1 Score** | **90.3%** | >= 85% | Pass |
| **Clean Specificity** | **100.0%** | >= 90% | Pass |
| **Citation Verification** | **100% Grounded** | 100% | Pass |

---

## Fixture Test Results

| Fixture ID | Planted Issues | Detected Findings | Status |
| :--- | :--- | :--- | :--- |
| `fixture_1_unsupported_claim` | 5 | 6 | Pass |
| `fixture_2_outdated_facts` | 2 | 2 | Pass |
| `fixture_3_off_brand_tone` | 3 | 1 | Review |
| `fixture_4_banned_terms` | 3 | 3 | Pass |
| `fixture_5_accessibility` | 2 | 2 | Pass |
| `fixture_6_clean_sample` | 0 | 0 | Pass |
| `fixture_7_ambiguous_case` | 1 | 1 | Pass |

---

## Grounded or Silent Verification

The citation validator enforces that every finding cites a verified `source_id` present in the retrieved set and matches an exact quote from the source text. During evaluation runs on candidate variations, 0 candidate assertions lacking strict source quotes were dropped, preventing ungrounded hallucinated flags.

## Intent Preservation Verification

Rewrites for accepted findings were evaluated against the creator's stated intent. Suggestions that diverged from intent anchors were automatically withheld, providing raw findings rather than flawed automatic suggestions.
