"""Zone D (Handoff/Exit) gate + the handoff-package generator.

The FDE's exit criterion: ownership has moved to Customer Success / customer
ops, the knowledge-transfer package is complete, and disengagement is
scheduled. The package generator assembles the tangible deliverables an FDE
hands over.
"""

from __future__ import annotations

from .context import EngagementContext
from .gates.base import Gate, GateResult


class HandoffSignoffGate(Gate):
    """Block disengagement until the handoff package is accepted."""

    slug = "handoff_signoff"
    name = "Handoff Sign-off"

    def check(self, ctx: EngagementContext) -> GateResult:
        blockers: list[str] = []
        warnings: list[str] = []
        pkg = ctx.assets.get("handoff_package")
        if not pkg:
            blockers.append("移交包未生成")
        else:
            required = ["runbook", "eval_report", "slo_definition", "training_material"]
            missing = [k for k in required if not pkg.get(k)]
            if missing:
                blockers.append(f"移交包缺失: {missing}")
            if not pkg.get("customer_accepted"):
                warnings.append("客户尚未书面接受移交")
        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)


# ---------------------------------------------------------------------------
# Handoff-package generator
# ---------------------------------------------------------------------------
def build_handoff_package(
    ctx: EngagementContext,
    *,
    runbook_path: str | None = None,
    eval_report_path: str | None = None,
    training_material: str | None = None,
    customer_accepted: bool = False,
) -> dict:
    """Assemble the knowledge-transfer deliverable record."""

    package = {
        "customer": ctx.customer,
        "engagement_id": ctx.id,
        "profile": ctx.profile,
        "runbook": runbook_path,
        "eval_report": eval_report_path,
        "slo_definition": [s.model_dump() for s in ctx.slos] or None,
        "training_material": training_material,
        "safety_posture": ctx.safety.model_dump() if ctx.is_industrial else None,
        "model_card": {
            "model": ctx.assets.get("model_name", "unknown"),
            "corpus_summary": ctx.assets.get("corpus_summary"),
            "known_limitations": ctx.assets.get("known_limitations", []),
        },
        "customer_accepted": customer_accepted,
    }
    ctx.assets["handoff_package"] = package
    return package


def render_handoff_summary(ctx: EngagementContext) -> str:
    pkg = ctx.assets.get("handoff_package", {})
    lines = [
        f"# 移交包 · {ctx.customer} ({ctx.id})",
        "",
        f"- profile: `{ctx.profile}`",
        f"- runbook: {pkg.get('runbook') or '—'}",
        f"- eval report: {pkg.get('eval_report') or '—'}",
        f"- training material: {pkg.get('training_material') or '—'}",
        f"- customer accepted: {'✅' if pkg.get('customer_accepted') else '❌'}",
    ]
    if pkg.get("safety_posture"):
        s = pkg["safety_posture"]
        lines += [
            "",
            "## 功能安全",
            f"- ISO 13849 PLr/PL: {s.get('required_plr')} / {s.get('achieved_pl')}",
            f"- IEC 61508 SIL 要求/达成: {s.get('sil_required')} / {s.get('sil_achieved')}",
            f"- ISO 10218 评估: {'✅' if s.get('iso10218_assessed') else '❌'}",
            f"- CE marking: {'✅' if s.get('ce_marking_done') else '❌'}",
        ]
    return "\n".join(lines)
