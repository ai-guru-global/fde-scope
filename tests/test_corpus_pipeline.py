"""Tests for Layer 2 — the corpus forge (the project's core)."""

from __future__ import annotations

import json

from fde_scope.config import CorpusConfig
from fde_scope.corpus import (
    CorpusForge,
    Deduplication,
    PIIScrub,
    QualityGate,
    SchemaNormalizer,
    render_html,
    score_item,
)
from fde_scope.corpus.synthesizer import CorpusSynthesizer
from fde_scope.corpus.types import (
    ConceptGap,
    CorpusItem,
    CorpusReport,
    CorpusSplit,
    CoverageReport,
    Provenance,
)
from fde_scope.ontology.extract import ConceptExtractor
from fde_scope.ontology.models import OntologySchema


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
    synth = [
        i
        for i in report.train.items + report.eval.items + report.test.items
        if i.provenance == Provenance.SYNTHETIC
    ]
    # synthesis actually happened, and every synthetic item across all splits
    # (including eval) carries the synthetic provenance
    assert len(synth) >= 1
    assert len(synth) == report.synthetic
    assert all(i.provenance == Provenance.SYNTHETIC for i in synth)


def test_report_html_escapes_injected_category() -> None:
    """Category names are customer-controlled strings — they must not inject markup."""
    evil = '<script>alert("xss")</script>'
    report = CorpusReport(
        total=0,
        real=0,
        synthetic=0,
        coverage=CoverageReport(category_counts={evil: 1}, target_per_category=5),
        train=CorpusSplit(name="train", items=[]),
        eval=CorpusSplit(name="eval", items=[]),
        test=CorpusSplit(name="test", items=[]),
    )
    html = render_html(report)
    assert evil not in html
    assert "&lt;script&gt;" in html


def test_dedup_near_duplicates_use_token_jaccard() -> None:
    dedup = Deduplication(threshold=0.5)
    items = [
        CorpusItem(id="1", content="one two three four five", category="c"),
        # token Jaccard 4/6 ≈ 0.67 ≥ 0.5 → near-dup, dropped
        CorpusItem(id="2", content="one two three four six", category="c"),
        # token Jaccard 0.0 → kept (character-level ratios must not kill it)
        CorpusItem(id="3", content="seven eight nine ten eleven", category="c"),
    ]
    out = dedup(items)
    assert [i.id for i in out] == ["1", "3"]
    assert dedup.dropped_count == 1


def test_quality_gate_drops_pure_redaction_residue() -> None:
    gate = QualityGate(min_score=3.0)
    item = CorpusItem(id="r", content="[REDACTED]([PHONE]) [REDACTED]([EMAIL])", category="退款")
    assert gate([item]) == []
    assert gate.dropped_count == 1


def test_forge_reuse_resets_stage_counters(sample_rows: list[dict]) -> None:
    forge = CorpusForge(CorpusConfig(min_samples_per_category=5, synth_per_gap=3))
    first = forge.forge_rows(sample_rows)
    second = forge.forge_rows(sample_rows)
    assert first.dropped >= 1
    assert second.dropped == first.dropped
    assert second.pii_entities_masked == first.pii_entities_masked


# -- P2.4 ontology concept annotation -----------------------------------------


def _taxonomy() -> OntologySchema:
    from fde_scope.ontology.store import OntologyStore

    schema = OntologyStore().load_schema("fde-corpus-taxonomy")
    assert schema is not None, "builtin fde-corpus-taxonomy missing"
    return schema


def test_forge_without_ontology_report_untouched(sample_rows: list[dict]) -> None:
    """ontology=None keeps the report byte-shape identical to the legacy path."""
    forge = CorpusForge(CorpusConfig(min_samples_per_category=2, synth_per_gap=1))
    report = forge.forge_rows(sample_rows)
    data = json.loads(report.model_dump_json(exclude_none=True))
    assert "concept_counts" not in data["coverage"]
    assert "concept_gaps" not in data["coverage"]
    items = data["train"]["items"] + data["eval"]["items"] + data["test"]["items"]
    assert all("ontology_concepts" not in i["metadata"] for i in items)
    assert all(not any(t.startswith("annotate:") for t in i["trace"]) for i in items)


def test_forge_with_ontology_annotates_real_items(sample_rows: list[dict]) -> None:
    forge = CorpusForge(
        CorpusConfig(min_samples_per_category=2, synth_per_gap=1),
        ontology=_taxonomy(),
    )
    report = forge.forge_rows(sample_rows)
    real = [
        i
        for i in report.train.items + report.eval.items + report.test.items
        if i.provenance == Provenance.REAL
    ]
    assert real
    assert all("ontology_concepts" in i.metadata for i in real)
    assert all(any(t.startswith("annotate:") for t in i.trace) for i in real)

    refund = next(i for i in real if "fde:cc-billing-refund" in i.metadata["ontology_concepts"])
    assert "fde:cc-billing" in refund.metadata["ontology_concepts"]  # ancestor merged


