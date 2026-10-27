"""BrandGuard Evaluation Script.

Evaluates review pipeline on test fixtures:
- Measures Precision, Recall, and F1 score against expected planted issues
- Measures Clean Text False Positive Rate (specificity)
- Measures Citation Validator drop rate
- Measures Intent Preservation rate
- Outputs detailed evaluation report
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure repo root in sys.path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.app.database import get_session_factory
from backend.app.models.models import Submission, SubmissionVersion, User, ContentType, SubmissionStatus
from backend.app.pipeline.runner import run_pipeline
from backend.app.pipeline.retriever import get_retrieval_status, start_embedding_warmup
from backend.app.seed import run_seed
from backend.app.pipeline.citation_validator import get_dropped_findings_count, reset_dropped_count


def run_evaluation() -> Dict[str, Any]:
    print("=" * 60)
    print("BrandGuard Pipeline Evaluation Engine")
    print("=" * 60)

    session_factory = get_session_factory()
    start_embedding_warmup(session_factory)
    deadline = time.monotonic() + 180
    while get_retrieval_status()["state"] in {"warming_up", "reindexing", "not_started"}:
        if time.monotonic() >= deadline:
            raise TimeoutError("Retrieval engine did not finish warming up within 180 seconds")
        time.sleep(0.2)
    retrieval = get_retrieval_status()
    retrieval_engine = retrieval["engine"]
    print(f"Retrieval engine used: {retrieval_engine} ({retrieval['state']})")

    db = session_factory()
    run_seed(db)

    fixtures_path = REPO_ROOT / "tests" / "fixtures" / "expected_findings.json"
    with open(fixtures_path) as f:
        fixtures = json.load(f)

    user = db.query(User).filter(User.role == "creator").first()

    total_expected_errors = 0
    total_detected_errors = 0
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    clean_samples_tested = 0
    clean_sample_flags = 0

    results_table = []
    reset_dropped_count()

    for item in fixtures:
        f_id = item["id"]
        text = item["text"]
        intent = item.get("intent", "")
        expected_errors = item.get("expected_errors", [])
        expected_cats = item.get("expected_categories", [])

        # Create temporary submission
        sub = Submission(
            creator_id=user.id,
            title=f_id,
            intent=intent,
            content_type=ContentType.text,
            status=SubmissionStatus.draft,
        )
        db.add(sub)
        db.flush()

        ver = SubmissionVersion(
            submission_id=sub.id,
            version_no=1,
            text=text,
            created_by=user.id,
        )
        db.add(ver)
        db.flush()

        # Run pipeline
        findings = run_pipeline(sub, ver, db)

        # Evaluate matches
        detected_spans = []
        for f in findings:
            if f.span_start is not None and f.span_end is not None:
                detected_text = text[f.span_start:f.span_end]
                detected_spans.append((detected_text, f.category.value, f.issue))
            else:
                detected_spans.append(("", f.category.value, f.issue))

        if not expected_errors:
            # Clean sample
            clean_samples_tested += 1
            if len(findings) > 0:
                clean_sample_flags += len(findings)
                false_positives += len(findings)
        else:
            total_expected_errors += len(expected_errors)
            matched_expected = set()

            for exp in expected_errors:
                matched = False
                for d_text, d_cat, d_issue in detected_spans:
                    if exp.lower() in d_text.lower() or exp.lower() in d_issue.lower():
                        matched = True
                        matched_expected.add(exp)
                        break

            tp_for_item = len(matched_expected)
            fn_for_item = len(expected_errors) - tp_for_item
            # Any findings that didn't correspond to expected errors
            fp_for_item = max(0, len(findings) - tp_for_item)

            true_positives += tp_for_item
            false_negatives += fn_for_item
            false_positives += fp_for_item

        results_table.append({
            "fixture": f_id,
            "expected_count": len(expected_errors),
            "detected_count": len(findings),
            "findings": [f"{f.category.value}: {f.issue[:60]}" for f in findings],
        })

    # Calculations
    precision = (true_positives / (true_positives + false_positives)) if (true_positives + false_positives) > 0 else 1.0
    recall = (true_positives / (true_positives + false_negatives)) if (true_positives + false_negatives) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    clean_fp_rate = (clean_sample_flags / clean_samples_tested) if clean_samples_tested > 0 else 0.0
    dropped_count = get_dropped_findings_count()

    print("\n--- Evaluation Results ---")
    print(f"Total Test Fixtures: {len(fixtures)}")
    print(f"Planted Errors: {total_expected_errors}")
    print(f"True Positives: {true_positives}")
    print(f"False Positives: {false_positives}")
    print(f"False Negatives: {false_negatives}")
    print(f"Precision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")
    print(f"F1 Score: {f1:.2%}")
    print(f"Clean Sample Over-flagging Rate: {clean_fp_rate:.2f} per sample")
    print(f"Citation Validator Dropped Count: {dropped_count}")

    # Write EVALUATION.md
    eval_doc_path = REPO_ROOT / "docs" / "EVALUATION.md"
    with open(eval_doc_path, "w") as f:
        f.write(f"""# BrandGuard Pipeline Evaluation Report

## Executive Summary

The BrandGuard review engine was evaluated across structured test fixtures containing planted brand compliance errors, factual discrepancies, banned terminology, tone inconsistencies, accessibility violations, and clean controls.

- **Precision**: {precision:.2%}
- **Recall**: {recall:.2%}
- **F1 Score**: {f1:.2%}
- **Clean Sample Over-flagging**: {clean_sample_flags} flags across {clean_samples_tested} clean control(s)
- **Citation Validator Dropped Count**: {dropped_count} invalid candidate findings dropped
- **Retrieval engine**: {retrieval_engine} ({retrieval['state']})

---

## Observed Metrics

| Metric | Observed |
| :--- | :--- |
| Precision | {precision:.1%} |
| Recall | {recall:.1%} |
| F1 score | {f1:.1%} |
| Clean-control flags | {clean_sample_flags} across {clean_samples_tested} clean control(s) |
| Invalid candidate findings dropped by citation validation | {dropped_count} |

---

## Fixture Test Results

| Fixture ID | Planted Issues | Detected Findings |
| :--- | :--- | :--- |
""")
        for r in results_table:
            f.write(f"| `{r['fixture']}` | {r['expected_count']} | {r['detected_count']} |\n")

        f.write(f"""
---

## Interpretation

These scores describe this finite synthetic fixture set, not production accuracy. The script counts a planted issue as found when its expected phrase appears in a finding span or issue. Clean-control flags are reported as a count and rate; they are not a calibrated specificity estimate. Citation validation drops candidates without supported sources, but this script does not calculate an overall citation-accuracy percentage. Intent preservation is covered by separate tests and is not measured here.
""")

    print(f"\nWritten evaluation report to: {eval_doc_path}")
    db.close()
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "dropped_count": dropped_count,
        "retrieval_engine": retrieval_engine,
        "retrieval_state": retrieval["state"],
    }


if __name__ == "__main__":
    run_evaluation()
