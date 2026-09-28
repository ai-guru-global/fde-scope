"""Guided mode — the SOP knowledge layer for non-FDE users.

Same engine, second audience: an FDE knows what to do at each phase; a
customer user left without a resident FDE does not. This module turns the
18-phase SOP into per-phase guidance (plain-language deliverable checklists,
gate blockers translated into concrete next steps, catalog reading links)
without touching the state machine.

Safety boundary (AGENTS.md invariant 1): everything here is READ-ONLY with
respect to gate enforcement — ``guided_view`` re-checks gates live via
``Gate.check(ctx)`` and never records outcomes, never caches, and never calls
``advance()``. Guidance output does not grant passage; only the gates do.
"""

from __future__ import annotations

from .catalog_map import pages_for_phase
from .context import EngagementContext
from .gates.base import GateResult
from .phases import phase_by_slug, phases_for_profile

#: phase slug → what the user must actually produce during that phase.
#: Curated from ``Phase.description`` + the attached gates' check items.
PHASE_DELIVERABLES: dict[str, list[str]] = {
    "qualification": [
        "一句话问题定义（客户的问题，不是平台能力）",
        "FDE-worthy 判定：高价值 / 数据难 / 客户集中",
        "初步时间框：≤14d 集成 · ≤90d 上线 · ≤120d 交接",
    ],
    "site_survey": [
        "现场信息：地点 / 班次数 / 网络拓扑（Context tab「现场 / Site」）",
        "资产清单：name / type / vendor / protocol / criticality",
        "OT/IT 隔离与气隙（air-gapped）状态确认",
        "工会（works council）代表是否在场",
    ],
    "stakeholder_map": [
        "干系人清单：姓名 + 角色（Context tab「干系人」）",
        "≥2 位 sponsor（防 Sponsor Collapse）",
        "每位 sponsor 的可度量 success_metric",
    ],
    "success_criteria": [
        "3-5 条可度量的成功标准（书面）",
        "双 sponsor 对成功标准的确认",
        "done 的定义契约化（时间框 + 可度量结果）",
    ],
    "connect": [
        "连接器选型与数据源配置（CSV / Zammad / OPC UA / MQTT …）",
        "schema + 样本数据预览跑通",
        "（工业·气隙现场）部署姿态定论：assets.air_gap_plan",
    ],
    "corpus": [
        "语料报告：PII 清洗 / 去重 / 质量评分",
        "train / eval / test 分层切分",
        "覆盖度缺口与合成补盲记录",
    ],
    "prototype_real_data": [
        "原型跑在生产形态的真实（未策展）数据上",
        "demo→production 落差记录与修正",
    ],
    "validate": [
        "与真实干系人（含成功指标冲突方）的验证记录",
        "验证反馈 → 原型修正闭环",
    ],
    "deploy": [
        "上线部署清单 / manifest",
        "（工业）FAT 记录：assets.fat（passed + signed_off_by）",
        "（工业）SAT 记录：assets.sat（客户现场签字）",
        "（工业）功能安全与 CE/EU-AI-Act 合规证据",
    ],
    "eval": [
        "评估指标：assets.eval_metrics",
        "bad case 清单（持续调优抓手）",
    ],
    "slo_sla": [
        "≥1 条 SLO：name / target / error_budget / alert_route / window",
        "on-call 轮值与升级路径",
        "（工业·多班次）班次交接：assets.shift_handover",
    ],
    "runbook": [
        "runbook：事件响应 / 回滚 / 安全失败模式",
        "runbook 路径登记（assets.runbook）",
    ],
    "monitoring_drift": [
        "监控配置：assets.monitoring（数据漂移 / 质量漂移 / 反馈时延）",
        "看板链接（dashboards）",
    ],
    "change_mgmt_training": [
        "终用户培训材料",
        "（工业·工会有代表）共决审批：assets.works_council_approval",
    ],
    "flywheel_productization": [
        "每周产品化评审记录",
        "现场学习回流清单（≥1 个特性产品化）",
    ],
    "ops_handoff": [
        "所有权转交客户运维 / Customer Success",
        "on-call 责任切换记录",
    ],
    "knowledge_transfer": [
        "移交文档包：runbook + eval 报告 + SLO + 培训材料",
        "模型卡与已知局限（known_limitations）",
    ],
    "disengage": [
        "移交包生成：assets.handoff_package（CLI: fde-scope handoff <id>）",
        "客户书面接受（customer_accepted）",
        "退场时间确认（上线后 ≤120d）",
    ],
}

