"""Core data types for the corpus engine.

These types flow through the forge pipeline:

    raw dict  →  CorpusItem  →  (scrub/dedup/gate/normalize)  →  CorpusItem
                                                                  ↓
                                              CorpusReport { real, synthetic, coverage, splits }

Everything here is a plain pydantic model so it serializes cleanly to JSON
and stays free of any framework coupling.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Provenance(str, Enum):
    """Where a corpus item came from."""

    REAL = "real"  # pulled verbatim from the connector
    SYNTHETIC = "synthetic"  # generated to fill a coverage gap
    GOLDEN = "golden"  # captured from a human override in the flywheel


class CorpusItem(BaseModel):
    """A single training/eval unit flowing through the forge."""

    id: str
    content: str
    category: str = "uncategorized"
    channel: str = "unknown"
    quality_score: float = 0.0  # 0-5, assigned by the quality gate
    provenance: Provenance = Provenance.REAL
    metadata: dict[str, Any] = Field(default_factory=dict)
    # transformation trace — which forge stages touched this item
    trace: list[str] = Field(default_factory=list)

    def with_trace(self, stage: str, **updates: Any) -> CorpusItem:
        """Return a copy with a stage recorded and arbitrary fields updated."""
        data = self.model_copy(update=updates)
        data.trace = [*self.trace, stage]
        return data


class CategoryGap(BaseModel):
    """A coverage gap the synthesizer should fill."""

    category: str
    current_count: int
    target_count: int

    @property
    def shortfall(self) -> int:
        return max(self.target_count - self.current_count, 0)


class ConceptGap(BaseModel):
    """A coverage gap measured over ontology concepts (see ontology module)."""

    concept: str
    current_count: int
    target_count: int

    @property
    def shortfall(self) -> int:
        return max(self.target_count - self.current_count, 0)


class CoverageReport(BaseModel):
    """Per-category distribution + identified gaps."""

    category_counts: dict[str, int]
    target_per_category: int
    gaps: list[CategoryGap] = Field(default_factory=list)
    diversity_index: float = 0.0  # 0-1, normalized Shannon entropy
    # None = ontology layer not in play for this run; only serialized when set
    concept_counts: dict[str, int] | None = None
    concept_gaps: list[ConceptGap] | None = None

    @property
    def total(self) -> int:
        return sum(self.category_counts.values())

    def identify_gaps(self) -> list[CategoryGap]:
        """Recompute gaps from current counts (also stored eagerly)."""
        self.gaps = [
            CategoryGap(
                category=cat,
                current_count=count,
                target_count=self.target_per_category,
            )
            for cat, count in self.category_counts.items()
            if count < self.target_per_category
        ]
        return self.gaps


class CorpusSplit(BaseModel):
    """A train/eval/test slice of the corpus.

    The provenance counts are derived from ``items`` rather than passed in, so
    a split can never *claim* to be all-real while holding synthetic rows: the
    report reads exactly what the split holds. ``real`` is the denominator an
    eval number has to be read against — a synthetic item in ``eval``/``test``
    measures the synthesizer, not the model.
    """

    name: str
    items: list[CorpusItem]

    @property
    def size(self) -> int:
        return len(self.items)

    @property
    def real(self) -> int:
        """Items with :attr:`Provenance.REAL` (the only honest denominator)."""
        return sum(1 for i in self.items if i.provenance == Provenance.REAL)

    @property
    def synthetic(self) -> int:
        return sum(1 for i in self.items if i.provenance == Provenance.SYNTHETIC)

    @property
    def golden(self) -> int:
        return sum(1 for i in self.items if i.provenance == Provenance.GOLDEN)

    @property
    def trusted(self) -> bool:
        """True when the split is free of generated items.

        Only a trusted split supports a claim about model quality; an
        untrusted one is still usable (e.g. a demo), but callers that report
        metrics must say which kind they were given.
        """
        return self.synthetic == 0 and self.size > 0


class CorpusReport(BaseModel):
    """The deliverable an FDE hands the customer after forging.

    This object is what makes the forge auditable: it states exactly how many
    real vs synthetic items exist, where the gaps were, and how the data was
    split. It renders to HTML via :mod:`fde_scope.corpus.report`.
    """

    total: int
    real: int
    synthetic: int
    golden: int = 0
    coverage: CoverageReport
    train: CorpusSplit
    eval: CorpusSplit  # noqa: A003 — shadows builtin, kept for domain clarity
    test: CorpusSplit
    dropped: int = 0  # items removed by dedup / quality gate
    pii_entities_masked: int = 0

    @property
    def heldout_real(self) -> int:
        """Real items across ``eval`` + ``test`` — the honest held-out count.

        Zero means every number measured on this split measures the
        synthesizer, not the model, and no accuracy claim can be made.
        """
        return self.eval.real + self.test.real

    @property
    def heldout_trusted(self) -> bool:
        """True when both held-out splits are free of generated items."""
        return self.eval.trusted and self.test.trusted

    @property
    def synthetic_ratio(self) -> float:
        """Share of the whole corpus that was generated (0.0 when empty)."""
        return self.synthetic / self.total if self.total else 0.0
