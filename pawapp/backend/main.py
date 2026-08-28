"""FDE Scope — PawApp backend.

Bridges the fde_scope engagement/corpus/eval/skills engine into QwenPaw as a
PawApp. All heavy lifting stays in the ``fde_scope`` package; this module only
exposes it over the PawApp HTTP router (mounted by the host at
``/api/fde-scope/*``) and wires agent tools so the host agent can drive the SOP.

Storage layout resolves through ``fde_scope.paths`` (remediation-plan B1):
``FDE_SCOPE_HOME`` > ``~/Documents/FDE Scope`` (when present) > the host
process CWD — the same root the standalone web console and CLI use:
    .fde_scope/engagements/*.json   — engagement state
    .fde_scope/skills/              — skill library
    reports/                        — generated runbooks / corpus reports
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from qwenpaw.pawapp import PawApp, get_ctx

try:
    import fde_scope  # noqa: F401
    from fde_scope import paths
except ModuleNotFoundError as exc:  # pragma: no cover — env guard
    raise ModuleNotFoundError(
        "fde_scope is not importable from the QwenPaw host process. "
        "Install it into QwenPaw's Python environment: "
        "'pip install /path/to/fde-scope' (or 'pip install -e .'). "
        "macOS note: if an editable install silently stops working, the "
        ".venv's .pth files may carry a hidden flag — run "
        "'chflags -R nohidden .venv' and retry."
    ) from exc

logger = logging.getLogger("qwenpaw.fde_scope")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB, same as the standalone console

router = APIRouter()


# ---------------------------------------------------------------------------
# engagement helpers (mirror fde_scope.web.app, kept dependency-light)
# ---------------------------------------------------------------------------
def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", value.lower().replace(" ", "-"))


def _eng_path(eid: str) -> Path:
    eng_dir = paths.engagements_dir()
    path = (eng_dir / f"{eid}.json").resolve()
    base = eng_dir.resolve()
    if not path.is_relative_to(base):
        raise HTTPException(status_code=400, detail=f"invalid engagement id: {eid!r}")
    return path


def _load_engagement(eid: str):
    from fde_scope.engagement import Engagement, EngagementContext

    p = _eng_path(eid)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"engagement '{eid}' not found")
    return Engagement(EngagementContext.load(p))


def _save_engagement(eng) -> None:
    _eng_path(eng.ctx.id).parent.mkdir(parents=True, exist_ok=True)
    eng.ctx.save(_eng_path(eng.ctx.id))


def _all_engagements() -> list:
    from fde_scope.engagement import Engagement, EngagementContext

    eng_dir = paths.engagements_dir()
    if not eng_dir.exists():
        return []
    out = []
    for p in sorted(eng_dir.glob("*.json")):
        try:
            out.append(Engagement(EngagementContext.load(p)))
        except ValueError:
            continue
    return out


def _skill_service():
    from fde_scope.skills.service import SkillService
    from fde_scope.skills.store import SkillStore

    return SkillService(SkillStore(paths.skills_dir()))


async def _sync_storage_snapshot(ctx, engagements: list[dict]) -> None:
    """Mirror the engagement index into ctx.storage so QwenPaw's agent can
    query SOP state without touching the filesystem. Files stay the source
    of truth; this is a best-effort read cache."""
    try:
        await ctx.storage.set("engagements_index", engagements)
    except Exception:  # storage unavailable must never break the SOP flow
        logger.debug("ctx.storage snapshot failed", exc_info=True)


# ---------------------------------------------------------------------------
# SOP lifecycle routes
# ---------------------------------------------------------------------------
@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "fde-scope", "version": "0.1.0"}


@router.get("/profiles")
def profiles() -> dict:
    from fde_scope.profiles import all_profiles

    return {
        slug: {
            "name": p.name,
            "industrial": p.is_industrial,
            "connectors": p.primary_connectors,
            "kpis": p.kpi_catalogue,
        }
        for slug, p in all_profiles().items()
    }


@router.get("/phases")
def phases(profile: str = "ticket") -> dict:
    from fde_scope.engagement.phases import phases_for_profile
    from fde_scope.profiles import get_profile

    try:
        is_industrial = get_profile(profile).is_industrial
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown profile: {profile!r}") from None
    seq = phases_for_profile(is_industrial)
    return {"phases": [p.__dict__ for p in seq], "is_industrial": is_industrial}


@router.get("/engagements")
def list_engagements() -> list[dict]:
    return [eng.status() for eng in _all_engagements()]


@router.post("/engagements")
async def create_engagement(
    customer: str = Form(...), profile: str = Form("ticket"), ctx=Depends(get_ctx)
) -> dict:
    from fde_scope.engagement import Engagement, EngagementContext

    eid = f"eng-{_slugify(customer)}-{_slugify(profile)}-{uuid.uuid4().hex[:6]}"
    eng = Engagement(EngagementContext(id=eid, customer=customer, profile=profile))
    _save_engagement(eng)
    await _sync_storage_snapshot(ctx, [e.status() for e in _all_engagements()])
    return eng.status()


@router.get("/engagements/{eid}")
def get_engagement(eid: str) -> dict:
    eng = _load_engagement(eid)
    return {**eng.status(), "context": eng.ctx.model_dump()}


@router.get("/engagements/{eid}/gates")
def engagement_gates(eid: str) -> dict:
    from fde_scope.engagement.engagement import _default_gate_registry

    eng = _load_engagement(eid)
    out = {}
    for slug, gate in _default_gate_registry().items():
        if gate.applies(eng.ctx):
            r = gate.check(eng.ctx)
            out[slug] = {
                "name": gate.name,
                "passed": r.passed,
                "blockers": r.blockers,
                "warnings": r.warnings,
            }
    return out


@router.post("/engagements/{eid}/advance")
async def advance_engagement(eid: str, force: bool = False, ctx=Depends(get_ctx)) -> dict:
    from fde_scope.engagement import AdvanceBlocked

    eng = _load_engagement(eid)
    try:
        eng.advance(force=force)
    except AdvanceBlocked as exc:
        _save_engagement(eng)
        return {"advanced": False, "result": exc.result.__dict__}
    except StopIteration:
        return {"advanced": False, "reason": "complete"}
    _save_engagement(eng)
    await _sync_storage_snapshot(ctx, [e.status() for e in _all_engagements()])
    return {"advanced": True, "status": eng.status()}


@router.post("/engagements/{eid}/gate/{slug}")
def evaluate_gate(eid: str, slug: str) -> dict:
    eng = _load_engagement(eid)
    try:
        r = eng.evaluate_gate(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown gate: {slug!r}") from None
    _save_engagement(eng)
    return {"slug": slug, "passed": r.passed, "blockers": r.blockers, "warnings": r.warnings}


# ---------------------------------------------------------------------------
# corpus forge
# ---------------------------------------------------------------------------
@router.post("/forge")
async def forge_corpus(
    file: UploadFile,
    min_samples: int = Form(5),
    synth_per_gap: int = Form(3),
) -> dict:
    from fde_scope.config import CorpusConfig
    from fde_scope.connectors.csv_fallback import CSVConnector
    from fde_scope.corpus import CorpusForge, save_html
    from fde_scope.llm import MiMoClient

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 10 MiB)")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="file is not valid UTF-8") from None
    safe_name = Path(file.filename or "").name or f"{uuid.uuid4().hex}.csv"
    tmp = paths.uploads_dir(create=True) / safe_name
    tmp.write_text(text, encoding="utf-8")

    rows = CSVConnector(str(tmp)).extract_sample(100000)
    cfg = CorpusConfig(min_samples_per_category=min_samples, synth_per_gap=synth_per_gap)
    report = await run_in_threadpool(CorpusForge(cfg, llm=MiMoClient()).forge_rows, rows)
    report_id = uuid.uuid4().hex[:8]
    report_dir = paths.reports_dir(create=True)
    out_html = report_dir / f"corpus_report_{report_id}.html"
    save_html(report, out_html)
    (report_dir / f"corpus_report_{report_id}.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    return {
        "report_id": report_id,
        "total": report.total,
        "real": report.real,
        "synthetic": report.synthetic,
        "dropped": report.dropped,
        "pii_masked": report.pii_entities_masked,
        "gaps": [g.model_dump() for g in report.coverage.gaps],
    }


# ---------------------------------------------------------------------------
# KPI computation
# ---------------------------------------------------------------------------
@router.post("/kpi")
async def compute_kpis(
    file: UploadFile,
    profile: str = Form("manufacturing"),
) -> dict:
    import json as _json

    from fde_scope.profiles import get_profile

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 10 MiB)")
    try:
        text = content.decode("utf-8")
        samples = [_json.loads(line) for line in text.splitlines() if line.strip()]
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="file is not valid UTF-8") from None
    except _json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="file is not valid JSONL") from None
    try:
        prof = get_profile(profile)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown profile: {profile!r}") from None
    return {"profile": profile, "kpis": prof.compute_kpis(samples), "sample_count": len(samples)}


# ---------------------------------------------------------------------------
# skills library
# ---------------------------------------------------------------------------
@router.get("/skills")
def list_skills(q: str | None = None, status: str = "published") -> list[dict]:
    from fde_scope.skills.models import SkillStatus

    return [
        r.model_dump() for r in _skill_service().search(q, status=SkillStatus(status) if status else None)
    ]


@router.get("/skills/drafts")
def list_skill_drafts() -> list[dict]:
    return [r.model_dump() for r in _skill_service().list_drafts()]


@router.post("/skills/{sid}/publish")
def publish_skill(sid: str) -> dict:
    try:
        return _skill_service().publish(sid).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/skills/{sid}/export")
def export_skill(sid: str, fmt: str = Form("qwenpaw")) -> dict:
    """Export one skill as AgentScope / QwenPaw SKILL.md files.

    Files are returned inline AND written to ``.fde_scope/skills/export/``,
    the directory registered with QwenPaw via ``skill_provider()`` — so an
    exported skill becomes immediately discoverable by the host agent.
    """
    from fde_scope.skills.exporters import export_skill as do_export

    try:
        rec = _skill_service().get(sid)
        files = do_export(rec, fmt)
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    out = []
    for f in files:
        dest = paths.skills_export_dir() / f.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f.content, encoding="utf-8")
        out.append({"name": f.name, "content": f.content, "path": str(dest)})
    return {"skill_id": sid, "format": fmt, "files": out}


# ---------------------------------------------------------------------------
# handoff (Zone D): runbook drafting via the host LLM + package assembly
# ---------------------------------------------------------------------------
_RUNBOOK_PROMPT = (
    "请为以下客户现场生成一份 agent 运维 runbook（Markdown，中文），"
    "包含章节：1) 系统概述 2) 关键 SLO 与告警 3) 事件响应流程 "
    "4) 回滚与安全失败模式 5) 已知限制。\n\n{context}"
)


@router.post("/handoff/{eid}/runbook")
async def draft_runbook(eid: str, ctx=Depends(get_ctx)) -> dict:
    """Draft the runbook with the QwenPaw host agent (ctx.chat); fall back
    to the deterministic Jinja template on any failure."""
    from fde_scope.engagement.operationalization import render_runbook

    eng = _load_engagement(eid)
    c = eng.ctx
    slo_lines = "\n".join(f"- {s.name}: {s.target} (route: {s.alert_route or '—'})" for s in c.slos)
    context = (
        f"- 客户: {c.customer}\n- 场景 profile: {c.profile}\n"
        f"- 当前阶段: {c.current_phase}\n- SLO:\n{slo_lines or '- 未定义'}"
    )
    used_llm = False
    try:
        reply = await ctx.chat(_RUNBOOK_PROMPT.format(context=context))
        text = getattr(reply, "text", "") or ""
        if text.strip():
            runbook_md = text
            used_llm = True
        else:
            runbook_md = await run_in_threadpool(render_runbook, c)
    except Exception:  # no workspace / model error → honest fallback
        logger.debug("LLM runbook draft failed; using template", exc_info=True)
        runbook_md = await run_in_threadpool(render_runbook, c)
    runbook_dir = paths.reports_dir(create=True)
    path = runbook_dir / f"runbook_{eid}.md"
    path.write_text(runbook_md, encoding="utf-8")
    return {"engagement_id": eid, "used_llm": used_llm, "path": str(path)}


@router.post("/handoff/{eid}")
def handoff_package(eid: str, accept: bool = Form(False)) -> dict:
    """Assemble the knowledge-transfer package (picks up the drafted
    runbook when present)."""
    from fde_scope.engagement import build_handoff_package

    eng = _load_engagement(eid)
    runbook = paths.reports_dir() / f"runbook_{eid}.md"
    package = build_handoff_package(
        eng.ctx,
        runbook_path=str(runbook) if runbook.exists() else None,
        customer_accepted=accept,
    )
    _save_engagement(eng)
    return package


# ---------------------------------------------------------------------------
# deploy (Layer 3): role → connector → tool plan, dry-run only
# ---------------------------------------------------------------------------
@router.post("/deploy/plan")
def deploy_plan(body: dict | None = None) -> dict:
    """Plan a tenant deployment: which role agent gets which connector tool.

    Shares :func:`fde_scope.deploy.build_deploy_plan` with the standalone web
    console and ``fde-scope deploy``, so the desktop app can never show a plan
    the deployer would not produce. Pure data: nothing is assembled and no
    model is called.
    """
    from pydantic import ValidationError

    from fde_scope.deploy import build_deploy_plan

    try:
        return build_deploy_plan(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


# ---------------------------------------------------------------------------
# PawApp definition + agent tools
# ---------------------------------------------------------------------------
app = PawApp(name="FDE Scope", app_id="fde-scope")
app.include_router(router)

# Expose exported skills (SKILL.md, Anthropic Agent Skills format) to the
# QwenPaw agent — FDE field experience captured here becomes agent capability.
# skill_provider() landed on main after the 2.1.0 PyPI release: detect and
# degrade gracefully so the app still loads on older hosts.
_SKILLS_EXPORT_DIR = paths.skills_export_dir(create=True)  # QwenPaw skill_provider source
if hasattr(app, "skill_provider"):
    app.skill_provider(_SKILLS_EXPORT_DIR)
else:  # pragma: no cover — host-side discovery only
    logger.info(
        "PawApp host lacks skill_provider(); exported skills stay in %s for manual discovery",
        _SKILLS_EXPORT_DIR,
    )


@app.tool(
    "fde_sop_status",
    description="Get the current SOP phase / zone / gate state of an FDE engagement.",
    icon="🛠️",
)
async def fde_sop_status(engagement_id: str) -> dict:
    """Tool: report an engagement's SOP status to the host agent."""
    eng = await run_in_threadpool(_load_engagement, engagement_id)
    return eng.status()


