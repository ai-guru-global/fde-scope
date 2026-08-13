"""Manufacturing production-KPI calculators.

Each function implements the standard industry formula (Nakajima TPM for OEE,
Six Sigma for DPMO, NIST grasp metrics). Pure and deterministic — no LLM,
no framework. These are the numbers an FDE reports to a plant manager.

References: oee.com / leanproduction.com (OEE 85% world-class), Six Sigma
(3.4 DPMO), NIST robot-grasp test methods, DexNet 2.0 (~80% real-robot
grasp success benchmark).
"""

from __future__ import annotations


def oee(availability: float, performance: float, quality: float) -> float:
    """OEE = Availability × Performance × Quality.

    Each input is a 0-1 fraction. World-class ≥ 0.85; typical plant ~0.60.
    """
    return max(0.0, min(availability, 1.0)) * max(0.0, min(performance, 1.0)) * max(0.0, min(quality, 1.0))


def mtbf(total_uptime_hours: float, failures: int) -> float:
    """Mean Time Between Failures (repairable assets). Higher is better."""
    return total_uptime_hours / max(failures, 1)


def mttr(total_repair_hours: float, repairs: int) -> float:
    """Mean Time To Repair. Lower is better."""
    return total_repair_hours / max(repairs, 1)


def first_pass_yield(good_units: int, started_units: int) -> float:
    """FPY — fraction of units passing first time, no rework/scrap.

    Raises ValueError when good_units exceeds started_units — a yield above
    100% means bad input data, not a great shift.
    """
    if good_units > started_units:
        raise ValueError(f"good_units ({good_units}) cannot exceed started_units ({started_units})")
    return good_units / max(started_units, 1)


def dpmo(defects: int, units: int, opportunities_per_unit: float) -> float:
    """Defects Per Million Opportunities (Six Sigma). Lower is better.

    3.4 DPMO = Six Sigma (99.99966% yield). Legitimate fractional
    opportunity counts (e.g. 0.5) are honored as-is; a zero denominator (no
    units or no opportunities) means there is nothing to measure, so the
    result is 0.0 rather than a meaningless inflated number.
    """
    opportunities = units * opportunities_per_unit
    if opportunities <= 0:
        return 0.0
    return (defects / opportunities) * 1_000_000


def grasp_success_rate(successes: int, attempts: int) -> float:
    """Fraction of pick attempts that succeed. DexNet 2.0 ~0.80 benchmark."""
    return successes / max(attempts, 1)


def task_completion_rate(succeeded: int, attempted: int) -> float:
    """Fraction of robot tasks reaching terminal success state."""
    return succeeded / max(attempted, 1)


def collision_intervention_rate(interventions: int, cycles: int) -> float:
    """E-stops / safety stops / human overrides per cycle. Lower is better."""
    return interventions / max(cycles, 1)


# Human-readable KPI catalogue (mirrors ManufacturingProfile.kpi_catalogue).
MANUFACTURING_KPI_LABELS: dict[str, str] = {
    "oee": "OEE 设备综合效率（A×P×Q，世界级≥85%）",
    "mtbf": "MTBF 平均无故障时间（h）",
    "mttr": "MTTR 平均修复时间（h，越低越好）",
    "first_pass_yield": "FPY 一次合格率",
    "dpmo": "DPMO 百万机会缺陷数（越低越好）",
    "grasp_success_rate": "抓取成功率（DexNet ~80% 基准）",
    "task_completion_rate": "任务完成率",
    "collision_intervention_rate": "碰撞/干预率（越低越好）",
}
