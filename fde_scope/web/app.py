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


# ---------------------------------------------------------------------------
# ontology（本体语义层：只读）
# ---------------------------------------------------------------------------
@app.get("/api/ontology/schemas")
def api_ontology_schemas() -> list[dict]:
    from ..ontology.store import OntologyStore

    return OntologyStore().list_schemas()


@app.get("/api/ontology/stores")
def api_ontology_stores() -> list[dict]:
    from ..ontology.store import OntologyStore

    return OntologyStore().list_stores()


@app.get("/api/ontology/schema/{schema_id}")
def api_ontology_schema(schema_id: str) -> dict:
    from ..ontology.store import OntologyStore

    schema = OntologyStore().load_schema(schema_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"unknown ontology schema: {schema_id}")
    return schema.model_dump()


@app.get("/api/ontology/store/{store_id}")
def api_ontology_store(store_id: str) -> dict:
    from ..ontology.store import OntologyStore

    store = OntologyStore().load_store(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail=f"unknown ontology store: {store_id}")
    return store.model_dump()


@app.get("/api/ontology/export/{target_id}")
def api_ontology_export(target_id: str) -> dict:
    """JSON-LD 导出：schema 直出；store 联同其 TBox 上下文（与 CLI ontology export 同语义）。"""
    from ..ontology.store import OntologyStore

    store = OntologyStore()
    schema = store.load_schema(target_id)
    if schema is not None:
        from ..ontology.jsonld import schema_to_jsonld

        return schema_to_jsonld(schema)
    inst = store.load_store(target_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"unknown ontology export target: {target_id}")
    ref_schema = store.load_schema(inst.ontology_ref.split("@", 1)[0])
    if ref_schema is None:
        raise HTTPException(status_code=404, detail=f"store references unknown schema: {inst.ontology_ref}")
    from ..ontology.jsonld import store_to_jsonld

    return store_to_jsonld(inst, ref_schema)


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
    ("overlay", "叠加层：仅工业 profile 才额外生效的 gate 集合（工厂小图标标记）。"),
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
.term{position:relative;cursor:help;border-bottom:1px dashed var(--border-strong);outline:none}
.term:hover,.term:focus{border-bottom-color:var(--accent)}
.term .q{display:inline-block;width:13px;height:13px;margin-left:3px;border:1px solid var(--muted);
border-radius:50%;color:var(--muted);font-size:9px;line-height:12px;text-align:center;font-weight:700;
vertical-align:1px;transition:color .12s,border-color .12s}
.term:hover .q,.term:focus .q{color:var(--accent);border-color:var(--accent)}
.term .tip{position:absolute;left:0;bottom:calc(100% + 9px);z-index:999;width:max-content;
max-width:min(300px,78vw);padding:9px 12px;border-radius:9px;background:var(--panel2);
border:1px solid var(--accent);box-shadow:0 10px 28px rgba(0,0,0,.3);color:var(--fg);
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
<script>(function(){var t=null;try{t=localStorage.getItem('fde-theme')}catch(e){}if(!t)t=(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';document.documentElement.dataset.theme=t})();</script>
<style>
/* Hallmark · genre: modern-minimal · macrostructure: long-document · design-system: design.md (Graphite) · designed-as-app */
:root{--bg:oklch(0.973 0.003 255);--bg2:oklch(1 0 0);--panel:oklch(1 0 0);--panel2:oklch(0.945 0.005 255);
--fg:oklch(0.225 0.014 255);--muted:oklch(0.47 0.016 255);--faint:oklch(0.52 0.014 255);
--border:oklch(0.9 0.006 255);--border-strong:oklch(0.8 0.01 255);
--accent:oklch(0.5 0.095 235);--accent-2:oklch(0.44 0.095 235);--accent-ink:oklch(0.99 0.002 255);--accent-dim:oklch(0.5 0.095 235/0.09);
--good:oklch(0.51 0.12 152);--warn:oklch(0.53 0.11 75);--bad:oklch(0.55 0.17 25);--code:oklch(0.955 0.004 255);
--font:-apple-system,"SF Pro Text","Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
--mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;color-scheme:light}
html[data-theme="dark"]{--bg:oklch(0.165 0.012 255);--bg2:oklch(0.2 0.013 255);--panel:oklch(0.2 0.013 255);--panel2:oklch(0.22 0.015 255);
--fg:oklch(0.93 0.006 255);--muted:oklch(0.68 0.014 255);--faint:oklch(0.61 0.013 255);
--border:oklch(0.3 0.014 255);--border-strong:oklch(0.4 0.016 255);
--accent:oklch(0.74 0.085 232);--accent-2:oklch(0.79 0.07 232);--accent-ink:oklch(0.2 0.04 232);--accent-dim:oklch(0.74 0.085 232/0.13);
--good:oklch(0.76 0.13 152);--warn:oklch(0.8 0.13 85);--bad:oklch(0.7 0.16 25);--code:oklch(0.14 0.012 255);color-scheme:dark}
*{box-sizing:border-box}
html,body{overflow-x:clip}
body{margin:0;font:400 15px/1.65 var(--font);background:var(--bg);color:var(--fg)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition-duration:0.01ms!important;scroll-behavior:auto!important}}
a{color:var(--accent);text-decoration:none}
.ic,.ic-xs{fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;flex:none}
.ic{width:16px;height:16px}.ic-xs{width:13px;height:13px}
.mk-g{color:var(--accent)}.mk-w{color:var(--warn)}
.topbar{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:14px;flex-wrap:wrap;
padding:11px 24px;border-bottom:1px solid var(--border);background:var(--bg);
background:color-mix(in oklab,var(--bg) 88%,transparent);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
.logo{font-size:1.08rem;font-weight:700;letter-spacing:-.01em}
.logo span{color:var(--accent)}
.tag{font:600 11px/1 var(--mono);color:var(--accent);background:var(--accent-dim);padding:5px 10px;border-radius:999px;white-space:nowrap}
.nav{margin-left:auto;display:flex;gap:4px;align-items:center;flex-wrap:wrap}
.nav a{color:var(--muted);font-size:.85rem;padding:6px 10px;border-radius:7px;transition:color .15s,background-color .15s}
.nav a:hover{color:var(--fg);background:var(--panel2)}
.nav a.active{color:var(--accent);background:var(--accent-dim)}
.tbtn{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:7px;
border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:color .15s,border-color .15s}
.tbtn:hover{color:var(--fg);border-color:var(--border-strong)}
.when-dark{display:none}
html[data-theme="dark"] .when-light{display:none}
html[data-theme="dark"] .when-dark{display:inline}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px 44px}
.hero{padding:58px 0 38px;max-width:760px}
.hero .eyebrow{font:600 11px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin:0 0 16px}
.hero h2{font-size:clamp(30px,4.5vw,42px);font-weight:680;letter-spacing:-.022em;line-height:1.12;margin:0 0 14px;overflow-wrap:anywhere;min-width:0}
.hero p{color:var(--muted);font-size:1.02rem;margin:0;max-width:660px}
.hero .cta{margin-top:26px;display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:7px;background:var(--accent);color:var(--accent-ink);border:1px solid transparent;
padding:9px 16px;border-radius:7px;font-weight:600;font-size:.9rem;font-family:inherit;text-decoration:none;cursor:pointer;
transition:background-color .15s,border-color .15s,color .15s}
.btn:hover{background:var(--accent-2)}
.btn.ghost{background:transparent;border-color:var(--border);color:var(--fg)}
.btn.ghost:hover{border-color:var(--border-strong);background:var(--panel2)}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--border);
border:1px solid var(--border);border-radius:10px;overflow:hidden}
.stat{background:var(--bg2);padding:16px 18px}
.stat .num{font-size:1.9rem;font-weight:700;line-height:1.1;letter-spacing:-.02em;color:var(--accent)}
.stat .lab{font-size:.78rem;color:var(--muted);margin-top:3px}
section{padding-top:44px}
.sec-head{display:flex;align-items:center;gap:10px;padding-bottom:12px;border-bottom:1px solid var(--border);margin-bottom:14px}
.sec-head .ic{color:var(--accent)}
.sec-head h2{margin:0;font-size:19px;font-weight:650;letter-spacing:-.01em;min-width:0;overflow-wrap:anywhere}
.sec-head .n{font:600 11px/1 var(--mono);color:var(--faint);margin-left:auto;letter-spacing:.1em}
.sec-note{font-size:.8rem;color:var(--muted);margin:0 0 14px;line-height:1.7;max-width:780px}
.grid{display:grid;gap:10px}
.cols-4{grid-template-columns:repeat(4,minmax(0,1fr))}
.cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}
.cols-2{grid-template-columns:repeat(2,minmax(0,1fr))}
.tile{background:var(--panel);border:1px solid var(--border);border-radius:9px;padding:14px 16px;transition:border-color .15s;min-width:0}
.tile:hover{border-color:var(--border-strong)}
.tile>.ic{color:var(--muted);margin-bottom:9px}
.tile .name{font-weight:600;font-size:.95rem;margin-bottom:4px;overflow-wrap:anywhere;min-width:0}
.tile.mono .name{font:600 .82rem/1.55 var(--mono)}
.tile .name .ic-xs{vertical-align:-2px;margin-left:3px}
.tile .desc{color:var(--muted);font-size:.82rem;line-height:1.55}
.tile .desc a{white-space:nowrap}
.status{display:inline-flex;align-items:center;gap:6px;margin-top:10px;padding:2px 9px;border:1px solid var(--border);
border-radius:999px;font:500 11px/1.6 var(--mono);color:var(--muted)}
.status::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--faint);flex:none}
.s-ok::before{background:var(--good)}
.s-partial::before{background:var(--warn)}
.s-stub::before{background:var(--bad)}
.step-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.zone{background:var(--panel);border:1px solid var(--border);border-radius:9px;padding:14px 16px;min-width:0}
.zone .ztag{font:600 10.5px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.zone .zname{font-size:.95rem;font-weight:650;margin:6px 0 10px}
.zone ol{margin:0;padding:0;list-style:none;font-size:.82rem;color:var(--muted)}
.zone li{display:flex;align-items:center;gap:7px;padding:5px 0;border-top:1px solid var(--border)}
.zone li:first-child{border-top:0}
.zone li b{color:var(--fg);font:600 .76rem/1.5 var(--mono)}
.zone .marks{margin-left:auto;display:inline-flex;gap:4px}
.kpi-row{display:flex;justify-content:space-between;align-items:baseline;gap:8px;padding:5px 0;border-bottom:1px solid var(--border);font-size:.8rem;color:var(--muted)}
.kpi-row:last-child{border:0}
.kpi-row .v{font:700 .85rem var(--mono);color:var(--fg)}
.cli{background:var(--code);border:1px solid var(--border);border-radius:8px;padding:14px 16px;
font:400 .78rem/1.75 var(--mono);overflow-x:auto;margin:8px 0 0}
.cli .c{color:var(--faint)}
.cli .cmd{color:var(--accent)}
.inv-n{display:inline-flex;width:20px;height:20px;border:1px solid var(--border);border-radius:6px;
align-items:center;justify-content:center;font:600 11px/1 var(--mono);color:var(--accent);margin-right:8px;vertical-align:-4px}
footer{margin-top:56px;padding:22px 0 6px;border-top:1px solid var(--border);color:var(--faint);
font-size:.8rem;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
@media(max-width:960px){
.cols-4,.cols-3,.step-flow{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:640px){
.cols-4,.cols-3,.cols-2,.step-flow{grid-template-columns:1fr}
.stats{grid-template-columns:repeat(2,minmax(0,1fr))}
.topbar{gap:10px;padding:10px 16px}
.wrap{padding:0 16px 32px}
.hero{padding:38px 0 26px}
footer{flex-direction:column}
}
</style>
</head>
<body>
__ICON_SPRITE__
<header class="topbar">
  <div class="logo">FDE <span>Scope</span></div>
  <span class="tag">72h · raw data → deployed agent</span>
  <nav class="nav">
    <a href="/" class="active">功能总览</a>
    <a href="/console">Engagement 控制台 →</a>
    <a href="#arch">架构清单</a>
    <a href="#practices">最佳实践</a>
    <a href="/docs/fde_sop_full.md" target="_blank">SOP 文档</a>
  </nav>
  <button class="tbtn" onclick="toggleTheme()" title="切换深浅主题" aria-label="切换深浅主题">
    <svg class="ic when-dark"><use href="#i-sun"/></svg>
    <svg class="ic when-light"><use href="#i-moon"/></svg>
  </button>
</header>

<div class="wrap">

<div class="hero">
  <div class="eyebrow">FDE · Field Delivery Engine</div>
  <h2>FDE 的完整现场工作台</h2>
  <p>从第一次 Gemba walk 到签字移交——覆盖软件/SaaS 与具身机器人/制造业两类场景。
     18 阶段 SOP、10 个可执行合规 gate、10 个数据连接器、真实生产 KPI。</p>
  <div class="cta">
    <a class="btn" href="/console">进入 Engagement 控制台</a>
    <a class="btn ghost" href="/console#deploy"><svg class="ic"><use href="#i-bot"/></svg>Agent 部署预检</a>
    <a class="btn ghost" href="#quickstart">快速上手</a>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="num">18</div><div class="lab">SOP 阶段（4 zones）</div></div>
  <div class="stat"><div class="num">10</div><div class="lab">可执行 gate</div></div>
  <div class="stat"><div class="num">10</div><div class="lab">数据连接器</div></div>
  <div class="stat"><div class="num">CI</div><div class="lab">测试全绿</div></div>
</div>

<section>
<div class="sec-head"><svg class="ic"><use href="#i-map"/></svg><h2>完整 SOP · 18 阶段 · 4 Zones</h2><span class="n">01</span></div>
<div class="step-flow">
  <div class="zone">
    <div class="ztag">Zone A</div><div class="zname">立项勘察</div>
    <ol>
      <li><b>qualification</b> 问题框定</li>
      <li><b>site_survey</b> Gemba<span class="marks"><svg class="ic-xs mk-g"><use href="#i-shield"/></svg><svg class="ic-xs mk-w"><use href="#i-factory"/></svg></span></li>
      <li><b>stakeholder_map</b> 双 sponsor</li>
      <li><b>success_criteria</b> 契约化<span class="marks"><svg class="ic-xs mk-g"><use href="#i-shield"/></svg></span></li>
    </ol>
  </div>
  <div class="zone">
    <div class="ztag">Zone B</div><div class="zname">构建</div>
    <ol>
      <li><b>connect</b> 数据接入</li>
      <li><b>corpus</b> 语料锻造</li>
      <li><b>prototype</b> 真实数据原型</li>
      <li><b>validate</b> 验证</li>
      <li><b>deploy</b> FAT/SAT<span class="marks"><svg class="ic-xs mk-g"><use href="#i-shield"/></svg><svg class="ic-xs mk-w"><use href="#i-factory"/></svg></span></li>
      <li><b>eval</b> 评估</li>
    </ol>
  </div>
  <div class="zone">
    <div class="ztag">Zone C</div><div class="zname">运营化</div>
    <ol>
      <li><b>slo_sla</b> SLO+on-call<span class="marks"><svg class="ic-xs mk-g"><use href="#i-shield"/></svg></span></li>
      <li><b>runbook</b> 应急手册</li>
      <li><b>monitoring</b> 漂移检测</li>
      <li><b>change_mgmt</b> 工会<span class="marks"><svg class="ic-xs mk-g"><use href="#i-shield"/></svg><svg class="ic-xs mk-w"><use href="#i-factory"/></svg></span></li>
      <li><b>flywheel</b> 飞轮产品化</li>
    </ol>
  </div>
  <div class="zone">
    <div class="ztag">Zone D</div><div class="zname">交接退场</div>
    <ol>
      <li><b>ops_handoff</b> 运维移交</li>
      <li><b>knowledge_transfer</b> 知识转移</li>
      <li><b>disengage</b> 签字退场<span class="marks"><svg class="ic-xs mk-g"><use href="#i-shield"/></svg></span></li>
    </ol>
  </div>
</div>
</section>

<section>
<div class="sec-head"><svg class="ic"><use href="#i-shield"/></svg><h2>10 个可执行合规 Gate（工业 overlay）</h2><span class="n">02</span></div>
<p class="sec-note">Gate 是谓词，不是清单：清单记录"曾经查过"，随现实漂移单向腐化；gate 在每次推进时重新评估，过期 passed 不作数。--force 只豁免拦截、照常评估留痕，例外进入审计日志。</p>
<div class="grid cols-4">
  <div class="tile mono"><div class="name">site_survey<svg class="ic-xs mk-w"><use href="#i-factory"/></svg></div><div class="desc">现场勘察记录校验</div></div>
  <div class="tile mono"><div class="name">success_criteria</div><div class="desc">双 sponsor + 可度量 done</div></div>
  <div class="tile mono"><div class="name">fat_sat<svg class="ic-xs mk-w"><use href="#i-factory"/></svg></div><div class="desc">FAT/SAT 验收签字</div></div>
  <div class="tile mono"><div class="name">functional_safety<svg class="ic-xs mk-w"><use href="#i-factory"/></svg></div><div class="desc">ISO 13849 / IEC 61508 / ISO 10218</div></div>
  <div class="tile mono"><div class="name">conformity<svg class="ic-xs mk-w"><use href="#i-factory"/></svg></div><div class="desc">CE / EU AI Act conformity</div></div>
  <div class="tile mono"><div class="name">works_council<svg class="ic-xs mk-w"><use href="#i-factory"/></svg></div><div class="desc">德国 BetrVG §87 工会共决</div></div>
  <div class="tile mono"><div class="name">air_gap<svg class="ic-xs mk-w"><use href="#i-factory"/></svg></div><div class="desc">air-gapped 部署清单</div></div>
  <div class="tile mono"><div class="name">shift_handover<svg class="ic-xs mk-w"><use href="#i-factory"/></svg></div><div class="desc">24/7 班次交接集成</div></div>
  <div class="tile mono"><div class="name">slo</div><div class="desc">SLO + on-call 定义</div></div>
  <div class="tile mono"><div class="name">handoff_signoff</div><div class="desc">移交包签字确认</div></div>
</div>
</section>

<section>
<div class="sec-head"><svg class="ic"><use href="#i-plug"/></svg><h2>10 个数据连接器</h2><span class="n">03</span></div>
<div class="grid cols-4">
  <div class="tile"><svg class="ic"><use href="#i-doc"/></svg><div class="name">CSV</div><div class="desc">通用兜底，冷启动</div><span class="status s-ok">真实可用</span></div>
  <div class="tile"><svg class="ic"><use href="#i-db"/></svg><div class="name">MySQL</div><div class="desc">关系库直连</div><span class="status s-ok">真实可用</span></div>
  <div class="tile"><svg class="ic"><use href="#i-broadcast"/></svg><div class="name">MQTT-Sparkplug</div><div class="desc">工厂设备遥测</div><span class="status s-ok">JSONL 可用</span></div>
  <div class="tile"><svg class="ic"><use href="#i-factory"/></svg><div class="name">MES (ISA-95)</div><div class="desc">工单/质量/停机</div><span class="status s-ok">JSONL 可用</span></div>
  <div class="tile"><svg class="ic"><use href="#i-cpu"/></svg><div class="name">OPC UA</div><div class="desc">PLC tag 读取（asyncua 驱动）</div><span class="status s-ok">真实可用</span></div>
  <div class="tile"><svg class="ic"><use href="#i-bot"/></svg><div class="name">ROS2 Bag</div><div class="desc">机器人轨迹回放</div><span class="status s-stub">stub</span></div>
  <div class="tile"><svg class="ic"><use href="#i-trend"/></svg><div class="name">Historian</div><div class="desc">时序历史库</div><span class="status s-stub">stub</span></div>
  <div class="tile"><svg class="ic"><use href="#i-ticket"/></svg><div class="name">Zammad</div><div class="desc">工单系统</div><span class="status s-stub">stub</span></div>
  <div class="tile"><svg class="ic"><use href="#i-cloud"/></svg><div class="name">Salesforce</div><div class="desc">CRM</div><span class="status s-stub">stub</span></div>
  <div class="tile"><svg class="ic"><use href="#i-docs"/></svg><div class="name">Documents</div><div class="desc">PDF/Word/Excel/PPT 解析（agentscope.rag，延迟导入）</div><span class="status s-partial">需 [agentscope]</span></div>
</div>
</section>

<section>
<div class="sec-head"><svg class="ic"><use href="#i-globe"/></svg><h2>Ontology 语义层 · TBox + ABox</h2><span class="n">04</span></div>
<div class="grid cols-4">
  <div class="tile"><svg class="ic"><use href="#i-layers"/></svg><div class="name">TBox 双 Schema</div><div class="desc">fde-core（Skill/Connector/Engagement 等核心概念）+ mfg-overlay（ISA-95 制造业 overlay，imports 复用）</div><span class="status s-ok">内置</span></div>
  <div class="tile"><svg class="ic"><use href="#i-map"/></svg><div class="name">SKOS 概念体系</div><div class="desc">fde-corpus-taxonomy 双向集成：corpus 引擎按概念覆盖度选样本，skill 搜索概念扩展召回</div><span class="status s-ok">内置</span></div>
  <div class="tile"><svg class="ic"><use href="#i-shield"/></svg><div class="name">SHACL-lite 校验</div><div class="desc">ONTO-* 错误码契约（domain/range、环引用、未声明前缀），校验失败即拦截</div><span class="status s-ok">10 个错误码</span></div>
  <div class="tile"><svg class="ic"><use href="#i-doc"/></svg><div class="name">JSON-LD 1.1 导出</div><div class="desc">schema 直出；store 导出自动并入其 TBox 上下文，CLI 与 Web API 同一实现。<a href="/console#ontology">→ 本体库</a></div><span class="status s-ok">零新依赖</span></div>
</div>
</section>

<section>
<div class="sec-head"><svg class="ic"><use href="#i-gears"/></svg><h2>6 大功能模块</h2><span class="n">05</span></div>
<div class="grid cols-3">
  <div class="tile"><svg class="ic"><use href="#i-flask"/></svg><div class="name">Corpus Engine</div><div class="desc">脱敏→去重→质量门→覆盖度分析→缺口检测→针对性合成→报告。<b>核心差异化</b>：合成是补盲区不是凑数量。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-trend"/></svg><div class="name">Eval 评估</div><div class="desc">ticket 指标 + 制造业 KPI（OEE/MTBF/抓取率/碰撞率）+ bad case 挖掘 + 自动建议。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-rocket"/></svg><div class="name">Deploy 部署</div><div class="desc">角色 Agent 真实装配：沙箱 workspace + 权限上下文（经 AgentState 注入）+ Toolkit 工具绑定 + SubAgentTemplate 蓝图，全部真实 AgentScope 2.0 API。<a href="/console#deploy">→ 部署预检台</a></div></div>
  <div class="tile"><svg class="ic"><use href="#i-refresh"/></svg><div class="name">Flywheel 飞轮</div><div class="desc">概念事件→真实事件映射 + 语料回流 + 周度增量重训。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-flow"/></svg><div class="name">SOP 状态机</div><div class="desc">18 阶段推进/回滚，gate 不通过即拦截。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-globe"/></svg><div class="name">Web 控制台</div><div class="desc">交互式 engagement 仪表盘 + gate + forge + KPI + Agent 部署预检（/console#deploy）+ 本体库（/console#ontology）。</div></div>
</div>
</section>

<section id="arch">
<div class="sec-head"><svg class="ic"><use href="#i-layers"/></svg><h2>架构清单 · 四层 + 横切</h2><span class="n">06</span></div>
<p class="sec-note">证据化建模见 docs/architecture-model/。</p>
<div class="grid cols-3">
  <div class="tile"><svg class="ic"><use href="#i-monitor"/></svg><div class="name">UI 层</div><div class="desc">CLI（Typer，全延迟导入）· Web 控制台（32 路由）· QwenPaw PawApp（18 路由 /api/fde-scope）· macOS App（DMG 双击即用，即本控制台）。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-compass"/></svg><div class="name">SOP 层</div><div class="desc">engagement/：18 阶段 · 4 zones · 10 个可执行 gate（advance 实时重评估）+ handoff；profiles/：ticket · manufacturing 场景选择器。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-gears"/></svg><div class="name">能力层</div><div class="desc">connectors · corpus · deploy · eval · flywheel · integrations · ontology · skills —— 核心数据管线，规则为底、LLM 可选增强。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-wrench"/></svg><div class="name">横切层</div><div class="desc">llm.py（唯一 LLM 出口，失败回退规则路径）· config.py · templates/（Jinja 报告与 runbook）· paths.py（data_root 唯一路径解析）。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-drive"/></svg><div class="name">文件事实源</div><div class="desc">零数据库：.fde_scope/（engagements · skills · uploads）+ reports/；一律经 fsutil.atomic_write_text 原子写。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-plug"/></svg><div class="name">外部依赖（全可选）</div><div class="desc">AgentScope 2.0.x（extra，实测窗口 >=2.0.4.post1,&lt;3；deploy 三支柱 + documents 延迟导入）· MiMo LLM（凭据仅环境变量）· QwenPaw 宿主。</div></div>
</div>
</section>

<section id="practices">
<div class="sec-head"><svg class="ic"><use href="#i-check-badge"/></svg><h2>工程最佳实践 · 六条不变式</h2><span class="n">07</span></div>
<p class="sec-note">AGENTS.md 契约，由架构守护测试钉住。</p>
<div class="grid cols-3">
  <div class="tile"><div class="name"><span class="inv-n">1</span>Gate 实时重评估</div><div class="desc">advance() 每次重评当前阶段全部 gate，过期通过不作数；强推也评估留痕。禁止缓存/短路。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">2</span>ID 服务端生成</div><div class="desc">SkillRecord.id / EngagementContext.id 由所属服务分配，外部输入永远不能指定。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">3</span>凭据只走环境变量</div><div class="desc">API key 不落 manifest / 报告 / engagement JSON / 日志。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">4</span>原子写盘</div><div class="desc">一切用户状态经 fsutil.atomic_write_text（临时文件 + os.replace），禁止裸 write_text。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">5</span>规则授权是唯一通道</div><div class="desc">build_toolkit 不打 is_read_only（上游 ≥2.0.5 read-only 先放行）；未匹配工具按模式回退 DEFAULT→ASK / DONT_ASK→DENY。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">6</span>实测版本窗口</div><div class="desc">pyproject 与 docs 逐字引用同一 agentscope specifier，放宽前逐版本真库跑测。</div></div>
</div>
<p class="sec-note">验证锚点：make test · pytest tests/test_architecture_guard.py（6 项契约）· pytest -m agentscope（真库运行时）· ruff check + format --check · 架构证据模型 docs/architecture-model/architecture-map.md</p>
</section>

<section>
<div class="sec-head"><svg class="ic"><use href="#i-trend"/></svg><h2>制造业 KPI（实测 BMW 数据）</h2><span class="n">08</span></div>
<div class="grid cols-4">
  <div class="tile"><div class="name">OEE</div><div class="kpi-row"><span>设备综合效率</span><span class="v">0.724</span></div><div class="desc">世界级 ≥0.85</div></div>
  <div class="tile"><div class="name">抓取成功率</div><div class="kpi-row"><span>pick success</span><span class="v">0.793</span></div><div class="desc">DexNet 基准 ~0.80</div></div>
  <div class="tile"><div class="name">MTBF</div><div class="kpi-row"><span>平均无故障(h)</span><span class="v">39.8</span></div><div class="desc">越高越好</div></div>
  <div class="tile"><div class="name">碰撞/干预率</div><div class="kpi-row"><span>per cycle</span><span class="v">1.08%</span></div><div class="desc">越低越好</div></div>
</div>
</section>

<section id="quickstart">
<div class="sec-head"><svg class="ic"><use href="#i-rocket"/></svg><h2>快速上手</h2><span class="n">09</span></div>
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
· 推进/回滚 SOP 状态机<br>
· Agent 部署预检（/console#deploy）
    </div>
  </div>
</div>
</section>

<section>
<div class="sec-head"><svg class="ic"><use href="#i-box"/></svg><h2>两种场景</h2><span class="n">10</span></div>
<div class="grid cols-2">
  <div class="tile">
    <svg class="ic"><use href="#i-ticket"/></svg>
    <div class="name">ticket · 客服工单</div>
    <div class="desc">CSV/Zammad/Salesforce/MySQL 接入。意图准确率、回复采纳率、升级率评估。无工业 gate。</div>
    <span class="status s-ok">完整可用</span>
  </div>
  <div class="tile">
    <svg class="ic"><use href="#i-factory"/></svg>
    <div class="name">manufacturing · 具身机器人</div>
    <div class="desc">OPC UA/MQTT/ROS2/MES/Historian 接入。OEE/MTBF/抓取率/碰撞率 + 6 个工业合规 gate。</div>
    <span class="status s-partial">核心可用 · 工业IO部分 stub</span>
  </div>
</div>
</section>

<footer>
  <span>FDE Scope · 基于真实 AgentScope 2.0 API · MIT License</span>
  <span>测试套件 CI 全绿（含架构守护测试 6 项契约）· 零配置可跑</span>
</footer>

</div>
<script>
function toggleTheme(){
  var h = document.documentElement;
  var n = h.dataset.theme === 'light' ? 'dark' : 'light';
  h.dataset.theme = n;
  try { localStorage.setItem('fde-theme', n); } catch(e) {}
}
</script>
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
<script>(function(){var t=null;try{t=localStorage.getItem('fde-theme')}catch(e){}if(!t)t=(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';document.documentElement.dataset.theme=t})();</script>
<style>
/* Hallmark · genre: modern-minimal · macrostructure: workbench · design-system: design.md (Graphite) · designed-as-app */
:root{
--bg:oklch(0.973 0.003 255);--bg2:oklch(1 0 0);--panel:oklch(1 0 0);
--panel2:oklch(0.945 0.005 255);--fg:oklch(0.225 0.014 255);--muted:oklch(0.47 0.016 255);
--faint:oklch(0.52 0.014 255);--border:oklch(0.9 0.006 255);--border-strong:oklch(0.8 0.01 255);
--accent:oklch(0.5 0.095 235);--accent-2:oklch(0.44 0.095 235);--accent-ink:oklch(0.99 0.002 255);
--accent-dim:oklch(0.5 0.095 235/0.09);--good:oklch(0.51 0.12 152);--warn:oklch(0.53 0.11 75);
--bad:oklch(0.55 0.17 25);--code:oklch(0.955 0.004 255);
--font:-apple-system,"SF Pro Text","Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
--mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;
color-scheme:light}
html[data-theme="dark"]{
--bg:oklch(0.165 0.012 255);--bg2:oklch(0.2 0.013 255);--panel:oklch(0.2 0.013 255);
--panel2:oklch(0.22 0.015 255);--fg:oklch(0.93 0.006 255);--muted:oklch(0.68 0.014 255);
--faint:oklch(0.61 0.013 255);--border:oklch(0.3 0.014 255);--border-strong:oklch(0.4 0.016 255);
--accent:oklch(0.74 0.085 232);--accent-2:oklch(0.79 0.07 232);--accent-ink:oklch(0.2 0.04 232);
--accent-dim:oklch(0.74 0.085 232/0.13);--good:oklch(0.76 0.13 152);--warn:oklch(0.8 0.13 85);
--bad:oklch(0.7 0.16 25);--code:oklch(0.14 0.012 255);
color-scheme:dark}
*{box-sizing:border-box}
html,body{overflow-x:clip}
body{margin:0;font-family:var(--font);background:var(--bg);color:var(--fg);font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
::selection{background:var(--accent);color:var(--accent-ink)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition-duration:0.01ms!important;scroll-behavior:auto!important}}
::-webkit-scrollbar{width:12px;height:12px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border-strong);border:3px solid var(--bg);border-radius:8px}
::-webkit-scrollbar-thumb:hover{background:var(--faint)}
.ic{width:14px;height:14px;flex:none;display:inline-block;vertical-align:-2px}
.when-dark{display:none}
html[data-theme="dark"] .when-light{display:none}
html[data-theme="dark"] .when-dark{display:inline-block}
header{position:sticky;top:0;z-index:60;display:flex;align-items:center;gap:10px;padding:12px 20px;border-bottom:1px solid var(--border);background:color-mix(in oklab,var(--bg) 88%,transparent);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
@supports not (backdrop-filter:blur(1px)){header{background:var(--bg)}}
.logo{font-weight:800;letter-spacing:-.01em;font-size:1.02rem}
.v{font-family:var(--mono);font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);background:var(--accent-dim);border:1px solid color-mix(in oklab,var(--accent) 28%,transparent);padding:3px 9px;border-radius:999px;white-space:nowrap}
.sub{color:var(--faint);font-size:.8rem;margin-left:6px}
.hdr-right{margin-left:auto;display:flex;align-items:center;gap:10px}
.back{color:var(--muted);font-size:.85rem;transition:color .13s}
.back:hover{color:var(--fg)}
.tbtn{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;padding:0;background:transparent;border:1px solid var(--border);border-radius:8px;color:var(--muted);cursor:pointer;transition:color .13s,border-color .13s}
.tbtn:hover{color:var(--fg);border-color:var(--border-strong)}
.layout{display:grid;grid-template-columns:300px minmax(0,1fr);min-height:calc(100vh - 57px)}
.sidebar{border-right:1px solid var(--border);padding:16px 14px;overflow-y:auto;background:var(--bg2)}
.main{padding:20px 22px;overflow-x:clip}
h2{font-size:.8rem;margin:0 0 10px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;font-weight:700}
.nav{display:flex;flex-direction:column;gap:4px;margin-bottom:18px}
.navbtn{display:flex;align-items:center;gap:9px;width:100%;background:transparent;border:1px solid transparent;color:var(--muted);padding:8px 11px;border-radius:8px;font-size:.9rem;font-weight:600;cursor:pointer;font-family:inherit;transition:background .13s,color .13s;text-align:left}
.navbtn:hover{background:var(--panel2);color:var(--fg)}
.navbtn.active{background:var(--accent-dim);color:var(--accent);border-color:color-mix(in oklab,var(--accent) 30%,transparent)}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:12px}
.eng{cursor:pointer;transition:border-color .13s}
.eng:hover{border-color:var(--accent)}
.eng .id{font-weight:600}
.meta{color:var(--muted);font-size:.78rem}
.eng .meta{margin-top:3px}
.pill{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:999px;font-size:.7rem;background:var(--panel2);border:1px solid var(--border);color:var(--muted);white-space:nowrap}
.pill .ic{width:11px;height:11px}
.pill.ind{color:var(--warn);background:color-mix(in oklab,var(--warn) 10%,transparent);border-color:color-mix(in oklab,var(--warn) 28%,transparent)}
.pill.tkt{color:var(--accent);background:var(--accent-dim);border-color:color-mix(in oklab,var(--accent) 26%,transparent)}
button,.btn{background:var(--accent);color:var(--accent-ink);border:1px solid transparent;padding:7px 13px;border-radius:7px;font-weight:600;cursor:pointer;font-size:.85rem;font-family:inherit;transition:background .13s,border-color .13s,color .13s;display:inline-flex;align-items:center;gap:6px;justify-content:center}
button:hover,.btn:hover{background:var(--accent-2)}
button.ghost,.btn.ghost{background:transparent;border-color:var(--border);color:var(--fg)}
button.ghost:hover,.btn.ghost:hover{border-color:var(--border-strong);background:var(--panel2)}
button:disabled{opacity:.4;cursor:not-allowed}
input,select,textarea{background:var(--code);border:1px solid var(--border);color:var(--fg);padding:7px 10px;border-radius:7px;font-size:.85rem;width:100%;font-family:inherit;transition:border-color .13s}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent)}
textarea{resize:vertical;line-height:1.5}
.row{display:flex;gap:8px;align-items:center;margin-bottom:8px}
.row label{min-width:90px;color:var(--muted);font-size:.8rem;flex:none}
.phases{display:flex;flex-direction:column;gap:6px}
.phase{display:flex;align-items:center;gap:8px;padding:7px 11px;border-radius:7px;background:var(--panel2);font-size:.85rem;border:1px solid transparent}
.phase.done{opacity:.55}
.phase.current{background:var(--accent-dim);border-color:color-mix(in oklab,var(--accent) 40%,transparent)}
.phase .idx{width:22px;height:22px;border-radius:50%;background:var(--border);display:flex;align-items:center;justify-content:center;font-size:.72rem;font-family:var(--mono);flex:none}
.phase.current .idx{background:var(--accent);color:var(--accent-ink)}
.zone-tag{font-size:.64rem;color:var(--faint);margin-left:auto;font-family:var(--mono);letter-spacing:.04em;flex:none}
.gate{padding:10px 13px;border-radius:8px;margin-bottom:8px;border:1px solid var(--border);border-left:3px solid var(--border-strong);background:var(--panel2)}
.gate.pass{border-left-color:var(--good)}
.gate.fail{border-left-color:var(--bad)}
.gate .h{display:flex;justify-content:space-between;gap:8px;margin-bottom:4px;font-size:.9rem}
.gate ul{margin:6px 0 0;padding-left:4px;font-size:.8rem;color:var(--muted);list-style:none;display:flex;flex-direction:column;gap:3px}
.gate li{display:flex;gap:6px;align-items:flex-start}
.gate li .ic{margin-top:2px;width:12px;height:12px;color:var(--faint)}
.gate li.bl .ic{color:var(--bad)}
.gate li.wn .ic{color:var(--warn)}
pre{background:var(--code);padding:10px;border-radius:7px;overflow:auto;font-size:.78rem;border:1px solid var(--border);font-family:var(--mono)}
code{font-family:var(--mono);font-size:.82em;background:var(--panel2);border:1px solid var(--border);border-radius:4px;padding:1px 5px}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px}
.kpi{background:var(--panel2);border:1px solid var(--border);border-radius:9px;padding:11px 12px}
.kpi .k{color:var(--faint);font-size:.66rem;text-transform:uppercase;letter-spacing:.07em;font-family:var(--mono)}
.kpi .v{font-size:1.35rem;font-weight:700;margin-top:3px;font-variant-numeric:tabular-nums}
.tabs{display:flex;gap:2px;margin-bottom:14px;border-bottom:1px solid var(--border);overflow-x:auto}
.tab{padding:8px 13px;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent;font-size:.88rem;white-space:nowrap;transition:color .13s}
.tab:hover{color:var(--fg)}
.tab.active{color:var(--accent);border-color:var(--accent)}
table{width:100%;border-collapse:collapse;font-size:.84rem}
th{font-family:var(--mono);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);text-align:left;padding:7px 9px;border-bottom:1px solid var(--border-strong);font-weight:600}
td{padding:8px 9px;border-bottom:1px solid var(--border);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
tbody tr{transition:background .13s}
tbody tr:hover{background:var(--panel2)}
.tablewrap{overflow-x:auto;margin:2px 0}
.hidden{display:none}
.empty{color:var(--faint);text-align:center;padding:28px 12px;font-size:.88rem;display:flex;flex-direction:column;align-items:center;gap:8px}
.empty .ic{width:18px;height:18px;opacity:.7}
details summary{cursor:pointer;color:var(--accent);font-size:.85rem;padding:6px 0}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--faint);vertical-align:1px}
.d-ok{background:var(--good)}
.d-bad{background:var(--bad)}
#toast-host{position:fixed;right:18px;bottom:18px;z-index:1000;display:flex;flex-direction:column;gap:8px;align-items:flex-end}
.toast{display:flex;align-items:center;gap:8px;background:var(--panel2);border:1px solid var(--border-strong);border-radius:9px;padding:9px 14px;font-size:.85rem;max-width:min(420px,86vw);box-shadow:0 12px 32px rgba(0,0,0,.35);opacity:0;transform:translateY(8px);transition:opacity .16s ease,transform .16s ease}
.toast.on{opacity:1;transform:none}
.toast .ic{color:var(--accent)}
.toast.ok .ic{color:var(--good)}
.toast.warn{border-color:color-mix(in oklab,var(--warn) 55%,var(--border))}
.toast.warn .ic{color:var(--warn)}
.toast.bad{border-color:color-mix(in oklab,var(--bad) 55%,var(--border))}
.toast.bad .ic{color:var(--bad)}
dialog{background:var(--panel);color:var(--fg);border:1px solid var(--border-strong);border-radius:12px;padding:0;width:min(560px,92vw);box-shadow:0 24px 64px rgba(0,0,0,.4)}
dialog::backdrop{background:color-mix(in oklab,var(--bg) 60%,transparent);backdrop-filter:blur(2px)}
.dlg-h{display:flex;align-items:center;gap:8px;padding:13px 16px;border-bottom:1px solid var(--border);font-size:.95rem}
.dlg-b{padding:16px}
@media(max-width:960px){.layout{grid-template-columns:1fr}.sidebar{border-right:0;border-bottom:1px solid var(--border)}}
@media(max-width:640px){.sub{display:none}.main{padding:14px}.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hdr-right .back{display:none}}
</style>
</head>
<body>
__ICON_SPRITE__
<header>
  <span class="logo">FDE Scope</span>
  <span class="v">Engagement Console</span>
  <span class="sub">72h from raw data to a deployed agent · 全 SOP 工作台</span>
  <div class="hdr-right">
    <a class="back" href="/">&#8592; 功能总览</a>
    <button class="tbtn" onclick="toggleTheme()" aria-label="切换深浅主题" title="切换深浅主题">
      <svg class="ic when-dark"><use href="#i-sun"/></svg>
      <svg class="ic when-light"><use href="#i-moon"/></svg>
    </button>
  </div>