#: gate slug → (blocker substring, next-step advice, UI target).
#: Blockers are already plain-Chinese strings (gates/base.py); this table
#: appends the *action* — what to do and where in the console to do it.
#: Deliberately rule-based (no LLM): the blocker set is finite and stable,
#: and acceptance guidance must be deterministic and honest.
BLOCKER_ADVICE: dict[str, list[tuple[str, str, str]]] = {
    "site_survey": [
        (
            "location 未记录",
            "在 Context tab 的现场卡片补「地点」；实地走查（Gemba）后如实填写。",
            "tab:context",
        ),
        (
            "资产清单为空",
            "补资产清单：每台关键设备的 name / type / vendor / protocol / criticality。",
            "tab:context",
        ),
        ("网络拓扑", "记录现场网络拓扑（networks），多班次现场尤其重要。", "tab:context"),
    ],
    "success_criteria": [
        (
            "成功标准未定义",
            "在 Context tab「成功标准」写 3-5 条可度量结果（如：首响时长 <8s、坏例率 <10%）。",
            "context:success_criteria",
        ),
        (
            "sponsor",
            "在 Context tab「干系人」添加至少 2 位 sponsor（勾选 is_sponsor），并各填一个 success_metric。",
            "context:stakeholders",
        ),
        ("success_metric", "给每位 sponsor 补可度量的 success_metric。", "context:stakeholders"),
    ],
    "fat_sat": [
        (
            "FAT",
            "执行出厂验收测试并记录：assets.fat = {passed, signed_off_by, notes}（需 FDE 或 CLI 写入）。",
            "assets:fat",
        ),
        (
            "SAT",
            "在客户现场执行 SAT 并记录：assets.sat = {passed, signed_off_by, notes}，须客户签字。",
            "assets:sat",
        ),
    ],
    "functional_safety": [
        (
            "危险分析",
            "先完成 STPA / HAZOP lite 危险分析，再把 safety.hazard_analysis_done 置 true——这是功能安全判定的前提。",
            "context:safety",
        ),
        (
            "PL",
            "达成 PL 低于要求：整改安全回路提升 PL，或经安全工程师重新评估 PLr 后更新 safety 卡片。",
            "context:safety",
        ),
        (
            "SIL",
            "SIL 不足：整改安全功能或重评 SIL 要求，更新 safety 卡片（sil_required / sil_achieved）。",
            "context:safety",
        ),
    ],
    "conformity": [
        ("CE marking", "完成 CE marking 流程后把 safety.ce_marking_done 置 true。", "context:safety"),
        (
            "技术构造文件",
            "准备 EU AI Act Annex IV 技术构造文件，登记为 assets.technical_construction_file。",
            "assets:technical_construction_file",
        ),
        (
            "危险分析",
            "高风险系统的 conformity 以危险分析为前提：先完成 HAZOP 并更新 safety.hazard_analysis_done。",
            "context:safety",
        ),
    ],
    "works_council": [
        (
            "共决审批",
            "与 works council 走 BetrVG §87 共决流程，结果记录 assets.works_council_approval = {status, signed_off_by}。",
            "assets:works_council_approval",
        ),
        (
            "否决",
            "works council 已否决：按否决理由重新协商方案（调整监控范围/绩效使用等），再次提交审批。",
            "assets:works_council_approval",
        ),
    ],
    "air_gap": [
        (
            "edge 硬件",
            "在 assets.air_gap_plan 指定边缘硬件（edge_hardware：GPU 服务器/边缘盒子型号与数量）。",
            "assets:air_gap_plan",
        ),
        (
            "离线模型更新",
            "定义离线模型更新流程（offline_model_update：介质、清单、校验、回滚）。",
            "assets:air_gap_plan",
        ),
        (
            "遥测出网",
            "关闭遥测出网（telemetry_egress_allowed=false）——气隙约束下任何 phone-home 都是违规。",
            "assets:air_gap_plan",
        ),
        (
            "本地持久化",
            "在 air_gap_plan 补 local_storage：日志/语料/审计的本地持久化方案。",
            "assets:air_gap_plan",
        ),
    ],
    "shift_handover": [
        (
            "班次交接",
            "建立 assets.shift_handover = {digital_log_integrated, per_shift_runbook}：接入数字化交接日志 + 每班次 runbook。",
            "assets:shift_handover",
        ),
        ("交接日志", "接入数字化交接日志系统（digital_log_integrated=true）。", "assets:shift_handover"),
        (
            "班次 runbook",
            "为每个班次补 runbook 与应急联系人（per_shift_runbook=true）。",
            "assets:shift_handover",
        ),
    ],
    "slo": [
        (
            "未定义任何 SLO",
            "在 Context tab「SLO」至少添加一条：name / target / error_budget / alert_route / window（可用模板：availability 99.5% · 1.68h/14d）。",
            "context:slos",
        ),
        ("告警路由", "给每条 SLO 补 alert_route（告警发给谁），否则告警无人认领。", "context:slos"),
    ],
    "handoff_signoff": [
        (
            "移交包未生成",
            "运行 CLI：fde-scope handoff <engagement-id> 生成移交包（assets.handoff_package）。",
            "cli:handoff",
        ),
        (
            "移交包缺失",
            "补齐移交包缺失项：runbook / eval_report / slo_definition / training_material。",
            "assets:handoff_package",
        ),
        (
            "书面接受",
            "取得客户对移交包的书面接受，把 handoff_package.customer_accepted 置 true——不得未签收就退场。",
            "assets:handoff_package",
        ),
    ],
}

