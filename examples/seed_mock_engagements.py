"""Seed the Web UI with realistic mock engagements.

Each mock is grounded in a real, publicly announced Alibaba Cloud customer
(2025-2026: GAC full-stack AI, FAW "Hongqi Yunmei" agent, FAW-VW plant
digitalization, Eclicktech overseas-marketing AI, CaoCao Mobility, Guming
new-tea retail). The vertical / phase / gate data is illustrative.

Beyond the engagement contexts the script also fills the two libraries the
console UI renders from, so no page opens empty:

    - 现场记录 (journal): 5-8 back-dated field notes per engagement, kind-mixed
      (research / implementation / optimization), chronologically ordered and
      timeline-consistent with the engagement's gate records, some linked to
      seeded skills.
    - 技能库 (skills): enriches the four starter skills and seeds a reusable
      cross-project library (published) plus a working draft review queue
      (gate hints, auto-captured incidents, pending proposals) via the real
      ``SkillService`` so they are store-consistent.

Run from the repo root:

    .venv/bin/python examples/seed_mock_engagements.py

The script writes one JSON context per engagement into ``.fde_scope/engagements``
(the same directory the Web UI reads). Gate records are produced by the real
engines (``Engagement.evaluate_gate``) so they are always self-consistent with
the context; only ``checked_at`` is back-dated to a plausible timeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fde_scope.corpus.report import save_html  # noqa: E402
from fde_scope.corpus.types import (  # noqa: E402
    CorpusItem,
    CorpusReport,
    CorpusSplit,
    CoverageReport,
    Provenance,
)
from fde_scope.engagement import Engagement, EngagementContext  # noqa: E402
from fde_scope.engagement.context import (  # noqa: E402
    JournalEntry,
    SafetyPosture,
    SiteInfo,
    SLOSpec,
    Stakeholder,
)
from fde_scope.engagement.handoff import build_handoff_package  # noqa: E402
from fde_scope.engagement.operationalization import render_runbook  # noqa: E402
from fde_scope.skills.models import (  # noqa: E402
    SkillCategory,
    SkillDraft,
    SkillPatch,
    SkillSource,
    SkillStatus,
)
from fde_scope.skills.service import SkillService  # noqa: E402
from fde_scope.skills.store import SkillStore  # noqa: E402

_OUT_DIR = Path(".fde_scope/engagements")
_SKILLS_DIR = Path(".fde_scope/skills")
_REPORTS_DIR = Path("reports")


def _st(name: str, role: str, sponsor: bool = False, metric: str = "") -> Stakeholder:
    return Stakeholder(name=name, role=role, is_sponsor=sponsor, success_metric=metric)


def _slo(name: str, target: str, route: str = "primary-oncall", window: str = "28d", budget: str = "") -> SLOSpec:
    return SLOSpec(name=name, target=target, error_budget=budget, alert_route=route, window=window)


def _run_gates(eng: Engagement, timeline: dict[str, str]) -> None:
    """Evaluate gates in order, then back-date each record's checked_at."""
    for slug, ts in timeline.items():
        eng.evaluate_gate(slug)
        eng.ctx.gate_records[slug].checked_at = ts


def _save(eng: Engagement) -> Path:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    return eng.ctx.save(_OUT_DIR / f"{eng.ctx.id}.json")


def _split(name: str, n: int, category: str = "语料样本") -> CorpusSplit:
    """A slice with real item records so the report's split sizes are honest."""
    return CorpusSplit(
        name=name,
        items=[
            CorpusItem(
                id=f"{name}-{i}",
                content=f"{category} #{i}",
                category=category,
                channel="seed",
                quality_score=4.5,
                provenance=Provenance.REAL,
            )
            for i in range(n)
        ],
    )


def _write_reports(
    slug: str,
    ctx: EngagementContext,
    *,
    categories: dict[str, int],
    target_per_category: int,
    real: int,
    synthetic: int,
    golden: int,
    dropped: int,
    pii: int,
    eval_metrics: dict[str, float],
    monitoring_enabled: bool = True,
) -> tuple[str, str]:
    """Generate the two tangible deliverables (runbook + corpus report).

    Both files are produced by the engine's own renderers so they look and
    behave exactly like real FDE outputs; the Web UI serves them under
    ``/reports/``. Returns (runbook_path, corpus_report_path).
    """
    _REPORTS_DIR.mkdir(exist_ok=True)
    runbook_path = f"reports/{slug}-runbook.md"
    corpus_path = f"reports/{slug}-corpus.html"
    (_REPORTS_DIR / f"{slug}-runbook.md").write_text(
        render_runbook(ctx, agent_name=f"{slug}-agent"), encoding="utf-8"
    )
    coverage = CoverageReport(category_counts=categories, target_per_category=target_per_category)
    coverage.identify_gaps()
    report = CorpusReport(
        total=real + synthetic,
        real=real,
        synthetic=synthetic,
        golden=golden,
        coverage=coverage,
        train=_split("train", int(real * 0.8)),
        eval=_split("eval", int(real * 0.15)),
        test=_split("test", int(real * 0.05)),
        dropped=dropped,
        pii_entities_masked=pii,
    )
    save_html(report, _REPORTS_DIR / f"{slug}-corpus.html")
    # deep assets: deliverables + eval + monitoring posture
    ctx.assets.update(
        {
            "runbook": runbook_path,
            "corpus_report": corpus_path,
            "eval_metrics": eval_metrics,
            "monitoring": {
                "data_drift": {
                    "enabled": monitoring_enabled,
                    "cadence": "daily",
                    "threshold": "PSI > 0.2",
                },
                "quality_drift": {"enabled": monitoring_enabled, "cadence": "weekly"},
                "feedback_latency": {"target_hours": 24},
                "dashboards": [{"name": "quality-dashboard", "url": f"/{corpus_path}"}],
            },
        }
    )
    return runbook_path, corpus_path


