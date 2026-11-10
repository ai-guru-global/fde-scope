"""Provenance invariants for the forge's split — the anti-self-deception guard.

Origin: the 2026-11-03 workbench assessment measured, on the quickstart's 20
real rows, that eval/test were 95-100% synthetic and 29-36% of their members
had a >=0.90 near-duplicate in train. The cause was structural, not a tuning
knob: synthesis ran *after* dedup (a generated no-op mutation could repeat a
real row verbatim), and ``_split`` shuffled real and generated items together,
so generated text could land in the held-out set.

That is the same mistake the project sells advice against — validating a model
with its own generated data — so it gets its own guard file rather than a test
buried in ``test_corpus_pipeline.py``. Each test below fails on the old code.
"""

from __future__ import annotations

import difflib

from fde_scope.config import CorpusConfig
from fde_scope.corpus import CorpusForge
from fde_scope.corpus.types import CorpusItem, Provenance

#: Realistic ticket rows: distinct topics, no PII, enough to survive the
#: quality gate so the real-vs-split arithmetic is not confounded by drops.
_ROWS = [
    {"id": str(i), "content": text, "category": cat}
    for i, (text, cat) in enumerate(
        [
            ("申请退款商品质量有问题已经拍照留存希望尽快处理", "退款"),
            ("订单里多了一件商品怎么取消", "订单"),
            ("账号被锁定了怎么解锁", "账号"),
            ("咨询一下会员权益有哪些", "咨询"),
            ("收到的商品和描述不符要求退款", "退款"),
            ("优惠券无法使用结算时报错请帮忙看一下", "订单"),
            ("登录时一直提示密码错误", "账号"),
            ("物流信息三天没有更新了", "物流"),
            ("发票抬头开错了需要重开", "发票"),
            ("商品有色差想换一个颜色", "退货"),
            ("退货流程走完了什么时候能收到退款", "退货"),
            ("客服一直不回复我的问题", "咨询"),
            ("付款失败但银行卡已经扣款", "支付"),
            ("地址填写错误能否修改收货信息", "订单"),
            ("会员自动续费如何关闭", "账号"),
            ("包装破损商品有损坏", "退款"),
            ("如何申请开具电子发票", "发票"),
            ("快递显示已签收但没有收到", "物流"),
            ("尺码不合适想换货", "退货"),
            ("积分兑换的商品什么时候发货", "咨询"),
        ]
    )
]


def _forge(**overrides) -> CorpusForge:
    return CorpusForge(CorpusConfig(**overrides))


def _near_dup_in_train(report) -> int:
    """Held-out items whose best train match is >=0.90 (the old leak metric)."""
    train = [i.content for i in report.train.items]
    heldout = [*report.eval.items, *report.test.items]
    hits = 0
    for item in heldout:
        best = max((difflib.SequenceMatcher(None, item.content, t).ratio() for t in train), default=0.0)
        hits += best >= 0.90
    return hits


# ---------------------------------------------------------------------------
# eval / test carry no generated data
# ---------------------------------------------------------------------------
def test_heldout_splits_are_real_only() -> None:
    """The bug: generated items were shuffled into the same list as real ones."""
    report = _forge().forge_rows(_ROWS)

    assert report.eval.synthetic == 0, "a synthetic item in eval measures the synthesizer, not the model"
    assert report.test.synthetic == 0, "a synthetic item in test measures the synthesizer, not the model"
    assert {i.provenance for i in report.eval.items} <= {Provenance.REAL, Provenance.GOLDEN}
    assert {i.provenance for i in report.test.items} <= {Provenance.REAL, Provenance.GOLDEN}
    assert report.heldout_trusted is True
    assert report.heldout_real > 0


def test_heldout_holds_no_near_duplicate_of_train() -> None:
    """The old metric: 29-36% of held-out rows had a >=0.90 twin in train."""
    report = _forge().forge_rows(_ROWS)
    assert _near_dup_in_train(report) == 0


def test_heldout_real_denominator_is_honest() -> None:
    """``heldout_real`` must be the count an eval number is divided by, and the
    split's own counters must be derived from what it actually holds."""
    report = _forge().forge_rows(_ROWS)

    assert report.heldout_real == report.eval.real + report.test.real
    for split in (report.train, report.eval, report.test):
        assert split.real + split.synthetic + split.golden == split.size


def test_synthetic_items_still_reach_train() -> None:
    """The fix must not over-correct: augmentation is the reason to synthesize."""
    report = _forge().forge_rows(_ROWS)
    assert report.synthetic > 0
    assert report.train.synthetic == report.synthetic


def test_generated_items_can_be_excluded_from_train_entirely() -> None:
    """``synth_in_train=False`` keeps every slice free of generated data.

    Real rows are still partitioned across all three slices (eval/test are
    reserved for measurement), so the real rows hold out by ratio — this test
    pins "train holds no synthetic", not "train holds every real row".
    """
    cfg = CorpusConfig(synth_in_train=False)
    report = CorpusForge(cfg).forge_rows(_ROWS)

    assert report.train.synthetic == 0
    assert report.train.real == report.real - report.heldout_real
    assert report.train.real > 0
    # the synthetic tail is still *generated* — it just is not handed out as data
    assert report.synthetic > 0
    assert report.total > report.train.size + report.eval.size + report.test.size


