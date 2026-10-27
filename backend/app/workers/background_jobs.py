"""Bounded in-process jobs for slow local document work."""
from __future__ import annotations

import logging
import multiprocessing
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class BackgroundQueueFull(Exception):
    """The bounded background queue has no capacity for another job."""


class BackgroundJobs:
    """Run heavy operations away from request handlers with visible progress."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="brandguard-job")
        self._slots = threading.BoundedSemaphore(get_settings().HEAVY_JOB_CONCURRENCY)
        self._jobs: dict[str, dict[str, Any]] = {}
        self._dedupe: dict[str, str] = {}

    def submit(
        self,
        *,
        owner_id: str,
        kind: str,
        payload: dict[str, Any],
        timeout_seconds: int = 180,
        dedupe_key: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if dedupe_key:
                existing_id = self._dedupe.get(dedupe_key)
                existing = self._jobs.get(existing_id or "")
                if existing and existing["status"] in {"queued", "running"}:
                    return self._view(existing)

            active_count = sum(job["status"] in {"queued", "running"} for job in self._jobs.values())
            if active_count >= get_settings().HEAVY_JOB_CONCURRENCY + 8:
                raise BackgroundQueueFull("All background review slots are full. Please retry in a moment.")

            job_id = str(uuid.uuid4())
            job = {
                "id": job_id,
                "owner_id": owner_id,
                "kind": kind,
                "status": "queued",
                "progress": 0,
                "message": "Waiting for an available review worker.",
                "result": None,
                "error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "dedupe_key": dedupe_key,
            }
            self._jobs[job_id] = job
            if dedupe_key:
                self._dedupe[dedupe_key] = job_id
            self._prune_locked()
        self._pool.submit(self._run, job_id, kind, payload, timeout_seconds)
        return self.get(job_id, owner_id)

    def _run(self, job_id: str, kind: str, payload: dict[str, Any], timeout_seconds: int) -> None:
        if not self._slots.acquire(timeout=20):
            self._finish(job_id, error="All review workers are busy. Please retry in a moment.")
            return
        process = None
        events = None
        try:
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job.update(status="running", progress=1, message="Review started.", updated_at=datetime.now(timezone.utc).isoformat())
            context = multiprocessing.get_context("spawn")
            events = context.Queue()
            from backend.app.workers.job_runner import execute_job_process

            process = context.Process(target=execute_job_process, args=(kind, payload, events), daemon=True)
            process.start()
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                try:
                    event, value = events.get(timeout=0.25)
                except queue.Empty:
                    if not process.is_alive():
                        break
                    continue
                if event == "progress":
                    self._progress(job_id, value[0], value[1])
                elif event == "completed":
                    self._finish(job_id, result=value)
                    break
                elif event == "failed":
                    self._finish(job_id, error=value)
                    break
            else:
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2)
                self._finish(job_id, error="This review exceeded its time limit and was stopped. Retry it after checking the file or service.")
            if process.is_alive():
                process.join(timeout=0.25)
            if process.is_alive() and self.get(job_id, self._owner(job_id)) and self.get(job_id, self._owner(job_id))["status"] not in {"completed", "failed"}:
                process.terminate()
                process.join(timeout=2)
            state = self.get(job_id, self._owner(job_id))
            if state and state["status"] not in {"completed", "failed"}:
                self._finish(job_id, error="The worker stopped before the review completed. Retry the action.")
        except Exception:
            logger.exception("Background %s job failed", job_id)
            self._finish(job_id, error="The review could not be completed. Retry the action or inspect the local log.")
        finally:
            if process and process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if events:
                events.close()
            self._slots.release()

    def _owner(self, job_id: str) -> str:
        with self._lock:
            return str(self._jobs.get(job_id, {}).get("owner_id", ""))

    def _progress(self, job_id: str, value: int, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] != "running":
                return
            job.update(
                progress=max(1, min(99, int(value))),
                message=str(message)[:240],
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

    def _finish(self, job_id: str, *, result=None, error: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["status"] in {"completed", "failed"}:
                return
            job.update(
                status="failed" if error else "completed",
                progress=100 if not error else job["progress"],
                message="Review complete." if not error else error,
                error=error,
                result=result,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

    @staticmethod
    def _view(job: dict[str, Any]) -> dict[str, Any]:
        return {key: job[key] for key in (
            "id", "kind", "status", "progress", "message", "error", "result", "created_at", "updated_at"
        )}

    def get(self, job_id: str, owner_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["owner_id"] != owner_id:
                return None
            return self._view(job)

    def _prune_locked(self) -> None:
        if len(self._jobs) <= 500:
            return
        terminal = [job for job in self._jobs.values() if job["status"] in {"completed", "failed"}]
        for job in terminal[: max(0, len(self._jobs) - 400)]:
            self._jobs.pop(job["id"], None)
            if job.get("dedupe_key"):
                self._dedupe.pop(job["dedupe_key"], None)


background_jobs = BackgroundJobs()
