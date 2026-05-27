"""内存导入任务进度（单机）。"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Optional

_lock = threading.Lock()
_jobs: dict[str, "ImportJob"] = {}


@dataclass
class ImportJobStep:
    id: str
    label: str
    status: str = "pending"  # pending | running | done | error
    detail: str = ""


@dataclass
class ImportJob:
    job_id: str
    status: str = "pending"  # pending | running | completed | failed
    steps: list[ImportJobStep] = field(default_factory=list)
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "steps": [
                {"id": s.id, "label": s.label, "status": s.status, "detail": s.detail} for s in self.steps
            ],
            "result": self.result,
            "error": self.error,
        }


def create_import_job(step_labels: list[tuple[str, str]]) -> ImportJob:
    job_id = f"imp_{uuid.uuid4().hex[:12]}"
    job = ImportJob(
        job_id=job_id,
        steps=[ImportJobStep(id=sid, label=label) for sid, label in step_labels],
    )
    with _lock:
        _jobs[job_id] = job
    return job


def get_import_job(job_id: str) -> Optional[ImportJob]:
    with _lock:
        return _jobs.get(job_id)


def _find_step(job: ImportJob, step_id: str) -> Optional[ImportJobStep]:
    for s in job.steps:
        if s.id == step_id:
            return s
    return None


def job_progress_callback(job_id: str) -> Callable[[str, str, str], None]:
    def _cb(step_id: str, status: str, detail: str = "") -> None:
        with _lock:
            job = _jobs.get(job_id)
            if not job:
                return
            job.updated_at = datetime.now(UTC)
            if job.status == "pending":
                job.status = "running"
            step = _find_step(job, step_id)
            if step:
                step.status = status
                step.detail = detail

    return _cb


def complete_job(job_id: str, *, result: Optional[dict[str, Any]] = None, error: Optional[str] = None) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.updated_at = datetime.now(UTC)
        if error:
            job.status = "failed"
            job.error = error
        else:
            job.status = "completed"
            job.result = result
            for s in job.steps:
                if s.status in ("pending", "running"):
                    s.status = "done"