</header>
<div class="layout">
  <aside class="sidebar">
    <nav class="nav">
      <button class="navbtn active" data-view="workbench" onclick="go('workbench')"><svg class="ic"><use href="#i-gauge"/></svg>工作台</button>
      <button class="navbtn" data-view="skills" onclick="go('skills')"><svg class="ic"><use href="#i-library"/></svg>技能库</button>
      <button class="navbtn" data-view="deploy" onclick="go('deploy')"><svg class="ic"><use href="#i-bot"/></svg>Agent 部署</button>
      <button class="navbtn" data-view="ontology" onclick="go('ontology')"><svg class="ic"><use href="#i-globe"/></svg>本体库</button>
    </nav>
    <h2>Engagements</h2>
    <div id="eng-list"></div>
    <div class="card" style="margin-top:16px">
      <h2>新建 Engagement</h2>
      <div class="row"><label>客户</label><input id="new-customer" placeholder="BMW Spartanburg"></div>
      <div class="row"><label>Profile</label>
        <select id="new-profile"><option value="ticket">ticket / 客服</option><option value="manufacturing">manufacturing / 制造业</option></select>
      </div>
      <button onclick="createEng()" style="width:100%">+ 创建</button>
    </div>
    <div class="card">
      <h2>工具</h2>
      <a class="btn ghost" style="display:flex;width:100%;margin-bottom:6px" href="/reports/" target="_blank"><svg class="ic"><use href="#i-folder"/></svg>报告归档</a>
      <button class="ghost" style="width:100%" onclick="loadProfiles()"><svg class="ic"><use href="#i-layers"/></svg>查看 Profiles &amp; Phases</button>
    </div>
  </aside>
  <main class="main" id="main">
    <div id="view-workbench"></div>
    <div id="view-skills" class="hidden"></div>
    <div id="view-deploy" class="hidden"></div>
    <div id="view-ontology" class="hidden"></div>
    <div id="view-detail" class="hidden"><div class="empty"><svg class="ic"><use href="#i-map"/></svg>选择或创建一个 engagement 开始</div></div>
  </main>
