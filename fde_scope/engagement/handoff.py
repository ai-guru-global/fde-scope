"""Zone D (Handoff/Exit) gate + the handoff-package generator.

The FDE's exit criterion: ownership has moved to Customer Success / customer
ops, the knowledge-transfer package is complete, and disengagement is
scheduled. The package generator assembles the tangible deliverables an FDE
hands over.
"""

from __future__ import annotations

from .context import EngagementContext
from .gates.base import Gate, GateResult, asset_record


class HandoffSignoffGate(Gate):
    """Block disengagement until the handoff package is accepted.

    G7 has four criteria. ① four-piece package and ② customer sign-off are
    hard stops; ③ applicability boundary and ④ termination condition are
    advisory, because a handoff that is merely thin must not be indistinguishable
    from one that is absent — and retroactively blocking every engagement written
    before these fields existed would be worse than warning.
    """

    slug = "handoff_signoff"
    name = "Handoff Sign-off"

    #: (package key, SOP label, flag that fills it) — the advisory half of G7.
    ADVISORY = (
        ("boundary", "适用边界（G7③）", "--boundary"),
        ("termination", "终止条件（G7④）", "--termination"),
    )

    def check(self, ctx: EngagementContext) -> GateResult:
        blockers: list[str] = []
        warnings: list[str] = []
        pkg, unreadable = asset_record(ctx.assets, "handoff_package")
        if unreadable:
            return GateResult(slug=self.slug, passed=False, blockers=[unreadable])
        if not pkg:
            blockers.append("移交包未生成")
        else:
            required = ["runbook", "eval_report", "slo_definition", "training_material"]
            missing = [k for k in required if not pkg.get(k)]
            if missing:
                blockers.append(f"移交包缺失: {missing}")
            if not pkg.get("customer_accepted"):
                blockers.append("客户尚未书面接受移交——不得退场")
            for key, label, flag in self.ADVISORY:
                if not pkg.get(key):
                    warnings.append(f"移交包未记录{label}：用 {flag} 写明，否则接手方无人知道边界与停手条件")
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
    boundary: str | None = None,
    termination: str | None = None,
    customer_accepted: bool = False,
) -> dict:
    """Assemble the knowledge-transfer deliverable record.

    ``boundary`` / ``termination`` are G7③/④: where the solution stops holding
    and when the customer should stop using it. They are recorded but not
    enforced by the gate — see :class:`HandoffSignoffGate`.

    Omitting them keeps what was already recorded, because refreshing the
    package (``handoff`` is re-run to snapshot a newly added SLO) has no reason
    to revoke free text the FDE wrote earlier. The four-piece set deliberately
    has no such carry-over: an evidence path left out of a re-assembly is a hole
    in the handoff, and silently reusing last run's path is how stale evidence
    ships under a fresh timestamp.
    """

    prior, _ = asset_record(ctx.assets, "handoff_package")
    package = {
        "customer": ctx.customer,
        "engagement_id": ctx.id,
        "profile": ctx.profile,
        "runbook": runbook_path,
        "eval_report": eval_report_path,
        "slo_definition": [s.model_dump() for s in ctx.slos] or None,
        "training_material": training_material,
        "boundary": boundary if boundary is not None else prior.get("boundary"),
        "termination": termination if termination is not None else prior.get("termination"),
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
    pkg, _ = asset_record(ctx.assets, "handoff_package")
    lines = [
        f"# 移交包 · {ctx.customer} ({ctx.id})",
        "",
        f"- profile: `{ctx.profile}`",
        f"- runbook: {pkg.get('runbook') or '—'}",
        f"- eval report: {pkg.get('eval_report') or '—'}",
        f"- training material: {pkg.get('training_material') or '—'}",
        f"- boundary (G7③): {pkg.get('boundary') or '—'}",
        f"- termination (G7④): {pkg.get('termination') or '—'}",
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
