"""FDE Scope Web UI — a single-file FastAPI dashboard.

A real, interactive workbench (not a static HTML report):
    - Engagement dashboard: list / create engagements, advance through the
      18-phase SOP with gate enforcement.
    - Gate inspector: see blockers/warnings for any gate.
    - Corpus forge: upload a CSV, forge a corpus, view the HTML report.
    - KPI explorer: compute profile-specific KPIs over a sample set.

The whole UI is one self-contained HTML page (no build step) served by
FastAPI; JSON endpoints back the interactive bits. The app imports lazily so
``fde-scope web`` only needs the optional ``[web]`` extra.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import TypeAdapter, ValidationError

from .. import paths
from ..engagement import Engagement, EngagementContext
from ..engagement.engagement import AdvanceBlocked, _default_gate_registry
from ..profiles import all_profiles, get_profile

# Import-time resolution is safe here: under the CWD fallback reports_dir()
# stays RELATIVE, so every use re-resolves against the current CWD (test
# isolation via chdir keeps working — see fde_scope.paths).
_REPORTS_DIR = paths.reports_dir(create=True)

#: Upload cap for /api/forge and /api/kpi (10 MiB). Read with a bounded
#: read so an oversized body is refused before it is fully buffered.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="FDE Scope", version="0.1.0")


async def _read_limited(file: UploadFile, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read an upload, refusing anything beyond ``limit`` bytes with 413."""
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"file exceeds {limit} byte limit")
    return content


# ---------------------------------------------------------------------------
# persistence helpers
# ---------------------------------------------------------------------------
_STR_LIST = TypeAdapter(list[str])


def _slugify(value: str) -> str:
    """Whitelist-sanitize a value for use in an engagement id / file name."""
    return re.sub(r"[^a-z0-9-]", "-", value.lower().replace(" ", "-"))


def _eng_path(eid: str) -> Path:
    eng_dir = paths.engagements_dir()
    path = (eng_dir / f"{eid}.json").resolve()
    base = eng_dir.resolve()
    if not path.is_relative_to(base):
        raise HTTPException(status_code=400, detail=f"invalid engagement id: {eid!r}")
    return path


def _load(eid: str) -> Engagement:
    p = _eng_path(eid)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"engagement '{eid}' not found")
    return Engagement(EngagementContext.load(p))


def _save(eng: Engagement) -> None:
    _eng_path(eng.ctx.id).parent.mkdir(parents=True, exist_ok=True)
    eng.ctx.save(_eng_path(eng.ctx.id))


def _all_engagements() -> list[Engagement]:
    eng_dir = paths.engagements_dir()
    if not eng_dir.exists():
        return []
    out = []
    for p in sorted(eng_dir.glob("*.json")):
        try:
            out.append(Engagement(EngagementContext.load(p)))
        except ValueError:
            continue  # skip a corrupt file instead of 500ing the whole list
    return out


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/profiles")
def profiles() -> dict:
    return {
        slug: {
            "name": p.name,
            "industrial": p.is_industrial,
            "connectors": p.primary_connectors,
            "kpis": p.kpi_catalogue,
        }
        for slug, p in all_profiles().items()
    }


@app.get("/api/phases")
def phases(profile: str = "ticket") -> dict:
    from ..engagement.phases import phases_for_profile

    try:
        is_industrial = get_profile(profile).is_industrial
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown profile: {profile!r}") from None
    seq = phases_for_profile(is_industrial)
    return {"phases": [p.__dict__ for p in seq], "is_industrial": is_industrial}


@app.get("/api/engagements")
def list_engagements() -> list[dict]:
    return [eng.status() for eng in _all_engagements()]


@app.post("/api/engagements")
def create_engagement(customer: str = Form(...), profile: str = Form("ticket")) -> dict:
    eid = f"eng-{_slugify(customer)}-{_slugify(profile)}-{uuid.uuid4().hex[:6]}"
    ctx = EngagementContext(id=eid, customer=customer, profile=profile)
    eng = Engagement(ctx)
    _save(eng)
    return eng.status()


@app.get("/api/engagements/{eid}")
def get_engagement(eid: str) -> dict:
    eng = _load(eid)
    return {**eng.status(), "context": eng.ctx.model_dump()}


@app.get("/api/engagements/{eid}/gates")
def engagement_gates(eid: str) -> dict:
    eng = _load(eid)
    out = {}
    for slug, gate in _default_gate_registry().items():
        if gate.applies(eng.ctx):
            result = gate.check(eng.ctx)
            out[slug] = {
                "name": gate.name,
                "passed": result.passed,
                "blockers": result.blockers,
                "warnings": result.warnings,
            }
    return out


@app.post("/api/engagements/{eid}/advance")
def advance_engagement(eid: str, force: bool = False) -> dict:
    eng = _load(eid)
    try:
        eng.advance(force=force)
    except AdvanceBlocked as exc:
        _save(eng)
        return {"advanced": False, "result": exc.result.__dict__}
    except StopIteration:
        return {"advanced": False, "reason": "complete"}
    _save(eng)
    return {"advanced": True, "status": eng.status()}


@app.post("/api/engagements/{eid}/gate/{slug}")
def evaluate_gate(eid: str, slug: str) -> dict:
    eng = _load(eid)
    try:
        result = eng.evaluate_gate(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown gate: {slug!r}") from None
    _save(eng)
    return {"slug": slug, "passed": result.passed, "blockers": result.blockers, "warnings": result.warnings}


# ---------------------------------------------------------------------------
# journal API（现场记录）
# ---------------------------------------------------------------------------
_JOURNAL_KINDS = ("research", "implementation", "optimization")


@app.get("/api/engagements/{eid}/journal")
def engagement_journal(eid: str) -> list[dict]:
    eng = _load(eid)
    return [e.model_dump() for e in eng.ctx.journal]


@app.post("/api/engagements/{eid}/journal")
def journal_append(eid: str, body: dict | None = None) -> dict:
    eng = _load(eid)
    body = body or {}
    note = body.get("note")
    if not isinstance(note, str) or not note.strip():
        raise HTTPException(status_code=422, detail="'note' is required") from None
    kind = body.get("kind", "research")
    if kind not in _JOURNAL_KINDS:
        raise HTTPException(status_code=422, detail=f"invalid kind: {kind!r}") from None
    from ..engagement.context import JournalEntry

    entry = JournalEntry(kind=kind, note=note.strip(), skill_id=body.get("skill_id"))
    eng.ctx.journal.append(entry)
    _save(eng)
    return entry.model_dump()


@app.post("/api/engagements/{eid}/journal/{jid}/skill")
def journal_to_skill(eid: str, jid: str) -> dict:
    """把一条现场记录沉淀为技能草稿（kind → category 映射预填）。"""
    eng = _load(eid)
    entry = next((e for e in eng.ctx.journal if e.id == jid), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"journal entry '{jid}' not found") from None
    if entry.skill_id:
        raise HTTPException(status_code=409, detail=f"already linked to skill {entry.skill_id}") from None
    from ..skills.models import SkillCategory, SkillDraft

    mapping = {
        "research": SkillCategory.RESEARCH,
        "implementation": SkillCategory.IMPLEMENTATION,
        "optimization": SkillCategory.OPTIMIZATION,
    }
    draft = SkillDraft(
        title=entry.note[:60],
        category=mapping[entry.kind],
        body_md=entry.note,
        source_engagement=eid,
    )
    rec = _skill_service().create(draft)
    entry.skill_id = rec.id
    _save(eng)
    return rec.model_dump()


@app.post("/api/engagements/{eid}/context")
def update_context(eid: str, body: dict | None = None) -> dict:
    """Patch an engagement context (site / safety / slo / stakeholders / assets)."""
    eng = _load(eid)
    body = body or {}
    try:
        if "site" in body:
            eng.ctx.site = type(eng.ctx.site).model_validate(body["site"])
        if "safety" in body:
            eng.ctx.safety = type(eng.ctx.safety).model_validate(body["safety"])
        if "success_criteria" in body:
            eng.ctx.success_criteria = _STR_LIST.validate_python(body["success_criteria"])
        if "stakeholders" in body:
            from ..engagement.context import Stakeholder

            eng.ctx.stakeholders = [Stakeholder.model_validate(s) for s in body["stakeholders"]]
        if "slos" in body:
            from ..engagement.context import SLOSpec

            eng.ctx.slos = [SLOSpec.model_validate(s) for s in body["slos"]]
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from None
    if "assets" in body:
        eng.ctx.assets.update(body["assets"])
    _save(eng)
    return eng.status()


@app.post("/api/forge")
async def forge_corpus(
    file: UploadFile = File(...),
    min_samples: int = Form(5),
    synth_per_gap: int = Form(3),
) -> dict:
    """Upload a CSV, forge a corpus, return a CorpusReport summary + report id."""
    from ..config import CorpusConfig
    from ..corpus import CorpusForge, save_html

    try:
        content = (await _read_limited(file)).decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="file is not valid UTF-8") from None
    # never trust the client-supplied name: basename only, uuid fallback
    safe_name = Path(file.filename or "").name or f"{uuid.uuid4().hex}.csv"
    tmp = paths.uploads_dir(create=True) / safe_name
    tmp.write_text(content, encoding="utf-8")

    from fastapi.concurrency import run_in_threadpool

    from ..connectors.csv_fallback import CSVConnector
    from ..llm import MiMoClient

    rows = CSVConnector(str(tmp)).extract_sample(100000)
    cfg = CorpusConfig(min_samples_per_category=min_samples, synth_per_gap=synth_per_gap)
    # LLM synthesis kicks in automatically when FDE_SCOPE_MIMO_API_KEY is
    # set (env-configured); without a key the forge stays rule-based.
    # forge_rows may make blocking LLM calls (up to ~60s each) — run it in a
    # worker thread so the event loop (and every other endpoint) stays live.
    report = await run_in_threadpool(CorpusForge(cfg, llm=MiMoClient()).forge_rows, rows)
    report_id = uuid.uuid4().hex[:8]
    out_html = paths.reports_dir() / f"corpus_report_{report_id}.html"
    out_json = paths.reports_dir() / f"corpus_report_{report_id}.json"
    save_html(report, out_html)
    out_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return {
        "report_id": report_id,
        "html_url": f"/reports/corpus_report_{report_id}.html",
        "total": report.total,
        "real": report.real,
        "synthetic": report.synthetic,
        "dropped": report.dropped,
        "pii_masked": report.pii_entities_masked,
        "gaps": [g.model_dump() for g in report.coverage.gaps],
    }


@app.post("/api/kpi")
async def compute_kpis(
    profile: str = Form("manufacturing"),
    file: UploadFile = File(...),
) -> dict:
    try:
        content = (await _read_limited(file)).decode("utf-8")
        samples = [json.loads(line) for line in content.splitlines() if line.strip()]
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="file is not valid UTF-8") from None
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="file is not valid JSONL") from None
    try:
        prof = get_profile(profile)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown profile: {profile!r}") from None
    return {"profile": profile, "kpis": prof.compute_kpis(samples), "sample_count": len(samples)}