</div>

<script>
const API = '';
let current = null;

function icon(n){return '<svg class="ic" aria-hidden="true"><use href="#'+n+'"/></svg>'}
function dot(ok){return '<span class="dot '+(ok?'d-ok':'d-bad')+'"></span>'}
function yn(ok){return dot(ok)+(ok?'是':'否')}

function toast(msg, kind, ms) {
  const t = document.createElement('div');
  t.className = 'toast' + (kind ? ' ' + kind : '');
  t.innerHTML = '<svg class="ic" aria-hidden="true"><use href="' + (kind === 'ok' ? '#i-check' : '#i-alert') + '"/></svg>';
  const span = document.createElement('span');
  span.textContent = msg;
  t.appendChild(span);
  document.getElementById('toast-host').appendChild(t);
  requestAnimationFrame(() => t.classList.add('on'));
  setTimeout(() => { t.classList.remove('on'); setTimeout(() => t.remove(), 200); }, ms || 3800);
}

function toggleTheme(){
  const cur = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
  const next = cur === 'light' ? 'dark' : 'light';
  document.documentElement.dataset.theme = next;
  try{localStorage.setItem('fde-theme', next)}catch(e){}
}

function showView(name) {
  ['workbench','skills','deploy','ontology','detail'].forEach(v=>{
    const e=document.getElementById('view-'+v); if(e) e.classList.toggle('hidden', v!==name);
  });
  document.querySelectorAll('.navbtn').forEach(b=>b.classList.toggle('active', b.dataset.view===name));
}

