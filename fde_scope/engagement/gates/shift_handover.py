"""Shift-handover gate — 24/7 production integration.

Factories run across shifts; the AI must plug into the digital
shift-handover process. A day-one miss here means night-shift operators are
flying blind when the agent misbehaves.
"""

from __future__ import annotations

from ..context import EngagementContext
from .base import Gate, GateResult


class ShiftHandoverGate(Gate):
    slug = "shift_handover"
    name = "Shift Handover Integration"
    industrial_only = True

    def check(self, ctx: EngagementContext) -> GateResult:
        blockers: list[str] = []
        warnings: list[str] = []

        if ctx.site.shift_count <= 1:
            return GateResult(
                slug=self.slug,
                passed=True,
                notes=["单班次现场，shift handover 不适用"],
            )

        handover = ctx.assets.get("shift_handover")
        if not handover:
            blockers.append(f"{ctx.site.shift_count} 班次现场，未集成班次交接流程")
        else:
            if not handover.get("digital_log_integrated"):
                warnings.append("未接入数字化交接日志系统")
            if not handover.get("per_shift_runbook"):
                warnings.append("缺每班次 runbook / 应急联系人")

        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)
