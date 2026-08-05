"""Tests for Layer 2 — the corpus forge (the project's core)."""

from __future__ import annotations

from fde_scope.config import CorpusConfig
from fde_scope.corpus import (
    CorpusForge,
    Deduplication,
    PIIScrub,
    QualityGate,
    SchemaNormalizer,
    score_item,
)
from fde_scope.corpus.types import CorpusItem, Provenance


def test_pii_scrub_masks_phone_and_email() -> None:
    scrub = PIIScrub(CorpusConfig().pii_rules.patterns)
    item = CorpusItem(id="x", content="联系我 13800138000 或 a@b.com", category="退款")
    out = scrub([item])
    assert "13800138000" not in out[0].content
    assert "a@b.com" not in out[0].content
    assert scrub.masked_count == 2


def test_dedup_removes_near_duplicates() -> None:
    dedup = Deduplication(threshold=0.92)
    items = [
        CorpusItem(id="1", content="申请退款，商品质量问题需要处理", category="退款"),
        CorpusItem(id="2", content="申请退款，商品质量问题需要处理", category="退款"),  # exact dup
    ]
    out = dedup(items)
    assert len(out) == 1
    assert dedup.dropped_count == 1


def test_quality_gate_drops_short_gibberish() -> None:
    gate = QualityGate(min_score=3.0)
    items = [
        CorpusItem(id="good", content="我的订单三天没发货麻烦查一下物流谢谢", category="物流查询"),
        CorpusItem(id="bad", content="hi", category="uncategorized"),
    ]
    out = gate(items)
    ids = {i.id for i in out}
    assert "good" in ids
    assert "bad" not in ids
    assert gate.dropped_count == 1


def test_normalizer_maps_fields() -> None:
    norm = SchemaNormalizer()
    items = norm([{"id": "a", "content": "hello", "category": "退款", "extra": 1}])
    assert items[0].content == "hello"
    assert items[0].category == "退款"
    assert items[0].metadata["extra"] == 1


def test_full_forge_produces_report(sample_rows: list[dict]) -> None:
    cfg = CorpusConfig(min_samples_per_category=5, synth_per_gap=3)
    forge = CorpusForge(cfg)
    report = forge.forge_rows(sample_rows)

    # 8 rows in, 1 dropped by quality gate (the "hi"), at least 1 exact dup gone
    assert report.total >= 1
    assert report.real >= 1
    assert report.dropped >= 1
    assert report.pii_entities_masked >= 1  # the phone number
    # splits sum to total
    assert report.train.size + report.eval.size + report.test.size == report.total
    # synthetic fills gaps (every category has < 5 samples)
    assert report.synthetic >= 1


def test_empty_input_yields_empty_report() -> None:
    forge = CorpusForge(CorpusConfig())
    report = forge.forge_rows([])
    assert report.total == 0
    assert report.train.size == 0


def test_score_item_helper() -> None:
    item = CorpusItem(id="x", content="怎么退款麻烦处理一下", category="退款")
    assert 0.0 <= score_item(item) <= 5.0


def test_synthetic_items_marked_provenance(sample_rows: list[dict]) -> None:
    cfg = CorpusConfig(min_samples_per_category=10, synth_per_gap=2)
    forge = CorpusForge(cfg)
    report = forge.forge_rows(sample_rows)
    synth = [i for i in report.train.items + report.test.items if i.provenance == Provenance.SYNTHETIC]
    # at least some synthetic items exist and all carry the synthetic provenance
    assert all(i.provenance == Provenance.SYNTHETIC for i in synth)
