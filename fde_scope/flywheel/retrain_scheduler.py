"""Retrain scheduler — periodic flush of flywheel-collected samples.

Defines the cron schedule and the threshold logic an FDE tunes ("retrain
weekly if ≥ N new samples"), and submits accepted runs to the configured
:class:`~fde_scope.flywheel.backends.TrainingBackend` (HTTP when the
``FDE_SCOPE_TRAINING_URL``/``FDE_SCOPE_TRAINING_TOKEN`` env vars are set,
otherwise an explicit noop — see :func:`get_training_backend`).

The schedule mirrors the design doc: weekly incremental retrain + monthly
full eval. Both are recorded as descriptors the runtime can hand to any
cron/scheduler (APScheduler, Kubernetes CronJob, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .backends import TrainingBackend, get_training_backend


@dataclass
class RetrainJob:
    """One scheduled retrain job descriptor."""

    name: str
    cron: str  # 5-field cron, local TZ
    min_new_samples: int  # skip the run if fewer new samples accumulated
    kind: str  # "incremental" | "full_eval"


DEFAULT_JOBS: list[RetrainJob] = [
    RetrainJob(
        name="weekly_incremental_retrain",
        cron="0 2 * * 1",  # every Monday 02:00
        min_new_samples=200,
        kind="incremental",
    ),
    RetrainJob(
        name="monthly_full_eval",
        cron="0 3 1 * *",  # 1st of the month 03:00
        min_new_samples=0,
        kind="full_eval",
    ),
]


class RetrainScheduler:
    """Decide whether a retrain job should fire, and submit it if so."""

    def __init__(
        self,
        jobs: list[RetrainJob] | None = None,
        backend: TrainingBackend | None = None,
    ) -> None:
        self.jobs = jobs or list(DEFAULT_JOBS)
        self.backend = backend or get_training_backend()

    def should_run(self, job: RetrainJob, new_sample_count: int) -> bool:
        """Threshold gate — don't burn compute on tiny accumulations."""
        return new_sample_count >= job.min_new_samples

    def build_job_spec(
        self,
        job: RetrainJob,
        samples,
        *,
        engagement_id: str | None = None,
        data_window: dict | None = None,
        trigger_reason: str | None = None,
    ) -> dict[str, Any]:
        """Serialize the trigger context into a backend-agnostic job spec.

        Sample payloads never cross the wire — only the count and the sample
        ids (when the items expose an ``id``), so corpus content stays local.
        """
        sample_ids: list[str] = []
        count = len(samples) if hasattr(samples, "__len__") else None
        if isinstance(samples, (list, tuple)):
            for item in samples:
                item_id = getattr(item, "id", None)
                if item_id is None and isinstance(item, dict):
                    item_id = item.get("id")
                if item_id is not None:
                    sample_ids.append(str(item_id))
        return {
            "job": job.name,
            "kind": job.kind,
            "cron": job.cron,
            "min_new_samples": job.min_new_samples,
            "sample_count": count,
            "sample_ids": sample_ids,
            "trigger": {
                "engagement_id": engagement_id,
                "data_window": data_window,
                "reason": trigger_reason,
            },
        }

    def submit(
        self,
        job: RetrainJob,
        samples,
        *,
        engagement_id: str | None = None,
        data_window: dict | None = None,
        trigger_reason: str | None = None,
    ) -> dict:
        """Submit a retrain to the configured training backend."""
        job_spec = self.build_job_spec(
            job,
            samples,
            engagement_id=engagement_id,
            data_window=data_window,
            trigger_reason=trigger_reason,
        )
        job_id = self.backend.submit(job_spec)
        return {
            "job": job.name,
            "kind": job.kind,
            "sample_count": job_spec["sample_count"],
            "job_id": job_id,
            "status": "submitted",
            "backend": self.backend.name,
        }

    def status(self, job_id: str) -> dict:
        """Query the backend for a submitted job's status."""
        return self.backend.status(job_id)

    def cancel(self, job_id: str) -> dict:
        """Cancel a submitted job on the backend."""
        return self.backend.cancel(job_id)
