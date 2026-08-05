"""Manufacturing / embodied-robotics profile.

The factory-floor scenario. Selects the industrial connector set
(OPC UA, MQTT/Sparkplug, ROS2 rosbag, MES, Historian) and reports the
production-KPI catalogue (OEE, MTBF/MTTR, FPY/DPMO, grasp success,
collision rate). Triggers the industrial gate overlay in the engagement.
"""

from __future__ import annotations

from ..eval.manufacturing_metrics import (
    collision_intervention_rate,
    dpmo,
    first_pass_yield,
    grasp_success_rate,
    mtbf,
    mttr,
    oee,
    task_completion_rate,
)
from .base import Profile, register


class ManufacturingProfile(Profile):
    def __init__(self) -> None:
        super().__init__(
            slug="manufacturing",
            name="具身机器人 / 制造业",
            is_industrial=True,
            primary_connectors=["opcua", "mqtt_sparkplug", "ros2_bag", "mes", "historian"],
            kpi_catalogue={
                "oee": "OEE 设备综合效率（A×P×Q，世界级≥85%）",
                "mtbf": "MTBF 平均无故障时间（h）",
                "mttr": "MTTR 平均修复时间（h，越低越好）",
                "first_pass_yield": "FPY 一次合格率",
                "dpmo": "DPMO 百万机会缺陷数（越低越好）",
                "grasp_success_rate": "抓取成功率（DexNet ~80% 基准）",
                "task_completion_rate": "任务完成率",
                "collision_intervention_rate": "碰撞/干预率（越低越好）",
            },
            description=(
                "工厂/机器人场景：OPC UA/MQTT-Sparkplug/ROS2 接入；"
                "OEE/MTBF/抓取率评估；启用 FAT/SAT、功能安全、CE、工会、air-gap、班次 gate。"
            ),
        )
        register(self)

    def compute_kpis(self, samples: list[dict]) -> dict[str, float]:
        """Aggregate per-station/per-cycle records into factory KPIs.

        Each sample dict may carry: availability, performance, quality (for
        OEE), uptime_hours, failures, repair_hours (MTBF/MTTR), good_units,
        started_units, defect_opportunities (FPY/DPMO), grasp_successes,
        grasp_attempts, tasks_succeeded, tasks_attempted, interventions,
        cycles.
        """
        if not samples:
            return dict.fromkeys(self.kpi_catalogue, 0.0)

        agg = _aggregate(samples)

        return {
            "oee": oee(agg["availability"], agg["performance"], agg["quality"]),
            "mtbf": mtbf(agg["total_uptime_hours"], agg["total_failures"]),
            "mttr": mttr(agg["total_repair_hours"], agg["total_failures"]),
            "first_pass_yield": first_pass_yield(agg["good_units"], agg["started_units"]),
            "dpmo": dpmo(agg["defects"], agg["started_units"], agg["opportunities_per_unit"]),
            "grasp_success_rate": grasp_success_rate(agg["grasp_successes"], agg["grasp_attempts"]),
            "task_completion_rate": task_completion_rate(agg["tasks_succeeded"], agg["tasks_attempted"]),
            "collision_intervention_rate": collision_intervention_rate(agg["interventions"], agg["cycles"]),
        }


def _mean(samples: list[dict], key: str) -> float:
    vals = [s[key] for s in samples if key in s and s[key] is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _sum(samples: list[dict], key: str) -> float:
    return sum(s.get(key, 0) or 0 for s in samples)


def _aggregate(samples: list[dict]) -> dict:
    return {
        "availability": _mean(samples, "availability"),
        "performance": _mean(samples, "performance"),
        "quality": _mean(samples, "quality"),
        "total_uptime_hours": _sum(samples, "uptime_hours"),
        "total_failures": _sum(samples, "failures"),
        "total_repair_hours": _sum(samples, "repair_hours"),
        "good_units": _sum(samples, "good_units"),
        "started_units": _sum(samples, "started_units"),
        "defects": _sum(samples, "defects"),
        "opportunities_per_unit": _mean(samples, "opportunities_per_unit") or 1.0,
        "grasp_successes": _sum(samples, "grasp_successes"),
        "grasp_attempts": _sum(samples, "grasp_attempts"),
        "tasks_succeeded": _sum(samples, "tasks_succeeded"),
        "tasks_attempted": _sum(samples, "tasks_attempted"),
        "interventions": _sum(samples, "interventions"),
        "cycles": _sum(samples, "cycles"),
    }
