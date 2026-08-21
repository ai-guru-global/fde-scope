"""Tests for Layer 5 — flywheel event mapping + collection."""

from __future__ import annotations

from fde_scope.flywheel import (
    MAPPINGS,
    DataFlywheel,
    RetrainScheduler,
    all_concepts,
    mapping_for_event,
    real_event_for,
    strategy_for,
)
from fde_scope.flywheel.engine import payload_from_event


class ExceedMaxItersEvent:
    """Stand-in for the real 2.0 event (name is what mapping matches on)."""

    def __init__(self, id: str | None = None, content: str = "", timed_out: bool = False) -> None:
        self.id = id
        self.content = content
        self.timed_out = timed_out


class ToolResultEndEvent:
    def __init__(self, id: str | None = None, content: str = "", error: str | None = None) -> None:
        self.id = id
        self.content = content
        self.error = error


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


def test_corpus_store_add_appends_exactly_once() -> None:
    """Regression: add() used to double-write (getattr + if/elif)."""
    from fde_scope.corpus.types import CorpusItem
    from fde_scope.flywheel.collectors import CorpusStore

    store = CorpusStore()
    item = CorpusItem(id="x", content="hi", category="c")
    store.add(item, bucket="labeling_queue")
    assert len(store.labeling_queue) == 1  # not 2
    assert store.total == 1

    store.add(item, bucket="edge_cases")
    assert len(store.edge_cases) == 1
    assert store.total == 2

    # default bucket
    store.add(item)
    assert len(store.accepted) == 1
    assert store.total == 3

    # unknown bucket raises
    import pytest

    with pytest.raises(ValueError):
        store.add(item, bucket="nonsense")


def test_retrain_scheduler_threshold() -> None:
    sched = RetrainScheduler()
    job = sched.jobs[0]  # weekly incremental, min 200
    assert sched.should_run(job, 150) is False
    assert sched.should_run(job, 250) is True


def test_mapping_for_event_disambiguates_shared_event_class() -> None:
    """Regression: session_timeout and low_confidence share ExceedMaxItersEvent;
    first-match-wins on the class name alone starved session_timeout forever."""
    timed_out = mapping_for_event(ExceedMaxItersEvent(timed_out=True))
    assert timed_out is not None
    assert timed_out.concept == "agent.session_timeout"

    fallback = mapping_for_event(ExceedMaxItersEvent(timed_out=False))
    assert fallback is not None
    assert fallback.concept == "agent.low_confidence"


def test_mapping_for_event_tool_error_requires_error_state() -> None:
    """Regression: ToolResultEndEvent fires for every tool call — only an
    errored result is an edge case."""
    errored = mapping_for_event(ToolResultEndEvent(error="boom"))
    assert errored is not None
    assert errored.concept == "agent.tool_error"

    # a normal, successful tool call must not be collected at all
    assert mapping_for_event(ToolResultEndEvent(error=None)) is None


def test_payload_from_event_extracts_content_and_unique_ids() -> None:
    """Regression: _drain used to dispatch {"event": event}, so collectors saw
    no id/ticket/input → empty content and a shared fw-<quality> fallback ID."""
    payload = payload_from_event(ExceedMaxItersEvent(id="evt-9", content="用户投诉物流"))
    assert payload["id"] == "evt-9"
    assert payload["input"] == "用户投诉物流"
    assert payload["event"] is not None

    # no event id → uuid fallback, unique across events
    p1 = payload_from_event(ToolResultEndEvent(content="tool failed"))
    p2 = payload_from_event(ToolResultEndEvent(content="tool failed"))
    assert p1["id"] != p2["id"]
    assert p1["input"] == "tool failed"


def test_live_stream_path_collects_non_empty_unique_samples() -> None:
    """End-to-end over the live path's building blocks: payload_from_event →
    handle_concept_event produces usable corpus items."""
    wheel = DataFlywheel()
    events = [ToolResultEndEvent(content=f"tool call {i} failed", error="boom") for i in range(3)]
    for e in events:
        mapping = mapping_for_event(e)
        assert mapping is not None
        assert wheel.handle_concept_event(mapping.concept, payload_from_event(e))

    assert len(wheel.store.edge_cases) == 3
    contents = [item.content for item in wheel.store.edge_cases]
    ids = [item.id for item in wheel.store.edge_cases]
    assert all(contents)
    assert len(set(ids)) == 3
