"""The data flywheel engine — online feedback → corpus → retrain → redeploy.

STATUS: rule-based v0. The engine consumes conceptual events (see
:mod:`event_mapping`) and routes them through :class:`Collector` into a
:class:`CorpusStore`. A scheduler (see :mod:`retrain_scheduler`) periodically
flushes the store into an incremental retrain.

AgentScope 2.0 reality: there is no ``EventSystem.on(name, cb)``. Real
wiring iterates ``agent.reply_stream()`` and dispatches each typed event
through :meth:`DataFlywheel.handle_concept_event` (the translation table
lives in event_mapping). In v0 we accept concept events directly so the
flywheel is testable without a live agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .collectors import Collector, CorpusStore
from .event_mapping import strategy_for


def payload_from_event(event: object) -> dict:
    """Build a collector-ready payload from a live 2.0 event object.

    Collectors read ``id``/``ticket``/``input`` keys (see
    :meth:`Collector._item_from_payload`); a raw ``{"event": event}`` payload
    would yield empty content and the shared ``fw-<quality>`` fallback ID.
    Here the event's own ``id`` is used when present, otherwise a uuid
    guarantees uniqueness, and the first non-empty text-ish attribute becomes
    the sample content. The raw event is kept under ``event`` for provenance.
    """
    payload: dict = {"event": event}
    event_id = getattr(event, "id", None)
    payload["id"] = str(event_id) if event_id else f"fw-{uuid4().hex[:12]}"
    for attr in ("ticket", "input", "content", "message"):
        value = getattr(event, attr, None)
        if value:
            payload["input"] = str(value)
            break
    return payload


@dataclass
class FlywheelStats:
    collected: int = 0
    golden: int = 0
    labeling_queued: int = 0
    edge_cases: int = 0
    failures: int = 0
    retrain_runs: int = 0


class DataFlywheel:
    """Wire runtime events into a self-improving corpus loop."""

    def __init__(self) -> None:
        self.store = CorpusStore()
        self.collector = Collector(self.store)
        self.stats = FlywheelStats()

    # -- the conceptual event surface (v0) --------------------------------------
    def handle_concept_event(self, concept: str, payload: dict) -> bool:
        """Apply the mapped collection strategy for a concept event.

        Returns True if the event was handled. Unknown concepts are ignored
        rather than raising — a noisy event stream must not crash the wheel.
        """
        strategy = strategy_for(concept)
        if strategy is None:
            return False
        item = self.collector.dispatch(strategy, payload)
        if item is None:
            return False
        self._bump_stats(strategy)
        return True

    # -- live AgentScope wiring (lazy) -----------------------------------------
    def attach_to_stream(self, agent) -> None:  # pragma: no cover — runtime path
        """Subscribe to a real agent's ``reply_stream()`` event generator.

        Iterates the async event stream, resolves each typed 2.0 event to a
        concept via :func:`mapping_for_event` (which disambiguates shared
        event classes by payload attributes), and dispatches a payload built
        by :func:`payload_from_event`. Requires the optional agentscope extra.
        """
        import asyncio

        from fde_scope.flywheel.event_mapping import mapping_for_event

        async def _drain() -> None:
            async for event in agent.reply_stream():
                mapping = mapping_for_event(event)
                if mapping is None:
                    continue
                self.handle_concept_event(mapping.concept, payload_from_event(event))

        asyncio.ensure_future(_drain())  # noqa: RUF006

    # -- stats ------------------------------------------------------------------
    def _bump_stats(self, strategy: str) -> None:
        self.stats.collected += 1
        if strategy == "collect_as_golden":
            self.stats.golden += 1
        elif strategy == "collect_for_labeling":
            self.stats.labeling_queued += 1
        elif strategy == "collect_as_edge_case":
            self.stats.edge_cases += 1
        elif strategy == "collect_as_failure":
            self.stats.failures += 1

    def snapshot(self) -> dict:
        return {
            "collected": self.stats.collected,
            "golden": self.stats.golden,
            "labeling_queued": self.stats.labeling_queued,
            "edge_cases": self.stats.edge_cases,
            "failures": self.stats.failures,
            "retrain_runs": self.stats.retrain_runs,
            "store_total": self.store.total,
        }
