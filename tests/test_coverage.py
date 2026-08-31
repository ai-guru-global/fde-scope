"""Tests for the coverage analyzer + synthesizer."""

from __future__ import annotations

from pathlib import Path

from fde_scope.corpus import CorpusSynthesizer, CoverageAnalyzer
from fde_scope.corpus.pipeline import save_report_json
from fde_scope.corpus.types import (
    CategoryGap,
    ConceptGap,
    CorpusItem,
    CorpusReport,
    CorpusSplit,
    CoverageReport,
)


def test_coverage_analyzer_detects_gaps() -> None:
    items = [
        CorpusItem(id="1", content="a b c d e", category="退款"),
        CorpusItem(id="2", content="b c d e f", category="退款"),
        CorpusItem(id="3", content="c d e f g", category="物流"),
    ]
    report = CoverageAnalyzer(min_samples_per_category=5).analyze(items)
    assert set(report.category_counts) == {"退款", "物流"}
    assert len(report.gaps) == 2  # both under 5
    assert report.diversity_index > 0.0


def test_diversity_single_category_is_zero() -> None:
    items = [CorpusItem(id=str(i), content="x" * 20, category="退款") for i in range(5)]
    report = CoverageAnalyzer(min_samples_per_category=10).analyze(items)
    assert report.diversity_index == 0.0


def test_synthesizer_fills_gaps() -> None:
    seeds = [CorpusItem(id="s1", content="申请退款，商品质量问题需要处理一下谢谢", category="退款")]
    gaps = [CategoryGap(category="退款", current_count=1, target_count=5)]
    synth = CorpusSynthesizer()
    out = synth.fill_gaps(seeds, gaps, per_gap_cap=3)
    assert len(out) == 3
    assert all(i.category == "退款" for i in out)


def test_synthesizer_no_gaps_returns_empty() -> None:
    synth = CorpusSynthesizer()
    assert synth.fill_gaps([], []) == []


def test_synthesizer_never_exceeds_gap_shortfall() -> None:
    """per_gap_cap bounds the shortfall — a 2-item gap must not get 50 items."""
    seeds = [CorpusItem(id="s1", content="申请退款，商品质量问题需要处理一下谢谢", category="退款")]
    gaps = [CategoryGap(category="退款", current_count=3, target_count=5)]  # shortfall 2
    out = CorpusSynthesizer().fill_gaps(seeds, gaps, per_gap_cap=50)
    assert 0 < len(out) <= 2


def test_synthesizer_output_is_deduplicated() -> None:
    """Synthetic items bypass the forge's dedup stage, so the synthesizer
    must not emit duplicates itself (they could leak across train/test)."""
    seeds = [CorpusItem(id="s1", content="申请退款，商品质量问题需要处理一下谢谢", category="退款")]
    gaps = [CategoryGap(category="退款", current_count=1, target_count=30)]
    out = CorpusSynthesizer().fill_gaps(seeds, gaps, per_gap_cap=20)
    contents = [i.content for i in out]
    assert len(contents) == len(set(contents))


def test_synthesizer_trace_records_actual_strategy() -> None:
    seeds = [CorpusItem(id="s1", content="申请退款，商品质量问题需要处理一下谢谢", category="退款")]
    gaps = [CategoryGap(category="退款", current_count=1, target_count=5)]
    synth = CorpusSynthesizer(strategies=["emotion_escalation"])
    out = synth.fill_gaps(seeds, gaps, per_gap_cap=3)
    assert len(out) == 3
    assert all(i.trace == ["synthesize:emotion_escalation"] for i in out)


# -- P2.3 概念覆盖 ----------------------------------------------------------------


def test_concept_counts_populate_fields_and_gaps() -> None:
    items = [CorpusItem(id="1", content="a", category="退款")]
    report = CoverageAnalyzer(min_samples_per_category=2).analyze(
        items, concept_counts={"fde:cc-billing": 2, "fde:cc-outage": 1}
    )
    assert report.concept_counts == {"fde:cc-billing": 2, "fde:cc-outage": 1}
    assert report.concept_gaps == [ConceptGap(concept="fde:cc-outage", current_count=1, target_count=2)]


def test_concept_counts_none_leaves_fields_none_and_json_excludes() -> None:
    items = [CorpusItem(id="1", content="a", category="退款")]
    report = CoverageAnalyzer().analyze(items)
    assert report.concept_counts is None
    assert report.concept_gaps is None
    assert "concept_counts" not in report.model_dump_json(exclude_none=True)
    assert "concept_gaps" not in report.model_dump_json(exclude_none=True)


def test_save_report_json_excludes_none_concept_fields(tmp_path: Path) -> None:
    report = CorpusReport(
        total=1,
        real=1,
        synthetic=0,
        coverage=CoverageReport(category_counts={"退款": 1}, target_per_category=1),
        train=CorpusSplit(name="train", items=[]),
        eval=CorpusSplit(name="eval", items=[]),
        test=CorpusSplit(name="test", items=[]),
    )
    path = save_report_json(report, tmp_path / "r.json")
    text = path.read_text(encoding="utf-8")
    assert "concept_counts" not in text
    assert "concept_gaps" not in text
