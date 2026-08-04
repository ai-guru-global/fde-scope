"""Tests for Layer 5 — flywheel event mapping + collection."""

from __future__ import annotations

from fde_scope.flywheel import (
    DataFlywheel,
    MAPPINGS,
    RetrainScheduler,
    all_concepts,
    real_event_for,
    strategy_for,
)


def test_event_mapping_covers_core_concepts() -> None:
    concepts = all_concepts()
    assert "agent.low_confidence" in concepts
    assert "agent.human_override" in concepts
    assert "agent.tool_error" in concepts
    # every mapping points at a real 2.0 event class
    for m in MAPPINGS:
        assert m.real_event_class.endswith("Event")
        assert m.collection_strategy.startswith("collect_")


def test_strategy_lookup() -> None:
    assert strategy_for("agent.human_override") == "collect_as_golden"
    assert strategy_for("agent.low_confidence") == "collect_for_labeling"
    assert strategy_for("unknown.concept") is None


def test_real_event_lookup() -> None:
    assert real_event_for("agent.human_override") == "RequireUserConfirmEvent"
    assert real_event_for("agent.low_confidence") == "ExceedMaxItersEvent"


def test_flywheel_collects_golden_on_override() -> None:
    wheel = DataFlywheel()
    handled = wheel.handle_concept_event(
        "agent.human_override",
        {"id": "evt-1", "ticket": "我要退款", "human_response": "好的，已为您办理", "category": "退款"},
    )
    assert handled
    snap = wheel.snapshot()
    assert snap["golden"] == 1
    assert snap["collected"] == 1


def test_flywheel_ignores_unknown_concept() -> None:
    wheel = DataFlywheel()
    assert wheel.handle_concept_event("agent.mystery", {}) is False
    assert wheel.snapshot()["collected"] == 0


def test_retrain_scheduler_threshold() -> None:
    sched = RetrainScheduler()
    job = sched.jobs[0]  # weekly incremental, min 200
    assert sched.should_run(job, 150) is False
    assert sched.should_run(job, 250) is True