function go(name) {
  showView(name);
  if (name==='skills') location.hash = 'skills';
  else if (name==='deploy') location.hash = 'deploy';
  else if (name==='ontology') location.hash = 'ontology';
  else if (location.hash) history.replaceState(null,'',location.pathname);
  if (name==='workbench') loadWorkbench();
  if (name==='skills') loadSkills();
  if (name==='deploy') renderDeploy();
  if (name==='ontology') loadOntology();
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
      <td>${s.gate?escapeHtml(s.gate)+' '+dot(s.gate_passed):'—'}</td>
      <td class="meta">${ts?escapeHtml(String(ts).slice(0,16).replace('T',' ')):'—'}</td>
      ${s.is_complete?'<td>'+dot(true)+' 完成</td>':''}
    </tr>`;
  }).join('');
  return `<div class="tablewrap"><table><thead><tr><th>客户</th><th>Profile</th><th>阶段</th><th>门禁</th><th>最近更新</th></tr></thead><tbody>${rows}</tbody></table></div>`;
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
  if (!title) return toast('请填写标题','warn');
  const tags = document.getElementById('sk-tags').value.split(',').map(s=>s.trim()).filter(Boolean);
  await api('/api/skills', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({title, category:document.getElementById('sk-new-cat').value,
      tags, body_md:document.getElementById('sk-body').value})});
  toast('技能已沉淀','ok');
  loadSkills();
}

async function publishSkill(sid) { await api(`/api/skills/${sid}/publish`, {method:'POST'}); toast('已发布','ok'); loadSkills(); }
async function archiveSkill(sid) { await api(`/api/skills/${sid}/archive`, {method:'POST'}); toast('已归档','ok'); loadSkills(); }

let editingId = null;
function editSkill(sid) {
  editingId = sid;
  document.getElementById('dlg-body').value = '';
  document.getElementById('dlg-edit').showModal();
}

async function dlgEditSave() {
  const body = document.getElementById('dlg-body').value;
  await api(`/api/skills/${editingId}`, {method:'PATCH', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({body_md: body})});
  document.getElementById('dlg-edit').close();
  toast('已保存','ok');
  loadSkills();
}

// -- 现场记录 -------------------------------------------------------------
function journalHtml(ctx) {
  const esc = escapeHtml;
  const entries = (ctx && ctx.journal) || [];
  const rows = entries.map(e => `<div class="card">
    <div class="row"><span class="pill">${esc(e.kind)}</span><span class="meta">${esc(e.ts)}</span>
      <span class="meta" style="margin-left:auto">${e.skill_id?icon('i-bulb')+' '+esc(e.skill_id):''}</span></div>
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
  if (!note) return toast('请填写记录内容','warn');
  await api(`/api/engagements/${current}/journal`, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({kind, note})});
  selectEng(current);
}

