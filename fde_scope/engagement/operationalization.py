"""Zone C (Operationalization) gate + generators.

Between deploy and flywheel: SLO/SLA + on-call, runbooks, monitoring/drift,
change management. The SLO gate is enforced; runbook/dashboard generators
produce the artifacts.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .context import EngagementContext
from .gates.base import Gate, GateResult

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class SLOGate(Gate):
    """An engagement is not 'done' until SLOs + on-call are defined."""

    slug = "slo"
    name = "SLO / SLA + On-call"

    def check(self, ctx: EngagementContext) -> GateResult:
        blockers: list[str] = []
        warnings: list[str] = []
        if not ctx.slos:
            blockers.append("未定义任何 SLO——错误预算/告警路由缺失")
        else:
            no_route = [s.name for s in ctx.slos if not s.alert_route]
            if no_route:
                warnings.append(f"SLO 缺告警路由: {no_route}")
        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
def render_runbook(ctx: EngagementContext, agent_name: str = "tenant_agent") -> str:
    """Render a Markdown runbook for the deployed agent."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("runbook.md.j2")
    return template.render(ctx=ctx, agent_name=agent_name)


def build_slo_template() -> list[dict]:
    """Default agent SLOs (SparkCo / Nobl9 consensus patterns)."""
    return [
        {
            "name": "availability",
            "target": "99.5%",
            "error_budget": "1.68h / 14d",  # 14d × 24h × (1 - 99.5%) = 1.68h
            "alert_route": "primary-oncall",
            "window": "14d",
        },
        {
            "name": "reply_latency_p95",
            "target": "<8s",
            "error_budget": "",
            "alert_route": "primary-oncall",
            "window": "14d",
        },
        {
            "name": "bad_case_rate",
            "target": "<10%",
            "error_budget": "",
            "alert_route": "fde-oncall",
            "window": "28d",
        },
    ]


def build_monitoring_template() -> dict:
    """Drift / quality monitoring checklist."""
    return {
        "data_drift": {"enabled": False, "cadence": "daily", "threshold": "PSI > 0.2"},
        "quality_drift": {"enabled": False, "cadence": "weekly"},
        "feedback_latency": {"target_hours": 24},
        "dashboards": [],  # {name, url}
    }