# ---------------------------------------------------------------------------
# deploy API（Layer 3 装配计划：角色 → 连接器 → 工具绑定，dry-run，不碰运行时）
# ---------------------------------------------------------------------------
@app.post("/api/deploy/plan")
def deploy_plan(body: dict | None = None) -> dict:
    """Dry-run ``fde-scope deploy`` for a tenant payload and return the manifest.

    The point is the tool plan: which role agent gets which connector tool,
    against which physical source — and which ones are still waiting for one.
    Delegates to :func:`fde_scope.deploy.build_deploy_plan` so the console, the
    PawApp backend and the CLI can never disagree. No AgentScope, no model.
    """
    from ..deploy import build_deploy_plan

    try:
        return build_deploy_plan(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


# ---------------------------------------------------------------------------
# workbench API（工作台聚合：全局统计 + 跨项目矩阵 + 最近沉淀）
# ---------------------------------------------------------------------------
@app.get("/api/workbench")
def api_workbench() -> dict:
    from collections import Counter

    from ..skills.models import SkillStatus

    matrix = [eng.status() for eng in _all_engagements()]
    active = [s for s in matrix if not s.get("is_complete")]
    skills = _skill_service()
    published = skills.search(status=SkillStatus.PUBLISHED)
    return {
        "stats": {
            "active_projects": len(active),
            "phase_distribution": dict(Counter(s["current_phase"] for s in active)),
            "draft_skills": len(skills.list_drafts()),
            "total_skills": len(skills.search()),
        },
        "matrix": matrix,
        "recent_skills": [
            r.model_dump() for r in sorted(published, key=lambda r: r.updated_at, reverse=True)[:5]
        ],
    }


# ---------------------------------------------------------------------------
# skills API（技能/方法论沉淀库）
# ---------------------------------------------------------------------------
# 模块级导入：FastAPI 路由注册时即解析请求体类型注解
from ..skills.models import SkillDraft, SkillPatch  # noqa: E402


def _skill_service():
    from ..skills.service import SkillService
    from ..skills.store import SkillStore

    # 与 engagements 同约定：经 fde_scope.paths 解析数据根（B1）
    return SkillService(SkillStore(paths.skills_dir()))


@app.get("/api/skills")
def api_skills(
    q: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    status: str = "published",
    profile: str | None = None,
    gate: str | None = None,
    phase: str | None = None,
) -> list[dict]:
    from ..skills.models import SkillCategory, SkillStatus

    return [
        r.model_dump()
        for r in _skill_service().search(
            q,
            category=SkillCategory(category) if category else None,
            tags=[tag] if tag else None,
            status=SkillStatus(status) if status else None,
            profile=profile,
            gate_slug=gate,
            phase_slug=phase,
        )
    ]


@app.post("/api/skills")
def api_skills_create(draft: SkillDraft) -> dict:
    return _skill_service().create(draft).model_dump()


@app.get("/api/skills/drafts")
def api_skills_drafts() -> list[dict]:
    return [r.model_dump() for r in _skill_service().list_drafts()]


@app.get("/api/skills/{sid}")
def api_skill_get(sid: str) -> dict:
    try:
        return _skill_service().get(sid).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found") from None


@app.patch("/api/skills/{sid}")
def api_skill_patch(sid: str, patch: SkillPatch) -> dict:
    try:
        return _skill_service().update(sid, patch).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found") from None


@app.post("/api/skills/{sid}/publish")
def api_skill_publish(sid: str) -> dict:
    try:
        return _skill_service().publish(sid).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/api/skills/{sid}/archive")
def api_skill_archive(sid: str) -> dict:
    try:
        return _skill_service().archive(sid).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/api/skills/{sid}/export")
def api_skill_export(sid: str, body: dict) -> dict:
    from ..skills.exporters import export_skill

    fmt = body.get("format")
    if not isinstance(fmt, str):
        raise HTTPException(status_code=400, detail="missing or invalid 'format'") from None
    try:
        rec = _skill_service().get(sid)
        files = export_skill(rec, fmt)
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"skill_id": sid, "format": fmt, "files": [{"name": f.name, "content": f.content} for f in files]}


from fastapi.staticfiles import StaticFiles  # noqa: E402

app.mount("/reports", StaticFiles(directory=str(_REPORTS_DIR)), name="reports")


# ---------------------------------------------------------------------------
# glossary tooltips（术语小问号标注：术语后跟 ?，悬停/聚焦弹出解释气泡）
# ---------------------------------------------------------------------------
_GLOSSARY: list[tuple[str, str]] = [
    (
        "Gemba walk",
        "源自日语「現場」：到价值创造的第一线（车间/工位）实地走查，"
        "观察真实作业、与一线员工交谈，而不是隔着报表判断。精益/丰田生产方式的核心实践。",
    ),
    ("Gemba", "现场走查：工程师驻车间实地观察真实流程、设备与痛点（对应 site_survey 阶段）。"),
    ("FDE", "Forward Deployed Engineer，前置部署工程师：带产品驻客户现场、快速交付解决方案的工程师角色。"),
    ("Engagements", "Engagement 列表：本项目所有驻场项目的入口。"),
    ("Engagement", "一次完整的驻场客户项目：从问题框定、构建、运营化到交接退场的全过程推进单位。"),
    ("SOP", "Standard Operating Procedure，标准作业程序；这里指覆盖项目全生命周期的 18 阶段流程。"),
    ("zones", "阶段分组（Zone）：A 立项勘察 → B 构建 → C 运营化 → D 交接退场。"),
    ("Zone", "SOP 阶段分组：A 立项勘察 → B 构建 → C 运营化 → D 交接退场。"),
    ("Gates", "Gate 列表：当前项目适用的所有门禁及其状态。"),
    (
        "Gate",
        "谓词式门禁：每次推进阶段都重新评估的条件（如双 sponsor、FAT/SAT 签字），"
        "不通过即拦截，过期结果不作数。",
    ),
    ("overlay", "叠加层：仅工业 profile 才额外生效的 gate 集合（🏭 标记）。"),
    (
        "FAT/SAT",
        "FAT = Factory Acceptance Test 出厂验收测试；SAT = Site Acceptance Test 现场验收测试，均需客户签字。",
    ),
    ("sponsor", "项目拍板人/出资方干系人；本 SOP 要求业务与工业双 sponsor 共同确认成功标准。"),
    ("works_council", "德国《企业组织法》BetrVG §87 工会共决：涉及员工监控/绩效的部署须工会同意。"),
    ("air-gapped", "气隙部署：与外部网络物理隔离的封闭环境，安装与更新需走离线清单。"),
    ("气隙", "air-gapped：与外部网络物理隔离的封闭网络环境。"),
    ("OT/IT 隔离", "运营技术（OT）车间网与企业 IT 网隔离，是工业现场安全的常见要求。"),
    ("班次", "轮班制度（如 3 班倒）；24/7 产线的部署需集成班次交接（shift_handover gate）。"),
    ("工会", "员工代表机构；涉及员工监控/绩效的部署在德国需其共决（见 works_council gate）。"),
    ("SLO", "Service Level Objective，服务等级目标：内部可度量的质量承诺，如「99% 工单 5 分钟内首次响应」。"),
    ("SLA", "Service Level Agreement，服务等级协议：对外的合同性承诺，通常由多个 SLO 支撑。"),
    ("on-call", "轮班值班响应机制：告警路由到当班人，保证 7×24 有人处置。"),
    ("告警路由", "SLO 违约时告警送达的渠道/值班组（alert_route）。"),
    ("runbook", "运维/应急手册：故障处置步骤、回滚方案与升级路径的文档。"),
    ("移交包", "项目结束时交付客户的完整产物集合：runbook、模型、监控配置、已知局限等。"),
    ("OEE", "Overall Equipment Effectiveness，设备综合效率 = 可用率 × 性能率 × 良品率；世界级水平 ≥ 0.85。"),
    ("MTBF", "Mean Time Between Failures，平均无故障时间（小时），越高越可靠。"),
    ("pick success", "机械臂抓取成功率；参照 DexNet 基准约 0.80。"),
    ("DexNet", "UC Berkeley 的抓取规划神经网络及基准数据集，抓取成功率的常用参照。"),
    ("KPI", "Key Performance Indicator，关键绩效指标；ticket 与 manufacturing 场景使用不同目录。"),
    ("Profile", "场景档案：定义可用连接器、KPI 目录与适用 gate（ticket 客服 / manufacturing 制造业）。"),
    ("ticket", "客服工单场景：CSV/Zammad/Salesforce/MySQL 数据接入，无工业 gate。"),
    ("manufacturing", "制造业/具身机器人场景：OPC UA、MQTT、ROS2 等工业接入 + 6 个工业合规 gate。"),
    ("Context", "项目上下文：现场、干系人、成功标准、SLO、功能安全与产物的结构化集合。"),
    ("success_criteria", "成功标准：契约化、可度量的验收条件，由双 sponsor 签字确认。"),
    ("干系人", "Stakeholder：与项目相关的角色（拍板人、使用者、运维、工会…）及其成功指标。"),
    ("成功标准", "契约化、可度量的验收条件（success_criteria），双 sponsor 确认。"),
    ("功能安全", "Functional Safety：机械/控制系统在故障时仍保持安全的标准体系（PL/SIL 等级）。"),
    ("ISO 13849", "机械安全功能安全标准，定义性能等级 PL / PLr。"),
    ("IEC 61508", "电气/电子/可编程电子安全系统的功能安全标准，定义 SIL 等级。"),
    ("ISO 10218", "工业机器人安全标准：协作与常规机器人的风险评估要求。"),
    ("CE", "欧盟合规标志：产品符合相关欧盟指令方可进入欧洲市场。"),
    ("EU AI Act", "欧盟人工智能法案：按风险分级监管 AI，高风险用途需合规评估与文档。"),
    ("PLr", "Required Performance Level，要求性能等级（ISO 13849）；PL 为实际达到的等级。"),
    ("SIL", "Safety Integrity Level，安全完整性等级（IEC 61508）。"),
    ("Corpus", "语料：训练/评估模型的样本集合；锻造（forge）即清洗、脱敏、补盲、合成的流水线。"),
    ("语料锻造", "CSV 等原始数据 → 脱敏 → 去重 → 质量门 → 覆盖度分析 → 针对性合成 → 报告的流水线。"),
    ("Flywheel", "飞轮：现场事件回流为语料、周度增量重训，让系统越用越准的闭环。"),
    ("飞轮", "数据回流 → 语料增量 → 再训练的闭环：项目用得越久，模型越贴合该客户。"),
    ("ISA-95", "企业系统与车间系统集成的国际标准，MES 数据模型的依据。"),
    ("MES", "Manufacturing Execution System，制造执行系统：工单、质量、停机等车间数据源。"),
    ("OPC UA", "工业自动化统一通信协议，可直接读取 PLC tag 数据。"),
    ("PLC", "Programmable Logic Controller，可编程逻辑控制器：产线设备的控制单元。"),
    ("MQTT-Sparkplug", "MQTT：轻量发布/订阅协议；Sparkplug B：规范其工业载荷语义。"),
    ("ROS2 Bag", "Robot Operating System 2 的录制回放格式，常用于机器人轨迹/传感数据。"),
    ("Historian", "时序历史数据库：存储生产过程历史数据（温度、节拍、报警等）。"),
    ("Zammad", "开源客服工单系统。"),
    ("Salesforce", "CRM 平台；此处为客户/工单相关数据源。"),
    ("stub", "占位实现：接口与数据模型就绪，但尚未接通真实系统。"),
    ("PII", "Personally Identifiable Information，个人身份信息（姓名/邮箱/电话）；锻造时自动脱敏。"),
    ("min_samples", "每个类别最少真实样本数，低于即判定为缺口并触发合成。"),
    ("synth_per_gap", "每个缺口类别补充合成的样本数量。"),
    ("JSONL", "每行一个 JSON 对象的文本格式，样本与评估数据常用。"),
    ("drift", "漂移：数据分布或质量随时间偏移，可能让模型失效；需持续检测并触发再训练。"),
    ("漂移", "数据分布/质量随时间偏移，模型效果随之衰减；监控项之一。"),
    ("bad case", "失败/低质样本挖掘：从评估结果中找出表现差的样本，归类归因。"),
    ("force", "强制推进：豁免拦截，但 gate 照常评估并留痕，例外进入审计日志。"),
    ("qualification", "问题框定：确认问题真实、客户有预算与意愿的阶段。"),
    ("stakeholder_map", "干系人地图：识别拍板人、使用者、反对者等角色及其诉求。"),
    ("prototype", "真实数据原型：用客户真实数据（非演示数据）搭建可验证原型。"),
    ("AgentState", "AgentScope 的智能体状态对象；权限上下文经其注入运行时。"),
    ("Toolkit", "AgentScope 的工具集合对象：把连接器/函数绑定为智能体可调用的工具。"),
    ("SubAgentTemplate", "AgentScope 的子智能体蓝图：预置角色、工具与提示词的模板。"),
    (
        "技能库",
        "沉淀的可复用方法论/经验文档，分 research / implementation / optimization / methodology 四类。",
    ),
    ("工作台", "跨项目总览：全局统计、项目矩阵与最近沉淀。"),
    ("现场记录", "Journal：research / implementation / optimization 三类现场笔记，可一键沉淀为技能草稿。"),
    ("沉淀", "把现场经验固化成可复用技能/文档，供后续项目检索复用。"),
    ("门禁", "当前阶段适用的 gate 校验结果（通过/拦截）。"),
]

