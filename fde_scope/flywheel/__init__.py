"""Layer 5 — the data flywheel.

Closed loop: online feedback → corpus回流 → retrain → redeploy. The flywheel
is what turns a one-shot deploy into a continuously improving system — the
difference between "we shipped a demo" and "we shipped a product".

Concept events (``agent.low_confidence`` etc.) are domain names; the
mapping to real AgentScope 2.0 streaming event types lives in
:mod:`event_mapping`. All agentscope imports are lazy.
"""

from .collectors import Collector, CorpusStore
from .engine import DataFlywheel, FlywheelStats
from .event_mapping import (
    MAPPINGS,
    all_concepts,
    mapping_for_event,
    real_event_for,
    strategy_for,
)
from .retrain_scheduler import DEFAULT_JOBS, RetrainJob, RetrainScheduler

__all__ = [
    "DataFlywheel",
    "FlywheelStats",
    "Collector",
    "CorpusStore",
    "MAPPINGS",
    "strategy_for",
    "real_event_for",
    "mapping_for_event",
    "all_concepts",
    "RetrainScheduler",
    "RetrainJob",
    "DEFAULT_JOBS",
]
