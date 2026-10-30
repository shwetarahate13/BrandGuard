from types import SimpleNamespace

import backend.app.pipeline.runner as runner


class EmptyQuery:
    def all(self):
        return []

    def first(self):
        return None

    def filter(self, *_args, **_kwargs):
        return self


class EmptyDatabase:
    def query(self, *_args, **_kwargs):
        return EmptyQuery()


def test_confidential_submission_skips_configured_external_llm(monkeypatch):
    submission = SimpleNamespace(
        id="confidential-submission",
        title="Private launch",
        intent="Describe the planned launch",
        confidential=True,
    )
    version = SimpleNamespace(
        id="confidential-version",
        version_no=1,
        text="Internal launch notes for next month.",
        source_mime_type=None,
        source_file=None,
        source_layout=None,
    )
    monkeypatch.setattr(runner, "get_settings", lambda: SimpleNamespace(RETRIEVAL_TOP_K=12, llm_available=True))
    monkeypatch.setattr(runner, "reindex_if_empty", lambda _db: None)
    monkeypatch.setattr(runner, "retrieve_sources", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(runner, "run_rules_engine", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(runner, "suppressed_writing_rules", lambda _db: set())
    monkeypatch.setattr(runner, "suppressed_span_combinations", lambda _db: set())
    monkeypatch.setattr(runner, "_mock_llm_check", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(runner, "validate_citations", lambda candidates, *_args: (candidates, 0))
    monkeypatch.setattr(runner, "rank_findings_by_acceptance", lambda _db, findings, _text: findings)
    monkeypatch.setattr(runner, "prepare_suggestions", lambda findings, *_args, **_kwargs: findings)

    def reject_external_provider():
        raise AssertionError("external provider requested for confidential content")

    monkeypatch.setattr(runner, "get_llm_client", reject_external_provider)

    findings = runner.run_pipeline(submission, version, EmptyDatabase(), persist_findings=False)

    assert findings == []
