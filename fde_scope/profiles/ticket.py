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
        """Recompute ticket KPIs from per-ticket records (idempotent)."""
        if not samples:
            return {k: 0.0 for k in self.kpi_catalogue}
        n = len(samples)
        acc = sum(1 for s in samples if s.get("intent_correct", True)) / n
        adopted = sum(1 for s in samples if s.get("adopted", True)) / n
        escalated = sum(1 for s in samples if s.get("escalated", False)) / n
        handle = sum(s.get("handle_time_seconds", 0) for s in samples) / n
        return {
            "intent_accuracy": acc,
            "reply_adoption_rate": adopted,
            "escalation_rate": escalated,
            "avg_handle_time": handle,
        }
