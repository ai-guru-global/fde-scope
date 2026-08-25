"""FDE delivery benchmark — prove value with data, not vibes.

Runs an agent (anything implementing ``str -> str``) over an eval corpus,
scores each case on the metric catalogue, mines bad cases, and emits an
:class:`EvalReport]` plus a plain-English recommendation.

AgentScope interop: a real ``agentscope.agent.Agent`` is adapted by wrapping
its ``reply``/``reply_stream`` in a ``ReplyFn``. The benchmark itself never
imports agentscope, so it runs with zero config.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fde_scope.corpus.types import CorpusReport
    from fde_scope.llm import MiMoClient

from .bad_case_miner import BadCaseMiner, BadCaseReport
from .metrics import (
    METRICS,
    EvalCase,
    ReplyFn,
    handle_time_ratio,
    score_adoption,
    score_escalation,
    score_first_contact,
    score_intent_accuracy,
)


class EvalReport(BaseModel):
    """The post-eval deliverable: metrics + bad cases + recommendations."""

    metrics: dict[str, float] = Field(default_factory=dict)
    metric_labels: dict[str, str] = Field(default_factory=dict)
    bad_cases: BadCaseReport
    case_count: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)


class FDEBenchmark:
    """Run an agent over an eval corpus and score it."""

    METRICS = METRICS

    def run(
        self,
        reply_fn: ReplyFn,
        eval_cases: list[EvalCase],
        corpus_report: CorpusReport | None = None,
    ) -> EvalReport:
        # Materialize agent replies (the only place an LLM would be called).
        scored: list[EvalCase] = []
        for case in eval_cases:
            reply = reply_fn(case.input) or ""
            scored.append(case.model_copy(update={"agent_reply": reply}))

        metrics = self._aggregate(scored)
        # Sample counts for the no-data-sensitive metrics, so a report reader
        # can tell a real score apart from a neutral placeholder (0 responses
        # → customer_satisfaction is the neutral midpoint, 0 timed cases →
        # cost_per_ticket is baseline parity).
        extras = {
            "csat_responses": sum(1 for c in scored if c.csat is not None),
            "handle_time_recorded": sum(1 for c in scored if c.handle_time_seconds > 0),
        }
        # Backfill the corpus dimension from the forge report when the caller
        # supplies one, so the eval isn't stuck reporting 0.0 for coverage.
        if corpus_report is not None:
            cov = corpus_report.coverage
            metrics["corpus_coverage"] = _corpus_coverage_fraction(cov)
            metrics["corpus_quality_avg"] = _corpus_quality_avg(corpus_report)
            metrics["corpus_diversity"] = cov.diversity_index
        bad = BadCaseMiner().mine(scored)
        return EvalReport(
            metrics=metrics,
            metric_labels=dict(METRICS),
            bad_cases=bad,
            case_count=len(scored),
            extra=extras,
        )

    # -- aggregation ------------------------------------------------------------
    def _aggregate(self, cases: list[EvalCase]) -> dict[str, float]:
        if not cases:
            return dict.fromkeys(METRICS, 0.0)

        n = len(cases)
        intent = sum(score_intent_accuracy(c) for c in cases) / n
        adoption = sum(score_adoption(c) for c in cases) / n
        escalation = sum(score_escalation(c) for c in cases) / n
        fcr = sum(score_first_contact(c) for c in cases) / n

        # No-data metrics must not masquerade as a best/worst score:
        # - CSAT: average only real responses; with none, report the neutral
        #   midpoint of the 1-5 scale (mirrors score_adoption's "no signal →
        #   not a failure" stance). Distinguishable via extra["csat_responses"].
        # - handle time: cases with no recorded duration (0 = unfilled) are
        #   skipped so they can't drag cost_per_ticket towards 0; with no
        #   durations at all, report parity with the human baseline (1.0).
        csat_scores = [c.csat for c in cases if c.csat is not None]
        avg_csat = sum(csat_scores) / len(csat_scores) if csat_scores else 3.0
        timed = [c for c in cases if c.handle_time_seconds > 0]
        avg_handle = sum(c.handle_time_seconds for c in timed) / len(timed) if timed else 0.0
        avg_ratio = sum(handle_time_ratio(c) for c in timed) / len(timed) if timed else 1.0

        return {
            # corpus dimension left to the caller (forge report) to fill in
            "corpus_coverage": 0.0,
            "corpus_quality_avg": 0.0,
            "corpus_diversity": 0.0,
            "intent_accuracy": intent,
            "reply_adoption_rate": adoption,
            "escalation_rate": escalation,
            "first_contact_resolve": fcr,
            "avg_handle_time": avg_handle,
            "customer_satisfaction": avg_csat,
            "cost_per_ticket": avg_ratio,  # proxy: time ratio ≈ cost ratio
        }


# ---------------------------------------------------------------------------
# A rule-based mock reply function — zero-config eval out of the box.
# ---------------------------------------------------------------------------
class MockReplyFn:
    """Deterministic mock agent: echoes the expected category when known.

    Lets the whole eval flow run with no LLM. A real deployment injects a
    callable wrapping ``agentscope.agent.Agent.reply`` instead.
    """

    def __init__(self, accuracy: float = 0.9, seed: int = 0) -> None:
        self.accuracy = accuracy
        import random

        self._rng = random.Random(seed)

    def __call__(self, user_input: str) -> str:
        # ~`accuracy` of the time produce a plausible on-topic reply.
        if self._rng.random() <= self.accuracy:
            return f"已为您处理：{user_input[:30]}…（mock 回复）"
        return "抱歉，我不太理解您的问题。（mock 回复）"


class MiMoReplyFn:
    """A real LLM-backed reply function for :class:`FDEBenchmark`.

    Wraps a :class:`~fde_scope.llm.MiMoClient` behind the same ``str -> str``
    ``ReplyFn`` protocol as :class:`MockReplyFn`, so ``FDEBenchmark.run``
    needs no changes. The system prompt casts the model as the deployed
    tenant support agent. Raises :class:`~fde_scope.llm.LLMError` when the
    endpoint fails — the benchmark caller decides how to surface it.
    """

    def __init__(self, llm: MiMoClient, tenant: str = "client") -> None:
        self.llm = llm
        self.tenant = tenant

    def __call__(self, user_input: str) -> str:
        return self.llm.complete(
            user_input,
            system=(
                f"You are the AI support agent for tenant {self.tenant}. "
                "Answer customer tickets in Chinese, concisely and helpfully. "
                "If the request is a refund above policy, say you must escalate."
            ),
            temperature=0.3,
            max_tokens=300,
        )


# ---------------------------------------------------------------------------
# Corpus-dimension helpers — backfill metrics from a CorpusReport
# ---------------------------------------------------------------------------
def _corpus_coverage_fraction(coverage) -> float:
    """Fraction of categories that meet the target sample count (0-1)."""
    if not coverage.category_counts:
        return 0.0
    met = sum(1 for c in coverage.category_counts.values() if c >= coverage.target_per_category)
    return met / len(coverage.category_counts)


def _corpus_quality_avg(report) -> float:
    """Mean quality score (1-5) across all forged items."""
    items = report.train.items + report.eval.items + report.test.items
    if not items:
        return 0.0
    return sum(i.quality_score for i in items) / len(items)