_GLOSSARY_CSS = """
.term{position:relative;cursor:help;border-bottom:1px dashed #5a6b85;outline:none}
.term:hover,.term:focus{border-bottom-color:var(--accent)}
.term .q{display:inline-block;width:13px;height:13px;margin-left:3px;border:1px solid var(--muted);
border-radius:50%;color:var(--muted);font-size:9px;line-height:12px;text-align:center;font-weight:700;
vertical-align:1px;transition:color .12s,border-color .12s}
.term:hover .q,.term:focus .q{color:var(--accent);border-color:var(--accent)}
.term .tip{position:absolute;left:0;bottom:calc(100% + 9px);z-index:999;width:max-content;
max-width:min(300px,78vw);padding:9px 12px;border-radius:9px;background:var(--panel2);
border:1px solid var(--accent);box-shadow:0 10px 28px rgba(0,0,0,.5);color:var(--fg);
font-size:.76rem;line-height:1.6;font-weight:400;letter-spacing:normal;text-transform:none;
white-space:normal;text-align:left;opacity:0;visibility:hidden;pointer-events:none;
transform:translateY(5px);transition:opacity .13s ease,transform .13s ease,visibility .13s}
.term:hover .tip,.term:focus .tip{opacity:1;visibility:visible;pointer-events:auto;transform:translateY(0)}
.term.tip-flip .tip{left:auto;right:0}
.term.tip-below .tip{bottom:auto;top:calc(100% + 9px)}
"""

_GLOSSARY_JS = r"""(() => {
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const escapeRe = t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const ASCII_TERM = /^[A-Za-z0-9][A-Za-z0-9 /+.-]*$/;
// id/slug 内的子串不标注（如 eng-caocao-ticket-seed05 里的 ticket、prototype_real_data 里的 prototype）
const ADJACENT = /[-_A-Za-z0-9]/;
const GLOSSARY = __GLOSSARY_DATA__.slice().sort((a, b) => b[0].length - a[0].length)
  .map(([term, tip]) => ({ term, tip, ascii: ASCII_TERM.test(term),
    pat: ASCII_TERM.test(term) ? '\\b' + escapeRe(term) : escapeRe(term) }));

function glossify(root) {
  if (!root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(n) {
      const p = n.parentElement;
      return (p && n.nodeValue.trim() && !p.closest('.term,.tip,script,style,textarea,option,.cli,pre,code')) ? 1 : 2;
    }
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    let text = node.nodeValue;
    const marks = [];
    for (const g of GLOSSARY) {
      if (!new RegExp(g.pat, 'i').test(text)) continue;
      text = text.replace(new RegExp(g.pat, 'gi'), (m, off, full) => {
        if (g.ascii && (ADJACENT.test(full[off - 1] || '') || ADJACENT.test(full[off + m.length] || ''))) return m;
        marks.push([m, g.tip]);
        return '\u0001' + marks.length + '\u0001';
      });
    }
    if (!marks.length) continue;
    const html = esc(text).replace(/\u0001(\d+)\u0001/g, (_, i) => {
      const [m, tip] = marks[i - 1];
      return '<span class="term" tabindex="0">' + esc(m) +
        '<span class="tip">' + esc(tip) + '</span><span class="q">?</span></span>';
    });
    const wrap = document.createElement('span');
    wrap.innerHTML = html;
    node.parentNode.replaceChild(wrap, node);
    wrap.querySelectorAll('.term').forEach(t => {
      const r = t.getBoundingClientRect();
      if (r.top < 130) t.classList.add('tip-below');
      else if (r.left > window.innerWidth * 0.62) t.classList.add('tip-flip');
    });
  }
}
window.glossify = glossify;
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => glossify(document.body));
} else {
  glossify(document.body);
}
})();
"""


def _glossary_snippet() -> str:
    data = json.dumps(_GLOSSARY, ensure_ascii=False)
    js = _GLOSSARY_JS.replace("__GLOSSARY_DATA__", data)
    return f"<style>{_GLOSSARY_CSS}</style><script>{js}</script>"


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def overview() -> str:
    """The landing page: a one-screen overview of every capability."""
    return _OVERVIEW_HTML


@app.get("/console", response_class=HTMLResponse)
def dashboard() -> str:
    """The engagement console (the detailed workbench)."""
    return _DASHBOARD_HTML