async function journalToSkill(jid) {
  const r = await api(`/api/engagements/${current}/journal/${jid}/skill`, {method:'POST'});
  toast(`已沉淀为技能草稿: ${r.id} (${r.category})`,'ok');
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
      : `<span class="pill" style="color:var(--bad)" title="${esc(t.note||'')}">${esc(t.tool)} ${icon('i-x')} unbound</span>`).join(' ');
    const un = (a.unbound||[]);
    return `<div class="card" style="margin-bottom:8px">
      <div class="row"><b>${esc(a.name)}</b><span class="pill ${esc(a.role_bucket)==='corpus'?'ind':'tkt'}">${esc(a.role)} · ${esc(a.role_bucket||'corpus-only')}</span>
        <span class="pill">${esc(a.model||'runtime 注入')}</span>
        <span class="meta" style="margin-left:auto">bound ${((a.bound||[]).length)} · unbound ${un.length}</span></div>
      <div class="meta" style="margin:4px 0">连接器集：${(a.connectors||[]).map(esc).join(' · ') || '—'} ｜ system_prompt: ${esc((a.system_prompt||'').slice(0,72))}…</div>
      <div style="margin:6px 0">${tools || '<span class="meta">仅语料工具</span>'}</div>
      ${un.length?`<div class="meta" style="color:var(--warn)">${icon('i-alert')} 未绑定 ${un.length} 个工具 — 在「数据源」里给对应连接器配 slug=源 即可绑定</div>`:''}
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
        ${s.is_complete?' '+dot(true):''}
      </div>
      <div class="meta">id: ${escapeHtml(s.engagement_id)}</div>
    </div>`).join('');
  if (window.glossify) glossify(el);
}

