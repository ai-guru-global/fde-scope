"""Air-gap gate — air-gapped / on-prem deployment readiness.

Defense, energy, and classified manufacturing cannot phone home. Air-gapped
deployments need edge GPU servers, offline model-update logistics, and zero
telemetry egress. This gate verifies the deployment plan honors that.
"""

from __future__ import annotations

from ..context import EngagementContext
from .base import Gate, GateResult


class AirGapGate(Gate):
    slug = "air_gap"
    name = "Air-Gapped Deployment Readiness"
    industrial_only = True

    def check(self, ctx: EngagementContext) -> GateResult:
        if not ctx.site.air_gapped:
            return GateResult(
                slug=self.slug,
                passed=True,
                notes=["非 air-gapped 现场，本 gate 不适用"],
            )

        blockers: list[str] = []
        warnings: list[str] = []
        plan = ctx.assets.get("air_gap_plan", {})

        if not plan.get("edge_hardware"):
            blockers.append("air-gapped 部署未指定 edge 硬件（GPU 服务器/边缘盒子）")
        if not plan.get("offline_model_update"):
            blockers.append("未定义离线模型更新流程（不能 phone home 拉模型）")
        if plan.get("telemetry_egress_allowed"):
            blockers.append("遥测出网被允许——违反 air-gap 约束")
        if not plan.get("local_storage"):
            warnings.append("未指定本地持久化方案（日志/语料/审计）")

        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)
