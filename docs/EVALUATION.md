# BrandGuard Pipeline Evaluation Report

## Executive Summary

The BrandGuard review engine was evaluated across structured test fixtures containing planted brand compliance errors, factual discrepancies, banned terminology, tone inconsistencies, accessibility violations, and clean controls.

- **Precision**: 93.33%
- **Recall**: 87.50%
- **F1 Score**: 90.32%
- **Clean Sample Over-flagging**: 0 flags across 1 clean control(s)
- **Citation Validator Dropped Count**: 0 invalid candidate findings dropped
- **Retrieval engine**: HashingVectorizer fallback (fallback)

---

## Observed Metrics

| Metric | Observed |
| :--- | :--- |
| Precision | 93.3% |
| Recall | 87.5% |
| F1 score | 90.3% |
| Clean-control flags | 0 across 1 clean control(s) |
| Invalid candidate findings dropped by citation validation | 0 |

---

## Fixture Test Results

| Fixture ID | Planted Issues | Detected Findings |
| :--- | :--- | :--- |
| `fixture_1_unsupported_claim` | 5 | 6 |
| `fixture_2_outdated_facts` | 2 | 2 |
| `fixture_3_off_brand_tone` | 3 | 1 |
| `fixture_4_banned_terms` | 3 | 3 |
| `fixture_5_accessibility` | 2 | 2 |
| `fixture_6_clean_sample` | 0 | 0 |
| `fixture_7_ambiguous_case` | 1 | 1 |

---

## Interpretation

These scores describe this finite synthetic fixture set, not production accuracy. The script counts a planted issue as found when its expected phrase appears in a finding span or issue. Clean-control flags are reported as a count and rate; they are not a calibrated specificity estimate. Citation validation drops candidates without supported sources, but this script does not calculate an overall citation-accuracy percentage. Intent preservation is covered by separate tests and is not measured here.