async function createEng() {
  const customer = document.getElementById('new-customer').value.trim();
  if (!customer) return toast('请填写客户名','warn');
  const profile = document.getElementById('new-profile').value;
  await api('/api/engagements', {method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({customer, profile})});
  document.getElementById('new-customer').value = '';
  toast('已创建 engagement','ok');
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
      ${p.industrial?`<span class="pill ind" title="工业阶段">${icon('i-factory')}</span>`:''}
      ${p.gates&&p.gates.length?`<span class="pill" title="gates: ${escapeHtml(p.gates.join(', '))}">${icon('i-shield')}</span>`:''}
      <span class="zone-tag">${escapeHtml(zoneLabel(p.zone))}</span></div>`;
  }).join('');

  const gateHtml = Object.entries(gates).map(([slug,g])=>{
    const cls = g.passed?'pass':'fail';
    const blocks = g.blockers.map(b=>`<li class="bl">${icon('i-ban')} ${escapeHtml(b)}</li>`).join('');
    const warns = g.warnings.map(w=>`<li class="wn">${icon('i-alert')} ${escapeHtml(w)}</li>`).join('');
    return `<div class="gate ${cls}"><div class="h"><b>${escapeHtml(g.name)}</b>
      <span>${g.passed?dot(true)+' PASS':dot(false)+' BLOCKED'}</span></div>
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
          <button onclick="advance(false)">${icon('i-next')} 推进到下一阶段</button>
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
      <div class="row"><label>班次</label>${esc(site.shift_count)} · OT/IT 隔离 ${yn(site.ot_it_separated)} · 气隙 ${yn(site.air_gapped)}</div>
      ${net?`<div class="row"><label>网络</label><ul style="margin:2px 0 0;padding-left:18px">${net}</ul></div>`:''}
      <div class="row"><label>资产</label>${(site.assets||[]).length} 项 · 工会代表 ${site.works_council_represented?yn(true):'—'}</div>
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
    <tr><td>ISO 10218 评估</td><td>${yn(safety.iso10218_assessed)}</td></tr>
    <tr><td>EU AI Act 高风险</td><td>${safety.eu_ai_act_high_risk?yn(true):'—'} · CE ${safety.ce_marking_done?yn(true):yn(false)}</td></tr>
    <tr><td>危险分析</td><td>${yn(safety.hazard_analysis_done)}</td></tr>
    ${safety.risk_assessment_notes?`<tr><td>评估备注</td><td>${esc(safety.risk_assessment_notes)}</td></tr>`:''}`
    : '<tr><td colspan="2" class="meta">非工业 profile，无功能安全数据</td></tr>';
  // 产物与交付
  const evRows = Object.entries(assets.eval_metrics||{}).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('');
  const links = [];
  if (assets.runbook) links.push(`<a class="btn" href="/${esc(assets.runbook)}" target="_blank">${icon('i-book')} Runbook</a>`);
  if (assets.corpus_report) links.push(`<a class="btn" href="/${esc(assets.corpus_report)}" target="_blank">${icon('i-doc')} 语料报告</a>`);
  const mon = assets.monitoring||{};
  const known = (assets.known_limitations||[]).map(k=>`<li>${esc(k)}</li>`).join('');
  return `<div class="card"><h2>现场 / Site</h2>${siteHtml}</div>
    <div class="card"><h2>干系人</h2><div class="tablewrap"><table><thead><tr><th>姓名</th><th>角色</th><th>Sponsor</th><th>成功指标</th></tr></thead><tbody>${stkRows||'<tr><td colspan="4" class="meta">未记录</td></tr>'}</tbody></table></div></div>
    <div class="card"><h2>成功标准</h2><ul style="padding-left:18px">${crit}</ul></div>
    <div class="card"><h2>SLO</h2><div class="tablewrap"><table><thead><tr><th>名称</th><th>目标</th><th>告警路由</th><th>窗口</th></tr></thead><tbody>${sloRows}</tbody></table></div></div>
    <div class="card"><h2>功能安全</h2><div class="tablewrap"><table><tbody>${safetyHtml}</tbody></table></div></div>
    <div class="card"><h2>产物与交付</h2>
      <div class="row"><label>语料</label>${esc(assets.corpus_summary||'—')}</div>
      <div class="row"><label>模型</label>${esc(assets.model_name||'—')}</div>
      ${evRows?`<div class="tablewrap" style="margin-top:8px"><table><thead><tr><th>评估指标</th><th>值</th></tr></thead><tbody>${evRows}</tbody></table></div>`:''}
      <div class="row" style="margin-top:10px">${links.join(' ')||'—'}</div>
      ${known?`<div class="row"><label>已知局限</label><ul style="padding-left:18px">${known}</ul></div>`:''}
      <div class="row"><label>监控</label>漂移 ${mon.data_drift&&mon.data_drift.enabled?dot(true)+' 每日':dot(false)+' 未启用'} · 质量 ${mon.quality_drift&&mon.quality_drift.enabled?dot(true)+' 每周':dot(false)+' 未启用'}</div>
    </div>`;
}

async function advance(force) {
  const r = await api(`/api/engagements/${current}/advance?force=${force}`,{method:'POST'});
  if (!r.advanced) {
    const res = r.result;
    toast('推进被拦截：' + (res.blockers||[]).join('；'), 'bad', 7000);
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
    <a class="btn" href="${r.html_url}" target="_blank">${icon('i-doc')} 查看完整 HTML 报告</a>`;
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
  document.getElementById('dlg-profiles-body').innerHTML = Object.entries(p).map(([k,v])=>
    `<div class="row"><span class="pill tkt">${escapeHtml(k)}</span><b>${escapeHtml(v.name)}</b>
     <span class="meta" style="margin-left:auto">${v.industrial?'工业':'SaaS'}</span></div>`).join('');
  document.getElementById('dlg-profiles').showModal();
}