_OVERVIEW_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FDE Scope · 功能总览</title>
<style>
:root{--bg:#0b0e14;--panel:#131822;--panel2:#1a2030;--fg:#e6edf3;--muted:#8b98a9;
--accent:#2dd4bf;--warn:#fbbf24;--bad:#f87171;--good:#4ade80;--border:#242c3d;--code:#0d1117}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,"PingFang SC","Segoe UI",sans-serif;background:var(--bg);color:var(--fg);line-height:1.6}
header{padding:20px 28px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:14px}
header .logo{font-size:1.5rem;font-weight:800}
header .logo span{color:var(--accent)}
header .tag{color:var(--accent);font-size:.75rem;background:#0d2e2a;padding:3px 10px;border-radius:6px;font-weight:600}
header .nav{margin-left:auto;display:flex;gap:6px}
header .nav a{color:var(--muted);font-size:.85rem;padding:6px 12px;border-radius:6px;border:1px solid transparent}
header .nav a:hover{color:var(--fg);border-color:var(--border)}
header .nav a.active{color:var(--accent);border-color:var(--accent)}
.wrap{max-width:1200px;margin:0 auto;padding:28px 24px}
.hero{text-align:center;padding:36px 0 28px}
.hero h2{font-size:1.9rem;margin:0 0 10px;font-weight:800}
.hero p{color:var(--muted);font-size:1.05rem;margin:0 auto;max-width:680px}
.hero .cta{margin-top:22px;display:flex;gap:10px;justify-content:center}
.btn{background:var(--accent);color:#04201d;border:0;padding:10px 18px;border-radius:8px;font-weight:700;cursor:pointer;font-size:.95rem;text-decoration:none;display:inline-block}
.btn.ghost{background:transparent;border:1px solid var(--border);color:var(--fg)}
.btn:hover{opacity:.9}
.sec-title{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin:36px 0 14px;border-bottom:1px solid var(--border);padding-bottom:8px}
.sec-note{font-size:.78rem;color:var(--muted);margin:-6px 0 14px;line-height:1.6}
.grid{display:grid;gap:14px}
.cols-4{grid-template-columns:repeat(4,1fr)}
.cols-3{grid-template-columns:repeat(3,1fr)}
.cols-2{grid-template-columns:repeat(2,1fr)}
@media(max-width:900px){.cols-4,.cols-3,.cols-2{grid-template-columns:1fr}}
.tile{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px;transition:border-color .15s,transform .15s}
.tile:hover{border-color:var(--accent);transform:translateY(-2px)}
.tile .icon{font-size:1.8rem;margin-bottom:8px}
.tile .name{font-weight:700;font-size:1rem;margin-bottom:4px}
.tile .desc{color:var(--muted);font-size:.82rem;line-height:1.5}
.tile .status{display:inline-block;margin-top:8px;padding:1px 8px;border-radius:999px;font-size:.68rem;font-weight:600}
.s-ok{background:#0f3d2e;color:var(--good)}
.s-partial{background:#3b2a1a;color:var(--warn)}
.s-stub{background:#2a1a1a;color:var(--bad)}
.step-flow{display:flex;flex-wrap:wrap;align-items:stretch;gap:0}
.zone{flex:1;min-width:200px;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px;margin:0 4px;position:relative}
.zone .ztag{font-size:.7rem;color:var(--accent);text-transform:uppercase;letter-spacing:.06em;font-weight:700}
.zone .zname{font-size:.95rem;font-weight:700;margin:4px 0 8px}
.zone ol{margin:0;padding-left:18px;font-size:.82rem;color:var(--muted)}
.zone ol li{margin-bottom:3px}
.zone ol li b{color:var(--fg)}
.stat{text-align:center;padding:14px;background:var(--panel2);border:1px solid var(--border);border-radius:10px}
.stat .num{font-size:2rem;font-weight:800;color:var(--accent)}
.stat .lab{font-size:.78rem;color:var(--muted)}
.kpi-row{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border);font-size:.85rem}
.kpi-row:last-child{border:0}
.kpi-row .v{font-weight:700;color:var(--accent)}
.cli{background:var(--code);border:1px solid var(--border);border-radius:8px;padding:14px;font-family:"SF Mono",Consolas,monospace;font-size:.8rem;overflow-x:auto}
.cli .c{color:var(--muted)}
.cli .cmd{color:var(--accent)}
footer{text-align:center;color:var(--muted);font-size:.8rem;padding:30px 0 20px;border-top:1px solid var(--border);margin-top:30px}
</style>
</head>
<body>
<header>
  <div class="logo">FDE <span>Scope</span></div>
  <span class="tag">72h · raw data → deployed agent</span>
  <nav class="nav">
    <a href="/" class="active">功能总览</a>
    <a href="/console">Engagement 控制台 →</a>
    <a href="#arch">架构清单</a>
    <a href="#practices">最佳实践</a>
    <a href="/docs/fde_sop_full.md" target="_blank">SOP 文档</a>
  </nav>
</header>

<div class="wrap">

<div class="hero">
  <h2>FDE 的完整现场工作台</h2>
  <p>从第一次 Gemba walk 到签字移交——覆盖软件/SaaS 与具身机器人/制造业两类场景。
     18 阶段 SOP、10 个可执行合规 gate、10 个数据连接器、真实生产 KPI。</p>
  <div class="cta">
    <a class="btn" href="/console">进入 Engagement 控制台</a>
    <a class="btn ghost" href="#quickstart">快速上手</a>
  </div>
</div>

<div class="grid cols-4" style="margin-bottom:8px">
  <div class="stat"><div class="num">18</div><div class="lab">SOP 阶段（4 zones）</div></div>
  <div class="stat"><div class="num">10</div><div class="lab">可执行 gate</div></div>
  <div class="stat"><div class="num">10</div><div class="lab">数据连接器</div></div>
  <div class="stat"><div class="num">CI</div><div class="lab">测试全绿</div></div>
</div>

<div class="sec-title">🗺 完整 SOP · 18 阶段 · 4 Zones</div>
<div class="step-flow">
  <div class="zone">
    <div class="ztag">Zone A</div><div class="zname">立项勘察</div>
    <ol><li><b>qualification</b> 问题框定</li><li><b>site_survey</b> 🚦🏭 Gemba</li><li><b>stakeholder_map</b> 双 sponsor</li><li><b>success_criteria</b> 🚦 契约化</li></ol>
  </div>
  <div class="zone">
    <div class="ztag">Zone B</div><div class="zname">构建</div>
    <ol><li><b>connect</b> 数据接入</li><li><b>corpus</b> 语料锻造</li><li><b>prototype</b> 真实数据原型</li><li><b>validate</b> 验证</li><li><b>deploy</b> 🚦🏭 FAT/SAT</li><li><b>eval</b> 评估</li></ol>
  </div>
  <div class="zone">
    <div class="ztag">Zone C</div><div class="zname">运营化</div>
    <ol><li><b>slo_sla</b> 🚦 SLO+on-call</li><li><b>runbook</b> 应急手册</li><li><b>monitoring</b> 漂移检测</li><li><b>change_mgmt</b> 🚦🏭 工会</li><li><b>flywheel</b> 飞轮产品化</li></ol>
  </div>
  <div class="zone">
    <div class="ztag">Zone D</div><div class="zname">交接退场</div>
    <ol><li><b>ops_handoff</b> 运维移交</li><li><b>knowledge_transfer</b> 知识转移</li><li><b>disengage</b> 🚦 签字退场</li></ol>
  </div>
</div>

<div class="sec-title">🚦 10 个可执行合规 Gate（工业 overlay）</div>
<p class="sec-note">Gate 是谓词，不是清单：清单记录"曾经查过"，随现实漂移单向腐化；gate 在每次推进时重新评估，过期 passed 不作数。--force 只豁免拦截、照常评估留痕，例外进入审计日志。</p>
<div class="grid cols-4">
  <div class="tile"><div class="name">site_survey 🏭</div><div class="desc">现场勘察记录校验</div></div>
  <div class="tile"><div class="name">success_criteria</div><div class="desc">双 sponsor + 可度量 done</div></div>
  <div class="tile"><div class="name">fat_sat 🏭</div><div class="desc">FAT/SAT 验收签字</div></div>
  <div class="tile"><div class="name">functional_safety 🏭</div><div class="desc">ISO 13849 / IEC 61508 / ISO 10218</div></div>
  <div class="tile"><div class="name">conformity 🏭</div><div class="desc">CE / EU AI Act conformity</div></div>
  <div class="tile"><div class="name">works_council 🏭</div><div class="desc">德国 BetrVG §87 工会共决</div></div>
  <div class="tile"><div class="name">air_gap 🏭</div><div class="desc">air-gapped 部署清单</div></div>
  <div class="tile"><div class="name">shift_handover 🏭</div><div class="desc">24/7 班次交接集成</div></div>
  <div class="tile"><div class="name">slo</div><div class="desc">SLO + on-call 定义</div></div>
  <div class="tile"><div class="name">handoff_signoff</div><div class="desc">移交包签字确认</div></div>
</div>

<div class="sec-title">🔌 10 个数据连接器</div>
<div class="grid cols-4">
  <div class="tile"><div class="icon">📄</div><div class="name">CSV</div><div class="desc">通用兜底，冷启动</div><span class="status s-ok">真实可用</span></div>
  <div class="tile"><div class="icon">🗄</div><div class="name">MySQL</div><div class="desc">关系库直连</div><span class="status s-ok">真实可用</span></div>
  <div class="tile"><div class="icon">📡</div><div class="name">MQTT-Sparkplug</div><div class="desc">工厂设备遥测</div><span class="status s-ok">JSONL 可用</span></div>
  <div class="tile"><div class="icon">🏭</div><div class="name">MES (ISA-95)</div><div class="desc">工单/质量/停机</div><span class="status s-ok">JSONL 可用</span></div>
  <div class="tile"><div class="icon">⚙️</div><div class="name">OPC UA</div><div class="desc">PLC tag 读取（asyncua 驱动）</div><span class="status s-ok">真实可用</span></div>
  <div class="tile"><div class="icon">🤖</div><div class="name">ROS2 Bag</div><div class="desc">机器人轨迹回放</div><span class="status s-stub">stub</span></div>
  <div class="tile"><div class="icon">📈</div><div class="name">Historian</div><div class="desc">时序历史库</div><span class="status s-stub">stub</span></div>
  <div class="tile"><div class="icon">🎫</div><div class="name">Zammad</div><div class="desc">工单系统</div><span class="status s-stub">stub</span></div>
  <div class="tile"><div class="icon">☁️</div><div class="name">Salesforce</div><div class="desc">CRM</div><span class="status s-stub">stub</span></div>
  <div class="tile"><div class="icon">📑</div><div class="name">Documents</div><div class="desc">PDF/Word/Excel/PPT 解析（agentscope.rag，延迟导入）</div><span class="status s-partial">需 [agentscope]</span></div>
</div>

<div class="sec-title">⚙️ 6 大功能模块</div>
<div class="grid cols-3">
  <div class="tile"><div class="icon">🔬</div><div class="name">Corpus Engine</div><div class="desc">脱敏→去重→质量门→覆盖度分析→缺口检测→针对性合成→报告。<b>核心差异化</b>：合成是补盲区不是凑数量。</div></div>
  <div class="tile"><div class="icon">📊</div><div class="name">Eval 评估</div><div class="desc">ticket 指标 + 制造业 KPI（OEE/MTBF/抓取率/碰撞率）+ bad case 挖掘 + 自动建议。</div></div>
  <div class="tile"><div class="icon">🚀</div><div class="name">Deploy 部署</div><div class="desc">角色 Agent 真实装配：沙箱 workspace + 权限上下文（经 AgentState 注入）+ Toolkit 工具绑定 + SubAgentTemplate 蓝图，全部真实 AgentScope 2.0 API。</div></div>
  <div class="tile"><div class="icon">🔄</div><div class="name">Flywheel 飞轮</div><div class="desc">概念事件→真实事件映射 + 语料回流 + 周度增量重训。</div></div>
  <div class="tile"><div class="icon">🗂</div><div class="name">SOP 状态机</div><div class="desc">18 阶段推进/回滚，gate 不通过即拦截。</div></div>
  <div class="tile"><div class="icon">🌐</div><div class="name">Web 控制台</div><div class="desc">交互式 engagement 仪表盘 + gate + forge + KPI。</div></div>
</div>

<div class="sec-title" id="arch">🏗 架构清单 · 四层 + 横切（证据化建模见 docs/architecture-model/）</div>
<div class="grid cols-3">
  <div class="tile"><div class="name">🖥 UI 层</div><div class="desc">CLI（Typer，全延迟导入）· Web 控制台（27 路由）· QwenPaw PawApp（18 路由 /api/fde-scope）· macOS App（DMG 双击即用，即本控制台）。</div></div>
  <div class="tile"><div class="name">🧭 SOP 层</div><div class="desc">engagement/：18 阶段 · 4 zones · 10 个可执行 gate（advance 实时重评估）+ handoff；profiles/：ticket · manufacturing 场景选择器。</div></div>
  <div class="tile"><div class="name">⚙️ 能力层</div><div class="desc">connectors · corpus · deploy · eval · flywheel · integrations · skills —— 核心数据管线，规则为底、LLM 可选增强。</div></div>
  <div class="tile"><div class="name">🧰 横切层</div><div class="desc">llm.py（唯一 LLM 出口，失败回退规则路径）· config.py · templates/（Jinja 报告与 runbook）· paths.py（data_root 唯一路径解析）。</div></div>
  <div class="tile"><div class="name">💾 文件事实源</div><div class="desc">零数据库：.fde_scope/（engagements · skills · uploads）+ reports/；一律经 fsutil.atomic_write_text 原子写。</div></div>
  <div class="tile"><div class="name">🔌 外部依赖（全可选）</div><div class="desc">AgentScope 2.0.x（extra，实测窗口 >=2.0.4.post1,&lt;3；deploy 三支柱 + documents 延迟导入）· MiMo LLM（凭据仅环境变量）· QwenPaw 宿主。</div></div>
</div>

<div class="sec-title" id="practices">✅ 工程最佳实践 · 六条不变式（AGENTS.md，架构守护测试钉住）</div>
<div class="grid cols-3">
  <div class="tile"><div class="name">1 · Gate 实时重评估</div><div class="desc">advance() 每次重评当前阶段全部 gate，过期通过不作数；强推也评估留痕。禁止缓存/短路。</div></div>
  <div class="tile"><div class="name">2 · ID 服务端生成</div><div class="desc">SkillRecord.id / EngagementContext.id 由所属服务分配，外部输入永远不能指定。</div></div>
  <div class="tile"><div class="name">3 · 凭据只走环境变量</div><div class="desc">API key 不落 manifest / 报告 / engagement JSON / 日志。</div></div>
  <div class="tile"><div class="name">4 · 原子写盘</div><div class="desc">一切用户状态经 fsutil.atomic_write_text（临时文件 + os.replace），禁止裸 write_text。</div></div>
  <div class="tile"><div class="name">5 · 规则授权是唯一通道</div><div class="desc">build_toolkit 不打 is_read_only（上游 ≥2.0.5 read-only 先放行）；未匹配工具按模式回退 DEFAULT→ASK / DONT_ASK→DENY。</div></div>
  <div class="tile"><div class="name">6 · 实测版本窗口</div><div class="desc">pyproject 与 docs 逐字引用同一 agentscope specifier，放宽前逐版本真库跑测。</div></div>
</div>
<p class="sec-note">验证锚点：make test · pytest tests/test_architecture_guard.py（6 项契约）· pytest -m agentscope（真库运行时）· ruff check + format --check · 架构证据模型 docs/architecture-model/architecture-map.md</p>

<div class="sec-title">📈 制造业 KPI（实测 BMW 数据）</div>
<div class="grid cols-4">
  <div class="tile"><div class="name">OEE</div><div class="kpi-row"><span>设备综合效率</span><span class="v">0.724</span></div><div class="desc">世界级 ≥0.85</div></div>
  <div class="tile"><div class="name">抓取成功率</div><div class="kpi-row"><span>pick success</span><span class="v">0.793</span></div><div class="desc">DexNet 基准 ~0.80</div></div>
  <div class="tile"><div class="name">MTBF</div><div class="kpi-row"><span>平均无故障(h)</span><span class="v">39.8</span></div><div class="desc">越高越好</div></div>
  <div class="tile"><div class="name">碰撞/干预率</div><div class="kpi-row"><span>per cycle</span><span class="v">1.08%</span></div><div class="desc">越低越好</div></div>
</div>

<div class="sec-title" id="quickstart">🚀 快速上手</div>
<div class="grid cols-2">
  <div class="tile">
    <div class="name">CLI 命令行</div>
    <div class="cli">
<span class="c"># 安装（核心层零依赖）</span><br>
<span class="cmd">pip install -e ".[dev]"</span><br><br>
<span class="c"># 启动制造业 engagement</span><br>
<span class="cmd">fde-scope</span> engage init --customer BMW --profile manufacturing<br><br>
<span class="c"># 推进 SOP（gate 拦截）</span><br>
<span class="cmd">fde-scope</span> engage advance &lt;id&gt;<br>
<span class="cmd">fde-scope</span> gate check &lt;id&gt; --gate fat_sat<br><br>
<span class="c"># 语料锻造 + KPI</span><br>
<span class="cmd">fde-scope</span> corpus --input alarm.jsonl --out r.html<br>
<span class="cmd">fde-scope</span> kpi &lt;id&gt; --samples station.jsonl<br><br>
<span class="c"># 生成移交包</span><br>
<span class="cmd">fde-scope</span> handoff &lt;id&gt; --accept
    </div>
  </div>
  <div class="tile">
    <div class="name">Web 界面</div>
    <div class="cli">
<span class="c"># 启动交互控制台</span><br>
<span class="cmd">pip install -e ".[web]"</span><br>
<span class="cmd">fde-scope</span> web<br><br>
<span class="c">→ http://127.0.0.1:8080</span><br><br>
<span class="c"># 控制台功能：</span><br>
· 新建 engagement（选 profile）<br>
· 18 阶段可视化 + gate 拦截<br>
· CSV → 语料锻造（HTML 报告）<br>
· KPI 计算（ticket / 制造业）<br>
· 推进/回滚 SOP 状态机
    </div>
  </div>
</div>

<div class="sec-title">📦 两种场景</div>
<div class="grid cols-2">
  <div class="tile">
    <div class="name">🎫 ticket · 客服工单</div>
    <div class="desc">CSV/Zammad/Salesforce/MySQL 接入。意图准确率、回复采纳率、升级率评估。无工业 gate。</div>
    <span class="status s-ok">完整可用</span>
  </div>
  <div class="tile">
    <div class="name">🏭 manufacturing · 具身机器人</div>
    <div class="desc">OPC UA/MQTT/ROS2/MES/Historian 接入。OEE/MTBF/抓取率/碰撞率 + 6 个工业合规 gate。</div>
    <span class="status s-partial">核心可用 · 工业IO部分 stub</span>
  </div>
</div>

<footer>
  FDE Scope · 基于真实 AgentScope 2.0 API · MIT License<br>
  测试套件 CI 全绿（含架构守护测试 6 项契约）· 零配置可跑
</footer>

</div>
__GLOSSARY__
</body>
</html>
"""


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FDE Scope · Engagement Console</title>
<style>
:root{--bg:#0b0e14;--panel:#131822;--panel2:#1a2030;--fg:#e6edf3;--muted:#8b98a9;
--accent:#2dd4bf;--warn:#fbbf24;--bad:#f87171;--good:#4ade80;--border:#242c3d;--code:#0d1117}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,"PingFang SC","Segoe UI",sans-serif;background:var(--bg);color:var(--fg)}
a{color:var(--accent);text-decoration:none}
header{padding:18px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}
header h1{margin:0;font-size:1.3rem}
header .v{color:var(--accent);font-size:.8rem;background:#0d2e2a;padding:2px 8px;border-radius:6px}
header .sub{color:var(--muted);font-size:.85rem;margin-left:auto}
.layout{display:grid;grid-template-columns:320px 1fr;min-height:calc(100vh - 61px)}
.sidebar{border-right:1px solid var(--border);padding:16px;overflow-y:auto}
.main{padding:20px;overflow-y:auto}
h2{font-size:1rem;margin:0 0 10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:12px}
.eng{cursor:pointer;transition:border-color .15s}
.eng:hover{border-color:var(--accent)}
.eng .id{font-weight:600}
.meta{color:var(--muted);font-size:.8rem}
.eng .meta{color:var(--muted);font-size:.78rem;margin-top:3px}
.pill{display:inline-block;padding:1px 7px;border-radius:999px;font-size:.7rem;background:#1e2738}
.pill.ind{background:#3b2a1a;color:var(--warn)}
.pill.tkt{background:#1a2e2a;color:var(--accent)}
button,.btn{background:var(--accent);color:#04201d;border:0;padding:7px 12px;border-radius:6px;font-weight:600;cursor:pointer;font-size:.85rem}
button.ghost{background:transparent;border:1px solid var(--border);color:var(--fg)}
button:disabled{opacity:.4;cursor:not-allowed}
input,select{background:var(--code);border:1px solid var(--border);color:var(--fg);padding:6px 9px;border-radius:6px;font-size:.85rem;width:100%}
textarea{background:var(--code);border:1px solid var(--border);color:var(--fg);padding:6px 9px;border-radius:6px;font-size:.85rem;width:100%;font-family:inherit;resize:vertical}
.row{display:flex;gap:8px;align-items:center;margin-bottom:8px}
.row label{min-width:90px;color:var(--muted);font-size:.8rem}
.phases{display:flex;flex-direction:column;gap:6px}
.phase{display:flex;align-items:center;gap:8px;padding:7px 10px;border-radius:6px;background:var(--panel2);font-size:.85rem}
.phase.done{opacity:.55}
.phase.current{background:#0d2e2a;border:1px solid var(--accent)}
.phase .idx{width:22px;height:22px;border-radius:50%;background:#2a3346;display:flex;align-items:center;justify-content:center;font-size:.72rem}
.phase.current .idx{background:var(--accent);color:#04201d}
.zone-tag{font-size:.66rem;color:var(--muted);margin-left:auto}
.gate{padding:10px;border-radius:8px;margin-bottom:8px;border:1px solid var(--border)}
.gate.pass{border-color:var(--good);background:#0f1f15}
.gate.fail{border-color:var(--bad);background:#1f0f0f}
.gate .h{display:flex;justify-content:space-between;margin-bottom:4px}
.gate ul{margin:4px 0 0;padding-left:18px;font-size:.8rem}
pre{background:var(--code);padding:10px;border-radius:6px;overflow:auto;font-size:.78rem;border:1px solid var(--border)}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px}
.kpi{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:10px}
.kpi .k{color:var(--muted);font-size:.72rem;text-transform:uppercase}
.kpi .v{font-size:1.4rem;font-weight:700;margin-top:2px}
.tabs{display:flex;gap:4px;margin-bottom:14px;border-bottom:1px solid var(--border)}
.tab{padding:8px 14px;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent}
.tab.active{color:var(--accent);border-color:var(--accent)}
.hidden{display:none}
.empty{color:var(--muted);text-align:center;padding:30px;font-size:.9rem}
details summary{cursor:pointer;color:var(--accent);font-size:.85rem;padding:6px 0}
</style>
</head>
<body>
<header>
  <h1>FDE Scope <span class="v">Engagement Console</span></h1>
  <span class="sub">72h from raw data to a deployed agent · 全 SOP 工作台</span>
  <a href="/" style="margin-left:auto;color:var(--muted);font-size:.85rem">← 功能总览</a>
</header>
<div class="layout">
  <aside class="sidebar">
    <div class="row" style="margin-bottom:8px">
      <button style="flex:1" onclick="go('workbench')">📊 工作台</button>
      <button class="ghost" style="flex:1" onclick="go('skills')">📚 技能库</button>
    </div>
    <button class="ghost" style="width:100%;margin-bottom:14px" onclick="go('deploy')">🤖 Agent 部署</button>
    <h2>Engagements</h2>
    <div id="eng-list"></div>
    <div class="card" style="margin-top:16px">
      <h2 style="margin-bottom:10px">新建 Engagement</h2>
      <div class="row"><label>客户</label><input id="new-customer" placeholder="BMW Spartanburg"></div>
      <div class="row"><label>Profile</label>
        <select id="new-profile"><option value="ticket">ticket / 客服</option><option value="manufacturing">manufacturing / 制造业</option></select>
      </div>
      <button onclick="createEng()" style="width:100%">+ 创建</button>
    </div>
    <div class="card">
      <h2 style="margin-bottom:10px">工具</h2>
      <a class="btn ghost" style="display:block;text-align:center;margin-bottom:6px" href="/reports/" target="_blank">📁 报告归档</a>
      <button class="ghost" style="width:100%" onclick="loadProfiles()">查看 Profiles & Phases</button>
    </div>
  </aside>
  <main class="main" id="main">
    <div id="view-workbench"></div>
    <div id="view-skills" class="hidden"></div>
    <div id="view-deploy" class="hidden"></div>
    <div id="view-detail" class="hidden"><div class="empty">← 选择或创建一个 engagement 开始</div></div>
  </main>
</div>

<script>
const API = '';
let current = null;

function showView(name) {
  ['workbench','skills','deploy','detail'].forEach(v=>{
    const e=document.getElementById('view-'+v); if(e) e.classList.toggle('hidden', v!==name);
  });
}

function go(name) {
  showView(name);
  if (name==='skills') location.hash = 'skills';
  else if (location.hash) history.replaceState(null,'',location.pathname);
  if (name==='workbench') loadWorkbench();
  if (name==='skills') loadSkills();
  if (name==='deploy') renderDeploy();
}

// -- 工作台 ---------------------------------------------------------------
async function loadWorkbench() {
  const w = await api('/api/workbench');
  const st = w.stats;
  const phaseChips = Object.entries(st.phase_distribution).map(([p,n])=>
    `<span class="pill">${escapeHtml(p)}: ${n}</span>`).join('') || '<span class="meta">—</span>';
  document.getElementById('view-workbench').innerHTML = `
    <div class="kpi-grid" style="margin-bottom:14px">
      <div class="kpi"><div class="k">进行中项目</div><div class="v">${st.active_projects}</div></div>
      <div class="kpi"><div class="k">技能总数</div><div class="v">${st.total_skills}</div></div>
      <div class="kpi"><div class="k">待审草稿</div><div class="v" style="color:${st.draft_skills?'var(--warn)':'var(--fg)'}">${st.draft_skills}</div></div>
      <div class="kpi"><div class="k">阶段分布</div><div class="v" style="font-size:.85rem;line-height:1.5">${phaseChips}</div></div>
    </div>
    <div class="card"><h2>跨项目矩阵</h2>${matrixHtml(w.matrix)}</div>
    <div class="card"><h2>最近沉淀 <button class="ghost" style="margin-left:8px;font-size:.7rem" onclick="go('skills')">去沉淀 →</button></h2>${recentHtml(w.recent_skills)}</div>`;
  if (window.glossify) glossify(document.getElementById('view-workbench'));
}

function matrixHtml(matrix) {
  if (!matrix.length) return '<div class="empty">暂无项目 — 左侧创建第一个 engagement</div>';
  const rows = matrix.map(s => {
    const ts = Object.values(s.gate_records||{}).map(g=>g.checked_at).filter(Boolean).sort().pop() || '';
    return `<tr onclick="selectEng('${escapeHtml(s.engagement_id)}')" style="cursor:pointer">
      <td><b>${escapeHtml(s.customer)}</b><div class="meta">${escapeHtml(s.engagement_id)}</div></td>
      <td><span class="pill ${s.profile==='manufacturing'?'ind':'tkt'}">${escapeHtml(s.profile)}</span></td>
      <td>${escapeHtml(s.current_phase)}<div class="meta">${escapeHtml(zoneLabel(s.current_zone))}</div></td>
      <td>${s.gate?`${escapeHtml(s.gate)} ${s.gate_passed?'✅':'❌'}`:'—'}</td>
      <td class="meta">${ts?escapeHtml(String(ts).slice(0,16).replace('T',' ')):'—'}</td>
      ${s.is_complete?'<td>✅ 完成</td>':''}
    </tr>`;
  }).join('');
  return `<table><thead><tr><th>客户</th><th>Profile</th><th>阶段</th><th>门禁</th><th>最近更新</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function recentHtml(skills) {
  if (!skills.length) return '<div class="empty">还没有沉淀 — 把现场经验变成可复用技能</div>';
  return skills.map(r => `<div class="card" style="display:flex;align-items:center;gap:10px">
    <div style="flex:1"><b>${escapeHtml(r.title)}</b>
      <div class="meta"><span class="pill">${escapeHtml(r.category)}</span>
      ${(r.tags||[]).length?' '+r.tags.map(t=>'#'+escapeHtml(t)).join(' '):''}</div></div>
    <button class="ghost" onclick="selectEng('${escapeHtml(r.source_engagement||'')}')" ${r.source_engagement?'':'disabled'}>查看来源</button>
  </div>`).join('');
}

// -- 技能库 ---------------------------------------------------------------
async function loadSkills() {
  const q = (document.getElementById('sk-q')||{}).value || '';
  const cat = (document.getElementById('sk-cat')||{}).value || '';
  const st = (document.getElementById('sk-status')||{}).value || 'published';
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (cat) params.set('category', cat);
  if (st) params.set('status', st);
  const list = await api('/api/skills?' + params);
  const drafts = await api('/api/skills/drafts');
  document.getElementById('view-skills').innerHTML = `
    <div class="card"><h2>技能库</h2>
      <div class="row"><label>搜索</label><input id="sk-q" value="${escapeHtml(q)}" placeholder="标题 / 正文关键词" onkeydown="if(event.key==='Enter')loadSkills()"></div>
      <div class="row"><label>分类</label><select id="sk-cat" onchange="loadSkills()">
        <option value="">全部</option>
        <option value="research">research</option><option value="implementation">implementation</option>
        <option value="optimization">optimization</option><option value="methodology">methodology</option></select>
        <label>状态</label><select id="sk-status" onchange="loadSkills()">
        <option value="published">published</option><option value="draft">draft</option><option value="archived">archived</option></select></div>
      ${list.map(skillCard).join('') || '<div class="empty">无匹配技能</div>'}
    </div>
    <div class="card"><h2>草稿审阅队列</h2>${draftCards(drafts)}</div>
    <div class="card"><h2>新建技能</h2>
      <div class="row"><label>标题</label><input id="sk-title" placeholder="如：OPC UA 连接踩坑"></div>
      <div class="row"><label>分类</label><select id="sk-new-cat">
        <option value="research">research 调研</option><option value="implementation" selected>implementation 实施</option>
        <option value="optimization">optimization 调优</option><option value="methodology">methodology 方法论</option></select></div>
      <div class="row"><label>标签</label><input id="sk-tags" placeholder="逗号分隔：opcua,plc"></div>
      <div class="row"><label>正文</label><textarea id="sk-body" rows="4" style="width:100%;background:var(--code);border:1px solid var(--border);color:var(--fg);border-radius:6px;font-size:.85rem;padding:6px 9px"></textarea></div>
      <button onclick="submitSkill()">+ 沉淀技能</button>
    </div>`;
  if (window.glossify) glossify(document.getElementById('view-skills'));
}

function skillCard(r) {
  const esc = escapeHtml;
  const act = r.status==='draft'
    ? `<button onclick="publishSkill('${esc(r.id)}')">发布</button> <button class="ghost" onclick="editSkill('${esc(r.id)}')">编辑</button>`
    : r.status==='published'
      ? `<button class="ghost" onclick="archiveSkill('${esc(r.id)}')">归档</button>` : '';
  return `<div class="card">
    <div class="row"><b>${esc(r.title)}</b>
      <span class="pill">${esc(r.category)}</span>
      <span class="pill ${r.status==='draft'?'ind':''}">${esc(r.status)}</span>
      <span class="meta" style="margin-left:auto">${esc(String(r.updated_at||'').slice(0,16).replace('T',' '))}</span></div>
    ${(r.tags||[]).length?`<div class="meta">${r.tags.map(t=>'#'+esc(t)).join(' ')}</div>`:''}
    <div class="meta">${esc(r.id)}${r.source_engagement?' · 来自 '+esc(r.source_engagement):''}</div>
    <div class="row" style="margin:8px 0 0">${act}</div>
  </div>`;
}

function draftCards(drafts) {
  if (!drafts.length) return '<div class="empty">无待审草稿 — 自动捕获与 gate 提示会出现在这里</div>';
  return drafts.map(r => `<div class="card" style="border-color:var(--warn)">
    <div class="row"><b>${escapeHtml(r.title)}</b>
      <span class="pill">${escapeHtml(r.category)}</span>
      <span class="pill ind">${escapeHtml(r.source)}</span>
      <span class="meta" style="margin-left:auto">${escapeHtml(String(r.created_at||'').slice(0,16).replace('T',' '))}</span></div>
    <div class="meta">${escapeHtml(r.id)}${r.phase_slug?' · phase: '+escapeHtml(r.phase_slug):''}${r.gate_slug?' · gate: '+escapeHtml(r.gate_slug):''}${r.source_engagement?' · 来自 '+escapeHtml(r.source_engagement):''}</div>
    <div class="row" style="margin:8px 0 0">
      <button onclick="publishSkill('${escapeHtml(r.id)}')">发布</button>
      <button class="ghost" onclick="editSkill('${escapeHtml(r.id)}')">编辑</button>
    </div></div>`).join('');
}

async function submitSkill() {
  const title = document.getElementById('sk-title').value.trim();
  if (!title) return alert('请填写标题');
  const tags = document.getElementById('sk-tags').value.split(',').map(s=>s.trim()).filter(Boolean);
  await api('/api/skills', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({title, category:document.getElementById('sk-new-cat').value,
      tags, body_md:document.getElementById('sk-body').value})});
  loadSkills();
}

async function publishSkill(sid) { await api(`/api/skills/${sid}/publish`, {method:'POST'}); loadSkills(); }
async function archiveSkill(sid) { await api(`/api/skills/${sid}/archive`, {method:'POST'}); loadSkills(); }

async function editSkill(sid) {
  const body = prompt('编辑正文（Markdown）：');
  if (body===null) return;
  await api(`/api/skills/${sid}`, {method:'PATCH', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({body_md: body})});
  loadSkills();
}

// -- 现场记录 -------------------------------------------------------------
function journalHtml(ctx) {
  const esc = escapeHtml;
  const entries = (ctx && ctx.journal) || [];
  const rows = entries.map(e => `<div class="card">
    <div class="row"><span class="pill">${esc(e.kind)}</span><span class="meta">${esc(e.ts)}</span>
      <span class="meta" style="margin-left:auto">${e.skill_id?'💡 '+esc(e.skill_id):''}</span></div>
    <div>${esc(e.note)}</div>
    ${e.skill_id?'':`<button class="ghost" style="margin-top:6px;font-size:.75rem" onclick="journalToSkill('${esc(e.id)}')">沉淀为技能</button>`}
  </div>`).join('') || '<div class="empty">暂无现场记录</div>';
  return `<div class="card"><h2>现场记录</h2>${rows}</div>
    <div class="card"><h2>追加记录</h2>
      <div class="row"><label>类型</label><select id="jn-kind">
        <option value="research">research 调研</option>
        <option value="implementation">implementation 实施</option>
        <option value="optimization">optimization 调优</option></select></div>
      <div class="row"><label>内容</label><input id="jn-note" placeholder="记录本次现场发现…"></div>
      <button onclick="addJournal()">+ 记录</button>
    </div>`;
}

async function addJournal() {
  const kind = document.getElementById('jn-kind').value;
  const note = document.getElementById('jn-note').value.trim();
  if (!note) return alert('请填写记录内容');
  await api(`/api/engagements/${current}/journal`, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({kind, note})});
  selectEng(current);
}

async function journalToSkill(jid) {
  const r = await api(`/api/engagements/${current}/journal/${jid}/skill`, {method:'POST'});
  alert(`已沉淀为技能草稿: ${r.id} (${r.category})`);
  selectEng(current);
}

// -- Agent 部署（dry-run 计划，与 CLI / PawApp 同一 build_deploy_plan） -----
let deployInit = false;
function renderDeploy() {
  if (deployInit) return;
  document.getElementById('view-deploy').innerHTML = `
    <div class="card"><h2>Agent 部署计划 · dry-run</h2>
      <div class="meta" style="margin-bottom:10px">与 <code>fde-scope deploy</code> / PawApp 走同一 <code>build_deploy_plan</code>：纯数据预览「哪个角色 Agent 拿到哪个连接器工具、对着哪个数据源」，不 import AgentScope、不调模型、不起服务。</div>
      <div class="row"><label>Tenant</label><input id="dp-tenant" value="acme"></div>
      <div class="row"><label>Profile</label><select id="dp-profile"><option value="ticket">ticket / 客服</option><option value="manufacturing">manufacturing / 制造业</option></select></div>
      <div class="row"><label>审批模式</label><select id="dp-mode">
        <option value="conservative">conservative · 例行外呼/高成本也 ASK</option>
        <option value="balanced" selected>balanced · 仅高风险 ASK</option>
        <option value="autonomous">autonomous · 无人值守（未匹配 DENY）</option></select></div>
      <div class="row"><label>模型</label><input id="dp-model" value="qwen-max"></div>
      <div class="row"><label>Agents</label><textarea id="dp-agents" rows="3" placeholder="每行一个：名字:角色[:模型]&#10;数据员:数据分析&#10;日志员:日志分析:qwen3-14b"></textarea></div>
      <div class="row"><label>数据源</label><textarea id="dp-sources" rows="2" placeholder="每行一个：slug=路径或URL&#10;csv=examples/quickstart_csv/sample_tickets.csv"></textarea></div>
      <div class="row" style="margin-bottom:0"><button onclick="runDeployPlan()">生成部署计划</button>
      <span class="meta">角色是自由文本 → 自动归 数据/日志/文件 工具桶；匹配不上 → corpus-only</span></div>
    </div>
    <div id="dp-result"><div class="empty">填写上方配置后点「生成部署计划」</div></div>
    <div class="card"><h2>注意事项</h2><ul style="margin:0;padding-left:18px;font-size:.85rem;line-height:1.8;color:var(--muted)">
      <li><b style="color:var(--fg)">数据源优先级</b>：Agent 级 <code>toolkit.sources</code> → tenant <code>sources</code> → 隐式字段（ticket 下 <code>ticket_api</code> 隐式喂 zammad/salesforce）。三处都没配的工具诚实标注 <span class="pill" style="color:var(--bad)">unbound</span>，不进 Toolkit、不假装可用。</li>
      <li><b style="color:var(--fg)">审批模式决定未匹配工具的命运</b>：绑定工具自动获得 ALLOW 规则；conservative / balanced 未匹配 → ASK（HITL 人工确认），autonomous → DENY。默认 deny 恒含 access_other_tenant / delete_any / exec_shell。</li>
      <li><b style="color:var(--fg)">skills_dirs 必须真实存在</b>（含 SKILL.md 的目录），技能经 <code>Toolkit(skills_or_loaders=…)</code> 注册，路径错误装配期即报。</li>
      <li><b style="color:var(--fg)">凭据只走环境变量</b>（<code>FDE_SCOPE_MIMO_API_KEY</code> 等）——不进 manifest / tenant_config / 报告。</li>
      <li><b style="color:var(--fg)">连接器 sample 每调用最多 50 行</b>（MAX_TOOL_ROWS），是预览不是导出通道。</li>
      <li><b style="color:var(--fg)">装配 ≠ 服务</b>：<code>deploy --serve</code> 需 <code>.[agentscope]</code> extra + Redis + 可达模型；2.0 无 <code>Agent.stop</code>，停服用 <code>TenantDeployer.stop()</code>。</li>
    </ul></div>`;
  deployInit = true;
}

function _parseAgentLines(text) {
  return text.split('\\n').map(s=>s.trim()).filter(Boolean).map(line=>{
    const parts = line.split(':').map(s=>s.trim());
    const a = {name: parts[0], role: parts[1] || ''};
    if (parts[2]) a.model = parts[2];
    return a;
  }).filter(a=>a.name && a.role);
}

function _parseSourceLines(text) {
  const out = {};
  text.split('\\n').map(s=>s.trim()).filter(Boolean).forEach(line=>{
    const i = line.indexOf('=');
    if (i > 0) out[line.slice(0,i).trim()] = line.slice(i+1).trim();
  });
  return out;
}

async function runDeployPlan() {
  const val = id => (document.getElementById(id)||{}).value || '';
  const body = {
    tenant: val('dp-tenant').trim() || 'acme',
    profile: val('dp-profile'),
    approval_mode: val('dp-mode'),
    model: val('dp-model').trim() || 'qwen-max',
    agents: _parseAgentLines(val('dp-agents')),
    sources: _parseSourceLines(val('dp-sources')),
  };
  const out = document.getElementById('dp-result');
  out.innerHTML = '<div class="empty">计算中…</div>';
  try {
    const plan = await api('/api/deploy/plan', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    out.innerHTML = planHtml(plan);
  } catch(e) {
    out.innerHTML = `<div class="gate fail"><b>校验失败（422）</b><pre>${escapeHtml(String(e.message||e))}</pre></div>`;
  }
}

function planHtml(plan) {
  const esc = escapeHtml;
  const m = plan.manifest, sum = plan.summary || {};
  const perm = m.permissions || {};
  const fmtRules = rules => (rules||[]).map(([t,c])=>`<span class="pill">${esc(t)}${c?` <span class="meta">${esc(c)}</span>`:''}</span>`).join(' ') || '<span class="meta">—</span>';
  const agents = (m.agents||[]).map(a => {
    const tools = (a.tools||[]).map(t => t.bound
      ? `<span class="pill tkt" title="${esc(t.note||'')}">${esc(t.tool)} → ${esc(t.source||'')}</span>`
      : `<span class="pill" style="color:var(--bad)" title="${esc(t.note||'')}">${esc(t.tool)} ✕ unbound</span>`).join(' ');
    const un = (a.unbound||[]);
    return `<div class="card" style="margin-bottom:8px">
      <div class="row"><b>${esc(a.name)}</b><span class="pill ${esc(a.role_bucket)==='corpus'?'ind':'tkt'}">${esc(a.role)} · ${esc(a.role_bucket||'corpus-only')}</span>
        <span class="pill">${esc(a.model||'runtime 注入')}</span>
        <span class="meta" style="margin-left:auto">bound ${((a.bound||[]).length)} · unbound ${un.length}</span></div>
      <div class="meta" style="margin:4px 0">连接器集：${(a.connectors||[]).map(esc).join(' · ') || '—'} ｜ system_prompt: ${esc((a.system_prompt||'').slice(0,72))}…</div>
      <div style="margin:6px 0">${tools || '<span class="meta">仅语料工具</span>'}</div>
      ${un.length?`<div class="meta" style="color:var(--warn)">⚠ 未绑定 ${un.length} 个工具 — 在「数据源」里给对应连接器配 slug=源 即可绑定</div>`:''}
    </div>`;
  }).join('');
  return `
    <div class="kpi-grid" style="margin-bottom:12px">
      <div class="kpi"><div class="k">Agents</div><div class="v">${sum.agents ?? (m.agents||[]).length}</div></div>
      <div class="kpi"><div class="k">Bound 工具</div><div class="v" style="color:var(--good)">${(sum.bound_tools||[]).length}</div></div>
      <div class="kpi"><div class="k">Unbound 工具</div><div class="v" style="color:${(sum.unbound_tools||[]).length?'var(--warn)':'var(--fg)'}">${(sum.unbound_tools||[]).length}</div></div>
      <div class="kpi"><div class="k">Sandbox / Collection</div><div class="v" style="font-size:.85rem;line-height:1.5">${esc(m.sandbox&&m.sandbox.backend)} · ${esc(m.corpus_collection)}</div></div>
    </div>
    ${agents}
    <div class="card"><h2>权限规则</h2>
      <div class="meta" style="margin-bottom:6px">审批模式：${esc(m.approval_policy&&m.approval_policy.mode)}（未匹配工具 → ${m.approval_policy&&m.approval_policy.mode==='autonomous'?'DENY':'ASK'}）</div>
      <div class="meta">ALLOW：${fmtRules(perm.allow)}</div>
      <div class="meta">DENY：${fmtRules(perm.deny)}</div>
      <div class="meta">ASK：${fmtRules(perm.ask)}</div>
    </div>
    <div class="card"><details><summary>查看完整 manifest JSON</summary><pre>${esc(JSON.stringify(m, null, 2))}</pre></details></div>`;
}

async function api(path, opts={}) {
  const r = await fetch(API+path, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function refreshList() {
  const list = await api('/api/engagements');
  const el = document.getElementById('eng-list');
  if (!list.length) { el.innerHTML = '<div class="empty" style="padding:14px">暂无</div>'; return; }
  el.innerHTML = list.map(s => `
    <div class="card eng" onclick="selectEng('${escapeHtml(s.engagement_id)}')">
      <div class="id">${escapeHtml(s.customer)}</div>
      <div class="meta">
        <span class="pill ${s.profile==='manufacturing'?'ind':'tkt'}">${escapeHtml(s.profile)}</span>
        ${escapeHtml(s.current_phase)} · ${escapeHtml(s.current_zone)}
        ${s.is_complete?' ✅':''}
      </div>
      <div class="meta">id: ${escapeHtml(s.engagement_id)}</div>
    </div>`).join('');
  if (window.glossify) glossify(el);
}

async function createEng() {
  const customer = document.getElementById('new-customer').value.trim();
  if (!customer) return alert('请填写客户名');
  const profile = document.getElementById('new-profile').value;
  await api('/api/engagements', {method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({customer, profile})});
  document.getElementById('new-customer').value = '';
  refreshList();
}

async function selectEng(eid) {
  current = eid;
  const s = await api(`/api/engagements/${eid}`);
  const phases = await api(`/api/phases?profile=${s.profile}`);
  const gates = await api(`/api/engagements/${eid}/gates`);
  renderDetail(s, phases, gates);
}

function zoneLabel(z){return {pre_engagement:'A·Pre',build:'B·Build',operationalization:'C·Ops',handoff:'D·Handoff'}[z]||z}

function renderDetail(s, phases, gates) {
  let curIdx = 0;
  phases.phases.forEach((p,i)=>{if(p.slug===s.current_phase) curIdx=i});
  const phaseHtml = phases.phases.map((p,i) => {
    const cls = i<curIdx?'done':(i===curIdx?'current':'');
    return `<div class="phase ${cls}">
      <span class="idx">${p.index}</span><span>${escapeHtml(p.name)}</span>
      ${p.industrial?'<span class="pill ind">🏭</span>':''}
      ${p.gates&&p.gates.length?`<span class="pill" title="gates: ${escapeHtml(p.gates.join(', '))}">🚦</span>`:''}
      <span class="zone-tag">${escapeHtml(zoneLabel(p.zone))}</span></div>`;
  }).join('');

  const gateHtml = Object.entries(gates).map(([slug,g])=>{
    const cls = g.passed?'pass':'fail';
    const blocks = g.blockers.map(b=>`<li>🚫 ${escapeHtml(b)}</li>`).join('');
    const warns = g.warnings.map(w=>`<li>⚠️ ${escapeHtml(w)}</li>`).join('');
    return `<div class="gate ${cls}"><div class="h"><b>${escapeHtml(g.name)}</b>
      <span>${g.passed?'✅ PASS':'❌ BLOCKED'}</span></div>
      ${blocks?`<ul>${blocks}</ul>`:''}${warns?`<ul>${warns}</ul>`:''}
      <button class="ghost" style="margin-top:6px;font-size:.75rem" onclick="recheck('${escapeHtml(slug)}')">重新校验</button></div>`;
  }).join('') || '<div class="empty">无适用 gate（当前 profile）</div>';

  const html = `
    <div class="tabs">
      <div class="tab active" onclick="tab('overview',this)">概览</div>
      <div class="tab" onclick="tab('sop',this)">SOP 阶段</div>
      <div class="tab" onclick="tab('gates',this)">Gates</div>
      <div class="tab" onclick="tab('context',this)">Context</div>
      <div class="tab" onclick="tab('forge',this)">Corpus Forge</div>
      <div class="tab" onclick="tab('kpi',this)">KPI</div>
      <div class="tab" onclick="tab('journal',this)">现场记录</div>
    </div>
    <div id="t-overview">
      <div class="card">
        <h2>Engagement</h2>
        <div class="row"><label>客户</label><b>${escapeHtml(s.customer)}</b></div>
        <div class="row"><label>Profile</label><span class="pill ${s.profile==='manufacturing'?'ind':'tkt'}">${escapeHtml(s.profile)}</span></div>
        <div class="row"><label>当前阶段</label><b style="color:var(--accent)">${escapeHtml(s.current_phase)}</b> (${escapeHtml(zoneLabel(s.current_zone))})</div>
        <div class="row"><label>下一阶段</label>${escapeHtml(s.next_phase||'— (完成)')}</div>
        <div class="row"><label>进度</label>${curIdx+1}/${phases.phases.length}</div>
        <div class="row" style="margin-top:10px">
          <button onclick="advance(false)">⏭ 推进到下一阶段</button>
          <button class="ghost" onclick="advance(true)">force 推进</button>
        </div>
      </div>
    </div>
    <div id="t-sop" class="hidden"><div class="card"><div class="phases">${phaseHtml}</div></div></div>
    <div id="t-gates" class="hidden">${gateHtml}</div>
    <div id="t-context" class="hidden">${contextHtml(s.context)}</div>
    <div id="t-forge" class="hidden"><div class="card">
      <h2>语料锻造（CSV → CorpusReport）</h2>
      <input type="file" id="forge-file" accept=".csv">
      <div class="row" style="margin-top:8px"><label>min_samples</label><input id="forge-min" value="5" type="number"></div>
      <div class="row"><label>synth_per_gap</label><input id="forge-synth" value="3" type="number"></div>
      <button onclick="forge()">锻造</button>
      <div id="forge-out" style="margin-top:10px"></div>
    </div></div>
    <div id="t-journal" class="hidden">${journalHtml(s.context)}</div>
    <div id="t-kpi" class="hidden"><div class="card">
      <h2>KPI 计算</h2>
      <div class="row"><label>profile</label>
        <select id="kpi-profile"><option value="manufacturing">manufacturing</option><option value="ticket">ticket</option></select></div>
      <input type="file" id="kpi-file" accept=".json,.jsonl">
      <button onclick="runKpi()">计算</button>
      <div id="kpi-out" style="margin-top:10px"></div>
    </div></div>
  `;
  document.getElementById('view-detail').innerHTML = html;
  showView('detail');
  if (window.glossify) glossify(document.getElementById('view-detail'));
}

function tab(name, el) {
  ['overview','sop','gates','context','forge','kpi','journal'].forEach(t=>{
    const e=document.getElementById('t-'+t); if(e) e.classList.toggle('hidden', t!==name);
  });
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
}

function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

function contextHtml(ctx) {
  if (!ctx) return '<div class="empty">无 context 数据</div>';
  const esc = escapeHtml;
  const site = ctx.site||{}, safety = ctx.safety||{}, assets = ctx.assets||{};
  // 现场 / Site
  let siteHtml;
  if (site.location) {
    const net = (site.networks||[]).map(n=>`<li>${esc(n)}</li>`).join('');
    siteHtml = `<div class="row"><label>地点</label><b>${esc(site.location)}</b></div>
      <div class="row"><label>班次</label>${esc(site.shift_count)} · OT/IT 隔离 ${site.ot_it_separated?'✅':'❌'} · 气隙 ${site.air_gapped?'✅':'❌'}</div>
      ${net?`<div class="row"><label>网络</label><ul style="margin:2px 0 0;padding-left:18px">${net}</ul></div>`:''}
      <div class="row"><label>资产</label>${(site.assets||[]).length} 项 · 工会代表 ${site.works_council_represented?'✅':'—'}</div>
      ${site.notes?`<div class="row"><label>备注</label>${esc(site.notes)}</div>`:''}`;
  } else {
    siteHtml = '<div class="empty">无现场数据（SaaS 项目）</div>';
  }
  // 干系人
  const stkRows = (ctx.stakeholders||[]).map(x=>`<tr>
    <td>${esc(x.name)}</td><td>${esc(x.role)}</td>
    <td>${x.is_sponsor?'<span class="pill" style="color:var(--good)">SPONSOR</span>':''}</td>
    <td>${esc(x.success_metric||'—')}</td></tr>`).join('');
  // 成功标准
  const crit = (ctx.success_criteria||[]).map(c=>`<li>${esc(c)}</li>`).join('')||'<li class="meta">未定义</li>';
  // SLO
  const sloRows = (ctx.slos||[]).map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.target)}</td><td>${esc(x.alert_route||'—')}</td><td>${esc(x.window)}</td></tr>`).join('')
    || '<tr><td colspan="4" class="meta">未定义 SLO</td></tr>';
  // 功能安全
  const safetyHtml = ctx.profile==='manufacturing'
    ? `<tr><td>ISO 13849</td><td>PLr ${esc(safety.required_plr||'—')} / PL ${esc(safety.achieved_pl||'—')}</td></tr>
    <tr><td>IEC 61508</td><td>SIL ${esc(safety.sil_required||'—')} / ${esc(safety.sil_achieved??'—')}</td></tr>
    <tr><td>ISO 10218 评估</td><td>${safety.iso10218_assessed?'✅':'❌'}</td></tr>
    <tr><td>EU AI Act 高风险</td><td>${safety.eu_ai_act_high_risk?'✅':'—'} · CE ${safety.ce_marking_done?'✅':'❌'}</td></tr>
    <tr><td>危险分析</td><td>${safety.hazard_analysis_done?'✅':'❌'}</td></tr>
    ${safety.risk_assessment_notes?`<tr><td>评估备注</td><td>${esc(safety.risk_assessment_notes)}</td></tr>`:''}`
    : '<tr><td colspan="2" class="meta">非工业 profile，无功能安全数据</td></tr>';
  // 产物与交付
  const evRows = Object.entries(assets.eval_metrics||{}).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('');
  const links = [];
  if (assets.runbook) links.push(`<a class="btn" href="/${esc(assets.runbook)}" target="_blank">📘 Runbook</a>`);
  if (assets.corpus_report) links.push(`<a class="btn" href="/${esc(assets.corpus_report)}" target="_blank">📄 语料报告</a>`);
  const mon = assets.monitoring||{};
  const known = (assets.known_limitations||[]).map(k=>`<li>${esc(k)}</li>`).join('');
  return `<div class="card"><h2>现场 / Site</h2>${siteHtml}</div>
    <div class="card"><h2>干系人</h2><table><thead><tr><th>姓名</th><th>角色</th><th>Sponsor</th><th>成功指标</th></tr></thead><tbody>${stkRows||'<tr><td colspan="4" class="meta">未记录</td></tr>'}</tbody></table></div>
    <div class="card"><h2>成功标准</h2><ul style="padding-left:18px">${crit}</ul></div>
    <div class="card"><h2>SLO</h2><table><thead><tr><th>名称</th><th>目标</th><th>告警路由</th><th>窗口</th></tr></thead><tbody>${sloRows}</tbody></table></div>
    <div class="card"><h2>功能安全</h2><table><tbody>${safetyHtml}</tbody></table></div>
    <div class="card"><h2>产物与交付</h2>
      <div class="row"><label>语料</label>${esc(assets.corpus_summary||'—')}</div>
      <div class="row"><label>模型</label>${esc(assets.model_name||'—')}</div>
      ${evRows?`<table style="margin-top:8px"><thead><tr><th>评估指标</th><th>值</th></tr></thead><tbody>${evRows}</tbody></table>`:''}
      <div class="row" style="margin-top:10px">${links.join(' ')||'—'}</div>
      ${known?`<div class="row"><label>已知局限</label><ul style="padding-left:18px">${known}</ul></div>`:''}
      <div class="row"><label>监控</label>漂移 ${mon.data_drift&&mon.data_drift.enabled?'✅ 每日':'❌ 未启用'} · 质量 ${mon.quality_drift&&mon.quality_drift.enabled?'✅ 每周':'❌ 未启用'}</div>
    </div>`;
}

async function advance(force) {
  const r = await api(`/api/engagements/${current}/advance?force=${force}`,{method:'POST'});
  if (!r.advanced) {
    const res = r.result;
    alert('推进被拦截:\\n' + (res.blockers||[]).join('\\n'));
  }
  selectEng(current);
}

async function recheck(slug) {
  await api(`/api/engagements/${current}/gate/${slug}`,{method:'POST'});
  selectEng(current);
}

async function forge() {
  const fd = new FormData();
  fd.append('file', document.getElementById('forge-file').files[0]);
  fd.append('min_samples', document.getElementById('forge-min').value);
  fd.append('synth_per_gap', document.getElementById('forge-synth').value);
  const r = await api('/api/forge',{method:'POST',body:fd});
  document.getElementById('forge-out').innerHTML = `
    <div class="kpi-grid">
      <div class="kpi"><div class="k">total</div><div class="v">${r.total}</div></div>
      <div class="kpi"><div class="k">real</div><div class="v" style="color:var(--good)">${r.real}</div></div>
      <div class="kpi"><div class="k">synthetic</div><div class="v" style="color:var(--accent)">${r.synthetic}</div></div>
      <div class="kpi"><div class="k">PII masked</div><div class="v">${r.pii_masked}</div></div>
    </div>
    <p>缺口: ${(r.gaps||[]).map(g=>escapeHtml(g.category)+'('+g.current_count+')').join(', ')||'无'}</p>
    <a class="btn" href="${r.html_url}" target="_blank">📄 查看完整 HTML 报告</a>`;
}

async function runKpi() {
  const fd = new FormData();
  fd.append('file', document.getElementById('kpi-file').files[0]);
  fd.append('profile', document.getElementById('kpi-profile').value);
  const r = await api('/api/kpi',{method:'POST',body:fd});
  document.getElementById('kpi-out').innerHTML = `
    <div class="kpi-grid">${Object.entries(r.kpis).map(([k,v])=>
      `<div class="kpi"><div class="k">${k}</div><div class="v">${(+v).toFixed(4)}</div></div>`
    ).join('')}</div>
    <p class="meta">samples: ${r.sample_count} · profile: ${r.profile}</p>`;
}

async function loadProfiles() {
  const p = await api('/api/profiles');
  alert('Profiles:\\n' + Object.entries(p).map(([k,v])=>`\\n${escapeHtml(k)}: ${escapeHtml(v.name)} (${v.industrial?'工业':'SaaS'})`).join(''));
}

refreshList();
if (location.hash === '#skills') go('skills'); else loadWorkbench();
window.addEventListener('hashchange', () => {
  if (location.hash === '#skills') go('skills');
  else if (location.hash) go('workbench');
});
</script>
__GLOSSARY__
</body>
</html>
"""

_OVERVIEW_HTML = _OVERVIEW_HTML.replace("__GLOSSARY__", _glossary_snippet())
_DASHBOARD_HTML = _DASHBOARD_HTML.replace("__GLOSSARY__", _glossary_snippet())