# ---------------------------------------------------------------------------
# 1) Guming — new-tea retail chain, full lifecycle DONE (Zone D)
# ---------------------------------------------------------------------------
def guming() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-guming-ticket-seed01",
        customer="古茗茶饮（Guming）",
        profile="ticket",
        current_phase="disengage",
        stakeholders=[
            _st("王芳", "副总裁 · 数字化中心", True, "门店周订货准确率 ≥98%"),
            _st("陈宇", "CTO", True, "全渠道会员 DAU 增长 30%"),
            _st("林晓", "供应链总监"),
            _st("赵磊", "数据平台负责人"),
        ],
        success_criteria=[
            "≤14d 完成门店经营数据接入（RocketMQ 实时链路，瞬时 10w+ TPS）",
            "≤90d 上线 AI 订货预测 agent，覆盖 90% 门店",
            "订货预测 MAE 较基线下降 ≥20%",
            "≤120d 完成运维移交，SLO 达成 99.5%",
        ],
        slos=[
            _slo("availability", "99.5%", window="14d", budget="3.6h 停机预算 / 14d 滚动"),
            _slo("forecast_latency_p95", "<8s", budget="预算内 · 近 7d P95 6.2s"),
            _slo("bad_case_rate", "<10%", route="fde-oncall", budget="已耗 21% · 近 14d 均值 2.1%"),
        ],
        assets={
            "corpus_summary": "32.4k 门店样本 · 86 个 SKU 维度 · 3 个数据源",
            "model_name": "guming-order-forecast-v2",
            "known_limitations": ["新开店首周预测偏差大", "促销叠加日样本稀疏"],
        },
    )
    runbook_path, corpus_path = _write_reports(
        "guming",
        ctx,
        categories={"订货建议": 9800, "缺货预警": 4200, "促销预测": 2600, "新品预测": 1900},
        target_per_category=5000,
        real=21000,
        synthetic=8600,
        golden=3400,
        dropped=1240,
        pii=86,
        eval_metrics={"forecast_mae": 12.4, "hit_rate_1d": 0.91, "bad_case_rate": 0.06, "eval_samples": 4200},
    )
    build_handoff_package(
        ctx,
        runbook_path=runbook_path,
        eval_report_path=corpus_path,
        training_material="店长培训包 v2（16 场）",
        customer_accepted=True,
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "success_criteria": "2026-05-10T09:00:00+08:00",
            "slo": "2026-07-05T14:30:00+08:00",
            "handoff_signoff": "2026-08-10T11:00:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 2) FAW-VW — automotive manufacturing digitalization, Zone C mid
# ---------------------------------------------------------------------------
def faw_vw() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-fawvw-manufacturing-seed02",
        customer="一汽-大众（FAW-VW）",
        profile="manufacturing",
        current_phase="runbook",
        site=SiteInfo(
            location="长春市汽车经济技术开发区 · 一厂总装车间",
            ot_it_separated=True,
            air_gapped=False,
            networks=["PROFINET 产线环网", "OPC UA 汇聚层", "IT 办公网（隔离）"],
            assets=[
                {
                    "name": "总装线 PLC #2",
                    "type": "PLC",
                    "vendor": "Siemens",
                    "protocol": "S7",
                    "criticality": "high",
                },
                {
                    "name": "焊接机器人 #7",
                    "type": "机器人",
                    "vendor": "ABB",
                    "protocol": "OPC UA",
                    "criticality": "high",
                },
                {
                    "name": "拧紧枪工位 12",
                    "type": "装配执行器",
                    "vendor": "KUKA",
                    "protocol": "PROFINET",
                    "criticality": "medium",
                },
                {
                    "name": "视觉质检相机线 A",
                    "type": "视觉",
                    "vendor": "Basler",
                    "protocol": "GigE",
                    "criticality": "medium",
                },
            ],
            shift_count=3,
            works_council_represented=True,
            notes="数字孪生仿真推演已覆盖总装主线；OT 与 IT 已按分区隔离。",
        ),
        stakeholders=[
            _st("孙建国", "生产数字化负责人", True, "产线停机时间降低 15%"),
            _st("李敏", "IT 总监", True, "OT 数据 90 天可回溯"),
            _st("周强", "总装车间经理"),
            _st("刘洋", "维修班组长"),
        ],
        success_criteria=[
            "≤14d 完成总装车间 OPC UA 数据接入（≥200 个测点）",
            "≤90d 上线产线异常诊断 agent，MTTR 下降 ≥20%",
            "≤120d 移交；bad_case_rate <5%",
        ],
        safety=SafetyPosture(
            required_plr="d",
            achieved_pl="d",
            sil_required=2,
            sil_achieved=2,
            iso10218_assessed=True,
            eu_ai_act_high_risk=True,
            ce_marking_done=True,
            hazard_analysis_done=True,
            risk_assessment_notes="HAZOP-lite 完成，覆盖焊接工位人机协作区。",
        ),
        slos=[
            _slo("availability", "99.5%", window="14d", budget="50min 停机预算 / 14d 滚动"),
            _slo("opcua_ingest_p95", "<1s", budget="预算内 · 熔断阈值 P99 <2.5s"),
            _slo("bad_case_rate", "<5%", route="fde-oncall", budget="已耗 28% · 试运行实测 1.4%"),
        ],
        assets={
            "fat": {
                "passed": True,
                "signed_off_by": "孙建国（客户）/ 集成商项目经理",
                "notes": "总装线诊断 agent 出厂测试通过",
            },
            "sat": {"passed": True, "signed_off_by": "周强（车间经理）", "notes": "现场 48h 试运行通过"},
            "technical_construction_file": "reports/fawvw-technical-file.pdf",
            "works_council_approval": {"status": "approved", "signed_off_by": "工会代表 · 长春基地"},
            "shift_handover": {"digital_log_integrated": True, "per_shift_runbook": True},
            "corpus_summary": "产线样本 1.2M 行 · 测点 208 · 故障标签 34 类",
            "model_name": "fawvw-line-diagnose-v1.1",
            "known_limitations": ["冬季冷启动工况样本不足", "新车型切换首周误报率偏高"],
        },
    )
    _write_reports(
        "fawvw",
        ctx,
        categories={
            "焊接缺陷": 2600,
            "装配异常": 2100,
            "停机预警": 1800,
            "参数漂移": 1500,
            "冷启动工况": 600,
        },
        target_per_category=1600,
        real=8600,
        synthetic=2400,
        golden=500,
        dropped=312,
        pii=0,
        eval_metrics={
            "diagnose_accuracy": 0.94,
            "mttr_reduction": 0.22,
            "false_positive_rate": 0.05,
            "eval_samples": 1900,
        },
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "site_survey": "2026-05-28T10:00:00+08:00",
            "success_criteria": "2026-06-08T15:00:00+08:00",
            "air_gap": "2026-06-20T09:30:00+08:00",
            "fat_sat": "2026-07-15T16:00:00+08:00",
            "functional_safety": "2026-07-16T10:00:00+08:00",
            "conformity": "2026-07-18T14:00:00+08:00",
            "slo": "2026-08-05T11:00:00+08:00",
            "shift_handover": "2026-08-06T09:00:00+08:00",
            "works_council": "2026-08-06T09:30:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 3) GAC — full-stack AI, currently BLOCKED at deploy gates (Zone B tail)
# ---------------------------------------------------------------------------
def gac() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-gac-manufacturing-seed03",
        customer="广汽集团（GAC）",
        profile="manufacturing",
        current_phase="deploy",
        site=SiteInfo(
            location="广州市番禺区化龙镇 · 广汽乘用车工厂",
            ot_it_separated=True,
            air_gapped=False,
            networks=["PROFINET 总装环网", "OPC UA 汇聚", "5G 园区专网"],
            assets=[
                {
                    "name": "焊装主线 PLC",
                    "type": "PLC",
                    "vendor": "Siemens",
                    "protocol": "S7",
                    "criticality": "high",
                },
                {
                    "name": "智能座舱 HIL 台架",
                    "type": "测试台架",
                    "vendor": "dSPACE",
                    "protocol": "CAN/LIN",
                    "criticality": "high",
                },
                {
                    "name": "AGV 车队 #3",
                    "type": "物流机器人",
                    "vendor": "GAC 自研",
                    "protocol": "5G",
                    "criticality": "medium",
                },
            ],
            shift_count=2,
            works_council_represented=False,
            notes="全栈 AI 战略合作（2025-11 签约）；座舱 + 产线双线推进。",
        ),
        stakeholders=[
            _st("何伟", "智能网联中心总经理", True, "座舱 AI 首月激活率 ≥60%"),
            _st("吴倩", "数字化部总监", True, "产线数据上云 ≤90d"),
            _st("郑凯", "焊装车间主任"),
        ],
        success_criteria=[
            "≤14d 接入焊装 + 座舱 HIL 数据",
            "≤90d 上线座舱语音 agent（Qwen 底座）与产线质检试点",
            "≤120d 移交；bad_case_rate <8%",
        ],
        safety=SafetyPosture(
            required_plr="c",
            achieved_pl="c",
            sil_required=1,
            sil_achieved=1,
            iso10218_assessed=True,
            eu_ai_act_high_risk=True,
            ce_marking_done=False,
            hazard_analysis_done=False,
            risk_assessment_notes="风险评估进行中——第三方机构已进场。",
        ),
        slos=[],
        assets={
            "fat": {"passed": True, "signed_off_by": "何伟（客户）", "notes": "座舱语音 agent FAT 通过"},
            "corpus_summary": "座舱语料 8.6k 条 · 产线图像 45k 张",
            "model_name": "gac-cabin-assistant-v1",
            "known_limitations": ["粤语方言识别待优化"],
        },
    )
    _write_reports(
        "gac",
        ctx,
        categories={"座舱指令": 3400, "质检缺陷": 2600, "粤语方言": 900, "多轮对话": 1200},
        target_per_category=2400,
        real=6800,
        synthetic=3100,
        golden=200,
        dropped=420,
        pii=18,
        eval_metrics={
            "command_accuracy": 0.89,
            "defect_recall": 0.92,
            "cantonese_cer": 0.21,
            "eval_samples": 1500,
        },
        monitoring_enabled=False,
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "site_survey": "2026-07-05T09:00:00+08:00",
            "success_criteria": "2026-07-15T14:00:00+08:00",
            "air_gap": "2026-07-28T10:00:00+08:00",
            # deploy 阶段三个 gate 均在 2026-08-18 被真实引擎判为 fail
            "fat_sat": "2026-08-18T09:00:00+08:00",
            "functional_safety": "2026-08-18T09:10:00+08:00",
            "conformity": "2026-08-18T09:20:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 4) FAW — "Hongqi Yunmei" enterprise agent, Zone C tail
# ---------------------------------------------------------------------------
def faw() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-faw-ticket-seed04",
        customer="中国一汽（FAW）",
        profile="ticket",
        current_phase="flywheel_productization",
        stakeholders=[
            _st("张立群", "集团 CIO", True, "全集团 8 万人周活跃率 ≥40%"),
            _st("陈晓东", "数字化部总经理", True, "单次问答成本下降 60%"),
            _st("马静", "红旗营销部数字化负责人"),
            _st("于涛", "HR 系统负责人"),
        ],
        success_criteria=[
            "≤14d 接入集团制度/流程/产品资料知识库",
            "≤90d 红旗云妹覆盖全集团办公问答 + 多领域智能 BI",
            "≤120d 移交；bad_case_rate <10%",
        ],
        slos=[
            _slo("availability", "99.5%", window="14d", budget="50min 停机预算 / 14d 滚动"),
            _slo("qa_latency_p95", "<3s", budget="已耗 35% · 近 7d P95 2.4s"),
            _slo("bad_case_rate", "<10%", route="fde-oncall", budget="抽检 200 条/周 · 已耗 46%"),
        ],
        assets={
            "corpus_summary": "制度库 12.8k 篇 · BI 指标 460 个 · 6 个业务域",
            "model_name": "yunmei-v1.4 (qwen 底座)",
            "known_limitations": ["跨部门数据权限边界偶发误答", "长文档引用溯源待增强"],
            "productized_features": ["智能 BI 问数", "制度问答（已产品化评审通过）"],
        },
    )
    _write_reports(
        "faw",
        ctx,
        categories={"制度问答": 5600, "BI 问数": 3200, "流程办理": 1800, "产品知识": 2200},
        target_per_category=3000,
        real=12800,
        synthetic=4200,
        golden=1500,
        dropped=890,
        pii=214,
        eval_metrics={
            "answer_accuracy": 0.93,
            "bi_sql_correctness": 0.88,
            "bad_case_rate": 0.07,
            "eval_samples": 3100,
        },
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "success_criteria": "2026-06-25T10:00:00+08:00",
            "slo": "2026-08-01T15:00:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 5) CaoCao Mobility — ride-hailing platform, Zone B mid
# ---------------------------------------------------------------------------
def caocao() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-caocao-ticket-seed05",
        customer="曹操出行（CaoCao）",
        profile="ticket",
        current_phase="prototype_real_data",
        stakeholders=[
            _st("罗永浩", "技术 VP", True, "AI 客服拦截率 ≥60%"),
            _st("邓丽君", "数据总监", True, "146 城订单数据 ≤14d 接入"),
            _st("钱锋", "客服中心负责人"),
            _st("孙丽", "司机端产品经理"),
        ],
        success_criteria=[
            "≤14d 接入 146 城订单/行程/投诉明细",
            "≤90d AI 客服上线，拦截率 ≥60%、人工工单下降 30%",
            "≤120d 移交；bad_case_rate <8%",
        ],
        slos=[],
        assets={
            "corpus_summary": "订单样本 5.2M 行 · 投诉 41k 条 · 司机侧会话 12k 条",
            "model_name": "caocao-driver-support-v1",
            "known_limitations": ["方言/口语化投诉理解待提升"],
            "prototype_notes": "真实未策展数据原型已跑通：客服工单自动分类 + 处置建议。",
        },
    )
    _write_reports(
        "caocao",
        ctx,
        categories={"投诉处理": 21000, "调度咨询": 9800, "发票报销": 7400, "司机准入": 5200},
        target_per_category=8000,
        real=52000,
        synthetic=8600,
        golden=1200,
        dropped=2400,
        pii=8900,
        eval_metrics={
            "deflection_rate": 0.63,
            "resolution_accuracy": 0.91,
            "bad_case_rate": 0.08,
            "eval_samples": 6600,
        },
        monitoring_enabled=False,
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "success_criteria": "2026-07-30T11:00:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 6) Eclicktech — overseas-marketing AI, Zone A (just signed, gate blocked)
# ---------------------------------------------------------------------------
def eclicktech() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-eclicktech-ticket-seed06",
        customer="易点天下（Eclicktech）",
        profile="ticket",
        current_phase="success_criteria",
        stakeholders=[
            # 只有 1 个 sponsor —— SuccessCriteriaGate 将判 fail（Sponsor Collapse 反模式）
            _st("徐超", "海外业务 COO", True, "AI 素材生产效率提升 50%"),
            _st("高媛", "市场 VP"),
        ],
        success_criteria=[
            "≤14d 接入广告投放与素材生产数据",
            "≤90d 上线出海素材智能生产 agent，单条素材成本下降 40%",
        ],
        slos=[],
        assets={
            "note": "2026-08-08 与阿里云签署全面深化合作（出海营销 + AI 应用）；第二发起人待确认。",
        },
    )
    _write_reports(
        "eclicktech",
        ctx,
        categories={"素材文案": 1400, "投放策略": 900, "KOL 匹配": 700, "多语种翻译": 400},
        target_per_category=1200,
        real=3400,
        synthetic=5600,
        golden=300,
        dropped=610,
        pii=42,
        eval_metrics={"copy_acceptance": 0.76, "cost_reduction_pct": 0.18, "eval_samples": 800},
        monitoring_enabled=False,
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "success_criteria": "2026-08-15T09:00:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 7) BMW Brilliance — air-gapped automotive plant, Zone D entry (all gates pass)
# ---------------------------------------------------------------------------
def bmw_brilliance() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-bmw-manufacturing-seed07",
        customer="华晨宝马（BMW Brilliance）",
        profile="manufacturing",
        current_phase="change_mgmt_training",
        site=SiteInfo(
            location="沈阳市铁西区 · 大东工厂总装车间",
            ot_it_separated=True,
            air_gapped=True,
            networks=["PROFINET 产线环网（园区内）", "OPC UA 汇聚层", "5G 园区专网（无外联）"],
            assets=[
                {
                    "name": "总装线拧紧轴群",
                    "type": "装配执行器",
                    "vendor": "Atlas Copco",
                    "protocol": "OPC UA",
                    "criticality": "high",
                },
                {
                    "name": "涂装车间送风机组",
                    "type": "HVAC",
                    "vendor": "Wagner",
                    "protocol": "Modbus TCP",
                    "criticality": "medium",
                },
                {
                    "name": "车身物流 AGV 群",
                    "type": "物流机器人",
                    "vendor": "Jungheinrich",
                    "protocol": "WLAN/5G",
                    "criticality": "medium",
                },
            ],
            shift_count=3,
            works_council_represented=True,
            notes="生产网与互联网物理隔离（air-gap）；边缘推理全部本地化，模型更新走摆渡盘。",
        ),
        stakeholders=[
            _st("Klaus Berger", "工厂数字化总监", True, "总装 OEE 提升 2pp"),
            _st("梁爽", "IT 基础架构经理", True, "气隙环境零安全事件"),
            _st("宋明", "总装车间高级经理"),
            _st("Andrea Wolf", "工会代表"),
        ],
        success_criteria=[
            "≤14d 完成总装/涂装 12 万条工艺参数 + 60k 张质检图像本地接入",
            "≤90d 上线装配异常诊断 agent（边缘部署），诊断准确率 ≥92%",
            "≤120d 移交；气隙架构下 SLO 99.5% 达成",
        ],
        safety=SafetyPosture(
            required_plr="d",
            achieved_pl="d",
            sil_required=2,
            sil_achieved=2,
            iso10218_assessed=True,
            eu_ai_act_high_risk=True,
            ce_marking_done=True,
            hazard_analysis_done=True,
            risk_assessment_notes="气隙环境下人机协作区风险评估完成，edge 机柜 EHS 会审通过。",
        ),
        slos=[
            _slo("availability", "99.5%", window="14d", budget="50min 停机预算 / 14d 滚动"),
            _slo("diagnose_latency_p95", "<2s", budget="连续 5min 超 3s 触发产线告警"),
            _slo("bad_case_rate", "<4%", route="fde-oncall", budget="已耗 38% · 产线验收基线 1.2%"),
        ],
        assets={
            "air_gap_plan": {
                "edge_hardware": "8 × 边缘推理一体机（A800），机柜位于总装车间配电间",
                "offline_model_update": "摆渡盘 + SHA256 签名校验 + 回滚镜像，双人在场",
                "telemetry_egress_allowed": False,
                "local_storage": "本地对象存储 48TB，保留 180d",
            },
            "fat": {
                "passed": True,
                "signed_off_by": "Klaus Berger（客户）/ 集成商 PM",
                "notes": "出厂测试含离线工况脚本 8h 全覆盖",
            },
            "sat": {"passed": True, "signed_off_by": "宋明（车间高级经理）", "notes": "48h 伴跑误报 4.1%"},
            "works_council_approval": {"status": "approved", "signed_off_by": "Andrea Wolf（工会代表）"},
            "shift_handover": {"digital_log_integrated": True, "per_shift_runbook": True},
            "corpus_summary": "工艺参数 12 万条 · 质检图像 60k 张（本地存储）",
            "model_name": "bmw-assembly-diagnose-v1.2 (edge)",
            "known_limitations": ["涂装送风机组 Modbus 采样粒度粗（1min）", "AGV 调度数据暂未接入"],
        },
    )
    _write_reports(
        "bmw",
        ctx,
        categories={
            "装配异常": 3200,
            "拧紧扭矩漂移": 2100,
            "质检缺陷": 1800,
            "物流阻塞": 900,
        },
        target_per_category=2000,
        real=7400,
        synthetic=1600,
        golden=420,
        dropped=188,
        pii=0,
        eval_metrics={
            "diagnose_accuracy": 0.95,
            "oee_delta_pp": 2.1,
            "false_positive_rate": 0.041,
            "eval_samples": 1500,
        },
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "site_survey": "2026-03-12T10:00:00+08:00",
            "success_criteria": "2026-03-20T14:00:00+08:00",
            "air_gap": "2026-04-02T09:30:00+08:00",
            "fat_sat": "2026-05-12T16:00:00+08:00",
            "functional_safety": "2026-05-14T10:00:00+08:00",
            "conformity": "2026-05-16T14:00:00+08:00",
            "slo": "2026-06-05T11:00:00+08:00",
            "shift_handover": "2026-06-06T09:00:00+08:00",
            "works_council": "2026-07-10T09:30:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 8) Chery — Wuhu plant, early Zone B (connect), fresh timeline, no deliverables yet
# ---------------------------------------------------------------------------
def chery() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-chery-manufacturing-seed08",
        customer="奇瑞汽车（Chery）",
        profile="manufacturing",
        current_phase="connect",
        site=SiteInfo(
            location="芜湖市鸠江区 · 一期总装车间",
            ot_it_separated=True,
            air_gapped=False,
            networks=["PROFINET 产线环网", "Modbus 老产线段（经网关）", "IT 办公网"],
            assets=[
                {
                    "name": "总装拧紧枪群",
                    "type": "装配执行器",
                    "vendor": "Bosch Rexroth",
                    "protocol": "OPC UA",
                    "criticality": "high",
                },
                {
                    "name": "老产线输送段（Modbus）",
                    "type": "输送线 PLC",
                    "vendor": "Mitsubishi",
                    "protocol": "Modbus TCP",
                    "criticality": "medium",
                },
                {
                    "name": "Andon 系统",
                    "type": "工位呼叫",
                    "vendor": "客户自研",
                    "protocol": "TCP/数据库",
                    "criticality": "medium",
                },
            ],
            shift_count=2,
            works_council_represented=False,
            notes="老产线 Modbus 占比 40%，网关转换方案选型中；Andon/MES 接口权限审批中。",
        ),
        stakeholders=[
            _st("黄志强", "制造数字化总监", True, "异常诊断 MTTR 下降 20%"),
            _st("吴敏", "质量部部长", True, "质检漏检率 <3%"),
            _st("李锐", "总装车间主任"),
        ],
        success_criteria=[
            "≤14d 完成总装 156 测点接入（含 Modbus 网关转换）",
            "≤90d 上线产线异常诊断 agent，MTTR 下降 ≥20%",
            "≤120d 移交；质检漏检率 <3%",
        ],
        safety=SafetyPosture(
            required_plr="c",
            achieved_pl="c",
            sil_required=1,
            sil_achieved=1,
            iso10218_assessed=True,
            eu_ai_act_high_risk=False,
            ce_marking_done=False,
            hazard_analysis_done=True,
            risk_assessment_notes="输送段人机协作风险评估完成；无出口欧盟车型产线，CE 暂不适用。",
        ),
        slos=[],
        assets={
            "corpus_summary": "首批测点接入中（OPC UA 94 / Modbus 62）",
            "model_name": "（待定，候选 qwen 底座 + 产线诊断微调）",
            "known_limitations": ["Andon/MES 接口权限审批中（客户 IT 5 个工作日流程）"],
        },
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "site_survey": "2026-08-06T10:00:00+08:00",
            "success_criteria": "2026-08-14T15:00:00+08:00",
            # 非气隙站点，air_gap gate 自动通过；不评估会在矩阵上误显示为阻塞
            "air_gap": "2026-08-20T09:00:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 9) Luzhou Laojiao — baijiu producer, Zone B mid (corpus), dual-scenario
# ---------------------------------------------------------------------------
def lzlj() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-lzlj-ticket-seed09",
        customer="泸州老窖（Luzhou Laojiao）",
        profile="ticket",
        current_phase="corpus",
        stakeholders=[
            _st("陈刚", "CIO", True, "经销商咨询自动应答率 ≥55%"),
            _st("周雪", "包装质检部部长", True, "包装缺陷检出率 ≥99%"),
            _st("何斌", "客服中心负责人"),
        ],
        success_criteria=[
            "≤14d 接入 CRM 工单 26k 条 + 包装质检图像 18k 张",
            "≤90d 上线经销商智能客服 + 包装质检视觉复核 agent",
            "≤120d 移交；包装缺陷检出率 ≥99%",
        ],
        slos=[],
        assets={
            "corpus_summary": "CRM 工单 26k 条 · 质检图像 18k 张（瓶身气泡占 71%，类别不均衡处理中）",
            "model_name": "（候选：客服 qwen 底座 + 缺陷检测 CV 模型）",
            "known_limitations": ["川南口音话务占比 34%，ASR 方言适配待专项"],
        },
    )
    _write_reports(
        "lzlj",
        ctx,
        categories={"防伪查询": 8000, "订单物流": 6200, "政策咨询": 4900, "投诉建议": 3100, "防伪异常": 900},
        target_per_category=5000,
        real=18000,
        synthetic=5100,
        golden=600,
        dropped=720,
        pii=3100,
        eval_metrics={"intent_accuracy": 0.86, "defect_detection_ap": 0.93, "eval_samples": 1800},
        monitoring_enabled=False,
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "success_criteria": "2026-08-08T10:30:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 10) Mengniu — dairy / cold-chain, Zone C (slo_sla), dual-scenario
# ---------------------------------------------------------------------------
def mengniu() -> EngagementContext:
    ctx = EngagementContext(
        id="eng-mengniu-ticket-seed10",
        customer="蒙牛集团（Mengniu）",
        profile="ticket",
        current_phase="slo_sla",
        stakeholders=[
            _st("郭颖", "数字化中心总经理", True, "客服拦截率 ≥50%"),
            _st("马啸", "冷链物流总监", True, "温控误报率 <30%"),
            _st("刘畅", "订奶业务负责人"),
        ],
        success_criteria=[
            "≤14d 接入订奶工单 88k 条 + 冷链温控时序 3 个月",
            "≤90d 上线订奶智能客服 + 冷链异常诊断，拦截率 ≥50%、误报率 <30%",
            "≤120d 移交；SLO 99.5%",
        ],
        slos=[
            _slo("availability", "99.5%", window="14d", budget="3.6h 停机预算 / 14d 滚动"),
            _slo("alert_response_p95", "<5min", route="cold-chain-oncall", budget="已耗 52% · 温控超限工单 4.1min"),
            _slo("bad_case_rate", "<8%", route="fde-oncall", budget="人工复核抽 5%/周 · 已耗 40%"),
        ],
        assets={
            "corpus_summary": "订奶工单 88k 条 · 冷链温控时序 3 个月 · PII 9.4k 实体脱敏",
            "model_name": "mengniu-coldchain-agent-v0.9",
            "known_limitations": ["传感器漂移误报仍 38%（目标 <30%）", "乡镇配送地址标准化率低"],
        },
    )
    _write_reports(
        "mengniu",
        ctx,
        categories={"订奶变更": 21000, "配送咨询": 14000, "冷链告警": 9600, "发票售后": 6800},
        target_per_category=12000,
        real=46000,
        synthetic=7800,
        golden=1600,
        dropped=2100,
        pii=9400,
        eval_metrics={
            "deflection_rate": 0.47,
            "sensor_drift_recall": 0.91,
            "false_alarm_rate": 0.38,
            "eval_samples": 5200,
        },
    )
    eng = Engagement(ctx)
    _run_gates(
        eng,
        {
            "success_criteria": "2026-06-11T10:00:00+08:00",
            "slo": "2026-08-01T14:00:00+08:00",
            # ticket profile 下 shift_handover 不适用（单班次+非工业），但
            # status().gate_passed 读 gate_records——不评估会在矩阵上误显示为阻塞
            "shift_handover": "2026-08-01T14:30:00+08:00",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# 技能库种子：既有 4 条 starter 技能补全正文，另补跨项目可复用技能 + 草稿队列
# ---------------------------------------------------------------------------
_SKILL_LIBRARY: list[dict] = [
    {
        "key": "site_survey_checklist",
        "title": "现场调研清单",
        "category": "research",
        "tags": ["调研", "gemba", "checklist"],
        "phase": "site_survey",
        "gate": None,
        "applies_to": ["manufacturing", "ticket"],
        "source": "manual",
        "engagement": "eng-fawvw-manufacturing-seed02",
        "published": True,
        "body": (
            "## Checklist\n"
            "1. 首件确认（客户端环境/版本）\n"
            "2. 网络拓扑与端口可达性（OT/IT 分区、气隙、专网时延实测）\n"
            "3. 数据源清单与访问权限（每源记录 owner、刷新频率、字段字典）\n"
            "4. 班次与交接方式（几班倒、纸质还是数字日志）\n"
            "5. 合规触点（工会代表、功能安全定级、数据出境）\n\n"
            "## 验收标准\n"
            "- 产出 SiteInfo 草稿 + 测点/数据源台账，sponsor 双签确认。"
        ),
    },
    {
        "key": "opcua_pitfalls",
        "title": "OPC UA 连接踩坑",
        "category": "implementation",
        "tags": ["opcua", "plc", "s7", "工业"],
        "phase": "connect",
        "gate": None,
        "applies_to": ["manufacturing"],
        "source": "manual",
        "engagement": "eng-fawvw-manufacturing-seed02",
        "published": True,
        "body": (
            "## 步骤\n"
            "1. 检查 OPC UA 端点 URL（opc.tcp://host:port）\n"
            "2. 确认安全策略匹配（None/Basic256Sha256）\n"
            "3. 证书信任链：两端互信或端点自签 + 白名单\n\n"
            "## 案例（长春一厂）\n"
            "Basic256Sha256 证书链未互信导致订阅**静默失败**——无报错但无数据。"
            "用 Wireshark 看到 BadCertificateInvalid 后改端点自签 + IP 白名单恢复。\n\n"
            "## 验收标准\n"
            "- 连续 24h 订阅无断流，测点值与 HMI 人工读数一致。"
        ),
    },
    {
        "key": "inference_latency",
        "title": "推理延迟调优",
        "category": "optimization",
        "tags": ["性能", "slo", "推理服务"],
        "phase": "slo_sla",
        "gate": "slo",
        "applies_to": ["ticket"],
        "source": "manual",
        "engagement": "eng-faw-ticket-seed04",
        "published": True,
        "body": (
            "## 方法\n"
            "1. 定位瓶颈（token 生成 vs 上下文检索 vs 网关排队）\n"
            "2. 检索召回量裁剪：top-k 50→20，重排后再取 5\n"
            "3. KV-cache 复用（system prompt + 指标口径字典前缀）\n"
            "4. 流式首 token 上报，P95 按 tok/s 单独监控\n\n"
            "## 案例（红旗云妹）\n"
            "qa_latency_p95 4.2s→2.8s，SLO <3s 达标；单次问答成本同步下降 63%。"
        ),
    },
    {
        "key": "weekly_report_template",
        "title": "现场周报模板",
        "category": "methodology",
        "tags": ["周报", "方法论", "沟通"],
        "phase": None,
        "gate": None,
        "applies_to": ["manufacturing", "ticket"],
        "source": "manual",
        "engagement": "eng-caocao-ticket-seed05",
        "published": True,
        "body": (
            "## 结构\n"
            "- 本周进展（对照 14/90/120d 里程碑给百分比，不写感受）\n"
            "- 风险与阻塞（每条带 owner + 需要客户做什么）\n"
            "- 下周计划（≤3 条，可验收）\n"
            "- 数据看板截图（KPI 走势 + bad case 抽样）\n\n"
            "## 纪律\n"
            "周报 Friday 17:00 前发 sponsor 群；阻塞项 48h 未动升级到发起人。"
        ),
    },
    {
        "key": "sponsor_collapse",
        "title": "双 sponsor 缺位的早期识别与破局",
        "category": "research",
        "tags": ["sponsor", "立项", "反模式"],
        "phase": "stakeholder_map",
        "gate": "success_criteria",
        "applies_to": ["manufacturing", "ticket"],
        "source": "manual",
        "engagement": "eng-eclicktech-ticket-seed06",
        "published": True,
        "body": (
            "## 信号\n"
            "- 干系人表只有 1 个 sponsor，其余全部无成功指标\n"
            "- 排期会采购/市场不同时到场；成功标准两次评审未签\n\n"
            "## 破局路径\n"
            "1. 从受益最大部门找第二发起人候选，逐一面访\n"
            "2. 把候选人的 KPI 翻译成成功标准里的可度量项\n"
            "3. 评审会前与两位 sponsor 预对齐，会上只做签认不做讨论\n\n"
            "## 案例（易点天下）\n"
            "海外 COO 单 sponsor 卡 gate 两周；市场 VP 面访后以「多语种素材过审率」"
            "入标准 v2，成为第二发起人。"
        ),
    },
    {
        "key": "uncurated_prototype",
        "title": "未策展真实数据原型 72h 冲刺法",
        "category": "methodology",
        "tags": ["prototype", "真实数据", "72h"],
        "phase": "prototype_real_data",
        "gate": None,
        "applies_to": ["ticket"],
        "source": "manual",
        "engagement": "eng-caocao-ticket-seed05",
        "published": True,
        "body": (
            "## 为什么不做干净数据集\n"
            "客户只相信「我自己数据跑出来的东西」。先接 3 类最脏的源"
            "（工单原文、通话转写、聊天记录），脱敏后直接进原型。\n\n"
            "## 72h 切片\n"
            "- 0-8h：数据契约 + 脱敏管道（PII 计数进日报）\n"
            "- 8-48h：最小可用 pipeline（分类/检索/建议）\n"
            "- 48-72h：离线评估 + 20 条 bad case 逐条标注\n\n"
            "## 验收标准\n"
            "- 原型 demo 数据 100% 来自客户生产库，评估集留痕可回放。"
        ),
    },
    {
        "key": "fat_sat_playbook",
        "title": "FAT/SAT 48h 试运行执行手册",
        "category": "implementation",
        "tags": ["fat", "sat", "验收"],
        "phase": "deploy",
        "gate": "fat_sat",
        "applies_to": ["manufacturing"],
        "source": "manual",
        "engagement": "eng-fawvw-manufacturing-seed02",
        "published": True,
        "body": (
            "## FAT（出厂验收）\n"
            "- 用仿真台架跑满 8h 工况脚本，覆盖率矩阵（车型 × 工况）签字\n\n"
            "## SAT（现场验收）\n"
            "- 48h 真实产线伴跑：工程师双人在场，每 2h 记录一次指标快照\n"
            "- 拦截条件：误报率 >8%、漏报 >2 例、任一安全联锁失效立即终止\n\n"
            "## 签字链\n"
            "车间经理 + 客户数字化负责人 + 集成商 PM 三方会签，缺一无效。"
        ),
    },
    {
        "key": "cantonese_asr_corpus",
        "title": "粤语方言 ASR 语料补齐实战",
        "category": "optimization",
        "tags": ["asr", "方言", "语料"],
        "phase": "corpus",
        "gate": None,
        "applies_to": ["manufacturing"],
        "source": "manual",
        "engagement": "eng-gac-manufacturing-seed03",
        "published": True,
        "body": (
            "## 现象\n"
            "通用 ASR 在粤语班组口音下 CER 21%，指令词「拿料/过机」频繁误识别。\n\n"
            "## 做法\n"
            "1. 按班组建籍贯分桶采样（肇庆/佛山优先），车间安静角录制\n"
            "2. 领域词典注入：工位名/物料号/俚语 800 条\n"
            "3. 上线期用双语字幕提示兜底，误识引导点按重说\n\n"
            "## 验收标准\n"
            "- 方言子集 CER ≤12%，指令意图准确率与普通话差距 ≤3pp。"
        ),
    },
    {
        "key": "bad_case_review",
        "title": "bad case 复盘会机制设计",
        "category": "methodology",
        "tags": ["bad-case", "运营", "复盘"],
        "phase": "monitoring_drift",
        "gate": None,
        "applies_to": ["manufacturing", "ticket"],
        "source": "manual",
        "engagement": "eng-guming-ticket-seed01",
        "published": True,
        "body": (
            "## 节奏\n"
            "双周 45 分钟，客户业务方必须有人对结果签字；会前 24h 发 case 清单。\n\n"
            "## 议程\n"
            "1. 抽样 20 条 bad case，按根因分桶（数据/特征/阈值/交互）\n"
            "2. 每桶指派 owner + 下双修复目标\n"
            "3. 回看上双目标完成率，未完成说明原因\n\n"
            "## 效果（古茗）\n"
            "bad_case_rate 11%→6%（4 个双周），复盘记录全部回流语料库。"
        ),
    },
    {
        "key": "eu_ai_act_conformity",
        "title": "EU AI Act 高风险系统 conformity 材料清单",
        "category": "research",
        "tags": ["eu-ai-act", "ce", "合规"],
        "phase": "deploy",
        "gate": "conformity",
        "applies_to": ["manufacturing"],
        "source": "manual",
        "engagement": "eng-gac-manufacturing-seed03",
        "published": True,
        "body": (
            "## 材料清单\n"
            "1. 技术文档（Annex III）：系统描述、训练数据治理、评估协议\n"
            "2. 风险管理系统文件（ISO 12100/13849 映射表）\n"
            "3. 人类监督措施说明（HITL 点位图）\n"
            "4. CE 符合性声明 + 公告机构意见（如适用）\n"
            "5. 欧盟境内授权代表协议\n\n"
            "## 常见缺口\n"
            "附录 III 的数据治理章节最常被退件——训练数据来源与偏置检验要逐项可追溯。"
        ),
    },
    {
        "key": "mysql_bulk_extract",
        "title": "MySQL 生产库批量抽取限流方案",
        "category": "implementation",
        "tags": ["mysql", "数据接入", "限流"],
        "phase": "connect",
        "gate": None,
        "applies_to": ["ticket", "manufacturing"],
        "source": "manual",
        "engagement": "eng-chery-manufacturing-seed08",
        "published": True,
        "body": (
            "## 原则\n"
            "生产库抽取永远走只读从库 + 游标分页，禁止大偏移 LIMIT。\n\n"
            "## 步骤\n"
            "1. 按 id/时间游标分批（每批 5k 行），批间 sleep 限流\n"
            "2. 连接池独占配额（max 4），pool_pre_ping 防半开连接\n"
            "3. 长事务避让：information_schema 监控 >60s 事务自动让路\n"
            "4. 抽取窗口与 DBA 排班对齐，失败断点续传按游标回放\n\n"
            "## 验收标准\n"
            "- 抽取期间业务库慢查询零新增，连接池可用率 ≥95%。"
        ),
    },
    {
        "key": "ticket_intent_taxonomy",
        "title": "客服工单意图分类体系对齐法",
        "category": "methodology",
        "tags": ["客服", "意图分类", "工单"],
        "phase": "corpus",
        "gate": None,
        "applies_to": ["ticket"],
        "source": "manual",
        "engagement": "eng-caocao-ticket-seed05",
        "published": True,
        "body": (
            "## 为什么不用 agent 自造分类\n"
            "客服中心已有口径（主类/子类/处置码），agent 分类必须与工单系统枚举一一映射，"
            "否则报表对不上、座席不信任。\n\n"
            "## 步骤\n"
            "1. 拉工单系统枚举 + 近 90 天分布，合并 <0.5% 长尾为「其他」\n"
            "2. 每 1k 条抽 50 条双人标注，Cohen's kappa <0.7 的类目拆分或合并\n"
            "3. 映射表进版本控制，客服中心改口径时同版本更新\n\n"
            "## 验收标准\n"
            "- 分类映射表获客服中心负责人签字，抽样一致率 ≥95%。"
        ),
    },
    {
        "key": "bi_metric_dictionary",
        "title": "BI 问数指标口径字典建设",
        "category": "research",
        "tags": ["bi", "指标口径", "语义层"],
        "phase": "corpus",
        "gate": None,
        "applies_to": ["ticket"],
        "source": "manual",
        "engagement": "eng-faw-ticket-seed04",
        "published": True,
        "body": (
            "## 现象\n"
            "「月活跃用户」在不同部门有 4 种口径，BI 问数直接生成 SQL 会随机选表，"
            "SQL 正确率卡在 0.82。\n\n"
            "## 做法\n"
            "1. 与业务方逐指标确认：定义/过滤条件/时间粒度/权威数据表\n"
            "2. 字典结构化存储（metric → canonical SQL 片段），生成时注入 schema linking\n"
            "3. 口径冲突以数据治理委员会裁决为准，字典记录裁决记录\n\n"
            "## 验收标准\n"
            "- TOP 300 指标全覆盖，BI SQL 正确率 ≥0.88，口径争议工单清零。"
        ),
    },
    {
        "key": "pii_masking_rules",
        "title": "工单文本 PII 脱敏规则集",
        "category": "implementation",
        "tags": ["pii", "脱敏", "合规"],
        "phase": "corpus",
        "gate": None,
        "applies_to": ["ticket"],
        "source": "manual",
        "engagement": "eng-caocao-ticket-seed05",
        "published": True,
        "body": (
            "## 规则集（正则 + NER 双通道）\n"
            "- 手机号/座机：保留前 3 后 2（回电场景可用）\n"
            "- 身份证/银行卡：全掩码，哈希留 trace 便于复查\n"
            "- 姓名+地址组合：NER 识别后整段掩码，防拼图还原\n"
            "- 车牌/订单号：保留类目格式但替换数字\n\n"
            "## 纪律\n"
            "脱敏计数进日报；抽样双人复核率 ≥2%；漏报 PII 一票否决，不得进入语料库。"
        ),
    },
    {
        "key": "slo_error_budget_talk",
        "title": "SLO 签认：错误预算沟通话术",
        "category": "research",
        "tags": ["slo", "错误预算", "沟通"],
        "phase": "slo_sla",
        "gate": "slo",
        "applies_to": ["ticket"],
        "source": "manual",
        "engagement": "eng-mengniu-ticket-seed10",
        "published": True,
        "body": (
            "## 谈判要点\n"
            "1. 目标值从用户旅程倒推，不从技术指标正推（「告警 5 分钟内响应」而非「CPU <70%」）\n"
            "2. 错误预算 = 变更节流阀：预算烧完自动冻结非紧急发布，需客户管理层背书\n"
            "3. 测量窗口 14d 起步：项目期一半内 28d 窗口没有意义\n\n"
            "## 常见僵局\n"
            "客户要 99.99% 时，把「每季度可容忍 downtime 换算成分钟」写在白板上再谈——"
            "多数客户看到 4.3 分钟会自己降级到 99.5%。"
        ),
    },
    {
        "key": "alert_routing_design",
        "title": "告警路由与升级路径设计",
        "category": "implementation",
        "tags": ["告警", "oncall", "路由"],
        "phase": "monitoring_drift",
        "gate": None,
        "applies_to": ["ticket", "manufacturing"],
        "source": "manual",
        "engagement": "eng-mengniu-ticket-seed10",
        "published": True,
        "body": (
            "## 三级路由\n"
            "1. L1 自动处置：已知的漂移/重启类事件走 playbook 自动执行，事后人审\n"
            "2. L2 FDE on-call：15 分钟响应，bad_case/准确率类告警专属通道\n"
            "3. L3 客户业务方：SLO 烧穿或涉及业务口径时升级，48h 内出 RCA\n\n"
            "## 纪律\n"
            "每条告警必须落「告警名→路由→升级人→处置手册」四元组；没有 owner 的告警一律先删。"
        ),
    },
    {
        "key": "airgap_deploy_checklist",
        "title": "气隙环境部署清单（edge 推理）",
        "category": "implementation",
        "tags": ["气隙", "edge", "部署"],
        "phase": "connect",
        "gate": "air_gap",
        "applies_to": ["manufacturing"],
        "source": "manual",
        "engagement": "eng-bmw-manufacturing-seed07",
        "published": True,
        "body": (
            "## 部署前\n"
            "1. edge 硬件按离线峰值负载 ×1.5 冗余选型；机柜位置与客户 EHS 会审\n"
            "2. 离线模型更新流程：摆渡盘 + SHA256 签名校验 + 回滚镜像，双人在场\n"
            "3. telemetry_egress 必须显式为 False：任何外联行为按安全事件处理\n\n"
            "## 部署后\n"
            "- 连续 72h 出口流量审计为零；本地存储容量水位监控上线\n"
            "- 把「拔网线」写进 runbook：气隙不是配置项，是物理事实。"
        ),
    },
    {
        "key": "works_council_talks",
        "title": "工会/works-council 共决沟通路径",
        "category": "methodology",
        "tags": ["工会", "共决", "沟通"],
        "phase": "change_mgmt_training",
        "gate": "works_council",
        "applies_to": ["manufacturing"],
        "source": "manual",
        "engagement": "eng-fawvw-manufacturing-seed02",
        "published": True,
        "body": (
            "## 时序\n"
            "沟通要在 site_survey 后立即启动，不能等 deploy 才谈——共决流程平均 6-10 周。\n\n"
            "## 话术框架\n"
            "1. 数据边界：agent 只读工单元数据，不做个人绩效评估（书面承诺）\n"
            "2. 岗位影响：辅助而非替代，附岗位影响评估表\n"
            "3. 试点代表：邀请工会代表参与 FAT/SAT 现场见证\n\n"
            "## 案例（长春一厂）\n"
            "两轮沟通 + 数字日志字段清单逐项过会后，共决签字一次通过，未阻塞部署。"
        ),
    },
    {
        "key": "llm_synthetic_quality",
        "title": "LLM 合成语料质检清单",
        "category": "research",
        "tags": ["synthetic", "质检", "语料"],
        "phase": "corpus",
        "gate": None,
        "applies_to": ["ticket", "manufacturing"],
        "source": "manual",
        "engagement": "eng-lzlj-ticket-seed09",
        "published": True,
        "body": (
            "## 为什么必须质检\n"
            "合成数据会放大模型偏见并「抹平」真实分布的长尾；不质检的 synthetic 比缺口更危险。\n\n"
            "## 清单（逐条打分）\n"
            "1. 真实性：与真实样本区分率（人审/分类器）≥70% 为合格\n"
            "2. 多样性：n-gram 重叠 <30%，类目内去重\n"
            "3. 标签一致性：与类目定义无冲突，边界样本单独标记\n"
            "4. 配比披露：报告必须写明 synthetic 占比，golden 集永不掺合成\n\n"
            "## 验收标准\n"
            "- 抽样 200 条，四项全过 ≥80% 方可入库。"
        ),
    },
    {
        "key": "weekly_retrain_pipeline",
        "title": "每周回流再训练管道",
        "category": "implementation",
        "tags": ["再训练", "mlops", "飞轮"],
        "phase": "monitoring_drift",
        "gate": None,
        "applies_to": ["ticket"],
        "source": "manual",
        "engagement": "eng-guming-ticket-seed01",
        "published": True,
        "body": (
            "## 管道节拍\n"
            "周一回流数据冻结 → 周二训练 + 离线评估 → 周三影子对比（新模型并行打分不生效）"
            "→ 周四人工抽检 50 条 → 周五灰度 10% 门店。\n\n"
            "## 回滚线\n"
            "影子对比任一核心指标劣化 >2% 即终止本周发布；连续 2 周终止则触发数据体检而不是硬上。\n\n"
            "## 交接形态\n"
            "移交后管道由客户数据团队运营，FDE 只保留月度架构评审职责。"
        ),
    },
    {
        "key": "handoff_acceptance_checklist",
        "title": "移交验收会签清单",
        "category": "methodology",
        "tags": ["移交", "验收", "会签"],
        "phase": "ops_handoff",
        "gate": "handoff_signoff",
        "applies_to": ["ticket", "manufacturing"],
        "source": "manual",
        "engagement": "eng-guming-ticket-seed01",
        "published": True,
        "body": (
            "## 包内六件套（缺一不签）\n"
            "1. runbook（事件响应/回滚/安全失败模式）\n"
            "2. eval 报告（含 bad case 根因分布）\n"
            "3. SLO 与告警路由表\n"
            "4. 模型卡（数据来源/已知局限/禁用场景）\n"
            "5. 培训材料与考核记录\n"
            "6. 飞轮回流管道操作手册\n\n"
            "## 签字链\n"
            "客户运维 owner + 业务 sponsor + FDE 三方会签；客户 30 天观察期内 FDE 保留 4h 响应 SLA。"
        ),
    },
    {
        "key": "oee_improvement_loop",
        "title": "OEE 提升闭环：诊断到改善动作",
        "category": "optimization",
        "tags": ["oee", "精益", "制造"],
        "phase": "eval",
        "gate": None,
        "applies_to": ["manufacturing"],
        "source": "manual",
        "engagement": "eng-bmw-manufacturing-seed07",
        "published": True,
        "body": (
            "## 闭环结构\n"
            "诊断 agent 只产「异常→可能根因→建议动作」三段输出；改善动作必须进入客户已有的"
            "精益改善系统（Kaizen/Andon 闭环），否则无人执行。\n\n"
            "## 度量\n"
            "- 每周对比 agent 建议采纳率与 OEE 增量，采纳率 <20% 时先改解释粒度而不是模型\n"
            "- MTTR/停机时间下降归因要剔除排产变化，用同车型同工位对照组。\n\n"
            "## 验收标准\n"
            "- 连续 8 周 OEE 增量 ≥1.5pp 且可归因到 agent 建议的改善动作。"
        ),
    },
    {
        "key": "shift_digital_handover",
        "title": "班次数字交接日志落地",
        "category": "implementation",
        "tags": ["班次", "交接", "runbook"],
        "phase": "slo_sla",
        "gate": "shift_handover",
        "applies_to": ["manufacturing"],
        "source": "manual",
        "engagement": "eng-bmw-manufacturing-seed07",
        "published": True,
        "body": (
            "## 落地三步\n"
            "1. 字段最小化：工位/异常/处置/待办四栏起步，禁止一开始上绩效字段\n"
            "2. 与现有纸质单并行 2 周，交接班 10 分钟内完成录入才允许切换\n"
            "3. per-shift runbook：每班次的 agent 异常处置入口 + 升级电话印在工位卡上\n\n"
            "## 验收标准\n"
            "- 连续 14 天交接日志无断档（gate 要求 digital_log_integrated + per_shift_runbook 双满足）。"
        ),
    },
    {
        "key": "agent_eval_harness",
        "title": "Agent 评估集构建 harness",
        "category": "implementation",
        "tags": ["eval", "评测集", "回归"],
        "phase": "validate",
        "gate": None,
        "applies_to": ["ticket", "manufacturing"],
        "source": "manual",
        "engagement": "eng-faw-ticket-seed04",
        "published": True,
        "body": (
            "## 构成\n"
            "- 真实 bad case 30%：历史投诉/误答，最贵也最有信息量\n"
            "- 边界 case 30%：权限边界/口径冲突/多轮改写\n"
            "- 回归基线 40%：历史通过集冻结版本，防「修一个坏两个」\n\n"
            "## 纪律\n"
            "评测集版本化，与模型版本配对存档；任何 prompt/检索改动必须先跑 harness，"
            "结果差异逐条人审后才能合入。golden 集禁止进训练语料。"
        ),
    },
    # -- 草稿审阅队列 ---------------------------------------------------------
    {
        "key": "conformity_blocked",
        "title": "gate 被阻塞: conformity — CE 标志与 EU AI Act 附录 III 缺口",
        "category": "methodology",
        "tags": ["conformity", "gate-blocked"],
        "phase": None,
        "gate": "conformity",
        "applies_to": [],
        "source": "gate_hint",
        "engagement": "eng-gac-manufacturing-seed03",
        "published": False,
        "body": (
            "## 背景\n\n`conformity` 门禁在 engagement `eng-gac-manufacturing-seed03` 被阻塞。\n\n"
            "## 阻塞项\n\nCE 标志未完成；EU AI Act 技术文档附录 III 缺失；第三方风险评估未出报告\n\n"
            "## 解法（待补充）\n\n- 按《EU AI Act conformity 材料清单》技能逐项补齐\n"
            "- 与公告机构约定 9/15 复评窗口\n\n"
            "## 验收标准\n\n- 三 gate 同日复评通过\n"
        ),
    },
    {
        "key": "cold_start_forecast",
        "title": "订货预测冷启动：新开店首周偏差治理",
        "category": "research",
        "tags": ["冷启动", "预测", "零售"],
        "phase": "corpus",
        "gate": None,
        "applies_to": ["ticket"],
        "source": "manual",
        "engagement": "eng-guming-ticket-seed01",
        "published": False,
        "body": (
            "## 现象\n"
            "新开店首周预测 MAE 达老店的 3.2 倍：开业爬坡期无历史销量，促销叠加放大偏差。\n\n"
            "## 候选方案（待评审）\n"
            "1. 同商圈同面积开业店曲线迁移 + 前 14 天逐日衰减融合\n"
            "2. 开业前问卷（商圈人流/竞品距离）作为先验特征\n"
            "3. 首周强制人工复核阈值：预测置信度低于 p30 时降级为建议模式\n\n"
            "## 下一步\n"
            "调 8 家 2026Q2 新开店回测三方案，胜出后进 corpus 补采清单。"
        ),
    },
    {
        "key": "mysql_pool_exhausted",
        "title": "MySQL 连接池打满：批量抽取挤占业务连接",
        "category": "optimization",
        "tags": ["auto-capture", "mysql", "连接池"],
        "phase": "connect",
        "gate": None,
        "applies_to": [],
        "source": "auto_capture",
        "engagement": "eng-chery-manufacturing-seed08",
        "published": False,
        "body": (
            "## 操作摘要\n\n`kpi` @ engagement `eng-chery-manufacturing-seed08`（阶段 `connect`）\n\n"
            "2026-08-28 晚间批量抽取把 MES 数据平台 MySQL 连接池打满（max 200 用满 8 分钟），"
            "业务慢查询告警 3 条。\n\n"
            "## 可复用点（待补充）\n\n- 独立配额 + 游标分页 + 批间限流（参见「MySQL 生产库批量抽取限流方案」）\n"
            "- 待确认：连接池监控是否已接入客户告警群\n"
        ),
    },
    {
        "key": "multilingual_review_rate",
        "title": "多语种素材过审率评估口径（待评审）",
        "category": "research",
        "tags": ["多语种", "评估", "待评审"],
        "phase": None,
        "gate": None,
        "applies_to": [],
        "source": "manual",
        "engagement": "eng-eclicktech-ticket-seed06",
        "published": False,
        "body": (
            "## 背景\n"
            "成功标准 v2 新增「多语种素材过审率」可度量项，但评估口径未定义："
            "Meta/TikTok/独立站审核标准不同，直接合并会失真。\n\n"
            "## 候选口径\n"
            "1. 按平台分层统计过审率，目标按平台基线分别设定\n"
            "2. 统一折算为「加权过审率」，权重按素材投放预算占比\n"
            "3. 首月只跟踪不设目标，积累基线后再签承诺值\n\n"
            "## 待办\n"
            "- 与 COO/Mkt VP 对齐口径后进成功标准 v3。"
        ),
    },
    {
        "key": "torque_param_governance",
        "title": "拧紧枪参数漂移治理思路（待评审）",
        "category": "research",
        "tags": ["拧紧", "参数漂移", "质量"],
        "phase": None,
        "gate": None,
        "applies_to": [],
        "source": "manual",
        "engagement": "eng-chery-manufacturing-seed08",
        "published": False,
        "body": (
            "## 现象\n"
            "芜湖一期拧紧枪扭矩曲线周漂移 0.8%，现有 SPC 抽检频次（2h/次）难以定位漂移起点。\n\n"
            "## 思路（待与质量部评审）\n"
            "1. 全量扭矩曲线入湖（当前仅抽检记录），按枪头寿命分桶\n"
            "2. 漂移起点定位用 CUSUM 控制图替代 Shewhart\n"
            "3. 与保养计划联动：枪头更换后自动重置基线\n\n"
            "## 待办\n"
            "- 数据量评估：全量曲线约 2.4k 条/班，入湖前先确认存储配额。"
        ),
    },
]


def _seed_skills() -> dict[str, str]:
    """Ensure every library skill exists (create or enrich in place).

    Returns a ``key -> skill id`` map so journal entries can link to the
    records they produced (the console shows the link as 💡).
    """
    svc = SkillService(SkillStore(_SKILLS_DIR))
    existing = {r.title: r for r in svc.search(status=None, limit=500)}
    ids: dict[str, str] = {}
    for spec in _SKILL_LIBRARY:
        rec = existing.get(spec["title"])
        if rec is None:
            rec = svc.create(
                SkillDraft(
                    title=spec["title"],
                    category=SkillCategory(spec["category"]),
                    tags=spec["tags"],
                    body_md=spec["body"],
                    phase_slug=spec["phase"],
                    gate_slug=spec["gate"],
                    applies_to=spec["applies_to"],
                    source=SkillSource(spec["source"]),
                    source_engagement=spec["engagement"],
                )
            )
        else:
            rec = svc.update(
                rec.id,
                SkillPatch(
                    tags=spec["tags"],
                    body_md=spec["body"],
                    phase_slug=spec["phase"],
                    gate_slug=spec["gate"],
                    applies_to=spec["applies_to"],
                ),
            )
        if spec["published"] and rec.status != SkillStatus.PUBLISHED:
            rec = svc.publish(rec.id)
        ids[spec["key"]] = rec.id
    return ids


# ---------------------------------------------------------------------------
# 现场记录种子：与各 engagement 的 gate 时间线一致，部分条目沉淀为技能
# ---------------------------------------------------------------------------
_JOURNAL: dict[str, list[tuple[str, str, str, str | None]]] = {
    "eng-guming-ticket-seed01": [
        (
            "research",
            "首日 Gemba：走访杭州 3 家门店 + 供应链中心。订货靠店长经验 + Excel，周订货准确率约 85%，"
            "促销日备货是核心痛点；按现场调研清单完成首件确认与数据源盘点。",
            "2026-05-06T10:30:00+08:00",
            "site_survey_checklist",
        ),
        (
            "research",
            "双 sponsor 访谈完成：王芳（数字化 VP）认领订货准确率 ≥98%，陈宇（CTO）认领会员 DAU +30%；"
            "成功标准 v1 含 14/90/120d 三个里程碑，双方签认。",
            "2026-05-12T15:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "RocketMQ 订货链路打通：瞬时 10w+ TPS 压测下消费 lag <5s；门店 POS/库存/供应链 3 源接入，"
            "86 个 SKU 维度对齐完成。",
            "2026-05-28T11:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "订货预测 agent v1 灰度 200 家门店：MAE 较基线下降 14%，未达 20% 目标——"
            "促销叠加日样本稀疏是主要缺口，缺口类别已进补采清单。",
            "2026-06-20T16:30:00+08:00",
            None,
        ),
        (
            "optimization",
            "bad case 复盘会运转 4 个双周：bad_case_rate 11%→6%；促销/天气特征增强后 hit_rate_1d 达 0.91，"
            "forecast MAE 收敛到 12.4。",
            "2026-07-08T14:00:00+08:00",
            "bad_case_review",
        ),
        (
            "implementation",
            "店长培训包 v2 完成 16 场巡讲，覆盖 90% 门店；运维移交清单会签，SLO 99.5% 连续 14d 达成。",
            "2026-07-30T10:00:00+08:00",
            None,
        ),
        (
            "optimization",
            "退场前最后一周巡检：新开店首周偏差仍偏大，已写入已知局限；冷启动治理方案草稿留在技能库待评审，"
            "飞轮回流管道交客户数据团队运营。",
            "2026-08-10T17:00:00+08:00",
            None,
        ),
        (
            "research",
            "数据源盘点收口：RocketMQ/POS/供应链 3 源 owner 与刷新频率确认，86 个 SKU 维度字段字典 v0 完成；"
            "促销日备货痛点抽样 40 条进语料清单。",
            "2026-05-08T11:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "干系人地图 v1：4 位干系人 RACI 落位，供应链总监认领缺货预警指标；"
            "门店满意度 vs 库存周转两项冲突指标现场对齐。",
            "2026-05-20T14:30:00+08:00",
            None,
        ),
        (
            "research",
            "语料盘点：32.4k 门店样本到齐，促销叠加日仅 1.9k 条——覆盖缺口确认，synthetic 补采 8.6k "
            "按合成语料质检清单逐项验收。",
            "2026-06-05T10:00:00+08:00",
            "llm_synthetic_quality",
        ),
        (
            "optimization",
            "店长可用性测试 12 人：5 人反馈「建议不可解释」——归因说明卡片上线后满意度 3.1→4.3（5 分制）。",
            "2026-06-28T15:30:00+08:00",
            None,
        ),
        (
            "implementation",
            "监控看板上线：data_drift 日检（PSI>0.2 告警 primary-oncall）+ bad case 周报自动化；"
            "每周回流再训练管道首跑通过。",
            "2026-07-18T11:00:00+08:00",
            "weekly_retrain_pipeline",
        ),
        (
            "research",
            "移交预演：客户数据团队 4 人跟岗 1 周，飞轮回流管道 + 周报机制实操演练全通过；验收会签清单六件套备齐。",
            "2026-07-26T14:00:00+08:00",
            "handoff_acceptance_checklist",
        ),
    ],
    "eng-fawvw-manufacturing-seed02": [
        (
            "research",
            "Gemba walk 长春一厂总装车间：3 班倒、候选测点 208 个、OT/IT 分区隔离确认；"
            "拧紧枪工位 12 数据最早缺失，列入首批补测，工会代表对接人已确认。",
            "2026-05-26T09:40:00+08:00",
            None,
        ),
        (
            "implementation",
            "OPC UA 汇聚层接入完成。踩坑：Basic256Sha256 证书链未互信导致订阅静默失败（无报错但无数据），"
            "改端点自签 + IP 白名单后恢复，沉淀为技能。",
            "2026-06-05T15:20:00+08:00",
            "opcua_pitfalls",
        ),
        (
            "research",
            "冷启动工况样本不足（冬季数据占比 <3%）：与维修班组约定 11 月补采窗口；"
            "先以仿真数据过渡并在语料报告如实标注。",
            "2026-06-18T10:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "FAT 通过（客户 + 集成商会签）；SAT 48h 真实产线伴跑完成，诊断 agent 误报率 5.2%、"
            "无安全联锁失效，按执行手册留全快照。",
            "2026-07-15T16:00:00+08:00",
            "fat_sat_playbook",
        ),
        (
            "optimization",
            "阈值调优：误报率 9%→5%，MTTR 下降 22% 达标；冬季冷启动工况按已知局限持续跟踪。",
            "2026-07-28T14:30:00+08:00",
            None,
        ),
        (
            "implementation",
            "班次数字交接日志集成上线，runbook 交车间经理复审；工会共决流程签字完成，进入移交准备。",
            "2026-08-06T09:00:00+08:00",
            None,
        ),
        (
            "research",
            "site_survey gate 通过：208 测点台账双 sponsor 签认；OT/IT 分区与 3 网拓扑写入调研纪要，资料归档进技术文档库。",
            "2026-05-28T16:30:00+08:00",
            "site_survey_checklist",
        ),
        (
            "implementation",
            "首批 50 测点接入（经 OPC UA 网关转换）：消费 lag <2s；OT 数据 90 天回溯存储上线，满足 IT 侧验收项。",
            "2026-06-12T14:00:00+08:00",
            None,
        ),
        (
            "research",
            "HAZOP-lite 工作坊：焊接工位人机协作区 PLr=D 确认，安全联锁点位 14 处逐点核验；"
            "功能安全材料按 ISO 13849 映射表成册。",
            "2026-06-25T10:30:00+08:00",
            None,
        ),
        (
            "implementation",
            "诊断 agent v1 三个工位试点：准确率 0.88、误报 9%——试点通过但误报超 8% 拦截线，"
            "阈值调优立项（评测集按 harness 规范冻结 v1.0）。",
            "2026-07-08T11:00:00+08:00",
            "agent_eval_harness",
        ),
        (
            "research",
            "工会共决沟通第 2 轮：确认数字交接日志仅记录工单元数据、不做个人绩效评估（书面承诺）；"
            "邀请代表参与 SAT 现场见证获同意。",
            "2026-07-20T09:30:00+08:00",
            "works_council_talks",
        ),
        (
            "optimization",
            "评估集扩容复测：bad case 260 条重标注（评测集 v1.1 冻结），diagnose_accuracy 0.88→0.94 复测确认，误报 5.2% 达标。",
            "2026-08-01T14:00:00+08:00",
            None,
        ),
    ],
    "eng-gac-manufacturing-seed03": [
        (
            "research",
            "番禺工厂首日勘察：焊装主线 PLC（S7）+ 智能座舱 HIL 台架（dSPACE）+ AGV 车队；"
            "5G 园区专网实测上行 230Mbps，满足质检图像回传。",
            "2026-07-03T09:30:00+08:00",
            None,
        ),
        (
            "implementation",
            "座舱语料采集完成 8.6k 条真实指令 + 多轮对话；产线质检图像 45k 张完成脱敏标注，PII 18 处。",
            "2026-07-20T14:00:00+08:00",
            None,
        ),
        (
            "research",
            "粤语方言 CER 高达 21%：主力用户为肇庆/佛山籍技工；启动方言语料专项补采（目标 2k 条），"
            "上线期先以双语字幕提示兜底。",
            "2026-07-29T11:00:00+08:00",
            "cantonese_asr_corpus",
        ),
        (
            "optimization",
            "座舱指令准确率 0.87→0.89（领域词典 + 唤醒词纠偏）；质检缺陷召回 0.92 保持。",
            "2026-08-12T16:00:00+08:00",
            None,
        ),
        (
            "research",
            "deploy 三 gate 同日评估未过：CE 标志未完成、EU AI Act 技术文档缺附录 III、第三方风险评估未出报告；"
            "按 conformity 材料清单逐项补齐，与何伟对齐 9/15 复评。",
            "2026-08-18T09:40:00+08:00",
            "eu_ai_act_conformity",
        ),
        (
            "research",
            "座舱 HIL 台架对接方案确认：dSPACE CAN/LIN 网关→云端 Broker，指令域时延实测 120ms（<200ms 要求）；"
            "HIL 用例库 340 条获何伟确认。",
            "2026-07-10T10:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "焊装主线 S7 数据接入：PROFINET 环网镜像口部署完成，首批 96 测点上线，消费 lag <1.8s。",
            "2026-07-16T15:00:00+08:00",
            None,
        ),
        (
            "research",
            "FAT 预检：座舱语音 agent 唤醒词在风噪 72dB 下失效率 8%——增加降噪前端后复测 2%，整改记录进 FAT 报告。",
            "2026-08-04T14:30:00+08:00",
            None,
        ),
        (
            "optimization",
            "粤语补采 2.2k 条完成（肇庆/佛山班组）：方言子集 CER 21%→14%，仍超 12% 目标——第二批补采已排期，继续跟踪。",
            "2026-08-08T16:00:00+08:00",
            None,
        ),
        (
            "research",
            "三 gate 阻塞复盘会：CE/EU AI Act/风险评估 owner 到人并给出 9/15 前完成计划；"
            "「附录 III 数据治理章节」拆为 3 项并行任务推进。",
            "2026-08-25T11:00:00+08:00",
            None,
        ),
    ],
    "eng-faw-ticket-seed04": [
        (
            "research",
            "集团制度库盘点：12.8k 篇制度/流程文档跨 6 个业务域；HR/财务两域权限模型最复杂，"
            "建立文档级 ACL 映射表并同法务确认边界。",
            "2026-06-20T10:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "红旗云妹 v1.4 全集团发布：办公问答 + 智能 BI 问数双入口，8 万员工开放；首周周活 31%，"
            "离 40% 目标差 9pp。",
            "2026-07-10T09:30:00+08:00",
            None,
        ),
        (
            "optimization",
            "BI 问数 SQL 正确率 0.82→0.88：460 个指标口径字典 + schema linking 优化；"
            "长文档引用改段落级 citation，溯源投诉清零。",
            "2026-07-22T15:00:00+08:00",
            None,
        ),
        (
            "research",
            "跨部门权限误答 case 复盘 37 例：81% 源自组织架构调整后 ACL 未同步；"
            "推动客户建立月度 ACL 对账机制，责任到系统管理员。",
            "2026-08-05T14:00:00+08:00",
            None,
        ),
        (
            "optimization",
            "qa_latency_p95 4.2s→2.8s：检索召回裁剪 + KV-cache 前缀复用；单次问答成本下降 63%，"
            "超 60% 目标，SLO <3s 达标。",
            "2026-08-20T11:30:00+08:00",
            "inference_latency",
        ),
        (
            "research",
            "知识库分域索引方案定稿：制度库 12.8k 篇按 6 业务域切分，域内再按密级分层；"
            "HR/财务域文档级 ACL 映射表启动。",
            "2026-06-12T09:30:00+08:00",
            None,
        ),
        (
            "implementation",
            "BI 问数 pilot：460 指标口径字典 v1 完成（首批 120 指标接语义层），pilot 5 部门 SQL 正确率 0.79——"
            "低于预期，口径冲突是主因。",
            "2026-06-30T14:00:00+08:00",
            "bi_metric_dictionary",
        ),
        (
            "research",
            "云妹 v1.4 发布前 HITL 评审：跨部门权限误答 5 例复现——上线期挂「数据边界」提示 + 误答举报入口，"
            "月度 ACL 对账机制立项。",
            "2026-07-18T10:00:00+08:00",
            None,
        ),
        (
            "optimization",
            "周报机制上线第 3 周：周活 31%→35%，BI 问数使用占比 18%→26%；周报模板被客户数字化部采纳为部门标准。",
            "2026-08-01T09:30:00+08:00",
            "weekly_report_template",
        ),
        (
            "research",
            "产品化评审通过：「智能 BI 问数」「制度问答」进入客户产品目录；移交启动会：运维 owner 确定，"
            "eval harness 与评测集交接入清单。",
            "2026-08-28T15:00:00+08:00",
            "agent_eval_harness",
        ),
    ],
    "eng-caocao-ticket-seed05": [
        (
            "research",
            "146 城订单/行程/投诉数据摸底：投诉明细 41k 条，TOP3 类目为发票报销(18%)、调度咨询(14%)、"
            "行程计费争议(11%)；方言/口语化表达占比高，先行标注策略待定。",
            "2026-07-24T10:30:00+08:00",
            None,
        ),
        (
            "implementation",
            "成功标准契约化签认：AI 客服拦截率 ≥60%、人工工单下降 30%；双 sponsor（技术 VP + 数据总监）确认，"
            "success_criteria gate 同日通过。",
            "2026-07-30T11:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "未策展真实数据原型跑通：客服工单自动分类 + 处置建议，生产库直连脱敏后进入，"
            "离线评估 resolution_accuracy 0.91，demo 全程可回放。",
            "2026-08-14T16:00:00+08:00",
            "uncurated_prototype",
        ),
        (
            "research",
            "原型方言投诉子集准确率仅 0.74：标注 1.2k 条川渝/粤语样本进下一批语料；"
            "PII 脱敏 8.9k 实体已双人复核。",
            "2026-08-22T10:00:00+08:00",
            None,
        ),
        (
            "optimization",
            "原型拦截率 0.63（目标 0.60 达标）：客服中心确认观察 2 周稳定性后进入 corpus 阶段准备。",
            "2026-08-28T15:30:00+08:00",
            None,
        ),
        (
            "research",
            "座席长访谈 12 人：TOP3 痛点 = 发票报销重复咨询、跨城计费争议、司机准入咨询；"
            "座席平均处理时长 6.4 分钟，重复咨询占 41%。",
            "2026-07-27T10:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "脱敏管道上线：手机号/身份证/地址三类规则引擎 + NER 双通道，首批 8.9k 实体脱敏双人复核通过，漏报率 0.3%。",
            "2026-08-04T14:00:00+08:00",
            "pii_masking_rules",
        ),
        (
            "research",
            "工单分类体系对齐：4 主类 21 子类映射表与客服中心口径逐项确认，长尾 7 类合并为「其他」；映射表进版本控制。",
            "2026-08-11T11:00:00+08:00",
            "ticket_intent_taxonomy",
        ),
        (
            "implementation",
            "原型 v2：处置建议增加「同类工单历史解决方案」检索，resolution_accuracy 0.88→0.91；"
            "座席端双栏界面可用性测试 8 人通过。",
            "2026-08-18T15:30:00+08:00",
            None,
        ),
        (
            "optimization",
            "响应延迟优化：检索+生成 P95 6.8s→4.1s（召回裁剪 + 工单摘要 KV-cache），座席端体感「跟得上对话节奏」。",
            "2026-08-26T10:30:00+08:00",
            "inference_latency",
        ),
    ],
    "eng-eclicktech-ticket-seed06": [
        (
            "research",
            "出海素材生产线调研：单条素材成本 $38，人工剪辑占 62%；「AI 生产效率 +50%」目标对应成本下降 40%，"
            "口径与 COO 对齐并写入备忘。",
            "2026-08-10T14:00:00+08:00",
            None,
        ),
        (
            "research",
            "success_criteria gate 未过：干系人表仅 1 名 sponsor（海外 COO），第二发起人待确认——"
            "按 Sponsor Collapse 破局路径启动市场 VP 面访。",
            "2026-08-15T09:20:00+08:00",
            "sponsor_collapse",
        ),
        (
            "implementation",
            "投放数据 POC：Meta/TikTok 双平台 API 拉通，素材-转化归因表 v0 可用；语料侧先以 synthetic 为主"
            "（5.6k），真实素材库授权谈判中。",
            "2026-08-24T16:30:00+08:00",
            None,
        ),
        (
            "research",
            "第二发起人访谈完成：高媛（市场 VP）确认加入，成功标准 v2 增加「多语种素材过审率」可度量项；"
            "待下周评审会签认后复评 gate。",
            "2026-08-29T10:30:00+08:00",
            None,
        ),
        (
            "research",
            "素材生产链路摸底：Meta/TikTok/独立站 3 渠道、多语种 14 种；当前过审率基线 62%，"
            "「效率 +50%」目标的成本换算口径获 COO 书面确认。",
            "2026-08-12T11:00:00+08:00",
            None,
        ),
        (
            "research",
            "语料盘点：真实素材 3.4k 条（授权范围法务确认中），synthetic 5.6k 已生成——"
            "按合成语料质检清单预检：多样性项 68% 过线，需去重再筛；报告如实标注 synthetic 占比 62%。",
            "2026-08-19T15:00:00+08:00",
            "llm_synthetic_quality",
        ),
        (
            "implementation",
            "素材-转化归因表 v1：ROAS 字段对齐 3 平台口径，投放策略分类 900 条；归因延迟从 T+3 压到 T+1。",
            "2026-08-27T16:00:00+08:00",
            None,
        ),
        (
            "research",
            "成功标准 v2 评审排期 9/2：多语种素材过审率口径草稿（按平台分层统计）随评审包发出；"
            "双 sponsor 签认后即复评 success_criteria gate。",
            "2026-08-31T10:00:00+08:00",
            None,
        ),
    ],
    "eng-bmw-manufacturing-seed07": [
        (
            "research",
            "铁西工厂首日 Gemba：总装/涂装双车间勘察，生产网与互联网物理隔离确认（air-gap），"
            "5G 园区专网实测仅园区内可达；按现场调研清单完成首件确认与资产盘点。",
            "2026-03-10T09:30:00+08:00",
            "site_survey_checklist",
        ),
        (
            "research",
            "site_survey gate 通过：测点台账双 sponsor 签认；气隙约束定为一号架构风险——"
            "连接器选型、模型更新、遥测回传全部按离线形态设计。",
            "2026-03-12T17:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "边缘推理一体机 8 台进场部署：机柜 EHS 会审通过；离线模型更新走摆渡盘 + SHA256 签名校验 + 回滚镜像，"
            "双人在场流程演练通过。",
            "2026-03-28T14:00:00+08:00",
            "airgap_deploy_checklist",
        ),
        (
            "implementation",
            "语料本地接入完成：工艺参数 12 万条 + 质检图像 60k 张全部落本地对象存储（48TB），"
            "出口流量审计连续 72h 为零。",
            "2026-04-15T16:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "SAT 48h 伴跑通过：诊断 agent 误报 4.1%、无安全联锁失效；气隙链路全程无外联记录，"
            "telemetry_egress=False 审计通过。",
            "2026-05-14T10:00:00+08:00",
            None,
        ),
        (
            "optimization",
            "评估复测：装配异常诊断准确率 0.93→0.95（工艺参数特征增强）；OEE 试点线周增量 2.1pp，"
            "改善动作进入客户 Kaizen 闭环。",
            "2026-06-10T14:30:00+08:00",
            "oee_improvement_loop",
        ),
        (
            "research",
            "班组长培训第 1 期：24 人完成数字交接日志实操考核通过率 100%；交接字段按最小化原则"
            "（工位/异常/处置/待办）运行 2 周无断档。",
            "2026-06-25T09:30:00+08:00",
            "shift_digital_handover",
        ),
        (
            "research",
            "runbook 中文版 v1.0 交客户运维部复审；变更管理流程与客户 EHS/CCB 对齐，工会共决签字完成。",
            "2026-07-15T11:00:00+08:00",
            None,
        ),
    ],
    "eng-chery-manufacturing-seed08": [
        (
            "research",
            "芜湖一期总装车间勘察：2 班倒确认；老产线 Modbus 段占比 40%（62 测点），网关转换不可避免；"
            "Andon/MES 接口需走客户 IT 权限流程。",
            "2026-08-04T10:00:00+08:00",
            None,
        ),
        (
            "research",
            "site_survey gate 通过：156 测点台账双 sponsor 签认；拧紧枪扭矩曲线全量采样问题记入调研备忘。",
            "2026-08-06T16:00:00+08:00",
            None,
        ),
        (
            "research",
            "success_criteria gate 通过：MTTR 下降 20% + 质检漏检率 <3% 双指标签认；"
            "成功标准含 14/90/120d 里程碑，制造数字化总监与质量部长双签。",
            "2026-08-14T16:30:00+08:00",
            None,
        ),
        (
            "implementation",
            "OPC UA 网关 PoC：3 家厂商对比测试，Modbus→OPC UA 转换时延 80ms（<100ms 要求）达标的方案 B 中标；"
            "首批 94 个 OPC UA 测点直接接入完成。",
            "2026-08-21T14:00:00+08:00",
            None,
        ),
        (
            "research",
            "MES 数据平台批量抽取首晚把连接池打满（8 分钟 max 200）——触发业务慢查询告警 3 条；"
            "限流方案已成草稿待评审，抽取窗口改至 DBA 排班低谷。",
            "2026-08-29T09:30:00+08:00",
            "mysql_pool_exhausted",
        ),
    ],
    "eng-lzlj-ticket-seed09": [
        (
            "research",
            "泸州云峰酒厂调研：包装质检车间 + 客服中心双场景；质检图像瓶颈在瓶身气泡/标签歪斜两类的判定分歧"
            "（质检员间一致率 0.78）。",
            "2026-08-05T10:00:00+08:00",
            None,
        ),
        (
            "research",
            "success_criteria gate 通过：经销商咨询自动应答率 ≥55% + 包装缺陷检出率 ≥99% 双 sponsor 签认；"
            "成功标准含 14/90/120d 里程碑。",
            "2026-08-08T11:30:00+08:00",
            None,
        ),
        (
            "implementation",
            "语料接入启动：CRM 工单 26k 条 + 质检图像 18k 张入库；图像类别不均衡确认（瓶身气泡 71%），"
            "均衡采样与针对性补采方案定稿。",
            "2026-08-15T15:00:00+08:00",
            None,
        ),
        (
            "research",
            "工单意图分类对齐：防伪查询 31%/订单物流 24%/政策咨询 19% 为 TOP3；"
            "川南口音话术标注方案定稿（方言标签 + 标准转写双轨）。",
            "2026-08-22T10:30:00+08:00",
            "ticket_intent_taxonomy",
        ),
        (
            "optimization",
            "低频类目合成补采 2.1k 条（防伪异常等）：按合成语料质检清单逐条打分，通过率 82% 达标入库；"
            "质检员判定分歧两类进标注仲裁流程。",
            "2026-08-29T14:30:00+08:00",
            "llm_synthetic_quality",
        ),
    ],
    "eng-mengniu-ticket-seed10": [
        (
            "research",
            "呼和浩特总部调研：订奶热线 + 冷链 IoT 双场景确认；冷链温控告警日均 1.2k 条中误报约 80%"
            "（传感器漂移/网关重连各占一半）——误报治理列为一级成功标准。",
            "2026-06-08T10:00:00+08:00",
            None,
        ),
        (
            "research",
            "success_criteria gate 通过：客服拦截率 ≥50% + 温控误报率 <30% 双 sponsor 签认；"
            "业务方担心「误报降了漏报升」，写入验收对照指标。",
            "2026-06-11T15:00:00+08:00",
            None,
        ),
        (
            "implementation",
            "语料接入：订奶工单 88k 条 + 冷链温控时序 3 个月；PII（手机号/住址）9.4k 实体按规则集脱敏，双人复核通过。",
            "2026-06-25T14:00:00+08:00",
            "pii_masking_rules",
        ),
        (
            "optimization",
            "温控误报治理第一阶段：传感器漂移检测上线，误报 80%→38%；漏报率同步 1.1%→1.0%（未恶化），"
            "距 30% 目标还差 8pp，网关重连类继续治理。",
            "2026-07-15T11:00:00+08:00",
            None,
        ),
        (
            "research",
            "slo gate 通过：availability 99.5% + 告警响应 P95 <5min 连续 14d 达成；"
            "错误预算规则（烧完冻结非紧急发布）获数字化中心总经理背书。",
            "2026-08-01T16:00:00+08:00",
            "slo_error_budget_talk",
        ),
        (
            "research",
            "runbook 预备会：移交对象为客户数据中心运维组；三级告警路由（L1 自动处置/L2 FDE on-call/L3 业务方）"
            "与客户值班体系逐条对齐完成。",
            "2026-08-24T10:00:00+08:00",
            "alert_routing_design",
        ),
    ],
}


def _apply_journal(ctx: EngagementContext, skill_ids: dict[str, str]) -> None:
    """Append back-dated field notes; linked entries point at seeded skills."""
    entries = sorted(_JOURNAL[ctx.id], key=lambda e: e[2])
    for i, (kind, note, ts, skill_key) in enumerate(entries, 1):
        ctx.journal.append(
            JournalEntry(
                id=f"jn-{ctx.id.removeprefix('eng-')}-{i:02d}",
                kind=kind,
                note=note,
                ts=ts,
                skill_id=skill_ids.get(skill_key) if skill_key else None,
            )
        )


def main() -> None:
    skill_ids = _seed_skills()
    builders = [
        guming,
        faw_vw,
        gac,
        faw,
        caocao,
        eclicktech,
        bmw_brilliance,
        chery,
        lzlj,
        mengniu,
    ]
    paths: list[Path] = []
    for b in builders:
        eng = Engagement(b())
        _apply_journal(eng.ctx, skill_ids)
        paths.append(_save(eng))
    for p in paths:
        print(f"seeded {p}")
    print(
        f"\n{len(paths)} engagements → {_OUT_DIR.resolve()}\n"
        f"{len(_SKILL_LIBRARY)} skills ({sum(1 for s in _SKILL_LIBRARY if s['published'])} published, "
        f"{sum(1 for s in _SKILL_LIBRARY if not s['published'])} drafts) → {_SKILLS_DIR.resolve()}"
    )


if __name__ == "__main__":
    main()