_FALLBACK_ADVICE = ("补齐上述阻塞项后，回到 Gates tab 点「重新校验」确认通过，再推进阶段。", "tab:gates")


def next_steps_for(slug: str, result: GateResult) -> list[dict]:
    """Translate a gate result's blockers/warnings into ordered next steps."""
    steps: list[dict] = []
    rules = BLOCKER_ADVICE.get(slug, ())
    for text in [*result.blockers, *result.warnings]:
        for needle, advice, target in rules:
            if needle in text:
                steps.append({"issue": text, "advice": advice, "target": target})
                break
        else:
            steps.append({"issue": text, "advice": _FALLBACK_ADVICE[0], "target": _FALLBACK_ADVICE[1]})
    return steps


def guided_view(ctx: EngagementContext, registry: dict | None = None, *, catalog_local: bool = False) -> dict:
    """Assemble the guided-mode payload for one engagement (read-only).

    Gates are re-checked live here (``Gate.check``), mirroring
    ``GET /api/engagements/{eid}/gates`` — no records are written and no
    results are cached, so guidance can never grant passage (invariant 1).
    """
    from .engagement import _default_gate_registry

    registry = registry or _default_gate_registry()
    phase = phase_by_slug(ctx.current_phase)
    visible = phases_for_profile(ctx.is_industrial)
    progress = f"{_phase_position(visible, phase.slug)}/{len(visible)}"

    gates_out: dict[str, dict] = {}
    for slug in phase.gates:
        gate = registry.get(slug)
        if gate is None or not gate.applies(ctx):
            continue
        result = gate.check(ctx)
        gates_out[slug] = {
            "name": gate.name,
            "passed": result.passed,
            "blockers": result.blockers,
            "warnings": result.warnings,
            "next_steps": next_steps_for(slug, result),
        }

    return {
        "phase": {
            "index": phase.index,
            "slug": phase.slug,
            "name": phase.name,
            "zone": phase.zone.value,
            "description": phase.description,
            "progress": progress,
        },
        "deliverables": PHASE_DELIVERABLES.get(phase.slug, []),
        "gates": gates_out,
        "catalog_pages": pages_for_phase(phase.slug, local=catalog_local),
        "plan": ctx.assets.get("guided_plan"),
        "llm_available": _llm_available(),
        "catalog_local": catalog_local,
    }


def _phase_position(visible: list, slug: str) -> int:
    for i, p in enumerate(visible):
        if p.slug == slug:
            return i + 1
    return 0


def _llm_available() -> bool:
    from ..llm import get_llm_client

    return get_llm_client().available


# ---------------------------------------------------------------------------
# AI-drafted context cards（迭代 3）
#
# Drafts are NEVER persisted here: the only write path is the existing
# POST /api/engagements/{eid}/context after the user reviews the diff, so
# gates remain the sole acceptance channel (invariant 1). SafetyPosture is
# deliberately NOT draftable — compliance sign-off data must not be
# AI-fabricated.
# ---------------------------------------------------------------------------
_DRAFT_SYSTEM = (
    "你是 FDE 驻场工程助手。只依据用户描述抽取事实：不得编造地点、人名、数值或承诺；"
    "无法确定的字段直接省略。输出严格合法的 JSON 对象：不要 markdown 围栏、不要解释文字。"
)

#: hard caps so a runaway completion can't bloat the engagement JSON
_MAX_STAKEHOLDERS = 20
_MAX_CRITERIA = 10
_MAX_SLOS = 10


