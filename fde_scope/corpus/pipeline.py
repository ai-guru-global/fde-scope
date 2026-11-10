"""The corpus forge — FDE Scope's core engine.

This wires the stages (normalize → scrub → dedup → gate) into a plain Python
function chain, then layers coverage analysis + targeted synthesis + split on
top. The result is a :class:`CorpusReport` — the auditable deliverable.

Why not AgentScope's ``SequentialPipeline``? Because it doesn't exist in 2.0
(see docs/agentscope_api_mapping.md). The honest v0 is a deterministic
function pipeline; the LLM v1 swaps stage internals, not the orchestration.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from ..fsutil import atomic_write_text
from ..logutil import get_logger
from ..ontology.extract import ConceptExtractor
from .agents import QualityGate, SchemaNormalizer, build_stages
from .coverage_analyzer import CoverageAnalyzer
from .synthesizer import CorpusSynthesizer
from .types import CorpusItem, CorpusReport, CorpusSplit, CoverageReport, Provenance

logger = get_logger("corpus.pipeline")

#: ``CorpusSynthesizer`` stamps ``channel`` with this value on items it makes
#: with no real seed rows (template-only). Kept as a module constant so the
#: pipeline and the synthesizer cannot drift apart on the marker.
_SEEDLESS_CHANNEL = "synthetic"

if TYPE_CHECKING:
    from fde_scope.config import CorpusConfig
    from fde_scope.connectors import DataConnector
    from fde_scope.llm import LLMClient
    from fde_scope.ontology.models import OntologySchema


class CorpusForge:
    """One-call forge: raw connector rows → a CorpusReport."""

    def __init__(
        self,
        config: CorpusConfig,
        llm: LLMClient | None = None,
        ontology: OntologySchema | None = None,
    ) -> None:
        self.config = config
        self._llm = llm
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
        self._extractor = ConceptExtractor(ontology) if ontology is not None else None

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
        logger.info("forge start: %d raw rows", len(rows))
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

        # Step 1.5: ontology concept annotation (no-op when no ontology loaded)
        concept_counts: dict[str, int] | None = None
        if self._extractor is not None:
            real_items, concept_counts = self._annotate(real_items)

        # Step 2: coverage analysis on the cleaned real data
        coverage = self.analyzer.analyze(real_items, concept_counts=concept_counts)

        # Step 3: targeted synthesis to fill the gaps
        gaps = coverage.identify_gaps()
        synthetic = self.synthesizer.fill_gaps(
            real_items,
            gaps,
            per_gap_cap=self.config.synth_per_gap,
            concept_gaps=coverage.concept_gaps if self._extractor is not None else None,
            extractor=self._extractor,
        )

        # Step 3.5: dedup across the merged corpus. Synthesis *follows* the
        # dedup stage, so without this second pass a generated item can repeat
        # a real one verbatim (a no-op mutation is common: 4 of the 7 openers
        # are "" and the rule path seeds from real text). Items are deduped
        # together so a surviving duplicate is the *real* row, never the copy.
        synthetic = self._dedup_against(real_items, synthetic)

        # Step 4: split. Real and generated items are assigned separately so
        # that eval/test can stay REAL-only (see ``_split``).
        train, eval_split, test = self._split(real_items, synthetic, self.config.split_ratios)

        dropped = self.deduper.dropped_count + self.gate.dropped_count
        full = real_items + synthetic
        logger.info(
            "forge done: %d items (%d real / %d synthetic), %d dropped, %d PII masked; "
            "held-out real=%d (eval %d real/%d, test %d real/%d)",
            len(full),
            len(real_items),
            len(synthetic),
            dropped,
            self.scrubber.masked_count,
            eval_split.real + test.real,
            eval_split.real,
            eval_split.size,
            test.real,
            test.size,
        )
        return CorpusReport(
            total=len(full),
            real=len(real_items),
            synthetic=len(synthetic),
            golden=sum(1 for i in full if i.provenance == Provenance.GOLDEN),
            coverage=coverage,
            train=train,
            eval=eval_split,
            test=test,
            dropped=dropped,
            pii_entities_masked=self.scrubber.masked_count,
        )

    # -- helpers ----------------------------------------------------------------
    def _annotate(self, items: list[CorpusItem]) -> tuple[list[CorpusItem], dict[str, int]]:
        """Annotate every item with ontology concepts (ancestors pre-merged)."""
        assert self._extractor is not None
        counts: Counter[str] = Counter()
        out: list[CorpusItem] = []
        for item in items:
            curies, source = self._extractor.annotate(item.content, llm=self._llm)
            counts.update(curies)
            out.append(
                item.with_trace(
                    f"annotate:{source}",
                    metadata={**item.metadata, "ontology_concepts": curies},
                )
            )
        return out, dict(counts)

    def _split(
        self,
        real_items: list[CorpusItem],
        synthetic: list[CorpusItem],
        ratios: tuple[float, float, float],
    ) -> tuple[CorpusSplit, CorpusSplit, CorpusSplit]:
        """Split with provenance-aware placement.

        **Real items are partitioned first, across all three splits**, using
        the configured ratios and a seeded shuffle (reproducible). Only then
        are synthetic items laid on top of ``train`` — and only when
        ``synth_in_train`` allows it. ``eval`` and ``test`` therefore hold
        *only* real (or golden) rows, which is the whole point: a held-out
        set containing generated text measures the synthesizer, not the
        model. The previous implementation shuffled the merged list, so eval
        and test were 95-100% synthetic on a real 20-row dump and 29-36% of
        their members had a near-duplicate in train.

        The trade-off is honest and stated in the report: a small site corpus
        yields a small (or empty) held-out set. That is the true measurement
        resolution, and the report exposes ``heldout_real`` so a customer can
        see it instead of being handed an inflated number.
        """
        import random

        rng = random.Random(0)
        real = list(real_items)
        rng.shuffle(real)
        n = len(real)
        t = max(int(n * ratios[0]), 0)
        e = max(int(n * ratios[1]), 0)
        # A real row that would land in train has priority over a held-out row:
        # otherwise a 1-row corpus puts its only real sample in eval, leaving
        # train as pure synthetic — the worst of both worlds (no real training
        # signal, and an untrusted eval). Below ~10 real rows the held-out set
        # shrinks to nothing anyway, so this only ever moves a row out of an
        # empty-because-too-small train.
        if n > 0 and t == 0:
            t = 1
        train_items = real[:t]
        eval_items = real[t : t + e]
        test_items = real[t + e :]

        if self.config.synth_in_train:
            train_items = [*train_items, *self._cap_seedless(synthetic)]

        return (
            CorpusSplit(name="train", items=train_items),
            CorpusSplit(name="eval", items=eval_items),
            CorpusSplit(name="test", items=test_items),
        )

    def _cap_seedless(self, synthetic: list[CorpusItem]) -> list[CorpusItem]:
        """Downsample template-only synthetic items to one per category.

        With no real seed rows the synthesizer emits ``_template(category)``
        variations, which are near-identical by construction: on an empty
        input the quickstart config used to yield 50 same-shape rows per
        category. Dedup cannot help (Jaccard on short texts falls under the
        threshold), so the duplicate is structural rather than textual. One
        exemplar per category is what the gap actually calls for — the rest
        is padding, and the synthesizer's own contract says it never pads.

        Seeded synthesis (``channel`` picked from the real seed) is left
        alone: it is real vocabulary, which is the reason to synthesize at
        all.
        """
        kept: list[CorpusItem] = []
        seen_seedless: set[str] = set()
        for item in synthetic:
            if item.channel == _SEEDLESS_CHANNEL:
                if item.category in seen_seedless:
                    continue
                seen_seedless.add(item.category)
            kept.append(item)
        if len(kept) != len(synthetic):
            self.deduper.dropped_count += len(synthetic) - len(kept)
        return kept

    def _dedup_against(self, real_items: list[CorpusItem], synthetic: list[CorpusItem]) -> list[CorpusItem]:
        """Drop synthetic items that duplicate a real one or an earlier synthetic.

        Runs the configured :class:`~fde_scope.corpus.agents.Deduplication`
        stage over ``real + synthetic`` in that order, returns only the
        synthetic survivors, and counts every drop in ``deduper.dropped_count``
        so ``CorpusReport.dropped`` keeps meaning "removed by dedup / gate".
        """
        merged = self.deduper([*real_items, *synthetic])
        return [i for i in merged if i.provenance == Provenance.SYNTHETIC]

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
    atomic_write_text(p, report.model_dump_json(indent=2, exclude_none=True))
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
    """Persist a split as JSONL. Scrubbed upstream, atomic on the way out."""
    payload = "".join(item.model_dump_json() + "\n" for item in items)
    atomic_write_text(Path(path), payload)
    return Path(path)
