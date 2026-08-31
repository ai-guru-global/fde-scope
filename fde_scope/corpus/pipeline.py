"""The corpus forge — FDE Scope's core engine.

This wires the stages (normalize → scrub → dedup → gate) into a plain Python
function chain, then layers coverage analysis + targeted synthesis + split on
top. The result is a :class:`CorpusReport` — the auditable deliverable.

Why not AgentScope's ``SequentialPipeline``? Because it doesn't exist in 2.0
(see docs/agentscope_api_mapping.md). The honest v0 is a deterministic
function pipeline; the LLM v1 swaps stage internals, not the orchestration.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from .agents import QualityGate, SchemaNormalizer, build_stages
from .coverage_analyzer import CoverageAnalyzer
from .synthesizer import CorpusSynthesizer
from .types import CorpusItem, CorpusReport, CorpusSplit, CoverageReport, Provenance

if TYPE_CHECKING:
    from fde_scope.config import CorpusConfig
    from fde_scope.connectors import DataConnector
    from fde_scope.llm import MiMoClient


class CorpusForge:
    """One-call forge: raw connector rows → a CorpusReport."""

    def __init__(self, config: CorpusConfig, llm: MiMoClient | None = None) -> None:
        self.config = config
        self.normalizer = SchemaNormalizer(
            text_field=config.text_field,
            category_field=config.category_field,
            id_field=config.id_field,
        )
        self.scrubber, self.deduper, self.gate = build_stages(config, llm=llm)
        self.analyzer = CoverageAnalyzer(config.min_samples_per_category)
        self.synthesizer = CorpusSynthesizer(
            quality_gate=QualityGate(config.synth_quality_min_score, llm=llm),
            llm=llm,
        )

    # -- the main entry point ---------------------------------------------------
    def forge_rows(self, rows: Iterable[dict]) -> CorpusReport:
        """Forge from an iterable of raw connector rows."""
        return self._forge(list(rows))

    def forge_connector(self, connector: DataConnector) -> CorpusReport:
        """Forge from a connected data source (streams all rows)."""
        rows: list[dict] = []
        for batch in connector.stream():
            rows.extend(batch)
        return self._forge(rows)

    def _forge(self, rows: list[dict]) -> CorpusReport:
        # Stages are long-lived; zero their counters so a reused forge reports
        # per-run numbers instead of accumulating across forge calls.
        self.scrubber.masked_count = 0
        self.deduper.dropped_count = 0
        self.gate.dropped_count = 0

        # Step 0: normalize raw rows into CorpusItems
        items = self.normalizer(rows)
        if not items:
            return self._empty_report()

        # Step 1: clean — scrub → dedup → gate
        items = self.scrubber(items)
        items = self.deduper(items)
        items = self.gate(items)
        real_items = items

        # Step 2: coverage analysis on the cleaned real data
        coverage = self.analyzer.analyze(real_items)

        # Step 3: targeted synthesis to fill the gaps
        gaps = coverage.identify_gaps()
        synthetic = self.synthesizer.fill_gaps(real_items, gaps, per_gap_cap=self.config.synth_per_gap)

        # Step 4: merge + split
        full = real_items + synthetic
        train, eval_split, test = self._split(full, self.config.split_ratios)

        dropped = self.deduper.dropped_count + self.gate.dropped_count
        return CorpusReport(
            total=len(full),
            real=sum(1 for i in full if i.provenance == Provenance.REAL),
            synthetic=sum(1 for i in full if i.provenance == Provenance.SYNTHETIC),
            golden=sum(1 for i in full if i.provenance == Provenance.GOLDEN),
            coverage=coverage,
            train=train,
            eval=eval_split,
            test=test,
            dropped=dropped,
            pii_entities_masked=self.scrubber.masked_count,
        )

    # -- helpers ----------------------------------------------------------------
    def _split(
        self, items: list[CorpusItem], ratios: tuple[float, float, float]
    ) -> tuple[CorpusSplit, CorpusSplit, CorpusSplit]:
        """Deterministic, stratification-light split.

        v0 is a stable shuffle (seeded) + ratio cut. Real stratification by
        category is a roadmap item; for now we keep the split reproducible.
        """
        import random

        r = list(items)
        rng = random.Random(0)
        rng.shuffle(r)
        n = len(r)
        t = max(int(n * ratios[0]), 0)
        e = max(int(n * ratios[1]), 0)
        train = CorpusSplit(name="train", items=r[:t])
        eval_split = CorpusSplit(name="eval", items=r[t : t + e])
        test = CorpusSplit(name="test", items=r[t + e :])
        return train, eval_split, test

    def _empty_report(self) -> CorpusReport:
        empty_cov = CoverageReport(
            category_counts={}, target_per_category=self.config.min_samples_per_category
        )
        return CorpusReport(
            total=0,
            real=0,
            synthetic=0,
            coverage=empty_cov,
            train=CorpusSplit(name="train", items=[]),
            eval=CorpusSplit(name="eval", items=[]),
            test=CorpusSplit(name="test", items=[]),
        )


# ---------------------------------------------------------------------------
# Serialization helpers (used by the CLI)
# ---------------------------------------------------------------------------
def save_report_json(report: CorpusReport, path: str | Path) -> Path:
    """Write a CorpusReport to JSON for downstream tooling."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    return p


def load_items_jsonl(path: str | Path) -> list[CorpusItem]:
    """Load CorpusItems from a JSONL file (e.g. a saved split)."""
    out: list[CorpusItem] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(CorpusItem.model_validate_json(line))
    return out


def save_items_jsonl(items: list[CorpusItem], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        for item in items:
            fh.write(item.model_dump_json() + "\n")
    return p
