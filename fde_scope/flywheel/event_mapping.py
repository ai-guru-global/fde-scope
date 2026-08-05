"""Concept-event → real AgentScope 2.0 event mapping.

STATUS: reference table. This is the single source of truth that translates
the *conceptual* flywheel events ("a human overrode the agent", "the agent
was low-confidence") into the *actual* 2.0 streaming event types emitted by
``agent.reply_stream()``.

Why this matters: the design doc used a fictional ``EventSystem.on(
"agent.low_confidence", ...)`` pub/sub API. In 2.0 there is no such API —
events are consumed by iterating the ``reply_stream()`` async generator and
matching on typed event classes. This module documents that mapping so the
flywheel can wire real listeners without guessing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventMapping:
    """One row of the concept→real-event table."""

    concept: str  # the flywheel's domain name for it
    real_event_class: str  # the actual 2.0 event type (string for lazy import)
    collection_strategy: str  # how the flywheel treats it
    quality_on_capture: float  # quality score assigned to the captured sample


# The authoritative mapping. Verify against agentscope.event when wiring live.
MAPPINGS: list[EventMapping] = [
    EventMapping(
        concept="agent.low_confidence",
        real_event_class="ExceedMaxItersEvent",
        collection_strategy="collect_for_labeling",
        quality_on_capture=2.0,
    ),
    EventMapping(
        concept="agent.human_override",
        real_event_class="RequireUserConfirmEvent",
        collection_strategy="collect_as_golden",
        quality_on_capture=5.0,
    ),
    EventMapping(
        concept="agent.tool_error",
        real_event_class="ToolResultEndEvent",
        collection_strategy="collect_as_edge_case",
        quality_on_capture=3.0,
    ),
    EventMapping(
        concept="agent.session_timeout",
        real_event_class="ExceedMaxItersEvent",
        collection_strategy="collect_as_failure",
        quality_on_capture=1.0,
    ),
]


def strategy_for(concept: str) -> str | None:
    """Look up the collection strategy for a concept event."""
    for m in MAPPINGS:
        if m.concept == concept:
            return m.collection_strategy
    return None


def all_concepts() -> list[str]:
    return [m.concept for m in MAPPINGS]


def real_event_for(concept: str) -> str | None:
    for m in MAPPINGS:
        if m.concept == concept:
            return m.real_event_class
    return None
