"""The 18-phase FDE engagement lifecycle.

This is the codified "complete on-site SOP" — the four zones a real FDE
engagement moves through, derived from Palantir's forward-deployed model,
OpenAI/Anthropic customer-engineering practice, and the manufacturing/OT
safety literature (see docs/fde_sop_full.md for sources).

A naive "5-step" model (connect → corpus → deploy → eval → flywheel) covers
only the Build zone. This module makes the full lifecycle explicit and
ordered, so the engagement state machine can advance/rollback with gates.

Industrial overlay: phases flagged ``industrial=True`` only apply when the
engagement profile is manufacturing/robotics (FAT/SAT, functional safety,
conformity, works council, air-gap, shift handover). Software/SaaS profiles
skip them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Zone(str, Enum):
    """The four zones of an FDE engagement."""

    PRE_ENGAGEMENT = "pre_engagement"
    BUILD = "build"
    OPERATIONALIZATION = "operationalization"
    HANDOFF = "handoff"


@dataclass(frozen=True)
class Phase:
    """One phase of the SOP."""

    index: int
    slug: str
    name: str
    zone: Zone
    industrial: bool = False  # True = only for manufacturing/robotics profiles
    gate: str | None = None   # gate slug that must pass before leaving this phase
    description: str = ""


# The canonical 18-phase sequence (Zone A: 1-4, Zone B: 5-10,
# Zone C: 11-15, Zone D: 16-18).
PHASES: list[Phase] = [
    # --- Zone A: Pre-engagement ------------------------------------------------
    Phase(1, "qualification", "项目立项与问题框定", Zone.PRE_ENGAGEMENT,
          description="客户带着问题而非平台来。判定是否 FDE-worthy：高价值、数据难、客户集中。"),
    Phase(2, "site_survey", "现场勘察 / Gemba walk", Zone.PRE_ENGAGEMENT,
          industrial=True,
          gate="site_survey",
          description="物理环境、OT 网络、资产清单、安全约束。工业现场独有。"),
    Phase(3, "stakeholder_map", "干系人地图与对齐", Zone.PRE_ENGAGEMENT,
          description="识别执行发起人 + 第二发起人（防 Sponsor Collapse）。统一成功标准。"),
    Phase(4, "success_criteria", "成功标准契约化", Zone.PRE_ENGAGEMENT,
          gate="success_criteria",
          description="可度量结果 + 书面 done 定义（≤14d 集成、≤90d 上线、≤120d 交接）。"),
    # --- Zone B: Build ---------------------------------------------------------
    Phase(5, "connect", "数据接入", Zone.BUILD,
          description="连接器把客户数据接进来（OPC UA / MQTT / CSV / Zammad…）。"),
    Phase(6, "corpus", "语料锻造", Zone.BUILD,
          description="清洗 → 覆盖度 → 合成补盲 → 报告。"),
    Phase(7, "prototype_real_data", "真实未策展数据上原型", Zone.BUILD,
          description="在生产形态的真实数据上原型，不用策展测试集——这是 demo→production 落差的主因。"),
    Phase(8, "validate", "干系人验证", Zone.BUILD,
          description="与真实干系人（含冲突成功指标的）验证。"),
    Phase(9, "deploy", "部署上线", Zone.BUILD,
          industrial=True,
          gate="fat_sat",
          description="工业现场：FAT→发货→SAT→commissioning。SaaS 直接上线。"),
    Phase(10, "eval", "评估交付", Zone.BUILD,
          description="用评估框架证明价值；bad cases 是持续调优抓手。"),
    # --- Zone C: Operationalization --------------------------------------------
    Phase(11, "slo_sla", "SLO/SLA + on-call", Zone.OPERATIONALIZATION,
          gate="slo",
          description="错误预算、告警路由、升级路径、含 FDE 的 on-call 轮值。"),
    Phase(12, "runbook", "Runbook 编写", Zone.OPERATIONALIZATION,
          description="事件响应、回滚、安全失败模式。"),
    Phase(13, "monitoring_drift", "监控与漂移检测", Zone.OPERATIONALIZATION,
          description="AI 是概率性的，暴露在生产数据上会退化。"),
    Phase(14, "change_mgmt_training", "变更管理 + 终用户培训", Zone.OPERATIONALIZATION,
          industrial=True,
          gate="works_council",
          description="工业现场含工会/works-council 共决。"),
    Phase(15, "flywheel_productization", "飞轮 → 产品化", Zone.OPERATIONALIZATION,
          description="现场学习回流核心产品（每周产品化评审，≥1 个特性产品化）。"),
    # --- Zone D: Handoff / Exit -----------------------------------------------
    Phase(16, "ops_handoff", "运维移交", Zone.HANDOFF,
          description="所有权转交 Customer Success / 客户运维。"),
    Phase(17, "knowledge_transfer", "知识转移", Zone.HANDOFF,
          description="文档包：runbook + eval 报告 + SLO + 模型卡 + 培训材料。"),
    Phase(18, "disengage", "退场", Zone.HANDOFF,
          gate="handoff_signoff",
          description="上线后 ≤120d 转交。无限 pilot 是反模式。"),
]


def phase_by_slug(slug: str) -> Phase:
    for p in PHASES:
        if p.slug == slug:
            return p
    raise KeyError(f"Unknown phase: {slug!r}")


def phases_for_profile(is_industrial: bool) -> list[Phase]:
    """Return phases visible to a profile (industrial phases included/excluded)."""
    if is_industrial:
        return list(PHASES)
    return [p for p in PHASES if not p.industrial]


def next_phase(current: str, is_industrial: bool) -> Phase | None:
    seq = phases_for_profile(is_industrial)
    for i, p in enumerate(seq):
        if p.slug == current:
            return seq[i + 1] if i + 1 < len(seq) else None
    return None
