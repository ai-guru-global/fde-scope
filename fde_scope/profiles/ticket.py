"""Ticket / customer-service profile (the original FDE Scope scenario)."""

from __future__ import annotations

from .base import Profile, register


class TicketProfile(Profile):
    def __init__(self) -> None:
        super().__init__(
            slug="ticket",
            name="工单 / 客服",
            is_industrial=False,
            primary_connectors=["csv", "zammad", "salesforce", "mysql"],
            kpi_catalogue={
                "intent_accuracy": "意图识别准确率",
                "reply_adoption_rate": "回复采纳率",
                "escalation_rate": "人工升级率（越低越好）",
                "avg_handle_time": "平均处理时长",
            },
            description="客服工单场景：CSV/Zammad/Salesforce 接入，意图/采纳率/升级率评估。",
        )
        register(self)

    def compute_kpis(self, samples: list[dict]) -> dict[str, float]:
        """Recompute ticket KPIs from per-ticket records (idempotent).

        A sample missing a metric's field is excluded from that metric's
        denominator — it counts as neither pass nor fail, so sparse records
        can't inflate (or deflate) a rate. A metric with no usable samples
        reports the neutral value 0.0.
        """
        if not samples:
            return dict.fromkeys(self.kpi_catalogue, 0.0)
        return {
            "intent_accuracy": _rate(samples, "intent_correct"),
            "reply_adoption_rate": _rate(samples, "adopted"),
            "escalation_rate": _rate(samples, "escalated"),
            "avg_handle_time": _mean(samples, "handle_time_seconds"),
        }


def _rate(samples: list[dict], key: str) -> float:
    """Fraction of true-ish values among samples that actually carry ``key``."""
    vals = [s[key] for s in samples if key in s]
    return sum(1 for v in vals if v) / len(vals) if vals else 0.0


def _mean(samples: list[dict], key: str) -> float:
    """Mean of ``key`` over samples that carry it; 0.0 when none do."""
    vals = [s[key] for s in samples if key in s]
    return sum(vals) / len(vals) if vals else 0.0
