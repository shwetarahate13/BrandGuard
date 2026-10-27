"""Spawn-safe dispatcher for CPU and network-bound work."""
from __future__ import annotations

import logging
from multiprocessing.queues import Queue
from typing import Any

logger = logging.getLogger(__name__)


def execute_job_process(kind: str, payload: dict[str, Any], events: Queue) -> None:
    """Execute one known job type and stream progress to its parent process."""
    progress = lambda value, message: events.put(("progress", (int(value), str(message))))
    try:
        from backend.app.api.submissions import _extract_uploaded_version, _run_check_job

        if kind == "document-extraction":
            result = _extract_uploaded_version(payload["version_id"], payload["owner_id"], progress)
        elif kind == "content-review":
            from backend.app.database import get_session_factory
            from backend.app.pipeline.retriever import initialize_retrieval_worker

            progress(5, "Loading the available source retrieval engine.")
            engine = initialize_retrieval_worker(get_session_factory())
            progress(8, f"Using {engine} for this review.")
            result = _run_check_job(
                payload["submission_id"],
                payload["version_id"],
                payload["owner_id"],
                progress,
            )
        else:
            raise ValueError("Unknown background job type")
        events.put(("completed", result))
    except Exception as exc:
        if isinstance(exc, ValueError):
            public_message = str(exc)
        elif getattr(exc, "status_code", None) in {403, 404, 409}:
            public_message = getattr(exc, "detail", "This action is no longer available.")
        else:
            logger.exception("Background job failed (%s)", kind)
            public_message = "The review could not be completed. Retry the action or inspect the local log."
        events.put(("failed", public_message))
