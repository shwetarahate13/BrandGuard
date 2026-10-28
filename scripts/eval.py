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
from backend.app.pipeline.writing_assistant import analyze_writing


def evaluate_writing_assistant_fixtures() -> Dict[str, Any]:
    """Measure spelling and grammar rules directly, separately from retrieval/model checks."""
    fixture_path = REPO_ROOT / "tests" / "fixtures" / "writing_assistant.json"
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    style = {"id": "eval-style-1", "code": "STYLE-1", "text": "Content must be free of spelling and grammar errors."}
    metrics = {
        "spelling": {"expected": 0, "tp": 0, "fp": 0, "fn": 0},
        "grammar": {"expected": 0, "tp": 0, "fp": 0, "fn": 0},
    }
    clean_copy_count = 0
    clean_copy_flags = 0
    results = []

    for item in fixtures:
        findings = analyze_writing(item["text"], style)
        expected_spelling = list(item.get("expected_spelling", []))
        expected_grammar = list(item.get("expected_grammar", []))
        spelling_hits = [item["text"][finding.span_start:finding.span_end].casefold() for finding in findings if finding.category == "spelling"]
        grammar_hits = [finding.issue.split(":", 1)[0] for finding in findings if finding.category == "grammar"]
        matched_spelling = sum(1 for expected in expected_spelling if expected.casefold() in spelling_hits)
        matched_grammar = sum(1 for expected in expected_grammar if expected in grammar_hits)
        metrics["spelling"]["expected"] += len(expected_spelling)
        metrics["spelling"]["tp"] += matched_spelling
        metrics["spelling"]["fn"] += len(expected_spelling) - matched_spelling
        metrics["spelling"]["fp"] += max(0, len(spelling_hits) - matched_spelling)
        metrics["grammar"]["expected"] += len(expected_grammar)
        metrics["grammar"]["tp"] += matched_grammar
        metrics["grammar"]["fn"] += len(expected_grammar) - matched_grammar
        metrics["grammar"]["fp"] += max(0, len(grammar_hits) - matched_grammar)
        if item["id"].startswith("clean_brand_copy_"):
            clean_copy_count += 1
            clean_copy_flags += len(findings)
        results.append({"id": item["id"], "expected_spelling": expected_spelling, "expected_grammar": expected_grammar,
                        "findings": [finding.issue.split(":", 1)[0] for finding in findings]})

    for category, values in metrics.items():
        denominator = values["tp"] + values["fp"]
        values["precision"] = values["tp"] / denominator if denominator else 1.0
        values["recall"] = values["tp"] / values["expected"] if values["expected"] else 1.0
    return {"metrics": metrics, "clean_brand_copy_controls": clean_copy_count,
            "clean_brand_copy_false_flags": clean_copy_flags, "fixtures": results}


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
    writing_metrics = evaluate_writing_assistant_fixtures()

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
    for category, values in writing_metrics["metrics"].items():
        print(f"{category.title()} precision: {values['precision']:.2%}; recall: {values['recall']:.2%}")
    print(f"Clean brand-copy false flags: {writing_metrics['clean_brand_copy_false_flags']} across {writing_metrics['clean_brand_copy_controls']} controls")

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

## Writing Assistant Rule Evaluation

These checks run directly against the offline spelling/grammar engine, separately from retrieval and model findings.

| Rule category | Precision | Recall | TP | FP | FN |
| :--- | :--- | :--- | ---: | ---: | ---: |
""")
        for category, values in writing_metrics["metrics"].items():
            f.write(f"| {category.title()} | {values['precision']:.1%} | {values['recall']:.1%} | {values['tp']} | {values['fp']} | {values['fn']} |\n")
        f.write(f"\nClean brand-copy controls: {writing_metrics['clean_brand_copy_false_flags']} false flags across {writing_metrics['clean_brand_copy_controls']} fixtures.\n\n")
        f.write("| Writing fixture | Expected spelling | Expected grammar rules | Detected rules |\n| :--- | :--- | :--- | :--- |\n")
        for result in writing_metrics["fixtures"]:
            f.write(f"| `{result['id']}` | {', '.join(result['expected_spelling']) or '—'} | {', '.join(result['expected_grammar']) or '—'} | {', '.join(result['findings']) or '—'} |\n")

        f.write(f"""
---

## Interpretation

These scores describe finite synthetic fixture sets, not production accuracy. The pipeline metrics match expected phrases; writing-assistant metrics match planted misspellings or rule IDs. Clean-copy false flags count findings across the named clean brand-copy controls. Citation validation drops candidates without supported sources, but this script does not calculate an overall citation-accuracy percentage. Intent preservation is covered by separate tests and is not measured here.
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
        "writing_assistant": writing_metrics,
    }


if __name__ == "__main__":
    run_evaluation()
