"""FAT / SAT gate — Factory Acceptance Test & Site Acceptance Test.

Industrial deployments have NO SaaS analog for this. The system is built and
tested at the integrator's site (FAT) before shipping, then re-tested on the
customer's actual floor (SAT) after install. Both must be signed off before
commissioning. A gate failure here means "do not energize on the customer
floor."
"""

from __future__ import annotations

from ..context import EngagementContext
from .base import Gate, GateResult


class FatSatGate(Gate):
    slug = "fat_sat"
    name = "FAT / SAT Acceptance"
    industrial_only = True

    def check(self, ctx: EngagementContext) -> GateResult:
        blockers: list[str] = []
        warnings: list[str] = []
        fat = ctx.assets.get("fat")
        sat = ctx.assets.get("sat")

        if not fat:
            blockers.append("FAT (Factory Acceptance Test) 未执行或未记录")
        else:
            if not fat.get("passed"):
                blockers.append(f"FAT 未通过: {fat.get('notes', '无说明')}")
            if not fat.get("signed_off_by"):
                warnings.append("FAT 缺少签字")

        if not sat:
            blockers.append("SAT (Site Acceptance Test) 未执行或未记录")
        else:
            if not sat.get("passed"):
                blockers.append(f"SAT 未通过: {sat.get('notes', '无说明')}")
            if not sat.get("signed_off_by"):
                warnings.append("SAT 缺少客户现场签字")

        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)