def test_forge_with_ontology_populates_concept_coverage(sample_rows: list[dict]) -> None:
    forge = CorpusForge(
        CorpusConfig(min_samples_per_category=2, synth_per_gap=1),
        ontology=_taxonomy(),
    )
    report = forge.forge_rows(sample_rows)
    cov = report.coverage
    assert cov.concept_counts == {
        "fde:cc-logistics": 2,
        "fde:cc-billing": 2,
        "fde:cc-billing-refund": 2,
        "fde:cc-quality": 1,
    }
    assert cov.concept_gaps is not None
    assert {g.concept for g in cov.concept_gaps} == {"fde:cc-quality"}


# -- P2.5 concept-gap targeted synthesis ---------------------------------------


def _concept_extractor() -> ConceptExtractor:
    return ConceptExtractor(_taxonomy())


def _refund_seeds() -> list[CorpusItem]:
    return [
        CorpusItem(
            id="r1",
            content="申请退款，商品质量有问题，已经拍照留存。希望尽快处理。",
            category="退款",
            metadata={"ontology_concepts": ["fde:cc-billing", "fde:cc-billing-refund", "fde:cc-quality"]},
        ),
        CorpusItem(
            id="r2",
            content="退款拖了一周还没到账，质量问题要求赔偿，麻烦处理一下。",
            category="退款",
            metadata={"ontology_concepts": ["fde:cc-billing", "fde:cc-billing-refund", "fde:cc-quality"]},
        ),
        CorpusItem(
            id="r3",
            content="商家说退款了但我一直没收到钱，订单还没发货。",
            category="售后",
            metadata={"ontology_concepts": ["fde:cc-billing", "fde:cc-billing-refund"]},
        ),
    ]


def test_fill_gaps_concept_gap_synthesizes_anchored_items() -> None:
    gap = ConceptGap(concept="fde:cc-billing-refund", current_count=1, target_count=3)
    out = CorpusSynthesizer().fill_gaps(
        _refund_seeds(), [], concept_gaps=[gap], extractor=_concept_extractor()
    )
    assert len(out) == 2  # shortfall, no cap
    assert all(i.provenance == Provenance.SYNTHETIC for i in out)
    assert all("synthesize:concept" in i.trace for i in out)
    # concept + ancestors (ancestor order mirrors annotate)
    assert all(i.metadata["ontology_concepts"] == ["fde:cc-billing", "fde:cc-billing-refund"] for i in out)
    # category = mode of seed categories (退款 x2 beats 售后 x1)
    assert all(i.category == "退款" for i in out)
    assert all(i.content not in {s.content for s in _refund_seeds()} for i in out)


def test_fill_gaps_concept_gap_respects_per_gap_cap() -> None:
    gap = ConceptGap(concept="fde:cc-billing-refund", current_count=1, target_count=4)
    out = CorpusSynthesizer().fill_gaps(
        _refund_seeds(), [], concept_gaps=[gap], per_gap_cap=1, extractor=_concept_extractor()
    )
    assert len(out) == 1


def test_fill_gaps_concept_gap_without_seeds_skips() -> None:
    items = [CorpusItem(id="r1", content="你好，请问怎么修改收货地址？麻烦了。", category="订单修改")]
    gap = ConceptGap(concept="fde:cc-safety", current_count=0, target_count=3)
    out = CorpusSynthesizer().fill_gaps(items, [], concept_gaps=[gap], extractor=_concept_extractor())
    assert out == []


def test_fill_gaps_concept_gap_zero_shortfall_noop() -> None:
    seeds = [
        CorpusItem(
            id="r1",
            content="申请退款，麻烦尽快处理一下，谢谢。",
            category="退款",
            metadata={"ontology_concepts": ["fde:cc-billing", "fde:cc-billing-refund"]},
        )
    ]
    gap = ConceptGap(concept="fde:cc-billing-refund", current_count=2, target_count=2)
    out = CorpusSynthesizer().fill_gaps(seeds, [], concept_gaps=[gap], extractor=_concept_extractor())
    assert out == []


def test_forge_synthesizes_concept_gap_fill(sample_rows: list[dict]) -> None:
    """fde:cc-quality is the sole concept gap and t-002 anchors it."""
    forge = CorpusForge(
        CorpusConfig(min_samples_per_category=2, synth_per_gap=1),
        ontology=_taxonomy(),
    )
    report = forge.forge_rows(sample_rows)
    concept_synth = [
        i
        for split in (report.train, report.eval, report.test)
        for i in split.items
        if "synthesize:concept" in i.trace
    ]
    assert len(concept_synth) == 1
    item = concept_synth[0]
    assert item.metadata["ontology_concepts"] == ["fde:cc-quality"]
    assert item.provenance == Provenance.SYNTHETIC
