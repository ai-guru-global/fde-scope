"""FDE delivery benchmark — prove value with data, not vibes.

Runs an agent (anything implementing ``str -> str``) over an eval corpus,
scores each case on the metric catalogue, mines bad cases, and emits an
:class:`EvalReport]` plus a plain-English recommendation.

AgentScope interop: a real ``agentscope.agent.Agent`` is adapted by wrapping
its ``reply``/``reply_stream`` in a ``ReplyFn``. The benchmark itself never
imports agentscope, so it runs with zero config.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

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

    def run(self, reply_fn: ReplyFn, eval_cases: list[EvalCase]) -> EvalReport:
        # Materialize agent replies (the only place an LLM would be called).
        scored: list[EvalCase] = []
        for case in eval_cases:
            reply = reply_fn(case.input) or ""
            scored.append(case.model_copy(update={"agent_reply": reply}))

        metrics = self._aggregate(scored)
        bad = BadCaseMiner().mine(scored)
        return EvalReport(
            metrics=metrics,
            metric_labels=dict(METRICS),
            bad_cases=bad,
            case_count=len(scored),
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
        avg_handle = sum(c.handle_time_seconds for c in cases) / n
        avg_ratio = sum(handle_time_ratio(c) for c in cases) / n
        avg_csat = sum(c.csat for c in cases if c.csat is not None) / max(
            sum(1 for c in cases if c.csat is not None), 1
        )

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
