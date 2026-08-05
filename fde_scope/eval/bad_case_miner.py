"""Bad-case mining — the FDE's continuous-improvement lever.

A benchmark number ("91% accuracy") closes a deal; the *bad cases* are what
the FDE uses to keep improving after deployment. This module pulls failures
out of an eval run and groups them so the next corpus iteration has a clear
target ("补充跨品类退换货语料 ~150 条").
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from .metrics import EvalCase, score_adoption, score_intent_accuracy


class BadCase(BaseModel):
    """A single failure surfaced for review."""

    case_id: str
    category: str
    reason: str
    input_preview: str = ""
    agent_reply_preview: str = ""


class BadCaseReport(BaseModel):
    """Aggregated bad cases + the top failing categories + a recommendation."""

    total_failures: int
    by_category: dict[str, int] = Field(default_factory=dict)
    top_category: str | None = None
    cases: list[BadCase] = Field(default_factory=list)
    recommendation: str = ""

    @property
    def sample_count_to_synthesize(self) -> int:
        """Heuristic: how many synthetic samples the top gap needs."""
        if not self.top_category:
            return 0
        return min(max(self.by_category.get(self.top_category, 0) * 30, 50), 300)


class BadCaseMiner:
    """Extract and aggregate failures from an eval run."""

    def mine(self, cases: list[EvalCase]) -> BadCaseReport:
        bad: list[BadCase] = []
        for c in cases:
            reason = self._failure_reason(c)
            if reason:
                bad.append(
                    BadCase(
                        case_id=c.id,
                        category=c.category,
                        reason=reason,
                        input_preview=c.input[:120],
                        agent_reply_preview=c.agent_reply[:120],
                    )
                )

        by_cat: Counter[str] = Counter(b.category for b in bad)
        top = by_cat.most_common(1)[0][0] if by_cat else None
        rec = self._recommendation(top, by_cat.get(top, 0)) if top else ""

        return BadCaseReport(
            total_failures=len(bad),
            by_category=dict(by_cat),
            top_category=top,
            cases=bad,
            recommendation=rec,
        )

    @staticmethod
    def _failure_reason(case: EvalCase) -> str:
        if score_intent_accuracy(case) < 1.0:
            return "intent_mismatch"
        if score_adoption(case) < 1.0:
            return "not_adopted"
        if case.escalated:
            return "escalated"
        return ""

    def _recommendation(self, top_category: str, count: int) -> str:
        n = min(max(count * 30, 50), 300)
        return f"建议补充「{top_category}」类语料 ~{n} 条，重点覆盖失败模式。"