// ---- Ontology 视图（只读：与 CLI `ontology` 子命令同源数据） ----
async function loadOntology() {
  const [schemas, stores] = await Promise.all([
    api('/api/ontology/schemas'), api('/api/ontology/stores')]);
  const esc = escapeHtml;
  const originPill = o => o === 'builtin'
    ? '<span class="pill ind">内置</span>'
    : '<span class="pill tkt">工作区</span>';
  const sCards = schemas.map(s => `
    <div class="card" style="margin-bottom:8px">
      <div class="row"><b>${esc(s.id)}</b> <span class="pill">${esc(s.version)}</span> ${originPill(s.origin)}
        ${s.imports && s.imports.length ? `<span class="meta">${icon('i-flow')} imports: ${s.imports.map(esc).join(', ')}</span>` : ''}</div>
      <div class="meta" style="margin:4px 0">类 ${s.classes} · 对象属性 ${s.object_properties} · 数据属性 ${s.data_properties} · 概念体系 ${s.concept_schemes}</div>
      <div class="row" style="margin-top:6px">
        <button class="btn" onclick="showSchema('${esc(s.id)}')">详情</button>
        <button class="btn ghost" onclick="showJsonld('${esc(s.id)}','')">${icon('i-doc')} JSON-LD</button>
      </div>
    </div>`).join('') || '<div class="empty">无 schema</div>';
  const stCards = stores.map(t => `
    <div class="card" style="margin-bottom:8px">
      <div class="row"><b>${esc(t.id)}</b> <span class="pill tkt">${esc(t.ontology_ref)}</span>
        <span class="meta" style="margin-left:auto">${t.individuals} individuals</span></div>
      <div class="row" style="margin-top:6px">
        <button class="btn ghost" onclick="showJsonld('${esc(t.id)}','')">${icon('i-doc')} JSON-LD（含 TBox）</button>
      </div>
    </div>`).join('') || '<div class="empty" style="padding:14px">工作区暂无实例库（ontology/stores/*.json）</div>';
  document.getElementById('view-ontology').innerHTML = `
    <div class="sec-head"><svg class="ic"><use href="#i-globe"/></svg><h2>本体库 · TBox + ABox</h2></div>
    <div class="card"><h2>Schema（TBox）</h2>${sCards}</div>
    <div class="card" style="margin-top:12px"><h2>实例库（ABox）</h2>
      <p class="meta">ontology_ref 指向 schema@version；导出时自动并入其 TBox 上下文（JSON-LD 1.1）。</p>${stCards}</div>`;
  if (window.glossify) glossify(document.getElementById('view-ontology'));
}

async function showSchema(sid) {
  const s = await api(`/api/ontology/schema/${encodeURIComponent(sid)}`);
  const esc = escapeHtml;
  const dep = d => d ? '<span class="pill" style="color:var(--warn)">deprecated</span>' : '';
  const classRows = (s.classes||[]).map(c => `
    <div class="row"><span class="pill tkt">${esc(c.curie)}</span><b>${esc(c.label)}</b>
      ${c.label_zh ? `<span class="meta">${esc(c.label_zh)}</span>` : ''}${dep(c.deprecated)}
      ${c.sub_class_of && c.sub_class_of.length ? `<span class="meta" style="margin-left:auto">⊆ ${c.sub_class_of.map(esc).join(', ')}</span>` : ''}</div>`).join('')
    || '<div class="empty">无</div>';
  const objRows = (s.object_properties||[]).map(p => `
    <div class="row"><span class="pill tkt">${esc(p.curie)}</span><b>${esc(p.label)}</b>
      <span class="meta" style="margin-left:auto">${esc(p.domain)} → ${esc(p.range)}</span></div>`).join('')
    || '<div class="empty">无</div>';
  const dataRows = (s.data_properties||[]).map(p => `
    <div class="row"><span class="pill tkt">${esc(p.curie)}</span><b>${esc(p.label)}</b>
      <span class="meta" style="margin-left:auto">${esc(p.domain)} : ${esc(p.range)}</span></div>`).join('')
    || '<div class="empty">无</div>';
  const schemeBlocks = (s.concept_schemes||[]).map(sc => `
    <div style="margin-top:10px">
      <div class="row"><b>${esc(sc.label)}</b>${sc.label_zh ? `<span class="meta">${esc(sc.label_zh)}</span>` : ''}
        <span class="pill">${(sc.concepts||[]).length} concepts</span></div>
      <div style="margin-top:4px">${conceptTree(sc)}</div>
    </div>`).join('') || '<div class="empty">无概念体系</div>';
  document.getElementById('view-ontology').innerHTML = `
    <div class="sec-head"><svg class="ic"><use href="#i-globe"/></svg><h2>${esc(s.id)}@${esc(s.version)}</h2>
      <button class="btn ghost" style="margin-left:auto" onclick="loadOntology()">← 返回</button></div>
    ${s.base_iri ? `<p class="meta">base IRI: ${esc(s.base_iri)}</p>` : ''}
    <div class="card" style="margin-top:8px"><h2>类（${(s.classes||[]).length}）</h2>${classRows}</div>
    <div class="card" style="margin-top:8px"><h2>对象属性（${(s.object_properties||[]).length}）</h2>${objRows}</div>
    <div class="card" style="margin-top:8px"><h2>数据属性（${(s.data_properties||[]).length}）</h2>${dataRows}</div>
    <div class="card" style="margin-top:8px"><h2>概念体系（SKOS）</h2>${schemeBlocks}</div>`;
  if (window.glossify) glossify(document.getElementById('view-ontology'));
}

function conceptTree(scheme) {
  const cs = scheme.concepts || [];
  const esc = escapeHtml;
  const byCurie = Object.fromEntries(cs.map(c => [c.curie, c]));
  const kidsOf = {}; const roots = [];
  const known = new Set(cs.map(c => c.curie));
  cs.forEach(c => {
    const parents = (c.broader||[]).filter(b => known.has(b));
    if (!parents.length) roots.push(c.curie);
    else parents.forEach(b => { (kidsOf[b] = kidsOf[b]||[]).push(c.curie); });
  });
  const visited = new Set();
  const node = (curie, depth) => {
    if (visited.has(curie))
      return `<div class="meta" style="padding-left:${depth*16}px">↺ ${esc(curie)}（环引用，仅渲染一次）</div>`;
    visited.add(curie);
    const c = byCurie[curie] || {};
    const label = `${esc(c.label || curie)}${c.label_zh ? ` <span class="meta">${esc(c.label_zh)}</span>` : ''}${c.deprecated ? ' <span class="pill" style="color:var(--warn)">deprecated</span>' : ''}`;
    const kw = (c.match_keywords||[]).length ? `<span class="meta"> · 关键词: ${c.match_keywords.map(esc).join(' / ')}</span>` : '';
    const kids = (kidsOf[curie]||[]).map(k => node(k, depth+1)).join('');
    return `<div style="padding-left:${depth*16}px">• ${label}${kw}</div>${kids}`;
  };
  const rendered = roots.map(r => node(r, 0)).join('');
  const orphans = cs.filter(c => !visited.has(c.curie))
    .map(c => `<div class="meta" style="padding-left:16px">↻ ${esc(c.curie)}（仅存在于环中）</div>`).join('');
  return rendered + orphans;
}

async function showJsonld(target, backSid) {
  const doc = await api(`/api/ontology/export/${encodeURIComponent(target)}`);
  const esc = escapeHtml;
  const back = backSid
    ? `<button class="btn ghost" onclick="showSchema('${esc(backSid)}')">← 返回详情</button>`
    : `<button class="btn ghost" onclick="loadOntology()">← 返回</button>`;
  document.getElementById('view-ontology').innerHTML = `
    <div class="sec-head"><svg class="ic"><use href="#i-doc"/></svg><h2>JSON-LD · ${esc(target)}</h2>${back}</div>
    <p class="meta">与 CLI <code>fde-scope ontology export ${esc(target)}</code> 同一实现；store 导出自动并入其 TBox。</p>
    <div class="card" style="margin-top:8px"><pre style="max-height:60vh;overflow:auto">${esc(JSON.stringify(doc, null, 2))}</pre></div>`;
  if (window.glossify) glossify(document.getElementById('view-ontology'));
}

refreshList();
if (location.hash === '#skills') go('skills');
else if (location.hash === '#deploy') go('deploy');
else if (location.hash === '#ontology') go('ontology');
else loadWorkbench();
window.addEventListener('hashchange', () => {
  if (location.hash === '#skills') go('skills');
  else if (location.hash === '#deploy') go('deploy');
  else if (location.hash === '#ontology') go('ontology');
  else if (location.hash) go('workbench');
});
</script>
<dialog id="dlg-edit" aria-labelledby="dlg-edit-title">
  <div class="dlg-h"><svg class="ic"><use href="#i-doc"/></svg><b id="dlg-edit-title">编辑技能正文（Markdown）</b></div>
  <div class="dlg-b">
    <textarea id="dlg-body" rows="10" placeholder="粘贴新的 Markdown 正文…"></textarea>
    <div class="row" style="margin:12px 0 0;justify-content:flex-end">
      <button class="ghost" onclick="document.getElementById('dlg-edit').close()">取消</button>
      <button onclick="dlgEditSave()">保存</button>
    </div>
  </div>
</dialog>
<dialog id="dlg-profiles" aria-label="Profiles &amp; Phases">
  <div class="dlg-h"><svg class="ic"><use href="#i-layers"/></svg><b>Profiles &amp; Phases</b></div>
  <div class="dlg-b" id="dlg-profiles-body"></div>