# ---------------------------------------------------------------------------
# dedup runs across the merged corpus, not just the real half
# ---------------------------------------------------------------------------
def test_dedup_pass_drops_synthetic_copies_of_real_rows() -> None:
    """Synthesis follows the dedup stage, so duplicates had to be caught here."""
    forge = _forge()
    real = [
        CorpusItem(id="r1", content="我要退款", category="退款", provenance=Provenance.REAL),
        CorpusItem(id="r2", content="申请退款", category="退款", provenance=Provenance.REAL),
    ]
    synthetic = [
        CorpusItem(
            id="s1", content="我要退款", category="退款", channel="email", provenance=Provenance.SYNTHETIC
        ),
        CorpusItem(
            id="s2", content="我要退款", category="退款", channel="chat", provenance=Provenance.SYNTHETIC
        ),
        CorpusItem(
            id="s3",
            content="全新的一条内容",
            category="退款",
            channel="chat",
            provenance=Provenance.SYNTHETIC,
        ),
    ]

    kept = forge._dedup_against(real, synthetic)

    assert [i.id for i in kept] == ["s3"], "the real row survives; both synthetic copies go"
    assert forge.deduper.dropped_count == 2, "drops must be reported in CorpusReport.dropped"


def test_dedup_never_removes_a_real_row_in_favour_of_a_copy() -> None:
    forge = _forge()
    real = [CorpusItem(id="r1", content="同一句话", category="x", provenance=Provenance.REAL)]
    synthetic = [CorpusItem(id="s1", content="同一句话", category="x", provenance=Provenance.SYNTHETIC)]

    assert forge._dedup_against(real, synthetic) == []


# ---------------------------------------------------------------------------
# degenerate inputs stay honest
# ---------------------------------------------------------------------------
def test_seedless_synthesis_is_downsampled_to_one_exemplar_per_category() -> None:
    """Every row filtered out => template-only synthesis. 50 near-identical
    template variations per category are padding, not coverage."""
    cfg = CorpusConfig()
    # Empty/blank content is dropped by the quality gate, forcing the seedless
    # (template) path for every gap.
    rows = [{"id": "x", "content": "", "category": "退款"}]
    report = CorpusForge(cfg).forge_rows(rows)

    seedless = [i for i in report.train.items if i.channel == "synthetic"]
    assert len({(i.category) for i in seedless}) == len(seedless), (
        "at most one template exemplar per category"
    )
    assert report.eval.size == 0 and report.test.size == 0, "no real rows => no honest held-out set"
    assert report.heldout_trusted is False


def test_split_is_reproducible() -> None:
    a = _forge().forge_rows(_ROWS)
    b = _forge().forge_rows(_ROWS)
    for name in ("train", "eval", "test"):
        assert [i.id for i in getattr(a, name).items] == [i.id for i in getattr(b, name).items]


def test_split_ratios_place_real_rows_across_all_three_slices() -> None:
    """Real rows are partitioned first, so ratio maths holds on the real set."""
    report = _forge().forge_rows(_ROWS)
    real_total = report.real
    n_eval_test = report.eval.size + report.test.size
    assert n_eval_test == int(real_total * 0.1) + max(int(real_total * 0.2) - int(real_total * 0.1), 0)
    assert report.train.real == real_total - n_eval_test


def test_shuffle_does_not_depend_on_generated_volume() -> None:
    """Changing synthesis volume must not move real rows between splits —
    the old merged-list shuffle made the split sensitive to it."""
    small = _forge(synth_per_gap=2).forge_rows(_ROWS)
    large = _forge(synth_per_gap=20).forge_rows(_ROWS)

    # Same seed + same real rows => identical real assignment.
    assert [i.id for i in small.train.items if i.provenance == Provenance.REAL] == [
        i.id for i in large.train.items if i.provenance == Provenance.REAL
    ]
    assert large.synthetic > small.synthetic


def test_report_synthetic_ratio_is_derived() -> None:
    report = _forge().forge_rows(_ROWS)
    assert report.total == report.real + report.synthetic + report.golden
    assert report.synthetic_ratio == report.synthetic / report.total


def test_empty_corpus_reports_zero_ratio() -> None:
    report = _forge().forge_rows([])
    assert report.total == 0
    assert report.synthetic_ratio == 0.0
    assert report.heldout_real == 0


def test_report_html_states_heldout_provenance() -> None:
    """The customer-facing deliverable must not present a size without saying
    what is in it."""
    from fde_scope.corpus import render_html

    html = render_html(_forge().forge_rows(_ROWS))
    assert "留出集" in html
    assert "真实" in html and "合成" in html
    # the trusted branch, explicitly
    assert "不含合成数据" in html


def test_split_with_a_single_real_row_degrades_cleanly() -> None:
    """One real row must not produce a phantom held-out set.

    With one real row the ratio cut puts it in train and leaves eval/test
    empty; the report must then say the held-out set is untrusted (zero real
    rows), never present an empty eval as if it were measurable.
    """
    rows = [{"id": "1", "content": "我要申请退款并说明质检报告已经留档", "category": "退款"}]
    report = _forge(synth_per_gap=1).forge_rows(rows)

    assert report.real == 1
    # the one real row trains, rather than being spent on a 1-row eval
    assert report.train.real == 1
    assert report.eval.size == 0 and report.test.size == 0
    assert report.heldout_real == 0
    assert report.heldout_trusted is False
    assert report.synthetic_ratio >= 0.0  # derived, never divides by zero
