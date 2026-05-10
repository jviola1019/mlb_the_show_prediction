"""In-memory scan job runner for hosted stateless deployments.

Jobs are bounded by ``MAX_JOBS`` via an LRU eviction policy so the dict cannot
grow unbounded on a long-running host. The eldest job is evicted when a new
one is created beyond the cap.
"""

from __future__ import annotations

import threading
import time
import uuid as uuidlib
from collections import OrderedDict
from copy import deepcopy
from typing import Any

from .scan import scan_payload


MAX_JOBS = 64
_LOCK = threading.Lock()
_JOBS: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _snapshot(job_id: str) -> dict[str, Any]:
    with _LOCK:
        return deepcopy(_JOBS[job_id])


def _update(job_id: str, values: dict[str, Any]) -> None:
    with _LOCK:
        if job_id not in _JOBS:
            return
        _JOBS[job_id].update(values)
        _JOBS[job_id]["updated_at"] = _utc_now()
        _JOBS.move_to_end(job_id)


def _evict_oldest_locked() -> None:
    while len(_JOBS) > MAX_JOBS:
        _JOBS.popitem(last=False)


def start_scan_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Start a scan in a background thread and return the initial job state."""

    job_id = uuidlib.uuid4().hex
    now = _utc_now()
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "total": 0,
            "completed": 0,
            "current_uuid": None,
            "current_name": None,
            "dropped_count": 0,
            "invalid_count": 0,
            "started_at": now,
            "updated_at": now,
            "completed_at": None,
            "elapsed_seconds": None,
            "rate_limit_message": "The Show API calls are server-side and may be rate limited; large scans should be batched.",
            "result": None,
            "error": None,
        }
        _JOBS.move_to_end(job_id)
        _evict_oldest_locked()

    def run() -> None:
        started = time.time()
        _update(job_id, {"status": "running"})

        def progress(values: dict[str, Any]) -> None:
            _update(job_id, values)

        try:
            result = scan_payload(payload, progress=progress)
            progress_payload = result.get("progress") or {}
            _update(job_id, {
                "status": "complete",
                "total": progress_payload.get("total", len(result.get("records") or [])),
                "completed": progress_payload.get("completed", len(result.get("records") or [])),
                "current_uuid": None,
                "current_name": None,
                "dropped_count": progress_payload.get("dropped_count", 0),
                "invalid_count": progress_payload.get("invalid_count", 0),
                "completed_at": _utc_now(),
                "elapsed_seconds": round(time.time() - started, 3),
                "result": result,
            })
        except Exception as exc:  # pragma: no cover - defensive background path
            _update(job_id, {
                "status": "error",
                "error": str(exc),
                "completed_at": _utc_now(),
                "elapsed_seconds": round(time.time() - started, 3),
            })

    thread = threading.Thread(target=run, name=f"scan-job-{job_id[:8]}", daemon=True)
    thread.start()
    return _snapshot(job_id)


def get_scan_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        if job_id not in _JOBS:
            return None
        _JOBS.move_to_end(job_id)
        return deepcopy(_JOBS[job_id])


def list_scan_jobs() -> list[dict[str, Any]]:
    """Return a snapshot of all active jobs (newest last)."""
    with _LOCK:
        return [deepcopy(job) for job in _JOBS.values()]


def clear_scan_jobs() -> None:
    """Test helper; runtime hosts keep jobs in memory only."""

    with _LOCK:
        _JOBS.clear()
