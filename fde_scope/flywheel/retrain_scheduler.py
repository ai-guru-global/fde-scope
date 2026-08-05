"""Retrain scheduler — periodic flush of flywheel-collected samples.

STATUS: stub interface. Defines the cron schedule and the threshold logic an
FDE tunes ("retrain weekly if ≥ N new samples"), but the actual fine-tune
submission is a roadmap item (it depends on a model-training backend).

The schedule mirrors the design doc: weekly incremental retrain + monthly
full eval. Both are recorded as descriptors the runtime can hand to any
cron/scheduler (APScheduler, Kubernetes CronJob, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass


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
    """Decide whether a retrain job should fire given current accumulation."""

    def __init__(self, jobs: list[RetrainJob] | None = None) -> None:
        self.jobs = jobs or list(DEFAULT_JOBS)

    def should_run(self, job: RetrainJob, new_sample_count: int) -> bool:
        """Threshold gate — don't burn compute on tiny accumulations."""
        return new_sample_count >= job.min_new_samples

    def submit(self, job: RetrainJob, samples) -> dict:
        """Submit a retrain (stub).

        Returns a descriptor; the real submission targets the model-training
        backend chosen at deploy time.
        """
        return {
            "job": job.name,
            "kind": job.kind,
            "sample_count": len(samples) if hasattr(samples, "__len__") else None,
            "status": "submitted (stub — no training backend wired)",
        }