@app.tool(
    "fde_sop_advance",
    description="Advance an FDE engagement to the next SOP phase (gates may block).",
    icon="⏭️",
)
async def fde_sop_advance(engagement_id: str, force: bool = False) -> dict:
    """Tool: advance the SOP state machine; returns blockers when a gate fails."""
    from fde_scope.engagement import AdvanceBlocked

    eng = await run_in_threadpool(_load_engagement, engagement_id)
    try:
        await run_in_threadpool(eng.advance, force=force)
    except AdvanceBlocked as exc:
        await run_in_threadpool(_save_engagement, eng)
        return {"advanced": False, "blockers": exc.result.blockers}
    except StopIteration:
        return {"advanced": False, "reason": "complete"}
    await run_in_threadpool(_save_engagement, eng)
    return {"advanced": True, "status": eng.status()}


@app.tool(
    "fde_deploy_plan",
    description="Plan an FDE tenant deployment: which role agent (data / log / file analyst) "
    "gets which connector tool, against which source, and which sources are still missing.",
    icon="🧭",
)
async def fde_deploy_plan(
    tenant: str,
    roles: str = "数据分析,日志分析,文件分析",
    sources_json: str = "{}",
) -> dict:
    """Tool: answer "will this tenant's agents actually reach their systems?".

    ``sources_json`` maps a connector slug to its physical source, e.g.
    ``{"csv": "data/tickets.csv", "documents": "docs/"}``.
    """
    import json

    from fde_scope.deploy import build_deploy_plan, summarize_deploy_plan

    try:
        sources = json.loads(sources_json or "{}")
    except json.JSONDecodeError as exc:
        return {"error": f"sources_json is not valid JSON: {exc}"}
    if not isinstance(sources, dict):
        return {"error": 'sources_json must be a {"slug": "source"} object'}
    agents = [
        {"name": f"{tenant}_{i}", "role": r.strip()} for i, r in enumerate(roles.split(","), 1) if r.strip()
    ]
    plan = await run_in_threadpool(
        build_deploy_plan,
        {"tenant": tenant, "sources": sources, "agents": agents},
    )
    return {
        "summary": plan["summary"],
        "plan": summarize_deploy_plan(plan),
    }


@app.on_launch
async def _on_launch() -> None:
    logger.info("FDE Scope PawApp launched (engagements dir: %s)", paths.engagements_dir().resolve())


# QwenPaw 2.1.0 contract: the runtime loader accepts a PawApp exported as
# ``app``, but ``qwenpaw plugin validate/install`` only recognises the name
# ``plugin`` — export both so the same file passes every pipeline.
plugin = app
