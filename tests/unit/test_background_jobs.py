import pytest

from backend.app.workers import background_jobs as jobs_module


class _FakeEvents:
    def close(self):
        pass


class _FakeProcess:
    def __init__(self):
        self.alive = False
        self.terminated = False
        self.killed = False

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        if self.terminated or self.killed:
            self.alive = False

    def terminate(self):
        self.terminated = True
        self.alive = False

    def kill(self):
        self.killed = True
        self.alive = False


class _FakeContext:
    def __init__(self):
        self.process = _FakeProcess()

    def Queue(self):
        return _FakeEvents()

    def Process(self, **_kwargs):
        return self.process


def _queued_job(owner_id="creator", kind="content-review"):
    return {
        "id": "job-test",
        "owner_id": owner_id,
        "kind": kind,
        "status": "queued",
        "progress": 0,
        "message": "Waiting",
        "result": None,
        "error": None,
        "created_at": "now",
        "updated_at": "now",
        "dedupe_key": None,
    }


@pytest.mark.parametrize("kind", ["content-review", "document-extraction"])
def test_background_job_timeout_terminates_worker_process(monkeypatch, kind):
    context = _FakeContext()
    manager = jobs_module.BackgroundJobs()
    manager._jobs["job-test"] = _queued_job(kind=kind)
    monkeypatch.setattr(jobs_module.multiprocessing, "get_context", lambda _method: context)

    manager._run("job-test", kind, {}, timeout_seconds=0)

    job = manager.get("job-test", "creator")
    assert context.process.terminated
    assert job["status"] == "failed"
    assert "time limit" in job["error"]


def test_background_job_progress_and_status_are_scoped_to_owner():
    manager = jobs_module.BackgroundJobs()
    job = _queued_job()
    job["status"] = "running"
    manager._jobs[job["id"]] = job

    manager._progress(job["id"], 46, "Matching claims")

    visible = manager.get(job["id"], "creator")
    assert visible["progress"] == 46
    assert visible["message"] == "Matching claims"
    assert manager.get(job["id"], "another-user") is None
