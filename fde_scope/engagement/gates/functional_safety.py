"""Functional-safety gate — ISO 13849 / IEC 61508 / ISO 10218.

The hardest gate. Industrial AI deployed into safety-related functions must
clear functional-safety validation. The standards are still catching up to
ML (IEC 61508-9/-10 in draft), which makes an *enforced* gate here a genuine
value-add — most teams treat it as a doc checkbox.

The gate checks the safety posture recorded during the site survey /
safety assessment against the standard's hierarchy:
    ISO 13849: required Performance Level (PLr) vs achieved PL (a < b < ... < e)
    IEC 61508: required SIL vs achieved SIL (1 < 2 < 3 < 4)
    ISO 10218-1:2025: robot-safety assessment completed
    Hazard analysis (STPA/HAZOP lite) performed
"""

from __future__ import annotations

from ..context import EngagementContext
from .base import Gate, GateResult

_PL_RANK = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}


def _pl_rank(pl: str | None) -> int:
    return _PL_RANK.get((pl or "").lower(), 0)


class FunctionalSafetyGate(Gate):
    slug = "functional_safety"
    name = "Functional Safety (ISO 13849 / IEC 61508 / ISO 10218)"
    industrial_only = True

    def check(self, ctx: EngagementContext) -> GateResult:
        s = ctx.safety
        blockers: list[str] = []
        warnings: list[str] = []

        # ISO 13849 PL
        # 非空但无法识别的 PL 字符串不能静默按 rank 0 处理——必须告警，
        # 否则 "PL_D" 之类的写法会让比较失去意义（甚至永远通过）。
        for label, value in (("PLr", s.required_plr), ("PL", s.achieved_pl)):
            if value and value.lower() not in _PL_RANK:
                warnings.append(f"ISO 13849: 无法识别的 {label} 值 {value!r}，未参与等级比较")
        if s.required_plr and s.achieved_pl:
            if _pl_rank(s.achieved_pl) < _pl_rank(s.required_plr):
                blockers.append(f"ISO 13849: 达成 PL={s.achieved_pl} 低于要求 PLr={s.required_plr}")
        elif s.required_plr and not s.achieved_pl:
            warnings.append(f"ISO 13849: 已定义 PLr={s.required_plr} 但未记录达成 PL")

        # IEC 61508 SIL
        if s.sil_required and s.sil_achieved is not None:
            if s.sil_achieved < s.sil_required:
                blockers.append(f"IEC 61508: SIL 不足 (要求 {s.sil_required}, 达成 {s.sil_achieved})")
        elif s.sil_required and s.sil_achieved is None:
            warnings.append(f"IEC 61508: 已定义 SIL 要求={s.sil_required} 但未记录达成值")

        # ISO 10218 robot safety
        if not s.iso10218_assessed:
            warnings.append("ISO 10218-1:2025 机器人安全评估未完成")

        # Hazard analysis
        if not s.hazard_analysis_done:
            blockers.append("未执行危险分析（STPA / HAZOP lite）——功能安全判定的前提")

        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)
