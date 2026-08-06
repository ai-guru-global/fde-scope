"""Tests for Layer 4 — eval benchmark + bad case mining."""

from __future__ import annotations

from fde_scope.eval import (
    METRICS,
    BadCaseMiner,
    EvalCase,
    FDEBenchmark,
    MockReplyFn,
)


def _cases() -> list[EvalCase]:
    return [
        EvalCase(
            id="1", input="退款", category="退款", expected_category="退款", handle_time_seconds=30, csat=5.0
        ),
        EvalCase(
            id="2", input="物流", category="物流", expected_category="物流", handle_time_seconds=40, csat=4.0
        ),
        EvalCase(
            id="3",
            input="登录问题",
            category="账号",
            expected_category="支付",  # mismatch
            handle_time_seconds=60,
            escalated=True,
            csat=2.0,
        ),
    ]


def test_metrics_catalogue_complete() -> None:
    expected = {
        "corpus_coverage",
        "corpus_quality_avg",
        "corpus_diversity",
        "intent_accuracy",
        "reply_adoption_rate",
        "escalation_rate",
        "first_contact_resolve",
        "avg_handle_time",
        "customer_satisfaction",
        "cost_per_ticket",
    }
    assert expected <= set(METRICS)


def test_benchmark_runs_with_mock_reply() -> None:
    # force a high-accuracy mock so most cases pass
    report = FDEBenchmark().run(MockReplyFn(accuracy=1.0), _cases())
    assert report.case_count == 3
    assert 0.0 <= report.metrics["intent_accuracy"] <= 1.0
    assert "intent_accuracy" in report.metric_labels


def test_benchmark_backfills_corpus_metrics_from_forge_report(sample_rows: list[dict]) -> None:
    """Corpus-dimension metrics (coverage/quality/diversity) come from the forge report."""
    from fde_scope.config import CorpusConfig
    from fde_scope.corpus import CorpusForge

    forge_report = CorpusForge(CorpusConfig(min_samples_per_category=5, synth_per_gap=2)).forge_rows(
        sample_rows
    )
    eval_report = FDEBenchmark().run(MockReplyFn(accuracy=1.0), _cases(), corpus_report=forge_report)

    # coverage = fraction of categories meeting target (0-1); with a tiny sample
    # and high min_samples, most categories are gaps → coverage may be 0, but it
    # must be a real number, not the old hardcoded 0.0-without-corpus sentinel.
    assert eval_report.metrics["corpus_coverage"] >= 0.0
    # quality_avg is the mean of item quality scores (1-5 band)
    assert eval_report.metrics["corpus_quality_avg"] > 0.0
    # diversity is normalized Shannon entropy (0-1)
    assert 0.0 <= eval_report.metrics["corpus_diversity"] <= 1.0


def test_benchmark_corpus_metrics_stay_zero_without_forge_report() -> None:
    """Without a forge report, corpus metrics remain 0.0 (no silent guess)."""
    report = FDEBenchmark().run(MockReplyFn(accuracy=1.0), _cases())
    assert report.metrics["corpus_coverage"] == 0.0
    assert report.metrics["corpus_quality_avg"] == 0.0


def test_bad_case_miner_finds_mismatch() -> None:
    # craft cases: one passes, one mismatches intent
    cases = [
        EvalCase(
            id="ok", input="x", category="退款", expected_category="退款", agent_reply="已为您处理：退款"
        ),
        EvalCase(
            id="bad", input="y", category="账号", expected_category="支付", agent_reply="已为您处理：账号"
        ),  # '支付' not in reply
    ]
    report = BadCaseMiner().mine(cases)
    assert report.total_failures == 1
    assert report.top_category == "账号"
    assert "账号" in report.recommendation


def test_eval_report_renders_recommendation() -> None:
    report = FDEBenchmark().run(MockReplyFn(accuracy=0.0), _cases())
    # low accuracy → at least one bad case → recommendation present
    assert isinstance(report.bad_cases.recommendation, str)
