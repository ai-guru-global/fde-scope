"""Flywheel collectors — turn runtime events into corpus samples.

Each collector maps one strategy (from :mod:`event_mapping`) to a concrete
action on the corpus store: append a golden sample, queue something for
labeling, record an edge case. The collectors are framework-neutral — they
operate on plain ``CorpusItem``-shaped payloads — so they're fully testable
without a running agent.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from fde_scope.corpus.types import CorpusItem, Provenance


@dataclass
class CorpusStore:
    """In-memory staging for flywheel-collected samples.

    A real deployment backs this with the tenant's vector collection; v0
    keeps it in memory so the flywheel is demonstrable end-to-end.
    """

    accepted: list[CorpusItem] = field(default_factory=list)
    labeling_queue: deque[CorpusItem] = field(default_factory=deque)
    edge_cases: list[CorpusItem] = field(default_factory=list)
    failures: list[CorpusItem] = field(default_factory=list)

    def add(self, item: CorpusItem, *, bucket: str = "accepted") -> None:
        getattr(self, bucket if bucket != "accepted" else "accepted").append(item)
        if bucket == "accepted":
            self.accepted.append(item)
        elif bucket == "labeling_queue":
            self.labeling_queue.append(item)
        elif bucket == "edge_cases":
            self.edge_cases.append(item)
        elif bucket == "failures":
            self.failures.append(item)

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.labeling_queue) + len(self.edge_cases) + len(self.failures)


class Collector:
    """Apply a collection strategy to an event payload."""

    def __init__(self, store: CorpusStore) -> None:
        self.store = store

    def dispatch(self, strategy: str, payload: dict) -> CorpusItem | None:
        """Route a payload to the right collector by strategy name."""
        fn = getattr(self, strategy, None)
        if fn is None:
            return None
        return fn(payload)

    # -- strategies (match event_mapping.collection_strategy) -------------------
    def collect_as_golden(self, payload: dict) -> CorpusItem:
        """A human override = the highest-quality labeled sample."""
        item = self._item_from_payload(payload, provenance=Provenance.GOLDEN, quality=5.0)
        self.store.accepted.append(item)
        return item

    def collect_for_labeling(self, payload: dict) -> CorpusItem:
        item = self._item_from_payload(payload, provenance=Provenance.REAL, quality=2.0)
        self.store.labeling_queue.append(item)
        return item

    def collect_as_edge_case(self, payload: dict) -> CorpusItem:
        item = self._item_from_payload(payload, provenance=Provenance.REAL, quality=3.0)
        self.store.edge_cases.append(item)
        return item

    def collect_as_failure(self, payload: dict) -> CorpusItem:
        item = self._item_from_payload(payload, provenance=Provenance.REAL, quality=1.0)
        self.store.failures.append(item)
        return item

    @staticmethod
    def _item_from_payload(payload: dict, *, provenance: Provenance, quality: float) -> CorpusItem:
        return CorpusItem(
            id=str(payload.get("id", f"fw-{quality}")),
            content=str(payload.get("ticket") or payload.get("input") or ""),
            category=str(payload.get("category", "uncategorized")),
            provenance=provenance,
            quality_score=quality,
            trace=[f"flywheel:{provenance.value}"],
            metadata={"human_response": payload.get("human_response")},
        )
