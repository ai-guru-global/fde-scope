"""Quality-gate facade.

The rule-based ``QualityGate`` stage lives in :mod:`fde_scope.corpus.agents`
(kept there so all forge stages share one module). This module re-exports it
under the path the architecture diagram promises, and adds a thin
``score_item`` helper for callers (e.g. the synthesizer) that want a score
without running the full gate.
"""

from __future__ import annotations

from .agents import QualityGate
from .types import CorpusItem

__all__ = ["QualityGate", "score_item"]


def score_item(item: CorpusItem) -> float:
    """Score a single item on the v0 rubric without dropping it."""
    return QualityGate._score(item)