def llm_draft_context(ctx: EngagementContext, description: str, llm: object) -> tuple[dict | None, bool]:
    """Draft context cards from a free-text business description.

    Mirrors ``llm_runbook``'s honesty contract: returns ``(draft, used_llm)``;
    ``(None, False)`` when the LLM is unavailable, the call fails, or the
    output contains nothing schema-valid. Partially valid output is partially
    adopted (block-level granularity).
    """
    if llm is None or not getattr(llm, "available", False):
        return None, False
    prompt = (
        "根据以下项目描述，抽取 engagement context 草稿。\n\n"
        f"- 客户: {ctx.customer}\n- profile: {ctx.profile}（工业现场: {'是' if ctx.is_industrial else '否'}）\n"
        f"- 当前阶段: {ctx.current_phase}\n\n项目描述：\n{description}\n\n"
        "输出 JSON，顶层键只允许：\n"
        '- "site": {"location": str, "ot_it_separated": bool, "air_gapped": bool, '
        '"networks": [str], "shift_count": int, "works_council_represented": bool, "notes": str}\n'
        '- "stakeholders": [{"name": str, "role": str, "is_sponsor": bool, "success_metric": str}]\n'
        '- "success_criteria": [str]\n'
        '- "slos": [{"name": str, "target": str, "error_budget": str, "alert_route": str, "window": str}]\n'
        "描述中没提到的键整块省略；stakeholders 至少给出描述中明确提到的干系人。"
    )
    try:
        raw = llm.complete(prompt, system=_DRAFT_SYSTEM, temperature=0.3, max_tokens=2048)  # type: ignore[attr-defined]
    except Exception:
        return None, False
    data = _extract_json(raw)
    if data is None:
        return None, False
    draft = _validate_draft(data)
    if not draft:
        return None, False
    return draft, True


def _extract_json(raw: str) -> dict | None:
    """Best-effort JSON object extraction (fences / prose around the payload)."""
    import json

    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _validate_draft(data: dict) -> dict:
    """Validate each draft block against the context models; keep valid ones."""
    import contextlib

    from pydantic import ValidationError

    from .context import SiteInfo, SLOSpec, Stakeholder

    out: dict = {}
    site = data.get("site")
    if isinstance(site, dict):
        with contextlib.suppress(ValidationError):
            out["site"] = SiteInfo.model_validate(site).model_dump()
    stakeholders = data.get("stakeholders")
    if isinstance(stakeholders, list):
        items = []
        for s in stakeholders[:_MAX_STAKEHOLDERS]:
            try:
                items.append(Stakeholder.model_validate(s).model_dump())
            except ValidationError:
                continue
        if items:
            out["stakeholders"] = items
    criteria = data.get("success_criteria")
    if isinstance(criteria, list):
        items = [c.strip() for c in criteria[:_MAX_CRITERIA] if isinstance(c, str) and c.strip()]
        if items:
            out["success_criteria"] = items
    slos = data.get("slos")
    if isinstance(slos, list):
        items = []
        for s in slos[:_MAX_SLOS]:
            try:
                items.append(SLOSpec.model_validate(s).model_dump())
            except ValidationError:
                continue
        if items:
            out["slos"] = items
    return out


def context_field_guide(is_industrial: bool) -> list[dict]:
    """Static per-field guidance for the manual (no-LLM / LLM-failed) form."""
    guide: list[dict] = []
    if is_industrial:
        guide.append(
            {
                "block": "site",
                "label": "现场 / Site",
                "kind": "fields",
                "fields": [
                    {
                        "field": "location",
                        "type": "text",
                        "hint": "客户现场地点（厂区/城市）",
                        "example": "长春汽开区工厂",
                    },
                    {"field": "ot_it_separated", "type": "bool", "hint": "OT/IT 网络是否隔离"},
                    {
                        "field": "air_gapped",
                        "type": "bool",
                        "hint": "是否气隙（不能连外网）——影响部署与更新方式",
                    },
                    {"field": "networks", "type": "lines", "hint": "网络拓扑，每行一个"},
                    {
                        "field": "shift_count",
                        "type": "int",
                        "hint": "班次数（>1 需要班次交接）",
                        "example": "3",
                    },
                    {
                        "field": "works_council_represented",
                        "type": "bool",
                        "hint": "是否有工会/职工代表（德国 BetrVG）",
                    },
                    {"field": "notes", "type": "text", "hint": "其他现场观察"},
                ],
            }
        )
    guide += [
        {
            "block": "stakeholders",
            "label": "干系人",
            "kind": "lines",
            "line_format": "姓名|角色|是否sponsor(y/n)|成功指标",
            "hint": "至少 2 位 sponsor（防 Sponsor Collapse），每行一位。",
            "example": "张三|CTO|y|首响时长 <8s",
        },
        {
            "block": "success_criteria",
            "label": "成功标准",
            "kind": "lines",
            "line_format": "每行一条可度量的成功标准",
            "hint": "3-5 条，写结果不写动作（如：坏例率 <10%，而非「优化模型」）。",
            "example": "工单首响时长 <8s",
        },
        {
            "block": "slos",
            "label": "SLO",
            "kind": "lines",
            "line_format": "名称|目标|错误预算|告警路由|窗口",
            "hint": "上线运营前必填；告警路由=告警发给谁。",
            "example": "availability|99.5%|1.68h/14d|primary-oncall|14d",
        },
    ]
    return guide


