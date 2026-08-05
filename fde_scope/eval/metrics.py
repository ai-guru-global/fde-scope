"""Evaluation metric definitions and rule-based scoring.

These metrics span three dimensions an FDE reports on:
    - corpus  : is the data itself any good?
    - agent   : does the agent reply correctly and confidently?
    - business: did deploying the agent actually move the needle?

Each metric is computed by a deterministic function over an
:class:`EvalResult` so the whole eval is runnable without an LLM. The agent
dimension defaults to rule-based heuristics (e.g. keyword overlap for intent
accuracy) that a real LLM call would replace behind the same interface.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field

# Human-readable metric catalogue — surfaced in reports and the CLI.
METRICS: dict[str, str] = {
    # corpus dimension
    "corpus_coverage": "意图覆盖率（%）",
    "corpus_quality_avg": "平均质量分（1-5）",
    "corpus_diversity": "语义多样性指数",
    # agent dimension
    "intent_accuracy": "意图识别准确率",
    "reply_adoption_rate": "回复采纳率（人工未修改直接使用）",
    "escalation_rate": "人工升级率（越低越好）",
    "first_contact_resolve": "首次接触解决率",
    # business dimension
    "avg_handle_time": "平均处理时长（对比人工基线）",
    "customer_satisfaction": "客户满意度（CSAT）",
    "cost_per_ticket": "单工单成本",
}


class Dimension(str, Enum):
    CORPUS = "corpus"
    AGENT = "agent"
    BUSINESS = "business"


METRIC_DIMENSION: dict[str, Dimension] = {
    "corpus_coverage": Dimension.CORPUS,
    "corpus_quality_avg": Dimension.CORPUS,
    "corpus_diversity": Dimension.CORPUS,
    "intent_accuracy": Dimension.AGENT,
    "reply_adoption_rate": Dimension.AGENT,
    "escalation_rate": Dimension.AGENT,
    "first_contact_resolve": Dimension.AGENT,
    "avg_handle_time": Dimension.BUSINESS,
    "customer_satisfaction": Dimension.BUSINESS,
    "cost_per_ticket": Dimension.BUSINESS,
}


class EvalCase(BaseModel):
    """One eval input plus the agent's reply and (optional) ground truth."""

    id: str
    input: str
    category: str = "uncategorized"
    expected_category: str | None = None
    expected_output: str | None = None
    agent_reply: str = ""
    adopted: bool | None = None  # True if human used the reply as-is
    escalated: bool = False  # True if it had to go to a human
    resolved_first_contact: bool = True
    handle_time_seconds: float = 0.0
    baseline_handle_time_seconds: float = 480.0  # 8min human baseline
    csat: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplyFn(Protocol):
    """The agent reply interface the benchmark calls.

    Any callable ``str -> str`` works — a real AgentScope ``Agent.reply`` is
    adapted to this, and the rule-based mock implements it directly.
    """

    def __call__(self, user_input: str) -> str: ...


# ---------------------------------------------------------------------------
# Per-case scorers (deterministic, no LLM)
# ---------------------------------------------------------------------------
def score_intent_accuracy(case: EvalCase) -> float:
    """1.0 if the agent's reply category matches expectation, else 0.0.

    v0 heuristic: if an expected category is given, check it appears in the
    reply; otherwise treat as correct (no signal). Replace with a real
    classifier in v1.
    """
    if not case.expected_category:
        return 1.0
    return 1.0 if case.expected_category in case.agent_reply else 0.0


def score_adoption(case: EvalCase) -> float:
    if case.adopted is None:
        return 1.0  # no signal → assume adopted
    return 1.0 if case.adopted else 0.0


def score_escalation(case: EvalCase) -> float:
    """Escalation is bad → return the escalation *rate* (higher = worse)."""
    return 1.0 if case.escalated else 0.0


def score_first_contact(case: EvalCase) -> float:
    return 1.0 if case.resolved_first_contact else 0.0


def handle_time_ratio(case: EvalCase) -> float:
    """Agent handle time as a fraction of the human baseline."""
    if case.baseline_handle_time_seconds <= 0:
        return 1.0
    return case.handle_time_seconds / case.baseline_handle_time_seconds
