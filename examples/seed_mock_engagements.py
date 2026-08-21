"""Seed the Web UI with realistic mock engagements.

Each mock is grounded in a real, publicly announced Alibaba Cloud customer
(2025-2026: GAC full-stack AI, FAW "Hongqi Yunmei" agent, FAW-VW plant
digitalization, Eclicktech overseas-marketing AI, CaoCao Mobility, Guming
new-tea retail). The vertical / phase / gate data is illustrative.

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
    SafetyPosture,
    SiteInfo,
    SLOSpec,
    Stakeholder,
)
from fde_scope.engagement.handoff import build_handoff_package  # noqa: E402
from fde_scope.engagement.operationalization import render_runbook  # noqa: E402

_OUT_DIR = Path(".fde_scope/engagements")
_REPORTS_DIR = Path("reports")


def _st(name: str, role: str, sponsor: bool = False, metric: str = "") -> Stakeholder:
    return Stakeholder(name=name, role=role, is_sponsor=sponsor, success_metric=metric)


def _slo(name: str, target: str, route: str = "primary-oncall", window: str = "28d") -> SLOSpec:
    return SLOSpec(name=name, target=target, alert_route=route, window=window)


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
            _slo("availability", "99.5%", window="14d"),
            _slo("forecast_latency_p95", "<8s"),
            _slo("bad_case_rate", "<10%", route="fde-oncall"),
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
            _slo("availability", "99.5%", window="14d"),
            _slo("opcua_ingest_p95", "<1s"),
            _slo("bad_case_rate", "<5%", route="fde-oncall"),
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
            _slo("availability", "99.5%", window="14d"),
            _slo("qa_latency_p95", "<3s"),
            _slo("bad_case_rate", "<10%", route="fde-oncall"),
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


def main() -> None:
    builders = [guming, faw_vw, gac, faw, caocao, eclicktech]
    paths = [_save(Engagement(b())) for b in builders]
    for p in paths:
        print(f"seeded {p}")
    print(f"\n{len(paths)} engagements → {_OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