# ---------------------------------------------------------------------------
# 目标拆解（迭代 4）：goal → 阶段任务清单，存 ctx.assets["guided_plan"]
# ---------------------------------------------------------------------------
def rule_plan(ctx: EngagementContext, goal: str) -> dict:
    """Deterministic per-phase task skeleton — complete without any LLM."""
    items = []
    for phase in phases_for_profile(ctx.is_industrial):
        deliverables = PHASE_DELIVERABLES.get(phase.slug, [])
        for text in deliverables[:2]:
            items.append({"phase_slug": phase.slug, "title": text, "detail": phase.description})
        for gate_slug in phase.gates:
            items.append(
                {
                    "phase_slug": phase.slug,
                    "title": f"通过门禁：{gate_slug}",
                    "detail": "门禁在推进时实时重评，blocker 清零才算通过。",
                }
            )
    return _finalize_plan(goal, items, used_llm=False)


def llm_goal_plan(ctx: EngagementContext, goal: str, llm: object) -> tuple[dict, bool]:
    """LLM-enhanced plan: the rule skeleton is always the base.

    The LLM may rewrite/extend tasks per phase, but phases it doesn't
    mention keep their rule-generated tasks and unknown slugs are dropped —
    the plan can never lose SOP coverage because of a bad completion.
    """
    skeleton = rule_plan(ctx, goal)
    if llm is None or not getattr(llm, "available", False):
        return skeleton, False
    phase_table = "\n".join(
        f"- {p.slug}: {p.name}（{p.description}）" for p in phases_for_profile(ctx.is_industrial)
    )
    prompt = (
        "把项目目标拆解为按阶段的任务清单。\n\n"
        f"- 客户: {ctx.customer}\n- profile: {ctx.profile}\n- 目标: {goal}\n\n阶段表：\n{phase_table}\n\n"
        '输出严格 JSON：{"<phase_slug>": ["任务1", "任务2"]}，每阶段 2-4 条，动词开头、白话，'
        "只输出 JSON，不要围栏和解释。"
    )
    try:
        raw = llm.complete(  # type: ignore[attr-defined]
            prompt,
            system="你是 FDE 交付规划助手。任务必须具体可执行，不得编造客户未提及的事实。",
            temperature=0.4,
            max_tokens=2048,
        )
    except Exception:
        return skeleton, False
    data = _extract_json(raw)
    if not isinstance(data, dict):
        return skeleton, False
    valid_slugs = {p.slug for p in phases_for_profile(ctx.is_industrial)}
    overrides = {k: [t.strip() for t in v[:4] if isinstance(t, str) and t.strip()] for k, v in data.items()}
    overrides = {k: v for k, v in overrides.items() if k in valid_slugs and v}
    if not overrides:
        return skeleton, False
    items = []
    for phase in phases_for_profile(ctx.is_industrial):
        tasks = overrides.get(phase.slug)
        if tasks:
            items += [{"phase_slug": phase.slug, "title": t, "detail": ""} for t in tasks]
        else:
            items += [i for i in skeleton["items"] if i["phase_slug"] == phase.slug]
    return _finalize_plan(goal, items, used_llm=True), True


def _finalize_plan(goal: str, items: list[dict], *, used_llm: bool) -> dict:
    """Assign server-generated item ids (invariant 2) and stamp metadata."""
    import uuid
    from datetime import UTC, datetime

    return {
        "goal": goal,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "used_llm": used_llm,
        "items": [{"id": uuid.uuid4().hex[:8], "done": False, **i} for i in items],
    }
