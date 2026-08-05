"""Works-council gate — German BetrVG §87 co-determination.

In Germany (BetrVG §87(1) No.1 & No.6), deploying AI that affects workers can
trigger mandatory works-council co-determination; a conciliation committee can
block or condition the deployment. IndustriALL and IG Metall are active here.
This gate records whether the engagement has works-council approval — treating
labor as a first-class gate, not an afterthought.
"""

from __future__ import annotations

from ..context import EngagementContext
from .base import Gate, GateResult


class WorksCouncilGate(Gate):
    slug = "works_council"
    name = "Works Council / Labor Co-determination"
    industrial_only = True

    def check(self, ctx: EngagementContext) -> GateResult:
        blockers: list[str] = []
        warnings: list[str] = []

        if not ctx.site.works_council_represented:
            return GateResult(
                slug=self.slug,
                passed=True,
                notes=["现场无 works council 代表，本 gate 不适用"],
            )

        approval = ctx.assets.get("works_council_approval")
        if not approval:
            blockers.append("works council 已在场，但未记录共决审批（BetrVG §87）—— deployment 可被吊销")
        else:
            if approval.get("status") == "denied":
                blockers.append(f"works council 否决: {approval.get('reason', '无说明')}")
            elif approval.get("status") == "pending":
                warnings.append("works council 审批进行中，未最终签署")
            elif not approval.get("signed_off_by"):
                warnings.append("works council 审批缺签字")

        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)
