"""Conformity gate — EU AI Act + CE marking.

High-risk AI systems (which include safety-related machinery AI) require CE
marking and a conformity assessment under the EU AI Act + Machinery
Regulation. This gate is what stops an FDE from shipping a non-conformant
system into the EU market.
"""

from __future__ import annotations

from ..context import EngagementContext
from .base import Gate, GateResult


class ConformityGate(Gate):
    slug = "conformity"
    name = "CE / EU AI Act Conformity"
    industrial_only = True

    def check(self, ctx: EngagementContext) -> GateResult:
        s = ctx.safety
        blockers: list[str] = []
        warnings: list[str] = []

        if s.eu_ai_act_high_risk:
            if not s.ce_marking_done:
                blockers.append("EU AI Act 高风险系统：CE marking 未完成")
            # Conformity assessment artifacts expected for high-risk systems
            technical_file = ctx.assets.get("technical_construction_file")
            if not technical_file:
                blockers.append("缺失技术构造文件（Annex IV 技术文档）")
            if not s.hazard_analysis_done:
                blockers.append("高风险系统要求危险分析作为 conformity 前提")
        else:
            if not s.ce_marking_done:
                warnings.append("CE marking 未记录（非高风险系统，建议但非阻断）")

        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)
