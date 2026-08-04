"""Tests for the coverage analyzer + synthesizer."""

from __future__ import annotations

from fde_scope.corpus import CorpusSynthesizer, CoverageAnalyzer
from fde_scope.corpus.types import CategoryGap, CorpusItem


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