</dialog>
<div id="toast-host" aria-live="polite"></div>
__GLOSSARY__
</body>
</html>
"""


_ICON_SPRITE = """<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
<symbol id="i-gauge" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.7 12a5.3 5.3 0 1 1 10.6 0"/><path d="M8 12l2.4-3.4"/><circle cx="8" cy="12" r=".9" fill="currentColor" stroke="none"/></symbol>
<symbol id="i-library" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 13.5v-9M6.5 13.5v-9M9.6 4.8l2.7 8.4"/><path d="M2 13.5h12"/></symbol>
<symbol id="i-bot" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5.5" width="10" height="7.5" rx="1.8"/><path d="M8 5.5V3.4"/><circle cx="8" cy="2.4" r=".9"/><circle cx="6" cy="9" r=".9" fill="currentColor" stroke="none"/><circle cx="10" cy="9" r=".9" fill="currentColor" stroke="none"/><path d="M1.4 8.7v2.2M14.6 8.7v2.2"/></symbol>
<symbol id="i-folder" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12.5v-8a1 1 0 0 1 1-1h3l1.5 2h5.5a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1z"/></symbol>
<symbol id="i-map" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1.8 4.2 5.5 3l5 1.6 3.7-1.3v9.5l-3.7 1.3-5-1.6-3.7 1.3z"/><path d="M5.5 3v9.5"/><path d="M10.5 4.6v9.5"/></symbol>
<symbol id="i-shield" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.8 13.2 3.6v4.2c0 3.2-2.2 5.4-5.2 6.3-3-.9-5.2-3.1-5.2-6.3V3.6z"/><path d="M6 7.7l1.4 1.4 2.6-2.8"/></symbol>
<symbol id="i-plug" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5.5 2.3V6M10.5 2.3V6"/><path d="M4 6h8v2.3a4 4 0 0 1-8 0z"/><path d="M8 12.3v1.7"/></symbol>
<symbol id="i-gears" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="3"/><path d="M8 1.6v1.9M8 12.5v1.9M1.6 8h1.9M12.5 8h1.9M3.5 3.5l1.3 1.3M11.2 11.2l1.3 1.3M12.5 3.5l-1.3 1.3M4.8 11.2l-1.3 1.3"/></symbol>
<symbol id="i-layers" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.8 14.2 5 8 8.2 1.8 5z"/><path d="M2.5 8 8 10.8 13.5 8"/><path d="M2.5 11 8 13.8 13.5 11"/></symbol>
<symbol id="i-check-badge" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6.2"/><path d="M5.4 8.2l1.8 1.8 3.4-3.7"/></symbol>
<symbol id="i-trend" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1.8 11.6 6 7.6l2.5 2.5 5.2-5.2"/><path d="M10.4 4.9h3.3v3.3"/></symbol>
<symbol id="i-rocket" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.6c2.3 1.5 3.5 3.9 3.5 6.4L9.9 11H6.1L4.5 8c0-2.5 1.2-4.9 3.5-6.4z"/><circle cx="8" cy="6.3" r="1.2"/><path d="M6.1 11 4.5 14l2.4-1.2M9.9 11l1.6 3-2.4-1.2"/></symbol>
<symbol id="i-box" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.2 5 8 2.2 13.8 5v6L8 13.8 2.2 11z"/><path d="M2.2 5 8 7.8l5.8-2.8"/><path d="M8 7.8v6"/></symbol>
<symbol id="i-doc" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.8 1.8h5.4l3 3v9.4H3.8z"/><path d="M9.2 1.8v3h3"/><path d="M6 8.2h4M6 10.7h4"/></symbol>
<symbol id="i-docs" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11.5V2.5h5.2"/><path d="M5.8 4.2h4l2.7 2.7v7.1H5.8z"/><path d="M9.8 4.2v2.7h2.7"/></symbol>
<symbol id="i-db" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="8" cy="3.8" rx="5.2" ry="1.9"/><path d="M2.8 3.8v8.4c0 1.1 2.3 1.9 5.2 1.9s5.2-.8 5.2-1.9V3.8"/><path d="M2.8 8c0 1.1 2.3 1.9 5.2 1.9s5.2-.8 5.2-1.9"/></symbol>
<symbol id="i-broadcast" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="1.6"/><path d="M5.2 10.8a4 4 0 0 1 0-5.6M10.8 5.2a4 4 0 0 1 0 5.6"/><path d="M3.3 12.7a6.7 6.7 0 0 1 0-9.4M12.7 3.3a6.7 6.7 0 0 1 0 9.4"/></symbol>
<symbol id="i-cpu" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="8" height="8" rx="1.2"/><rect x="6.7" y="6.7" width="2.6" height="2.6"/><path d="M6 1.8V4M10 1.8V4M6 12v2.2M10 12v2.2M1.8 6H4M1.8 10H4M12 6h2.2M12 10h2.2"/></symbol>
<symbol id="i-ticket" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 5.6V4.3a.8.8 0 0 1 .8-.8h10.4a.8.8 0 0 1 .8.8v1.3a2.4 2.4 0 0 0 0 4.8v1.3a.8.8 0 0 1-.8.8H2.8a.8.8 0 0 1-.8-.8v-1.3a2.4 2.4 0 0 0 0-4.8z"/><path d="M10 3.7v8.6" stroke-dasharray="1.7 1.6"/></symbol>
<symbol id="i-cloud" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4.7 13h6.6a2.9 2.9 0 0 0 .5-5.8 4.3 4.3 0 0 0-8.3-.6A2.9 2.9 0 0 0 4.7 13z"/></symbol>
<symbol id="i-factory" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 13.5V6.8l3.4 2.2V6.8l3.4 2.2V4.4l5.2 2v7.1z"/><path d="M2 13.5h13"/></symbol>
<symbol id="i-flask" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5.8 1.8h4.4"/><path d="M6.6 1.8v4.1L3 12.3a1.6 1.6 0 0 0 1.4 2.4h7.2a1.6 1.6 0 0 0 1.4-2.4L9.4 5.9V1.8"/><path d="M4.8 9.8h6.4"/></symbol>
<symbol id="i-refresh" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13.2 8A5.2 5.2 0 1 1 11.6 4.3"/><path d="M13.6 1.9v3h-3"/></symbol>
<symbol id="i-flow" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="1.8" y="1.8" width="4.6" height="3.6" rx="1"/><rect x="9.6" y="1.8" width="4.6" height="3.6" rx="1"/><rect x="5.7" y="10.6" width="4.6" height="3.6" rx="1"/><path d="M6.4 3.6h3.2"/><path d="M4.1 5.4V8h7.8"/><path d="M11.9 5.4V8"/><path d="M8 8v2.6"/></symbol>
<symbol id="i-globe" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M2 8h12"/><ellipse cx="8" cy="8" rx="2.6" ry="6"/></symbol>
<symbol id="i-monitor" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2.8" width="12" height="8" rx="1.2"/><path d="M8 10.8v2.6M5.2 13.4h5.6"/></symbol>
<symbol id="i-compass" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M10.6 5.4 9.1 9.1 5.4 10.6 6.9 6.9z"/></symbol>
<symbol id="i-wrench" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9.8 4.2a.67.67 0 0 0 0 .94l1.06 1.06a.67.67 0 0 0 .94 0l2.52-2.51a4 4 0 0 1-5.3 5.29l-4.6 4.61a1.41 1.41 0 0 1-2-2l4.61-4.6a4 4 0 0 1 5.29-5.3L9.8 4.2z"/></symbol>
<symbol id="i-drive" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3.2" width="12" height="9.6" rx="1.4"/><path d="M2 8.4h12"/><circle cx="11.2" cy="10.4" r=".9" fill="currentColor" stroke="none"/></symbol>
<symbol id="i-ban" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M4 12 12 4"/></symbol>
<symbol id="i-alert" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2.2 14.4 13H1.6z"/><path d="M8 6.4v3"/><circle cx="8" cy="11.4" r=".8" fill="currentColor" stroke="none"/></symbol>
<symbol id="i-next" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 3.5 9.5 8l-6 4.5z"/><path d="M12.5 3.5v9"/></symbol>
<symbol id="i-bulb" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5.9 12.5a4.7 4.7 0 1 1 4.2 0"/><path d="M6.2 12.5h3.6"/><path d="M6.7 14.6h2.6"/><path d="M8 10.2V8"/></symbol>
<symbol id="i-book" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.67 13a1.67 1.67 0 0 1 1.66-1.67h9"/><path d="M4.33 1.33h9v13.34h-9A1.67 1.67 0 0 1 2.66 13V3a1.67 1.67 0 0 1 1.67-1.67z"/></symbol>
<symbol id="i-check" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.8 8.6l3.4 3.4 7-8"/></symbol>
<symbol id="i-sun" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="3.2"/><path d="M8 1.2v1.8M8 13v1.8M1.2 8H3M13 8h1.8M3.2 3.2l1.3 1.3M11.5 11.5l1.3 1.3M12.8 3.2l-1.3 1.3M4.5 11.5l-1.3 1.3"/></symbol>
<symbol id="i-moon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 8.53A6 6 0 1 1 7.47 2 4.67 4.67 0 0 0 14 8.53z"/></symbol>
<symbol id="i-x" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></symbol>
</defs></svg>"""

_OVERVIEW_HTML = _OVERVIEW_HTML.replace("__GLOSSARY__", _glossary_snippet()).replace(
    "__ICON_SPRITE__", _ICON_SPRITE
)
_DASHBOARD_HTML = _DASHBOARD_HTML.replace("__GLOSSARY__", _glossary_snippet()).replace(
    "__ICON_SPRITE__", _ICON_SPRITE
)
