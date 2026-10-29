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
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import TypeAdapter, ValidationError

from .. import audit, fsutil, paths
from ..course import LABS, doctor_report, lab_for, run_lab
from ..engagement import Engagement, EngagementContext
from ..engagement.engagement import AdvanceBlocked, _default_gate_registry
from ..engagement.retrospective import build_retrospective
from ..logutil import configure_logging, get_logger
from ..profiles import all_profiles, get_profile
from .i18n import to_en
from .layout import BASE_CSS, NAV_JS, NOTICE_CSS, SHELL_CSS, SHELL_JS, side_nav

configure_logging()
logger = get_logger("web.app")

# Import-time resolution is safe here: under the CWD fallback reports_dir()
# stays RELATIVE, so every use re-resolves against the current CWD (test
# isolation via chdir keeps working — see fde_scope.paths).
_REPORTS_DIR = paths.reports_dir(create=True)

#: Upload cap for /api/forge and /api/kpi (10 MiB). Read with a bounded
#: read so an oversized body is refused before it is fully buffered.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="FDE Scope", version="0.1.0")


@app.exception_handler(fsutil.UnsafeIdentifier)
async def _unsafe_identifier_handler(request: Request, exc: fsutil.UnsafeIdentifier) -> JSONResponse:
    """An id that cannot name a file is the client's fault, not a 500.

    ``skills`` and ``ontology`` resolve path parameters through
    :func:`fde_scope.fsutil.safe_child`; several of their read-only routes
    would otherwise surface that guard as an internal error.
    """
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def _read_limited(file: UploadFile, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read an upload, refusing anything beyond ``limit`` bytes with 413."""
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"file exceeds {limit} byte limit")
    return content


# ---------------------------------------------------------------------------
# persistence helpers (shared with guided_api via deps — extracted verbatim)
# ---------------------------------------------------------------------------
_STR_LIST = TypeAdapter(list[str])
_ASSET_MAP = TypeAdapter(dict[str, Any])

from .deps import (  # noqa: E402
    _all_engagements,
    _archive,
    _delete,
    _load,
    _save,
    _slugify,
    catalog_site_dir,
    engagement_lock,
    gtm_site_dir,
    resources_site_dir,
)
from .guided_api import router as _guided_router  # noqa: E402

app.include_router(_guided_router)

from .auth import ApiTokenAuthMiddleware  # noqa: E402
from .certification import render as _render_certification  # noqa: E402
from .course import render as _render_course  # noqa: E402
from .docs_reader import SLUGS as _DOC_SLUGS  # noqa: E402
from .docs_reader import image_path as _doc_image_path  # noqa: E402
from .docs_reader import render as _render_doc  # noqa: E402
from .glossary import render as _render_glossary  # noqa: E402
from .resources import render as _render_resources  # noqa: E402
from .share import (  # noqa: E402
    create_share,
    record_of,
    render_ack_page,
    render_share_page,
    revoke_share,
    verify_share_token,
)  # noqa: E402
from .showcase import render as _render_showcase  # noqa: E402
from .sop import render as _render_sop  # noqa: E402

app.add_middleware(ApiTokenAuthMiddleware)


# ---------------------------------------------------------------------------
# Static assets
# ---------------------------------------------------------------------------
#: Every HTML shell links ``/static/favicon.svg``; the glyph is inlined here so
#: the asset ships with the package and never 404s (a missing icon makes the
#: browser fall back to ``/favicon.ico``, which is also absent).
#: The fills are literals because a standalone SVG resolves outside the document's
#: cascade, where ``var(--accent)`` computes to nothing. ``#0a5efa`` is the sRGB of
#: the light ``--accent`` (``oklch(0.545 0.243 262)``) and ``rx="4"`` is ``--r2``:
#: move the accent in ``layout.py`` and move it here too.
_FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="4" fill="#0a5efa"/>'
    '<path d="M16 6l2.6 6.6L25 15l-6.4 2.4L16 24l-2.6-6.6L7 15l6.4-2.4z" fill="#fff"/>'
    "</svg>"
)


@app.get("/static/favicon.svg")
def favicon() -> Response:
    return Response(
        content=_FAVICON_SVG, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"}
    )


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    """Liveness + readiness probe: real subsystem state, HTTP 200 even when
    degraded (probe semantics — the process is up, subsystems may not be).
    Public route (auth.PUBLIC_PATHS); never exposes credentials."""
    checks: dict[str, dict] = {}

    root = paths.data_root()
    root_abs = root.resolve()
    checks["data_root"] = {"ok": root_abs.is_dir() and os.access(root_abs, os.W_OK), "path": str(root_abs)}

    reports = paths.reports_dir(create=True)
    checks["reports_dir"] = {"ok": reports.is_dir() and os.access(reports, os.W_OK)}

    from ..llm import get_llm_client

    # env-configured only — no request is ever sent from a health probe.
    checks["llm"] = {"ok": True, "configured": get_llm_client().available}

    eng_dir = paths.engagements_dir()
    checks["engagements_count"] = {
        "ok": True,
        "count": len(list(eng_dir.glob("*.json"))) if eng_dir.is_dir() else 0,
    }

    degraded = any(not c["ok"] for c in checks.values())
    return {
        "status": "degraded" if degraded else "ok",
        "version": "0.1.0",
        "checks": checks,
    }


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
    with engagement_lock(eid):
        _save(eng)
    audit.log_event(
        "engagement.create",
        detail={"engagement_id": eid, "customer": customer, "profile": profile},
    )
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
def advance_engagement(
    eid: str,
    force: bool = False,
    reason: str | None = Form(None),
    operator: str | None = Form(None),
) -> dict:
    # A forced advance overrides a blocking gate — it must always say why
    # (and ideally who); without a reason it is refused before touching state.
    if force and not (reason and reason.strip()):
        raise HTTPException(status_code=422, detail="force advance requires a non-empty 'reason'") from None
    with engagement_lock(eid):
        eng = _load(eid)
        try:
            eng.advance(force=force)
        except AdvanceBlocked as exc:
            _save(eng)
            logger.debug("advance blocked for %s: %s", eid, exc.result.blockers)
            result = {"advanced": False, "result": exc.result.__dict__}
        except StopIteration:
            result = {"advanced": False, "reason": "complete"}
        else:
            _save(eng)
            logger.debug("advanced %s → %s (force=%s)", eid, eng.ctx.current_phase, force)
            result = {"advanced": True, "status": eng.status()}
    detail: dict = {"engagement_id": eid, "force": force, "advanced": result["advanced"]}
    if reason and reason.strip():
        detail["reason"] = reason.strip()
    if operator and operator.strip():
        detail["operator"] = operator.strip()
    if result.get("reason") == "complete":
        # “已完结”不是一次被拦的推进——复盘重放据此区分（retrospective.py）。
        detail.setdefault("reason", "complete")
    audit.log_event("engagement.advance", detail=detail)
    return result


@app.post("/api/engagements/{eid}/rollback")
def rollback_engagement(
    eid: str,
    to_phase: str = Form(...),
    reason: str | None = Form(None),
    operator: str | None = Form(None),
) -> dict:
    """Roll an engagement back to an earlier phase.

    The transition belongs to ``Engagement.rollback`` (profile visibility +
    no-forward checks live there); this route only maps its domain errors onto
    HTTP codes and leaves a trace in the audit log.
    """
    with engagement_lock(eid):
        eng = _load(eid)
        from_phase = eng.ctx.current_phase
        try:
            target = eng.rollback(to_phase)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown phase: {to_phase!r}") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        _save(eng)
        status = eng.status()
    detail = {"engagement_id": eid, "from_phase": from_phase, "to_phase": target.slug}
    if reason and reason.strip():
        detail["reason"] = reason.strip()
    if operator and operator.strip():
        detail["operator"] = operator.strip()
    audit.log_event("engagement.rollback", detail=detail)
    return {
        "rolled_back": True,
        "from_phase": from_phase,
        "to_phase": target.slug,
        "status": status,
    }


@app.post("/api/engagements/{eid}/gate/{slug}")
def evaluate_gate(eid: str, slug: str, operator: str | None = Form(None)) -> dict:
    with engagement_lock(eid):
        eng = _load(eid)
        try:
            result = eng.evaluate_gate(slug)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown gate: {slug!r}") from None
        _save(eng)
    detail = {"engagement_id": eid, "gate": slug, "passed": result.passed}
    if operator and operator.strip():
        detail["operator"] = operator.strip()
    audit.log_event("engagement.gate_evaluate", detail=detail)
    return {"slug": slug, "passed": result.passed, "blockers": result.blockers, "warnings": result.warnings}


# ---------------------------------------------------------------------------
# license gating (pro+ features — see fde_scope/license.py; honesty, not DRM)
# ---------------------------------------------------------------------------
def _require_feature(feature: str) -> None:
    """402 when the effective license doesn't grant ``feature``.

    Without a key the install is community tier, so this is where the tier
    boundary becomes visible to the customer with an actionable message.
    """
    from .. import license as lic

    if not lic.has_feature(feature):
        tier = lic.current_tier()
        raise HTTPException(
            status_code=402,
            detail=(
                f"feature '{feature}' requires a pro or enterprise license "
                f"(current tier: {tier}). Set {lic.ENV_LICENSE_KEY} or place a key at "
                f".fde_scope/license.key — contact your vendor to upgrade."
            ),
        ) from None


# ---------------------------------------------------------------------------
# audit export（审计导出：按 engagement 过滤 + Markdown 报告）
# ---------------------------------------------------------------------------
def _export_audit_md(eid: str, events: list[dict]) -> Path:
    out = paths.reports_dir(create=True) / f"audit_{eid}.md"
    fsutil.atomic_write_text(out, audit.render_markdown(events, eid))
    return out


@app.get("/api/engagements/{eid}/audit/export")
def export_audit(eid: str) -> dict:
    """Write a Markdown audit report for *eid* into the reports dir."""
    _require_feature("audit_export")
    events = list(audit.read_events(eid))
    out = _export_audit_md(eid, events)
    return {"engagement_id": eid, "count": len(events), "path": str(out)}


@app.get("/api/engagements/{eid}/audit")
def engagement_audit(eid: str, format: str | None = None) -> dict:
    """Audit events for one engagement (JSON); ``?format=md`` also exports a file."""
    events = list(audit.read_events(eid))
    out = {"engagement_id": eid, "count": len(events), "events": events}
    if format == "md":
        # writes the same report as /audit/export, so it carries the same gate —
        # reading events is free, materialising a file is a paid feature
        _require_feature("audit_export")
        out["path"] = str(_export_audit_md(eid, events))
    return out


@app.get("/api/engagements/{eid}/retrospective")
def engagement_retrospective(eid: str) -> dict:
    """复盘报告：SLA 时钟 + 阶段时间线 + gate 统计（纯读 audit 流 + context）。"""
    eng = _load(eid)
    report = build_retrospective(eng.ctx, list(audit.read_events(eid)))
    return report.model_dump()


# ---------------------------------------------------------------------------
# course labs（实验判分：真实 CLI 在一次性工作区里跑 —— fde_scope.course.verifier；
# 与 CLI `fde-scope course check` 同一 run_lab，学习平台与执行引擎共用一个真相）
# ---------------------------------------------------------------------------
@app.get("/api/course/labs")
def course_labs_registry() -> list[dict]:
    """D1–D8 实验注册表：每天的门禁、产出与判分项数（只读元数据）。"""
    return [
        {
            "day": lab.day,
            "title": lab.title,
            "gate": lab.gate,
            "deliverable": lab.deliverable,
            "eid": lab.eid,
            "profile": lab.profile,
            "checks": len(lab.checks),
        }
        for lab in LABS
    ]


@app.get("/api/course/doctor")
def course_doctor_payload() -> dict:
    """G0 入学门自检（环境探测，只读）：解释器、包、教案目录、数据目录。"""
    exit_code, _items, payload = doctor_report()
    return {"exit_code": exit_code, **payload}


@app.post("/api/course/labs/{day}/grade")
async def grade_course_lab(day: str) -> dict:
    """机器判分一天：在一次性工作区里对真实 CLI 跑全部检查（多次子进程，秒级）。

    与 CLI ``fde-scope course check <day>`` 走同一 ``run_lab``；``manual`` 项
    报告但不进分母（诚实分母），学生自己的真实 engagement 永远不被触碰。
    """
    try:
        lab = lab_for(day)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown lab: {day!r}") from None
    from fastapi.concurrency import run_in_threadpool

    result = await run_in_threadpool(run_lab, lab)
    return result.as_dict()


# ---------------------------------------------------------------------------
# share（干系人只读分享：share token 是 env token 之外的第二种凭据；
# /share/{eid} 与 /ack 由 auth 中间件的 share 分支校验，这里防御性复检）
# ---------------------------------------------------------------------------
@app.post("/api/engagements/{eid}/share")
def create_engagement_share(eid: str) -> dict:
    """生成（或轮换）只读分享 token；明文只在本响应出现一次，落盘的是 sha256。"""
    with engagement_lock(eid):
        eng = _load(eid)
        token, record = create_share(eng.ctx)
        _save(eng)
    audit.log_event("share.create", detail={"engagement_id": eid, "token_prefix": record["token_prefix"]})
    return {
        "engagement_id": eid,
        "url_path": f"/share/{eid}",
        "token": token,
        "token_prefix": record["token_prefix"],
        "created_at": record["created_at"],
    }


@app.get("/api/engagements/{eid}/share")
def engagement_share_status(eid: str) -> dict:
    """分享状态（永不回传 token 本体）。"""
    eng = _load(eid)
    record = record_of(eng.ctx)
    if record is None:
        return {"engagement_id": eid, "active": False}
    return {
        "engagement_id": eid,
        "active": True,
        "token_prefix": record["token_prefix"],
        "created_at": record["created_at"],
    }


@app.delete("/api/engagements/{eid}/share")
def revoke_engagement_share(eid: str) -> dict:
    """吊销分享链接（幂等）。"""
    with engagement_lock(eid):
        eng = _load(eid)
        existed = revoke_share(eng.ctx)
        _save(eng)
    if existed:
        audit.log_event("share.revoke", detail={"engagement_id": eid})
    return {"engagement_id": eid, "revoked": existed}


@app.get("/share/{eid}")
def share_page(eid: str, t: str = "") -> HTMLResponse:
    """干系人只读页：进度 + SLA 时钟 + 门禁现况 + 签收表单。"""
    ctx = verify_share_token(eid, t)
    if ctx is None:
        raise HTTPException(status_code=404, detail="share link invalid or revoked") from None
    gates = []
    for slug, gate in _default_gate_registry().items():
        if not gate.applies(ctx):
            continue
        result = gate.check(ctx)
        gates.append(
            {
                "slug": slug,
                "name": gate.name,
                "passed": result.passed,
                "blockers": result.blockers,
                "warnings": result.warnings,
            }
        )
    return HTMLResponse(render_share_page(ctx, t, gates))


@app.post("/share/{eid}/ack")
def share_ack(eid: str, t: str = "", label: str = Form("")) -> HTMLResponse:
    """客户签收：只写 ``share.ack`` 审计事件（证据，不是授权、不推进状态机）。"""
    if verify_share_token(eid, t) is None:
        raise HTTPException(status_code=404, detail="share link invalid or revoked") from None
    clean = label.strip()[:80]
    audit.log_event(
        "share.ack",
        actor="stakeholder",
        detail={"engagement_id": eid, "label": clean or None, "via": "share-link"},
    )
    return HTMLResponse(render_ack_page(eid))


# ---------------------------------------------------------------------------
# handoff（移交包：runbook + package JSON，sha256 证据入审计）
# ---------------------------------------------------------------------------
def _file_evidence(path: Path) -> dict:
    digest, size = audit.sha256_file(path)
    return {"path": str(path), "sha256": digest, "bytes": size}


@app.post("/api/engagements/{eid}/handoff")
def handoff_package(
    eid: str,
    accept: bool = Form(False),
    boundary: str | None = Form(None),
    termination: str | None = Form(None),
    operator: str | None = Form(None),
) -> dict:
    """Render the runbook, assemble the handoff package, hash both into the audit trail."""
    from ..engagement import build_handoff_package, render_handoff_summary
    from ..engagement.operationalization import render_runbook

    with engagement_lock(eid):
        eng = _load(eid)
        runbook_path = paths.reports_dir(create=True) / f"runbook_{eid}.md"
        package = build_handoff_package(
            eng.ctx,
            runbook_path=str(runbook_path),
            boundary=boundary,
            termination=termination,
            customer_accepted=accept,
        )
        # Rendered after the package exists: the runbook's 移交状态 section reads
        # ctx.assets["handoff_package"], so rendering first wrote "❌ 未签" into the
        # customer-facing runbook even when this call marked the handoff accepted.
        fsutil.atomic_write_text(runbook_path, render_runbook(eng.ctx))
        package_path = paths.reports_dir() / f"handoff_package_{eid}.json"
        fsutil.atomic_write_text(package_path, json.dumps(package, ensure_ascii=False, indent=2))
        _save(eng)
        summary = render_handoff_summary(eng.ctx)
    detail = {
        "engagement_id": eid,
        "runbook": _file_evidence(runbook_path),
        "package": _file_evidence(package_path),
    }
    if operator and operator.strip():
        detail["operator"] = operator.strip()
    audit.log_event("handoff.package", detail=detail)
    if accept:
        accepted = {"engagement_id": eid, **_file_evidence(package_path)}
        if operator and operator.strip():
            accepted["operator"] = operator.strip()
        audit.log_event("handoff.accepted", detail=accepted)
    return {
        "engagement_id": eid,
        "customer_accepted": accept,
        "runbook": str(runbook_path),
        "package": str(package_path),
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# evidence（签字/验收证据留存：FAT/SAT 扫描件等，sha256 + 时间戳）
# ---------------------------------------------------------------------------
def _evidence_index_path(eid: str) -> Path:
    return paths.evidence_dir(eid) / "index.json"


def _read_evidence_index(eid: str) -> list[dict]:
    path = _evidence_index_path(eid)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


@app.post("/api/engagements/{eid}/evidence")
async def attach_evidence(
    eid: str,
    name: str = Form(...),
    operator: str | None = Form(None),
    file: UploadFile | None = File(None),
    path: str | None = Form(None),
) -> dict:
    """Attach an external evidence file (signed FAT/SAT scan …) to an engagement."""
    from datetime import UTC, datetime

    _require_feature("evidence")
    if file is None and not (path and path.strip()):
        raise HTTPException(status_code=422, detail="either 'file' or 'path' is required") from None
    if file is not None:
        content = await _read_limited(file)
    else:
        src = Path(path.strip())  # type: ignore[union-attr]
        if not src.is_file():
            raise HTTPException(status_code=404, detail=f"evidence source not found: {src}") from None
        if src.stat().st_size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"file exceeds {MAX_UPLOAD_BYTES} byte limit")
        content = src.read_bytes()
    if not name.strip():
        raise HTTPException(status_code=422, detail="'name' must not be empty") from None
    safe_name = Path(name).name
    with engagement_lock(eid):
        _load(eid)  # 404 for unknown engagements; nothing attaches to ghosts
        dest = fsutil.safe_child(paths.evidence_dir(eid, create=True), safe_name)
        fsutil.atomic_write_bytes(dest, content)
        digest, size = audit.sha256_file(dest)
        entry = {
            "name": safe_name,
            "sha256": digest,
            "bytes": size,
            "ts": datetime.now(UTC).isoformat(),
            "operator": (operator or "").strip() or None,
        }
        index = [r for r in _read_evidence_index(eid) if r.get("name") != safe_name]
        index.append(entry)
        fsutil.atomic_write_text(_evidence_index_path(eid), json.dumps(index, ensure_ascii=False, indent=2))
    audit.log_event(
        "evidence.attached",
        detail={
            "engagement_id": eid,
            "name": safe_name,
            "path": str(dest),
            "sha256": digest,
            "bytes": size,
            **({"operator": operator.strip()} if operator and operator.strip() else {}),
        },
    )
    return entry


@app.get("/api/engagements/{eid}/evidence")
def list_evidence(eid: str) -> dict:
    return {"engagement_id": eid, "evidence": _read_evidence_index(eid)}


# ---------------------------------------------------------------------------
# lifecycle（归档 / GDPR 删除权）
# ---------------------------------------------------------------------------
@app.post("/api/engagements/{eid}/archive")
def archive_engagement(eid: str) -> dict:
    """Archive the engagement (out of every listing) via the storage backend."""
    with engagement_lock(eid):
        eng = _load(eid)
        dest = _archive(eid)
    audit.log_event(
        "engagement.archived",
        detail={"engagement_id": eid, "customer": eng.ctx.customer, "archive_path": dest},
    )
    return {"archived": True, "engagement_id": eid}


@app.delete("/api/engagements/{eid}")
def delete_engagement(eid: str, confirm: str = Form(...)) -> dict:
    """Delete the engagement JSON + its evidence (right to erasure).

    Requires ``confirm=<customer name>`` verbatim. The audit log itself is
    kept on purpose — erasure covers customer data, not the compliance trail.
    """
    with engagement_lock(eid):
        eng = _load(eid)
        customer = eng.ctx.customer
        if confirm != customer:
            raise HTTPException(
                status_code=400,
                detail=f"confirm must exactly match the customer name {customer!r}",
            ) from None
        _delete(eid)
        ev_dir = paths.evidence_dir(eid)
        if ev_dir.exists():
            shutil.rmtree(ev_dir)
    audit.log_event("engagement.deleted", detail={"engagement_id": eid, "customer": customer})
    return {"deleted": True, "engagement_id": eid}


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
    body = body or {}
    note = body.get("note")
    if not isinstance(note, str) or not note.strip():
        raise HTTPException(status_code=422, detail="'note' is required") from None
    kind = body.get("kind", "research")
    if kind not in _JOURNAL_KINDS:
        raise HTTPException(status_code=422, detail=f"invalid kind: {kind!r}") from None
    from ..engagement.context import JournalEntry

    entry = JournalEntry(kind=kind, note=note.strip(), skill_id=body.get("skill_id"))
    with engagement_lock(eid):
        eng = _load(eid)
        eng.ctx.journal.append(entry)
        _save(eng)
    return entry.model_dump()


@app.post("/api/engagements/{eid}/journal/{jid}/skill")
def journal_to_skill(eid: str, jid: str) -> dict:
    """把一条现场记录沉淀为技能草稿（kind → category 映射预填）。"""
    from ..skills.models import SkillCategory, SkillDraft

    mapping = {
        "research": SkillCategory.RESEARCH,
        "implementation": SkillCategory.IMPLEMENTATION,
        "optimization": SkillCategory.OPTIMIZATION,
    }
    with engagement_lock(eid):
        eng = _load(eid)
        entry = next((e for e in eng.ctx.journal if e.id == jid), None)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"journal entry '{jid}' not found") from None
        if entry.skill_id:
            raise HTTPException(status_code=409, detail=f"already linked to skill {entry.skill_id}") from None
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
    body = body or {}

    def _checked(field: str, validate, value):
        """Validate one field, prefixing bare pydantic errors with the field
        name — the console's context editor renders ``loc`` as the field path,
        and a bare ``validate_python`` error carries an empty one."""
        try:
            return validate(value)
        except ValidationError as exc:
            errors = [{**e, "loc": (field, *e.get("loc", ()))} for e in exc.errors()]
            raise HTTPException(status_code=422, detail=errors) from None

    patched: dict = {}
    if "site" in body:
        from ..engagement.context import SiteInfo

        patched["site"] = _checked("site", SiteInfo.model_validate, body["site"])
    if "safety" in body:
        from ..engagement.context import SafetyPosture

        patched["safety"] = _checked("safety", SafetyPosture.model_validate, body["safety"])
    if "success_criteria" in body:
        patched["success_criteria"] = _checked(
            "success_criteria", _STR_LIST.validate_python, body["success_criteria"]
        )
    if "stakeholders" in body:
        from ..engagement.context import Stakeholder

        patched["stakeholders"] = _checked(
            "stakeholders", lambda v: [Stakeholder.model_validate(s) for s in v], body["stakeholders"]
        )
    if "slos" in body:
        from ..engagement.context import SLOSpec

        patched["slos"] = _checked("slos", lambda v: [SLOSpec.model_validate(s) for s in v], body["slos"])
    assets_patch: dict[str, Any] | None = None
    if "assets" in body:
        # The *values* stay free-form (that is what assets are for), but the
        # container must be an object: ``dict.update("ab")`` raises ValueError,
        # so a console typo would surface as a 500 instead of a 422 naming the
        # field — and a list of pairs would silently merge as keys.
        assets_patch = _checked("assets", _ASSET_MAP.validate_python, body["assets"])
    with engagement_lock(eid):
        eng = _load(eid)
        for field, value in patched.items():
            setattr(eng.ctx, field, value)
        if assets_patch is not None:
            eng.ctx.assets.update(assets_patch)
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
    # ``Path("..").name`` is still ``..``, so the basename alone does not make
    # the name safe as a segment. The upload is *unscrubbed* customer data, so
    # it must stay inside uploads/ and must not land world-readable.
    tmp = fsutil.safe_child(paths.uploads_dir(create=True), safe_name)
    fsutil.atomic_write_text(tmp, content)

    from fastapi.concurrency import run_in_threadpool

    from ..connectors.csv_fallback import CSVConnector
    from ..llm import get_llm_client

    rows = CSVConnector(str(tmp)).extract_sample(100000)
    cfg = CorpusConfig(min_samples_per_category=min_samples, synth_per_gap=synth_per_gap)
    # LLM synthesis kicks in automatically when an LLM credential is
    # configured (env); without a key the forge stays rule-based.
    # forge_rows may make blocking LLM calls (up to ~60s each) — run it in a
    # worker thread so the event loop (and every other endpoint) stays live.
    llm = get_llm_client()
    logger.info(
        "forge start: %d rows from %s (llm=%s)",
        len(rows),
        safe_name,
        llm.describe()["provider"] if llm.available else "off",
    )
    report = await run_in_threadpool(CorpusForge(cfg, llm=llm).forge_rows, rows)
    logger.info(
        "forge done: total=%d real=%d synthetic=%d dropped=%d pii_masked=%d",
        report.total,
        report.real,
        report.synthetic,
        report.dropped,
        report.pii_entities_masked,
    )
    report_id = uuid.uuid4().hex[:8]
    out_html = paths.reports_dir() / f"corpus_report_{report_id}.html"
    out_json = paths.reports_dir() / f"corpus_report_{report_id}.json"
    save_html(report, out_html)
    fsutil.atomic_write_text(out_json, report.model_dump_json(indent=2))
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
def _parse_agent_lines(text: str) -> tuple[list[dict], list[dict]]:
    """Parse the deploy form's agent textarea: ``name: role[: model]`` per line.

    Returns ``(agents, errors)``. Blank lines are skipped (not user errors);
    anything else that cannot become an ``AgentSpec`` comes back as a
    structured error with its 1-based line number, instead of being silently
    dropped by the front-end like the old JS parser did.
    """
    agents: list[dict] = []
    errors: list[dict] = []
    for i, raw in enumerate(text.split("\n"), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(":")]
        name, role = parts[0], parts[1] if len(parts) > 1 else ""
        if not name or not role:
            errors.append(
                {
                    "field": "agents",
                    "line": i,
                    "text": line,
                    "reason": "expected `name: role` (optional third segment: model)",
                }
            )
            continue
        agent: dict = {"name": name, "role": role}
        if len(parts) > 2 and parts[2]:
            agent["model"] = parts[2]
        agents.append(agent)
    return agents, errors


def _parse_source_lines(text: str) -> tuple[dict[str, str], list[dict]]:
    """Parse the deploy form's source textarea: ``connector_slug=source`` per line."""
    sources: dict[str, str] = {}
    errors: list[dict] = []
    for i, raw in enumerate(text.split("\n"), start=1):
        line = raw.strip()
        if not line:
            continue
        key, sep, value = line.partition("=")
        if not sep or not key.strip() or not value.strip():
            errors.append(
                {"field": "sources", "line": i, "text": line, "reason": "expected `connector=source`"}
            )
            continue
        sources[key.strip()] = value.strip()
    return sources, errors


@app.post("/api/deploy/parse")
def deploy_parse(body: dict) -> dict:
    """Parse the deploy form's raw textarea text server-side.

    The old flow parsed in the browser and silently dropped malformed lines, so
    a typo made an agent vanish with no explanation. Here every dropped line
    comes back with its line number and a reason; the front-end renders the
    list and refuses to build a plan until it is empty.
    """
    agents, errors = _parse_agent_lines(str(body.get("agents_text", "")))
    sources, src_errors = _parse_source_lines(str(body.get("sources_text", "")))
    return {"agents": agents, "sources": sources, "errors": errors + src_errors}


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
        plan = build_deploy_plan(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    logger.debug(
        "deploy plan built: agents=%d bound=%d unbound=%d",
        plan["summary"]["agents"],
        len(plan["summary"]["bound_tools"]),
        len(plan["summary"]["unbound_tools"]),
    )
    return plan


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


@app.get("/api/skills/facets")
def api_skills_facets() -> dict:
    """Distinct facet values across the skill store, for the console filters.

    The search endpoint already accepts ``tag`` / ``profile`` / ``gate`` /
    ``phase``; this returns the values that actually exist so the UI can offer
    selects instead of asking the user to guess slugs.
    """
    tags: set[str] = set()
    phases: set[str] = set()
    gates: set[str] = set()
    profiles: set[str] = set()
    for rec in _skill_service().store.load_all():
        tags.update(rec.tags)
        if rec.phase_slug:
            phases.add(rec.phase_slug)
        if rec.gate_slug:
            gates.add(rec.gate_slug)
        profiles.update(rec.applies_to)
    return {
        "tags": sorted(tags),
        "phases": sorted(phases),
        "gates": sorted(gates),
        "profiles": sorted(profiles),
    }


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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.patch("/api/skills/{sid}")
def api_skill_patch(sid: str, patch: SkillPatch) -> dict:
    try:
        return _skill_service().update(sid, patch).model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.post("/api/skills/{sid}/publish")
def api_skill_publish(sid: str) -> dict:
    try:
        rec = _skill_service().publish(sid)
    except KeyError:
        raise HTTPException(status_code=404, detail="skill not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    audit.log_event("skill.publish", detail={"skill_id": sid})
    return rec.model_dump()


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
# showcase API（作品集登记与审校 —— 三个端点全部在 token 之后）
# ---------------------------------------------------------------------------
# 模块级导入：FastAPI 路由注册时即解析请求体类型注解
from ..course import showcase as _showcase  # noqa: E402
from ..course.showcase import ShowcaseRegistration  # noqa: E402


@app.post("/api/showcase/entries")
def api_showcase_register(registration: ShowcaseRegistration) -> dict:
    """登记一条作品集记录：代号、期次、等级、证书编号、作品集文件名。

    ``entry_id`` 由 :func:`fde_scope.course.showcase.register` 生成，请求体里没有
    这个字段（AGENTS.md 不变量 2：外部输入不能设置服务端生成的 id）。作品集文件
    本身不复制进登记表，只记文件名 —— 审校时现读 ``course-labs/D8/`` 下的原文件
    （11 §6.1：公开面只带代号，副本越少越难守住）。
    """
    try:
        entry = _showcase.register(registration)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    audit.log_event("showcase.register", detail={"entry_id": entry.entry_id})
    return entry.model_dump(mode="json")


@app.get("/api/showcase/entries")
def api_showcase_entries() -> list[dict]:
    """本机登记清单。刻意不公开：代号与证书编号是识别信息（11 §6.1–6.2）。"""
    return _showcase.listing()


@app.get("/api/showcase/entries/{entry_id}/audit")
def api_showcase_audit(entry_id: str) -> dict:
    """重新审校一条记录：逐条规则重算，返回判定、依据与可信度档位。

    每次调用都重新读盘，所以一次通过的记录不会替下一次说话（AGENTS.md 不变量 1
    的同一条纪律）。返回里 ``graded`` 恒为 ``false`` —— A/B/C 判级是人的 blocker
    （03:75 ③④），而且 23 附 C.2 记录教案措辞存在谁都不满足的组合。
    """
    try:
        return _showcase.audit(entry_id).as_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="showcase entry not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


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


@app.get("/api/ontology/schema/{schema_id}/diagram")
def api_ontology_diagram(schema_id: str) -> dict:
    """Mermaid 类图（与 CLI ``ontology diagram`` 同语义：父类继承 + 对象属性边 + 数据属性行）。"""
    from ..ontology.diagram import schema_to_mermaid
    from ..ontology.store import OntologyStore

    store = OntologyStore()
    schema = store.load_schema(schema_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"unknown ontology schema: {schema_id}")
    return {"schema_id": schema.id, "version": schema.version, "mermaid": schema_to_mermaid(schema)}


@app.get("/api/ontology/validate/{target_id}")
def api_ontology_validate(target_id: str) -> dict:
    """SHACL-lite 校验：schema 走 TBox（含 import 合并视图），store 走 ABox（对
    ``ontology_ref`` 指向的 TBox）——与 CLI ``ontology validate`` / ``check`` 同语义。"""
    from ..ontology.store import OntologyStore

    store = OntologyStore()
    schema = store.load_schema(target_id)
    if schema is not None:
        from ..ontology.validation import validate_schema

        report = validate_schema(schema, loader=store.load_schema)
        return {"kind": "schema", "target": f"{schema.id}@{schema.version}", **report.model_dump()}
    inst = store.load_store(target_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"unknown ontology target: {target_id}")
    from ..ontology.validation import validate_store

    report = validate_store(inst, loader=store.load_schema)
    return {"kind": "store", "target": target_id, **report.model_dump()}


@app.post("/api/ontology/diff")
def api_ontology_diff(body: dict) -> dict:
    """TBox 版本 diff（D1-D4）+ 全部引用工作区实例库的 ABox 影响面
    （与 CLI ``ontology diff`` 同语义；影响面是迁移工作量证据，不是推断）。"""
    from dataclasses import asdict

    from ..ontology.diff import diff_schemas, store_impact
    from ..ontology.store import OntologyStore

    old_id = str(body.get("old", "")).strip()
    new_id = str(body.get("new", "")).strip()
    if not old_id or not new_id:
        raise HTTPException(status_code=422, detail="both `old` and `new` schema ids are required")
    store = OntologyStore()
    old = store.load_schema(old_id)
    new = store.load_schema(new_id)
    missing = [i for i, s in ((old_id, old), (new_id, new)) if s is None]
    if missing:
        raise HTTPException(status_code=404, detail=f"unknown ontology schema: {', '.join(missing)}")
    assert old is not None and new is not None  # narrowed above; mypy cannot see the comprehension
    diff = diff_schemas(old, new)
    impact: list[dict] = []
    for meta in store.list_stores():
        inst = store.load_store(meta["id"])
        if inst is not None and inst.ontology_ref.split("@", 1)[0] == old.id:
            impact.extend(asdict(c) for c in store_impact(inst, diff))
    return {
        "from": f"{old.id}@{diff.from_version}",
        "to": f"{new.id}@{diff.to_version}",
        "ok": diff.ok,
        "breaking": [asdict(c) for c in diff.breaking],
        "info": [asdict(c) for c in diff.info],
        "impact": impact,
    }


# ---------------------------------------------------------------------------
# ops API（连接器 / eval / flywheel / license —— §1.3 的四个面板）
# ---------------------------------------------------------------------------
#: Credential env var *names* per connector. The endpoint reports only
#: whether each is set (a boolean) — never its value (invariant 3).
_CONNECTOR_ENV: dict[str, tuple[str, ...]] = {
    "mes": ("FDE_SCOPE_MES_BASE_URL", "FDE_SCOPE_MES_API_TOKEN"),
    "historian": ("FDE_SCOPE_HISTORIAN_BASE_URL", "FDE_SCOPE_HISTORIAN_API_TOKEN"),
    "mqtt_sparkplug": ("FDE_SCOPE_MQTT_USERNAME", "FDE_SCOPE_MQTT_PASSWORD"),
    "zammad": ("FDE_SCOPE_ZAMMAD_BASE_URL", "FDE_SCOPE_ZAMMAD_API_TOKEN"),
    "salesforce": ("FDE_SCOPE_SF_INSTANCE_URL", "FDE_SCOPE_SF_ACCESS_TOKEN"),
}

#: One-line mode notes from each module's docstring — what the connector does
#: when its optional dependency or its credentials are missing.
_CONNECTOR_NOTES: dict[str, str] = {
    "csv": "JSONL/CSV 通用兜底，零依赖，冷启动默认路径",
    "documents": "导入无需 extra；解析文件需要 [agentscope]",
    "mqtt_sparkplug": "JSONL 抓包回放零依赖；实连 broker 需 paho-mqtt（[mqtt]），凭据走 env",
    "mes": "HTTP 模式 / JSONL 回放 / 未配置三态；凭据走 env 或 options",
    "historian": "时序库 HTTP API；凭据走 env 或 options",
    "zammad": "纯 urllib 的 REST 实现；凭据走 env",
    "salesforce": "纯 urllib 的 REST 实现；凭据走 env",
    "mysql": "MySQL 8+ 直连，选 [mysql] extra",
    "opcua": "asyncua 对接 OPC UA 地址空间，选 [opcua] extra",
    "ros2_bag": "读 rosbag2 / .mcap，选 [ros2] extra；大二进制类型默认排除",
}


@app.get("/api/connectors")
def api_connectors() -> dict:
    """Connector registry status. Import-level truth only: a slug in the
    registry imported cleanly, one in the module table but not the registry is
    missing its optional dependency. Runtime reachability of a customer system
    is deliberately NOT probed from a GET — constructing connections is a
    deploy-time act. Env credentials surface as booleans, never values."""
    from ..connectors._registry import _MODULE_BY_TYPE, get_registry

    registry = get_registry()
    entries: list[dict] = []
    for slug in sorted(set(_MODULE_BY_TYPE) | set(registry)):
        env_names = _CONNECTOR_ENV.get(slug, ())
        entries.append(
            {
                "slug": slug,
                "import_ok": slug in registry,
                "note": _CONNECTOR_NOTES.get(slug, ""),
                # names + booleans only — values never leave the process
                "env": {name: bool(os.environ.get(name, "").strip()) for name in env_names},
            }
        )
    return {"connectors": entries, "registered": len(registry)}


@app.get("/api/eval/info")
def api_eval_info() -> dict:
    """What the eval panel needs before running: metric names + honest labels,
    and whether a real LLM is configured (mock runs need nothing)."""
    from ..eval.metrics import METRICS
    from ..llm import get_llm_client

    return {"metrics": dict(METRICS), "llm_available": get_llm_client().available}


@app.post("/api/eval/run")
def api_eval_run(body: dict) -> dict:
    """Run the FDE benchmark over inline cases or a JSON/JSONL test-set path.

    ``agent: "mock"`` needs nothing; ``"mimo"`` needs a configured LLM and
    returns 502 with upgrade guidance when the env has none — the panel shows
    that instead of pretending to run.
    """
    import json as _json

    from ..eval import FDEBenchmark, MiMoReplyFn, MockReplyFn
    from ..eval.metrics import EvalCase, ReplyFn
    from ..llm import LLMError, get_llm_client

    agent = str(body.get("agent", "mock"))
    cases_raw = body.get("cases")
    if not cases_raw and body.get("test_set"):
        path = Path(str(body["test_set"]))
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"test_set not found: {path}")
        text = path.read_text(encoding="utf-8")
        try:
            cases_raw = _json.loads(text)
        except _json.JSONDecodeError:
            cases_raw = [_json.loads(line) for line in text.splitlines() if line.strip()]
    if not cases_raw:
        raise HTTPException(status_code=422, detail="provide `cases` (list) or `test_set` (JSON/JSONL path)")
    try:
        cases = [EvalCase.model_validate(c) for c in cases_raw]
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from None

    reply_fn: ReplyFn
    if agent == "mock":
        accuracy = min(1.0, max(0.0, float(body.get("accuracy", 0.9))))
        reply_fn = MockReplyFn(accuracy=accuracy)
    elif agent == "mimo":
        client = get_llm_client()
        if not client.available:
            raise HTTPException(
                status_code=502,
                detail="no LLM configured — set the provider env key (see llm docs), or run agent=mock",
            )
        reply_fn = MiMoReplyFn(client)
    else:
        raise HTTPException(status_code=422, detail=f"unknown agent: {agent!r} — use 'mock' or 'mimo'")
    try:
        report = FDEBenchmark().run(reply_fn, cases)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed mid-run: {exc}") from exc
    return report.model_dump(mode="json")


@app.get("/api/flywheel")
def api_flywheel() -> dict:
    """Flywheel snapshot + retrain job descriptors, honestly labelled.

    The counters are *this server process*: the engine is in-memory, so the
    panel must not claim fleet-wide numbers. The jobs are descriptors for an
    external orchestrator — nothing in this process fires them (the CLI used
    to print a nonexistent scheduler; the panel will not repeat that)."""
    from ..flywheel import DataFlywheel
    from ..flywheel.retrain_scheduler import RetrainScheduler

    jobs = [
        {"name": j.name, "cron": j.cron, "min_new_samples": j.min_new_samples, "kind": j.kind}
        for j in RetrainScheduler().jobs
    ]
    return {"snapshot": DataFlywheel().snapshot(), "jobs": jobs, "process_local": True}


@app.get("/api/license")
def api_license() -> dict:
    """Read-only license facts. The key and its signature never appear here —
    only where the key was found (env / key file / none)."""
    from .. import license as lic

    info = lic.load_license()
    if os.environ.get(lic.ENV_LICENSE_KEY, "").strip():
        key_source = "env"
    else:
        key_source = "file" if (paths.data_root() / paths.DATA_SUBDIR / lic.KEY_FILENAME).exists() else "none"
    all_features = sorted(set().union(*lic.TIER_FEATURES.values()))
    return {
        "customer": info.customer,
        "tier": info.tier,
        "tier_rank": lic.TIER_ORDER[info.tier],
        "seats": info.seats,
        "expires_at": info.expires_at.isoformat() if info.expires_at else None,
        "expired": bool(info.expired),
        "key_source": key_source,
        "features": {name: lic.has_feature(name) for name in all_features},
    }


from fastapi.staticfiles import StaticFiles  # noqa: E402

app.mount("/reports", StaticFiles(directory=str(_REPORTS_DIR)), name="reports")

# Skills-catalog portal (generated site/, self-contained). Read-only repo
# asset; the mount is conditional because the wheel packages ``fde_scope``
# only, and without ``docs/`` there is nothing to mount. The rail links to
# /catalog on every install, so the else-branch answers that path with an
# in-app notice — the reader learns where the portal lives instead of
# landing on a 404 or being thrown off-site.
_CATALOG_DIR = catalog_site_dir()
if _CATALOG_DIR is not None:
    app.mount("/catalog", StaticFiles(directory=str(_CATALOG_DIR), html=True), name="catalog")
else:
    _CATALOG_NOTICE = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>技能手册库 · FDE Scope</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{NOTICE_CSS}</style>
</head>
<body>
<main class="main">
<div class="notice">
<div class="brand"><div class="logo">FDE <span>Scope</span></div><span class="tag">技能手册库</span></div>
<h1>技能手册库不在这次安装里</h1>
<p>这个地址渲染的是技能手册门户 <code>docs/skills-catalog/site/</code> ——
由 <code>scripts/build_catalog_site.py</code> 生成的单文件站点。当前安装里没有
<code>docs/</code> 目录（从 wheel 安装时就是这样），所以这里没有内容可读。</p>
<p>门户全文在仓库的 <code>docs/skills-catalog/site/index.html</code>。克隆仓库后重启服务，
这个地址就会直接渲染它。</p>
<p class="cta"><a class="btn ghost" href="/">返回功能总览</a></p>
</div>
</main>
</body>
</html>"""
    _CATALOG_NOTICE_EN = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Skills handbook · FDE Scope</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{NOTICE_CSS}</style>
</head>
<body>
<main class="main">
<div class="notice">
<div class="brand"><div class="logo">FDE <span>Scope</span></div><span class="tag">skills handbook</span></div>
<h1>The skills handbook is not in this install</h1>
<p>This address renders the skills-catalog portal <code>docs/skills-catalog/site/</code> —
a self-contained site generated by <code>scripts/build_catalog_site.py</code>. This
install has no <code>docs/</code> directory (a wheel install never ships one), so there
is nothing to read here.</p>
<p>The portal lives in the repository at <code>docs/skills-catalog/site/index.html</code>.
Clone the repository and restart the server and this address renders it directly.</p>
<p class="cta"><a class="btn ghost" href="/en/">Back to the overview</a></p>
</div>
</main>
</body>
</html>"""

    @app.get("/catalog/{rest:path}", response_class=HTMLResponse)
    def catalog_notice(rest: str) -> str:
        """The portal mount's absence notice (see the comment above).

        Read-only and carries no engagement data, so it is reachable
        without a token (see ``auth.PUBLIC_PATHS``)."""
        return _CATALOG_NOTICE_EN if rest.startswith("en/") else _CATALOG_NOTICE


# GTM one-page portal (hand-authored static site at repo-root GTM/). Mounted
# when present; otherwise the rail's /GTM links land on an in-app notice for
# the same reason as /catalog above.
_GTM_DIR = gtm_site_dir()
if _GTM_DIR is not None:
    app.mount("/GTM", StaticFiles(directory=str(_GTM_DIR), html=True), name="gtm")
else:
    _GTM_NOTICE = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GTM 官网 · FDE Scope</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{NOTICE_CSS}</style>
</head>
<body>
<main class="main">
<div class="notice">
<div class="brand"><div class="logo">FDE <span>Scope</span></div><span class="tag">GTM 官网</span></div>
<h1>GTM 官网不在这次安装里</h1>
<p>这个地址渲染的是仓库根目录 <code>GTM/</code> 下的单页官网（含 <code>GTM/index.html</code>
与其英版 <code>GTM/en/index.html</code>）。当前安装里没有这个目录（从 wheel 安装时就是这样），
所以这里没有内容可读。</p>
<p>克隆仓库后重启服务，这个地址就会直接渲染它。</p>
<p class="cta"><a class="btn ghost" href="/">返回功能总览</a></p>
</div>
</main>
</body>
</html>"""
    _GTM_NOTICE_EN = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GTM site · FDE Scope</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{NOTICE_CSS}</style>
</head>
<body>
<main class="main">
<div class="notice">
<div class="brand"><div class="logo">FDE <span>Scope</span></div><span class="tag">GTM site</span></div>
<h1>The GTM site is not in this install</h1>
<p>This address renders the one-page site at repo-root <code>GTM/</code> (with
<code>GTM/index.html</code> and its English variant <code>GTM/en/index.html</code>).
This install has no such directory (a wheel install never ships one), so there is
nothing to read here.</p>
<p>Clone the repository and restart the server and this address renders it directly.</p>
<p class="cta"><a class="btn ghost" href="/en/">Back to the overview</a></p>
</div>
</main>
</body>
</html>"""

    @app.get("/GTM/{rest:path}", response_class=HTMLResponse)
    def gtm_notice(rest: str) -> str:
        """The GTM mount's absence notice (see the comment above).

        Read-only and carries no engagement data, so it is reachable
        without a token (see ``auth.PUBLIC_PATHS``)."""
        return _GTM_NOTICE_EN if rest.startswith("en/") else _GTM_NOTICE


# GitHub-resources portal + verbatim mirrors (generated site/ + mirror/ under
# docs/github-resources/). Mounted when present; a wheel install ships no
# docs/, so the rail's /gh-resources links fall through to an in-app notice,
# exactly as /catalog and /GTM above do.
_RESOURCES_DIR = resources_site_dir()
if _RESOURCES_DIR is not None:
    app.mount("/gh-resources", StaticFiles(directory=str(_RESOURCES_DIR), html=True), name="resources")
else:
    _RESOURCES_NOTICE = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub 资源门户 · FDE Scope</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{NOTICE_CSS}</style>
</head>
<body>
<main class="main">
<div class="notice">
<div class="brand"><div class="logo">FDE <span>Scope</span></div><span class="tag">GitHub 资源门户</span></div>
<h1>静态门户不在这次安装里</h1>
<p>这个地址渲染的是 <code>docs/github-resources/</code> 下的静态门户
（<code>site/index.html</code> 与其英版）和逐字镜像（<code>mirror/</code>）——
由 <code>scripts/build_resources_site.py</code> 生成。当前安装里没有 <code>docs/</code>
目录（从 wheel 安装时就是这样），所以这里没有内容可读。</p>
<p>全量资源索引仍然可用：打开 <a href="/resources">GitHub 资源页</a>，它从包内的
<code>fde_scope/resources/data/resources.yaml</code> 渲染，安装版也带得上。</p>
<p class="cta"><a class="btn ghost" href="/resources">GitHub 资源页</a><a class="btn ghost" href="/">返回功能总览</a></p>
</div>
</main>
</body>
</html>"""
    _RESOURCES_NOTICE_EN = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub resources portal · FDE Scope</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{NOTICE_CSS}</style>
</head>
<body>
<main class="main">
<div class="notice">
<div class="brand"><div class="logo">FDE <span>Scope</span></div><span class="tag">GitHub resources portal</span></div>
<h1>The static portal is not in this install</h1>
<p>This address renders <code>docs/github-resources/</code>: the generated portal
(<code>site/index.html</code> and its English variant) plus the verbatim mirrors
under <code>mirror/</code>, built by <code>scripts/build_resources_site.py</code>.
This install has no <code>docs/</code> directory (a wheel install never ships one),
so there is nothing to read here.</p>
<p>The full index is still available: open the <a href="/en/resources">GitHub
resources page</a> — it renders from the packaged
<code>fde_scope/resources/data/resources.yaml</code>, which a wheel install does carry.</p>
<p class="cta"><a class="btn ghost" href="/en/resources">GitHub resources page</a><a class="btn ghost" href="/en/">Back to the overview</a></p>
</div>
</main>
</body>
</html>"""

    @app.get("/gh-resources/{rest:path}", response_class=HTMLResponse)
    def resources_notice(rest: str) -> str:
        """The resources-portal mount's absence notice (see the comment above).

        Read-only and carries no engagement data, so it is reachable
        without a token (see ``auth.PUBLIC_PATHS``)."""
        return _RESOURCES_NOTICE_EN if rest.startswith("en/") else _RESOURCES_NOTICE


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


@app.get("/en/", response_class=HTMLResponse)
def overview_en() -> str:
    """English variant of the landing page."""
    return _OVERVIEW_HTML_EN


@app.get("/en/console", response_class=HTMLResponse)
def dashboard_en() -> str:
    """English variant of the engagement console."""
    return _DASHBOARD_HTML_EN


@app.get("/certification", response_class=HTMLResponse)
def certification() -> str:
    """The FDE certification centre: vendor exam specs, the public outline,
    sourced practice items and the channel due-diligence checklist."""
    return _CERTIFICATION_HTML


@app.get("/en/certification", response_class=HTMLResponse)
def certification_en() -> str:
    """English variant of the certification centre."""
    return _CERTIFICATION_HTML_EN


@app.get("/glossary", response_class=HTMLResponse)
def glossary() -> str:
    """The field vocabulary shared by the SOP, the outline and the console.

    Read-only and carries no engagement data, so it is reachable without a
    token (see ``auth.PUBLIC_PATHS``)."""
    return _GLOSSARY_HTML


@app.get("/en/glossary", response_class=HTMLResponse)
def glossary_en() -> str:
    """English variant of the glossary."""
    return _GLOSSARY_HTML_EN


@app.get("/resources", response_class=HTMLResponse)
def resources() -> str:
    """The GitHub-resource index: every harvested FDE repository, provenance-
    stamped and searchable, rendered from the packaged YAML.

    Static read-only material with no engagement data, so it is reachable
    without a token (see ``auth.PUBLIC_PATHS``). GitHub URLs render as inert
    ``<code>``, never outbound links."""
    return _RESOURCES_HTML


@app.get("/en/resources", response_class=HTMLResponse)
def resources_en() -> str:
    """English variant of the GitHub-resource index."""
    return _RESOURCES_HTML_EN


@app.get("/course", response_class=HTMLResponse)
def course() -> str:
    """The Level-1 beginner course, rendered from ``course-level-1/``.

    Static reading material with no engagement data, so it is reachable
    without a token (see ``auth.PUBLIC_PATHS``)."""
    return _COURSE_HTML


@app.get("/en/course", response_class=HTMLResponse)
def course_en() -> str:
    """English variant of the course page (chrome translated, lessons are
    served as the Chinese authors wrote them)."""
    return _COURSE_HTML_EN


@app.get("/sop", response_class=HTMLResponse)
def sop() -> str:
    """The full FDE SOP, rendered from ``docs/fde_sop_full.md``.

    Static reading material with no engagement data, so it is reachable
    without a token (see ``auth.PUBLIC_PATHS``)."""
    return _SOP_HTML


@app.get("/en/sop", response_class=HTMLResponse)
def sop_en() -> str:
    """English variant of the SOP page (chrome translated, the document is
    served as the Chinese authors wrote it)."""
    return _SOP_HTML_EN


@app.get("/showcase", response_class=HTMLResponse)
def showcase() -> str:
    """The portfolio registry's public explainer: the rubric, the credibility
    tiers, the endpoints and the known gaps.

    It renders no listings — an unauthenticated page must not carry a cohort's
    codenames or certificate numbers (11 §6.1), and the records never leave the
    machine's data root either way. Read-only static material, so it is
    reachable without a token (see ``auth.PUBLIC_PATHS``)."""
    return _SHOWCASE_HTML


@app.get("/en/showcase", response_class=HTMLResponse)
def showcase_en() -> str:
    """English variant of the portfolio-registry page (chrome translated, the
    rubric table is served as authored because it cites Chinese lessons)."""
    return _SHOWCASE_HTML_EN


# Repository documents rendered locally (fde_scope/web/docs_reader.py). The
# images route is registered first so its literal two-segment path can never
# be shadowed; both are read-only with no engagement data (auth.PUBLIC_PATHS).
@app.get("/docs/images/{name}")
def repo_doc_image(name: str) -> FileResponse:
    path = _doc_image_path(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"unknown image: {name!r}")
    return FileResponse(path)


@app.get("/docs/{slug}", response_class=HTMLResponse)
def doc_page(slug: str) -> str:
    """Render one repository document (README, docs/*.md, LICENSE, NOTICE)."""
    if slug not in _DOC_SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown document: {slug!r}")
    return _DOC_PAGES[slug]


@app.get("/en/docs/{slug}", response_class=HTMLResponse)
def doc_page_en(slug: str) -> str:
    """English chrome over the same document corpus (bodies stay as authored)."""
    if slug not in _DOC_SLUGS:
        raise HTTPException(status_code=404, detail=f"unknown document: {slug!r}")
    return _DOC_PAGES_EN[slug]


#: Homepage connector tiles: curated copy per slug (what it is), while the
#: status pill comes from the registry at import time — a hand-written "stub"
#: label drifted from the shipped code once already (plan §2.1).
_CONNECTOR_TILE_META: dict[str, tuple[str, str, str]] = {
    "csv": ("i-doc", "CSV", "通用兜底，冷启动"),
    "zammad": ("i-ticket", "Zammad", "工单系统"),
    "salesforce": ("i-cloud", "Salesforce", "CRM"),
    "mysql": ("i-db", "MySQL", "关系库直连"),
    "documents": ("i-docs", "Documents", "PDF/Word/Excel/PPT 解析（agentscope.rag，延迟导入）"),
    "opcua": ("i-cpu", "OPC UA", "PLC tag 读取（asyncua 驱动）"),
    "mqtt_sparkplug": ("i-broadcast", "MQTT-Sparkplug", "工厂设备遥测"),
    "ros2_bag": ("i-bot", "ROS2 Bag", "机器人轨迹回放（rosbags）"),
    "mes": ("i-factory", "MES (ISA-95)", "工单/质量/停机"),
    "historian": ("i-trend", "Historian", "时序历史库"),
}


def _connector_tiles() -> tuple[int, str]:
    """(count, tile markup) for the homepage connectors section."""
    from ..connectors._registry import _MODULE_BY_TYPE, get_registry

    registry = get_registry()
    tiles: list[str] = []
    for slug in _MODULE_BY_TYPE:
        icon, name, desc = _CONNECTOR_TILE_META.get(slug, ("i-plug", slug, ""))
        ok = slug in registry
        tiles.append(
            f'<div class="tile"><svg class="ic"><use href="#{icon}"/></svg><div class="name">{name}</div>'
            f'<div class="desc">{desc}</div><span class="status {"s-ok" if ok else "s-stub"}">'
            f"{'已注册' if ok else '缺可选依赖'}</span></div>"
        )
    return len(tiles), "\n".join(tiles)


_OVERVIEW_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FDE Scope · 功能总览</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){var t=null,q=null;try{t=localStorage.getItem('fde-theme')}catch(e){}try{q=new URLSearchParams(location.search).get('theme')}catch(e){}if(q==='dark'||q==='light'){t=q}else if(!t){t='light'}document.documentElement.dataset.theme=t})();</script>
<style>
/* Hallmark · genre: modern-minimal · macrostructure: long-document · design-system: DESIGN.md (Workbench) · designed-as-app */
__BASE_CSS__
/* Overview-only vocabulary. The status chip, the zone flow and the readout
   rows are this page's own components; everything shared with certification
   and glossary comes from ``layout.BASE_CSS`` rather than a copy that drifted
   from it. */
.tile .name .ic-xs{vertical-align:-2px;margin-left:3px}
.status{display:inline-flex;align-items:center;gap:6px;margin-top:var(--sp2);padding:3px 8px;
border:1px solid var(--border-ink);border-radius:var(--r1);font:500 var(--fs-xs)/1.5 var(--mono);color:var(--muted)}
.status::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--faint);flex:none}
.s-ok::before{background:var(--good-dot)}
.s-partial::before{background:var(--warn-dot)}
.s-stub::before{background:var(--bad-dot)}
.step-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--sp2)}
.zone{background:var(--panel);border:1px solid var(--border);border-radius:var(--r1);padding:var(--sp3);min-width:0}
.zone .ztag{font:600 var(--fs-xs)/1.5 var(--mono);letter-spacing:var(--track-kicker);text-transform:uppercase;color:var(--accent-text)}
.zone .zname{font-size:var(--fs-body);font-weight:650;margin:6px 0 10px}
.zone ol{margin:0;padding:0;list-style:none;font-size:var(--fs-sm);color:var(--muted)}
.zone li{display:flex;align-items:center;gap:7px;padding:5px 0;border-top:1px solid var(--border)}
.zone li:first-child{border-top:0}
.zone li b{color:var(--fg);font:600 var(--fs-xs)/1.5 var(--mono)}
.zone .marks{margin-left:auto;display:inline-flex;gap:4px}
.kpi-row{display:flex;justify-content:space-between;align-items:baseline;gap:var(--sp2);
padding:5px 0;border-bottom:1px solid var(--border);font-size:var(--fs-sm);color:var(--muted)}
.kpi-row:last-child{border:0}
.kpi-row .v{font:700 var(--fs-sm) var(--mono);color:var(--fg)}
.cli{background:var(--code);border:1px solid var(--border);border-radius:var(--r0);padding:var(--sp3);
font:400 var(--fs-xs)/1.75 var(--mono);overflow-x:auto;margin:var(--sp2) 0 0}
.cli .c{color:var(--muted)}
.cli .cmd{color:var(--accent-text)}
.inv-n{display:inline-flex;width:20px;height:20px;border:1px solid var(--border-ink);border-radius:var(--r1);
align-items:center;justify-content:center;font:600 var(--fs-xs)/1 var(--mono);color:var(--accent-text);
margin-right:var(--sp2);vertical-align:-4px}
@media(max-width:960px){
.cols-4,.cols-3,.step-flow{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:640px){
.cols-4,.cols-3,.cols-2,.step-flow{grid-template-columns:1fr}
.stats{grid-template-columns:repeat(2,minmax(0,1fr))}
.hero{padding:6px 0 24px}
footer{flex-direction:column}
}
__SHELL_CSS__
</style>
</head>
<body>
__ICON_SPRITE__
<div class="shell">
<aside class="side">
  <div class="brand">
    <div class="logo">FDE <span>Scope</span></div>
    <span class="tag">72h · raw data → deployed agent</span>
  </div>
  <nav class="snav">
__SIDE_NAV__
  </nav>
  <div class="side-foot">
    <a class="lang" href="/en/" title="English version" aria-label="Switch to English">EN</a>
    <button class="tbtn" onclick="toggleTheme()" title="切换深浅主题" aria-label="切换深浅主题">
      <svg class="ic when-dark"><use href="#i-sun"/></svg>
      <svg class="ic when-light"><use href="#i-moon"/></svg>
    </button>
  </div>
</aside>

<main class="main">
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

<section id="sop">
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

<section id="gates">
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

<section id="connectors">
<div class="sec-head"><svg class="ic"><use href="#i-plug"/></svg><h2>__CONNECTOR_COUNT__ 个数据连接器</h2><span class="n">03</span></div>
<p class="meta" style="margin:6px 0 0">状态由连接器注册表在导入时生成（依赖齐 = 已注册）；运行时能力矩阵见 <a href="/console#ops">控制台运维面板</a>。</p>
<div class="grid cols-4">
__CONNECTOR_TILES__
</div>
</section>

<section id="ontology">
<div class="sec-head"><svg class="ic"><use href="#i-globe"/></svg><h2>Ontology 语义层 · TBox + ABox</h2><span class="n">04</span></div>
<div class="grid cols-4">
  <div class="tile"><svg class="ic"><use href="#i-layers"/></svg><div class="name">TBox 双 Schema</div><div class="desc">fde-core（Skill/Connector/Engagement 等核心概念）+ mfg-overlay（ISA-95 制造业 overlay，imports 复用）</div><span class="status s-ok">内置</span></div>
  <div class="tile"><svg class="ic"><use href="#i-map"/></svg><div class="name">SKOS 概念体系</div><div class="desc">fde-corpus-taxonomy 双向集成：corpus 引擎按概念覆盖度选样本，skill 搜索概念扩展召回</div><span class="status s-ok">内置</span></div>
  <div class="tile"><svg class="ic"><use href="#i-shield"/></svg><div class="name">SHACL-lite 校验</div><div class="desc">ONTO-* 错误码契约（domain/range、环引用、未声明前缀），校验失败即拦截</div><span class="status s-ok">10 个错误码</span></div>
  <div class="tile"><svg class="ic"><use href="#i-doc"/></svg><div class="name">JSON-LD 1.1 导出</div><div class="desc">schema 直出；store 导出自动并入其 TBox 上下文，CLI 与 Web API 同一实现。<a href="/console#ontology">→ 本体库</a></div><span class="status s-ok">零新依赖</span></div>
</div>
</section>

<section id="modules">
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
  <div class="tile"><svg class="ic"><use href="#i-monitor"/></svg><div class="name">UI 层</div><div class="desc">CLI（Typer，全延迟导入）· Web 控制台（86 路由）· QwenPaw PawApp（18 路由 /api/fde-scope）· macOS App（DMG 双击即用，即本控制台）。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-compass"/></svg><div class="name">SOP 层</div><div class="desc">engagement/：18 阶段 · 4 zones · 10 个可执行 gate（advance 实时重评估）+ handoff；profiles/：ticket · manufacturing 场景选择器。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-gears"/></svg><div class="name">能力层</div><div class="desc">connectors · corpus · deploy · eval · flywheel · integrations · ontology · skills —— 核心数据管线，规则为底、LLM 可选增强。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-wrench"/></svg><div class="name">横切层</div><div class="desc">llm.py（唯一 LLM 出口，失败回退规则路径）· config.py · templates/（Jinja 报告与 runbook）· paths.py（data_root 唯一路径解析）。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-drive"/></svg><div class="name">文件事实源</div><div class="desc">零数据库：.fde_scope/（engagements · skills · uploads）+ reports/；一律经 fsutil.atomic_write_text 原子写。</div></div>
  <div class="tile"><svg class="ic"><use href="#i-plug"/></svg><div class="name">外部依赖（全可选）</div><div class="desc">AgentScope 2.0.x（extra，实测窗口 >=2.0.4.post1,&lt;3；deploy 三支柱 + documents 延迟导入）· MiMo LLM（凭据仅环境变量）· QwenPaw 宿主。</div></div>
</div>
</section>

<section id="practices">
<div class="sec-head"><svg class="ic"><use href="#i-check-badge"/></svg><h2>工程最佳实践 · 七条不变式</h2><span class="n">07</span></div>
<p class="sec-note">AGENTS.md 契约，由架构守护测试钉住。</p>
<div class="grid cols-3">
  <div class="tile"><div class="name"><span class="inv-n">1</span>Gate 实时重评估</div><div class="desc">advance() 每次重评当前阶段全部 gate，过期通过不作数；强推也评估留痕。禁止缓存/短路。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">2</span>ID 服务端生成</div><div class="desc">SkillRecord.id / EngagementContext.id 由所属服务分配，外部输入永远不能指定。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">3</span>凭据只走环境变量</div><div class="desc">API key 不落 manifest / 报告 / engagement JSON / 日志。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">4</span>原子写盘</div><div class="desc">一切用户状态经 fsutil.atomic_write_text（临时文件 + os.replace），禁止裸 write_text。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">5</span>规则授权是唯一通道</div><div class="desc">build_toolkit 不打 is_read_only（上游 ≥2.0.5 read-only 先放行）；未匹配工具按模式回退 DEFAULT→ASK / DONT_ASK→DENY。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">6</span>实测版本窗口</div><div class="desc">pyproject 与 docs 逐字引用同一 agentscope specifier，放宽前逐版本真库跑测。</div></div>
  <div class="tile"><div class="name"><span class="inv-n">7</span>Web 变更路由须过认证</div><div class="desc">新路由确认未被 auth 白名单误放；token 只从 FDE_SCOPE_API_TOKEN 环境变量读，不落文件/日志/响应。</div></div>
</div>
<p class="sec-note">验证锚点：make test · pytest tests/test_architecture_guard.py（6 项契约）· pytest -m agentscope（真库运行时）· ruff check + format --check · 架构证据模型 docs/architecture-model/architecture-map.md</p>
</section>

<section id="kpi">
<div class="sec-head"><svg class="ic"><use href="#i-trend"/></svg><h2>制造业 KPI（虚构演示数据）</h2><span class="n">08</span></div>
<p class="meta" style="margin:6px 0 0">换成真实数据：在控制台创建 manufacturing engagement，门禁与 KPI 探索器（/console → KPI tab）会从真实 engagement 计算；本区数字仅作版式演示。</p>
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
<span class="cmd">fde-scope</span> engage init --customer aurora-motors --profile manufacturing<br><br>
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

<section id="scenarios">
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
    <span class="status s-ok">核心可用 · 工业 IO 已接入</span>
  </div>
</div>
</section>

<footer>
  <span>FDE Scope · 基于真实 AgentScope 2.0 API · MIT License</span>
  <span>测试套件 CI 全绿（含架构守护测试 6 项契约）· 零配置可跑</span>
</footer>

</div>
</main>
</div>
<script>
function toggleTheme(){
  var h = document.documentElement;
  var n = h.dataset.theme === 'light' ? 'dark' : 'light';
  h.dataset.theme = n;
  try { localStorage.setItem('fde-theme', n); } catch(e) {}
}
</script>
<script>__SHELL_JS__</script>
</body>
</html>
"""


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FDE Scope · Engagement Console</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){var t=null,q=null;try{t=localStorage.getItem('fde-theme')}catch(e){}try{q=new URLSearchParams(location.search).get('theme')}catch(e){}if(q==='dark'||q==='light'){t=q}else if(!t){t='light'}document.documentElement.dataset.theme=t})();</script>
<style>
/* Hallmark · genre: modern-minimal · macrostructure: workbench · design-system: DESIGN.md (Workbench) · designed-as-app */
/* Tokens, base and the app shell come from layout.py (see its docstring for
   the contract); everything below the two placeholders is console-only CSS. */
__BASE_CSS__
__SHELL_CSS__
/* the console keeps an app-width main column: its workbench views are
   master-detail layouts, not long documents */
.main{padding:var(--sp4) var(--sp4) var(--sp5);overflow-x:clip;max-width:1240px;margin:0 auto}
h2{font-size:var(--fs-body);margin:0 0 var(--sp2);color:var(--fg);font-weight:650;letter-spacing:0;text-wrap:balance}
/* the global button rule pads every button; without this the fixed-size
   theme toggle crushes its 16px icon */
.tbtn{padding:0}
.card{background:var(--layer-01);border:1px solid var(--border);border-radius:var(--r1);
padding:var(--sp3);margin-bottom:var(--sp3)}
.eng{cursor:pointer;transition:border-color var(--dur) var(--ease),background-color var(--dur) var(--ease)}
.eng:hover{border-color:var(--border-ink)}
.eng .id{font-weight:600}
.meta{color:var(--muted);font-size:var(--fs-xs)}
.eng .meta{margin-top:2px}
/* no pills anywhere: a state chip is a hairline box with a 2px corner, the
   same shape as every other boundary in the workbench */
.pill{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:var(--r1);
font-size:var(--fs-xs);background:var(--layer-02);border:1px solid var(--border);color:var(--muted);white-space:nowrap}
.pill .ic{width:12px;height:12px}
.pill.ind{color:var(--warn);background:var(--warn-fill);border-color:var(--warn-dot)}
/* the failed/unbound arm of the same state vocabulary as ``.pill.ind``: ink for the
   label, the hue's own fill, a dot-tone border. Four call sites carried
   ``style="color:var(--bad)"`` inline, which left the chip with a neutral
   ``--layer-02`` background — half a state, so the eye could not group it with the
   warned chips it sits beside. */
.pill.bad{color:var(--bad);background:var(--bad-fill);border-color:var(--bad-dot)}
/* a solid layer, not an alpha tint: the ticket chip also sits inside selected
   rows, where a 10% accent wash over the selection fill disappears. The border
   keeps saturated ``--accent`` (a rule is a graphic: 3:1), the ink does not. */
.pill.tkt{color:var(--accent-text);background:var(--layer-01);border-color:var(--accent)}
/* buttons and fields share one padding so a .row of label + input + button
   lands on the same baseline without per-view nudging */
button,.btn{background:var(--accent);color:var(--accent-ink);border:1px solid transparent;
padding:8px 12px;border-radius:var(--r1);font-weight:600;cursor:pointer;font-size:var(--fs-sm);font-family:inherit;
transition:background-color var(--dur) var(--ease),border-color var(--dur) var(--ease),color var(--dur) var(--ease);
display:inline-flex;align-items:center;gap:6px;justify-content:center}
button:hover,.btn:hover{background:var(--accent-2)}
button:active,.btn:active{background:var(--accent-3)}
button.ghost,.btn.ghost{background:transparent;border-color:var(--border-ink);color:var(--fg)}
button.ghost:hover,.btn.ghost:hover{border-color:var(--fg);background:var(--layer-02)}
button:disabled{opacity:.4;cursor:not-allowed}
/* Eight call sites each carried their own inline ``font-size:.7rem``/``.72rem``/
   ``.75rem`` for the secondary action tucked under a heading or beside a row. That
   is a size fork, not a layout need: a small action is a *state of the button*, so
   it gets a class and lands on ``--fs-xs`` with on-grid padding. */
button.sm,.btn.sm{padding:var(--sp1) 9px;font-size:var(--fs-xs)}
/* Destructive is a state of the control, not a colour pinned to one call site.
   Ghost form keeps the hairline boundary (this is a workbench row action, not a
   modal CTA) and takes the same ``--bad`` ink the state chips use. */
button.danger,.btn.danger{color:var(--bad);border-color:var(--bad-dot)}
button.danger:hover,.btn.danger:hover{background:var(--bad-fill);border-color:var(--bad)}
.row{display:flex;gap:var(--sp2);align-items:center;margin-bottom:var(--sp2);flex-wrap:wrap}
.row label{min-width:90px;color:var(--muted);font-size:var(--fs-xs);flex:none}
.phases{display:flex;flex-direction:column;gap:var(--sp1)}
.phase{display:flex;align-items:center;gap:var(--sp2);padding:8px 12px;border-radius:var(--r1);
background:var(--layer-02);font-size:var(--fs-sm);border:1px solid transparent}
/* done rows keep ink, not opacity: a 55% group would drop the label under AA */
.phase.done{color:var(--muted)}
.phase.done .idx{background:var(--layer-03);color:var(--muted)}
/* current = the selection fill the rail uses, with a filled badge as the mark */
.phase.current{background:var(--layer-accent)}
.phase .idx{width:22px;height:22px;border-radius:var(--r0);background:var(--layer-03);
display:flex;align-items:center;justify-content:center;font-size:var(--fs-xs);font-family:var(--mono);flex:none}
.phase.current .idx{background:var(--accent);color:var(--accent-ink)}
.zone-tag{font-size:var(--fs-xs);color:var(--muted);margin-left:auto;font-family:var(--mono);letter-spacing:var(--track-label);flex:none}
.gate{padding:12px;border-radius:var(--r1);margin-bottom:var(--sp2);border:1px solid var(--border);background:var(--layer-01)}
.gate.fail{background:var(--bad-fill);border-color:var(--bad)}
.gate.pass{background:var(--good-fill)}
.gate .h{display:flex;justify-content:space-between;gap:var(--sp2);margin-bottom:var(--sp1);font-size:var(--fs-body)}
.gate ul{margin:var(--sp1) 0 0;padding-left:0;font-size:var(--fs-xs);color:var(--muted);list-style:none;display:flex;flex-direction:column;gap:var(--sp1)}
.gate li{display:flex;gap:var(--sp1);align-items:flex-start}
/* a neutral gate icon still carries meaning (it says "not blocked"), so it meets
   the same 3:1 graphic bar as its ``.bl``/``.wn`` siblings rather than ``--faint`` */
.gate li .ic{margin-top:2px;width:12px;height:12px;color:var(--muted)}
.gate li.bl .ic{color:var(--bad-dot)}
.gate li.wn .ic{color:var(--warn-dot)}
.steps{margin:var(--sp1) 0 0;padding-left:var(--sp3);display:flex;flex-direction:column;gap:var(--sp2);font-size:var(--fs-sm)}
.steps li::marker{color:var(--muted);font-family:var(--mono);font-size:var(--fs-xs)}
.steps .adv{color:var(--muted);font-size:var(--fs-xs);margin-top:2px}
.stack{display:flex;flex-direction:column;gap:var(--sp2)}
.w-full{width:100%}
/* Spacing utilities are named for the grid step, not for the pixel they used to
   spell. The old set was three names for two values: ``.mt2`` and ``.mt2`` were the
   same 8px, and ``.mt1`` was 4px written as an off-grid number. ``mt1``/``mt2`` are
   ``--sp1``/``--sp2`` read aloud, so a class can never drift from the ramp. */
.mt1{margin-top:var(--sp1)}.mt2{margin-top:var(--sp2)}
.gap1{gap:var(--sp1)}
.plan-group{display:flex;align-items:center;gap:var(--sp2);margin:var(--sp3) 0 2px;font-size:var(--fs-xs);font-weight:650;color:var(--muted)}
.plan-group:first-of-type{margin-top:var(--sp2)}
.plan-group .idx{width:20px;height:20px;border-radius:var(--r0);background:var(--layer-03);
display:flex;align-items:center;justify-content:center;font-size:var(--fs-xs);font-family:var(--mono);flex:none}
/* the group heading stays ink; blue belongs to the badge, so the current phase
   reads without a 12px accent label sitting under AA */
.plan-group.cur{color:var(--fg)}
.plan-group.cur .idx{background:var(--accent);color:var(--accent-ink)}
.plan-item{display:flex;gap:var(--sp2);align-items:flex-start;padding:8px;border-radius:var(--r1);transition:background-color var(--dur) var(--ease)}
.plan-item:hover{background:var(--layer-02)}
.plan-item input{margin-top:var(--sp1)}
.plan-item .t{font-size:var(--fs-sm)}
.plan-item.done .t{text-decoration:line-through;color:var(--muted)}
.plan-item .d{color:var(--muted);font-size:var(--fs-xs);margin-top:2px}
.diff{border:1px solid var(--border);border-radius:var(--r1);background:var(--layer-01);margin-top:var(--sp2);overflow:hidden}
.diff-h{display:flex;align-items:center;gap:var(--sp2);padding:8px 12px;background:var(--layer-02);border-bottom:1px solid var(--border);font-size:var(--fs-sm);font-weight:600}
.diff-b{padding:12px;display:flex;flex-direction:column;gap:var(--sp1)}
.diff-row{display:flex;gap:var(--sp2);font-size:var(--fs-sm);align-items:baseline;flex-wrap:wrap}
/* these micro-labels carry Chinese: mono/uppercase/tracking are no-ops for CJK,
   so size and tone carry the hierarchy instead (same call as .grp). */
.diff-row .k{flex:none;min-width:52px;color:var(--muted);font-size:var(--fs-xs)}
.diff-row .old{color:var(--muted)}
.diff-row .new{color:var(--fg);font-weight:600}
pre{background:var(--code);padding:var(--sp2);border-radius:var(--r1);overflow:auto;font-size:var(--fs-xs);border:1px solid var(--border);font-family:var(--mono)}
/* Hash and payload cells are machine strings, not prose inline code. The canonical
   ``code`` chip scales with its text (``max(.85em, --fs-xs)``), which is right in a
   sentence and wrong in a table row: a digest belongs to the row it is read in, so
   it pins the small step outright, and takes ``anywhere`` so a 64-char sha256 wraps
   rather than pushing the audit table sideways. */
code.digest{font-size:var(--fs-xs);overflow-wrap:anywhere}
.kpi-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--sp2)}
.kpi{background:var(--layer-01);border:1px solid var(--border);border-radius:var(--r1);padding:12px var(--sp3)}
.kpi .k{color:var(--muted);font-size:var(--fs-xs);font-weight:600}
/* the system's one large-text accent: ``--fs-num`` is 27px at 700, so 1.4.11's
   3:1 bar applies and the action blue clears it on every neutral layer. Do not
   copy this onto smaller text — see the ``--accent-text`` invariant in layout.py. */
.kpi .v{font-size:var(--fs-num);font-weight:700;margin-top:var(--sp1);line-height:1.15;font-variant-numeric:tabular-nums;color:var(--accent)}
/* Not every KPI value is a metric. A backend name or a collection id is text the
   operator reads, not a figure they scan, so it drops to the small step, loses the
   tabular numerals, and goes back to ``--fg``: ``--accent`` clears the 3:1 bar that
   ``--fs-num``/700 earns, but 14px text has to clear 4.5:1, which it does not. */
.kpi .v.txt{font-size:var(--fs-sm);line-height:1.5;font-weight:600;color:var(--fg)}
/* -- workbench: page head + master-detail --------------------------------- */
.wbh{display:flex;align-items:flex-end;justify-content:space-between;gap:var(--sp3);flex-wrap:wrap;
margin-bottom:var(--sp4);padding-bottom:var(--sp3);border-bottom:1px solid var(--border)}
/* zero tracking: these headings mix Chinese and Latin, and a negative em
   tightens the hanzi until they touch */
.wbh h1{margin:0;font-size:var(--fs-h2);font-weight:600;letter-spacing:0}
.wbh-sub{color:var(--muted);font-size:var(--fs-sm);margin:var(--sp1) 0 0}
.wbh-act{display:flex;align-items:center;gap:var(--sp2);flex-wrap:wrap}
/* page-head CTAs use the site .btn metrics; form/card buttons stay compact */
.wbh-act button,.wbh-act .btn{padding:8px var(--sp3);font-size:var(--fs-sm)}
.phasebar{display:flex;align-items:center;gap:var(--sp1);flex-wrap:wrap;margin:0 0 var(--sp3)}
.phasebar .lab{font-size:var(--fs-xs);font-weight:600;color:var(--muted);margin-right:2px}
.md{display:grid;grid-template-columns:minmax(280px,340px) minmax(0,1fr);gap:var(--sp3);align-items:start}
.md-list{position:sticky;top:var(--sp2);max-height:calc(100vh - var(--sp4));overflow-y:auto}
.md-head{display:flex;align-items:center;justify-content:space-between;gap:var(--sp2);margin-bottom:var(--sp2)}
.md-head h2{margin:0}
.md-head .n{font:600 var(--fs-xs)/1.5 var(--mono);color:var(--muted);letter-spacing:var(--track-label)}
.md-empty{color:var(--muted);font-size:var(--fs-xs);line-height:1.6;padding:2px 2px var(--sp1)}
.eng.sel{border-color:var(--border-ink);background:var(--layer-accent)}
.checklist{display:flex;flex-direction:column;margin:2px 0 0}
.chk{display:grid;grid-template-columns:24px minmax(0,1fr);gap:3px var(--sp3);padding:var(--sp3) 2px;border-bottom:1px solid var(--border)}
.chk:last-child{border-bottom:0;padding-bottom:var(--sp1)}
.chk .n{grid-row:span 2;width:24px;height:24px;border-radius:var(--r0);background:var(--accent);color:var(--accent-ink);
display:flex;align-items:center;justify-content:center;font:600 var(--fs-xs)/1 var(--mono)}
.chk .t{font-weight:600;font-size:var(--fs-body)}
.chk .d{color:var(--muted);font-size:var(--fs-sm);line-height:1.6}
.chk .d .btn,.chk .d button{margin-top:var(--sp2)}
.tabs{display:flex;gap:2px;margin-bottom:var(--sp3);border-bottom:1px solid var(--border);overflow-x:auto}
.tab{background:none;border:0;border-bottom:2px solid transparent;padding:8px 12px;cursor:pointer;color:var(--muted);font-size:var(--fs-sm);white-space:nowrap;transition:color var(--dur) var(--ease),border-color var(--dur) var(--ease);font-family:inherit;font-weight:500}
.tab:hover{color:var(--fg)}
/* ink label + blue rule: the underline is the indicator, so the text does not
   have to carry the state in a 14px accent that sits right on the AA line */
.tab.active{color:var(--fg);border-bottom-color:var(--accent);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:var(--fs-sm)}
th{font-size:var(--fs-xs);letter-spacing:0;color:var(--muted);text-align:left;padding:8px;border-bottom:1px solid var(--border-strong);font-weight:600}
td{padding:8px;border-bottom:1px solid var(--border);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
tbody tr{transition:background-color var(--dur) var(--ease)}
tbody tr:hover{background:var(--layer-02)}
.tablewrap{overflow-x:auto;margin:2px 0}
.hidden{display:none}
/* the empty state is the only thing a user reads on an empty panel, so it is
   ``--muted`` text, not ``--faint``. ``--faint`` survives as a *mark* role: the
   icon is decorative and carries it explicitly instead of inheriting the ink. */
.empty{color:var(--muted);text-align:center;padding:var(--sp5) var(--sp3);font-size:var(--fs-sm);display:flex;flex-direction:column;align-items:center;gap:var(--sp2)}
.empty .ic{width:18px;height:18px;color:var(--faint)}
details summary{cursor:pointer;color:var(--accent-text);font-size:var(--fs-sm);padding:var(--sp1) 0}
/* .dot / .d-ok / .d-warn / .d-bad and .hint are shared marks in COMPONENT_CSS:
   the /course lab table renders the same verdicts this panel does, and two
   definitions of one mark is how the console and the docs drifted apart. */
#toast-host{position:fixed;right:var(--sp3);bottom:var(--sp3);z-index:var(--z-toast);display:flex;flex-direction:column;gap:var(--sp2);align-items:flex-end}
/* fade only: a translating toast next to a sticky rail is the one place where
   motion fights the layout instead of explaining it */
.toast{display:flex;align-items:center;gap:var(--sp2);background:var(--layer-02);border:1px solid var(--border-strong);border-radius:var(--r2);padding:8px 12px;font-size:var(--fs-sm);max-width:min(420px,86vw);box-shadow:var(--elev);opacity:0;transition:opacity var(--dur) var(--ease)}
.toast.on{opacity:1}
.toast .ic{color:var(--accent)}
.toast.ok .ic{color:var(--good-dot)}
.toast.warn{border-color:var(--warn)}
.toast.warn .ic{color:var(--warn-dot)}
.toast.bad{border-color:var(--bad)}
.toast.bad .ic{color:var(--bad-dot)}
dialog{background:var(--layer-01);color:var(--fg);border:1px solid var(--border-strong);border-radius:var(--r2);padding:0;width:min(560px,92vw);box-shadow:var(--elev-lg)}
dialog::backdrop{background:color-mix(in oklab,var(--bg) 60%,transparent);backdrop-filter:blur(2px)}
.dlg-h{display:flex;align-items:center;gap:var(--sp2);padding:12px var(--sp3);border-bottom:1px solid var(--border);font-size:var(--fs-body);font-weight:600}
.dlg-b{padding:var(--sp3)}
@media(max-width:1100px){.md{grid-template-columns:1fr}.md-list{position:static;max-height:none}}
@media(max-width:640px){.main{padding:var(--sp3) var(--sp3) var(--sp4)}.kpi-grid{grid-template-columns:1fr}.wbh-act .btn,.wbh-act button{flex:1 1 auto}}
</style>
</head>
<body>
__ICON_SPRITE__
<div class="shell">
  <aside class="side">
    <div class="brand">
      <div class="logo">FDE <span>Scope</span></div>
      <span class="tag">Engagement Console</span>
    </div>
    <nav class="snav">
__SIDE_NAV__
    </nav>
    <div class="side-foot">
      <a class="lang" href="/en/console" title="English version" aria-label="Switch to English">EN</a>
      <button class="tbtn" onclick="toggleTheme()" aria-label="切换深浅主题" title="切换深浅主题">
        <svg class="ic when-dark"><use href="#i-sun"/></svg>
        <svg class="ic when-light"><use href="#i-moon"/></svg>
      </button>
    </div>
  </aside>
  <main class="main" id="main">
    <div id="view-workbench"></div>
    <div id="view-skills" class="hidden"></div>
    <div id="view-deploy" class="hidden"></div>
    <div id="view-ontology" class="hidden"></div>
    <div id="view-ops" class="hidden"></div>
  </main>
</div>

<script>
const API = '';
let current = null;

function icon(n){return '<svg class="ic" aria-hidden="true"><use href="#'+n+'"/></svg>'}
function dot(ok){return '<span class="dot '+(ok?'d-ok':'d-bad')+'"></span>'}
function yn(ok){return dot(ok)+(ok?'是':'否')}
/* A verdict is a mark plus a word, never a mark alone and never an emoji.
   ``✅❌⚠️🟢❔`` came over from the terminal port: a glyph from the emoji font sits
   outside the ramp (it cannot be re-tinted for dark mode), outside the type contract
   and outside the grid. ``mark()`` maps the SLA enum onto the same dots the /course
   lab table uses, so one vocabulary covers both surfaces; an unrecognised status
   falls through to the undecorated ``--faint`` dot, which reads as "no verdict yet"
   rather than inventing a colour for data we do not understand. */
const MARK={met:'d-ok',on_track:'d-ok',missed:'d-bad',at_risk:'d-warn',unknown:''};
function mark(st){return '<span class="dot '+(MARK[st]===undefined?'':MARK[st])+'"></span>'}

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
  ['workbench','skills','deploy','ontology'].forEach(v=>{
    const e=document.getElementById('view-'+v); if(e) e.classList.toggle('hidden', v!==name);
  });
  document.querySelectorAll('.navbtn').forEach(b=>b.classList.toggle('active', b.dataset.view===name));
}

function go(name) {
  showView(name);
  if (name==='skills') location.hash = 'skills';
  else if (name==='deploy') location.hash = 'deploy';
  else if (name==='ontology') location.hash = 'ontology';
  else if (name==='ops') location.hash = 'ops';
  else if (location.hash) history.replaceState(null,'',location.pathname);
  if (name==='workbench') loadWorkbench();
  if (name==='skills') loadSkills();
  if (name==='deploy') renderDeploy();
  if (name==='ontology') loadOntology();
  if (name==='ops') loadOps();
}

// -- 工作台 ---------------------------------------------------------------
let wbMatrix = [];
function wbFilteredMatrix() {
  const q = ((document.getElementById('wb-q')||{}).value||'').trim().toLowerCase();
  const ph = (document.getElementById('wb-phase')||{}).value||'';
  const zo = (document.getElementById('wb-zone')||{}).value||'';
  return wbMatrix.filter(s =>
    (!q || (s.customer||'').toLowerCase().includes(q) || (s.engagement_id||'').toLowerCase().includes(q))
    && (!ph || s.current_phase === ph) && (!zo || s.current_zone === zo));
}
function applyWbFilter() {
  const box = document.getElementById('wb-cards');
  if (box) box.innerHTML = engCardsHtml(wbFilteredMatrix());
}

async function loadWorkbench() {
  const w = await api('/api/workbench');
  const st = w.stats;
  const empty = !w.matrix.length;
  const phaseChips = Object.entries(st.phase_distribution).map(([p,n])=>
    `<span class="pill">${escapeHtml(p)}: ${n}</span>`).join('') || '<span class="meta">—</span>';
  const head = `<header class="wbh">
    <div><h1>工作台</h1><p class="wbh-sub">跨项目总览 · 阶段推进、门禁状态与最近沉淀</p></div>
    <div class="wbh-act">
      <a class="btn ghost" href="/reports/" target="_blank">${icon('i-folder')}报告归档</a>
      <button class="ghost" onclick="loadProfiles()">${icon('i-layers')}查看 Profiles &amp; Phases</button>
      <button onclick="focusCreate()">+ 新建 Engagement</button>
    </div></header>`;
  const strips = empty ? '' : `
    <div class="kpi-grid" style="margin-bottom:12px">
      <div class="kpi"><div class="k">进行中项目</div><div class="v">${st.active_projects}</div></div>
      <div class="kpi"><div class="k">技能总数</div><div class="v">${st.total_skills}</div></div>
      <div class="kpi"><div class="k">待审草稿</div><div class="v" style="color:${st.draft_skills?'var(--warn)':'var(--fg)'}">${st.draft_skills}</div></div>
    </div>
    <div class="phasebar"><span class="lab">阶段分布</span>${phaseChips}</div>`;
  wbMatrix = w.matrix;
  const sel = id => (document.getElementById(id)||{}).value||'';
  const prevQ = sel('wb-q'), prevPhase = sel('wb-phase'), prevZone = sel('wb-zone');
  const opt = (v, cur) => `<option value="${escapeHtml(v)}"${v===cur?' selected':''}>${escapeHtml(v)}</option>`;
  const phaseOpts = [...new Set(w.matrix.map(s=>s.current_phase))].sort().map(p=>opt(p, prevPhase)).join('');
  const zoneOpts = [...new Set(w.matrix.map(s=>s.current_zone))].sort().map(z=>opt(z, prevZone)).join('');
  const master = `<section class="md-list">
    <div class="md-head"><h2>Engagements</h2><span class="n">${w.matrix.length}</span></div>
    ${createBoxHtml(empty)}
    ${empty?'':`<div class="row">
      <input id="wb-q" value="${escapeHtml(prevQ)}" placeholder="搜索客户 / engagement id" oninput="applyWbFilter()">
      <label>阶段</label><select id="wb-phase" onchange="applyWbFilter()"><option value="">全部阶段</option>${phaseOpts}</select>
      <label>分区</label><select id="wb-zone" onchange="applyWbFilter()"><option value="">全部分区</option>${zoneOpts}</select>
    </div>`}
    <div id="wb-cards">${engCardsHtml(empty?w.matrix:wbFilteredMatrix())}</div>
  </section>`;
  const detail = empty ? gettingStartedHtml()
    : `<div class="card"><div class="empty">${icon('i-map')}选择左侧的 engagement，查看阶段、门禁与 KPI</div></div>`;
  const recent = empty ? ''
    : `<div class="card"><h2>最近沉淀 <button class="ghost sm" style="margin-left:var(--sp2)" onclick="go('skills')">去沉淀 →</button></h2>${recentHtml(w.recent_skills)}</div>`;
  document.getElementById('view-workbench').innerHTML =
    head + strips + `<div class="md">${master}<section id="md-detail">${detail}</section></div>` + recent;
  if (current && w.matrix.some(s=>s.engagement_id===current)) selectEng(current).catch(()=>{});
}

function createBoxHtml(openIt) {
  return `<details class="card" id="create-box"${openIt?' open':''}>
    <summary>+ 新建 Engagement</summary>
    <div class="row"><label>客户</label><input id="new-customer" placeholder="Aurora Motors"></div>
    <div class="row"><label>Profile</label>
      <select id="new-profile"><option value="ticket">ticket / 客服</option><option value="manufacturing">manufacturing / 制造业</option></select>
    </div>
    <button class="w-full" onclick="createEng()">+ 创建</button>
  </details>`;
}

function focusCreate() {
  const box = document.getElementById('create-box');
  const el = document.getElementById('new-customer');
  if (!box || !el) return;
  box.open = true;
  box.scrollIntoView({block:'nearest',behavior:'smooth'});
  el.focus({preventScroll:true});
}

function gettingStartedHtml() {
  return `<div class="card">
    <h2>三步跑通第一条 SOP</h2>
    <div class="checklist">
      <div class="chk"><span class="n">1</span><span class="t">创建第一个 Engagement</span>
        <div class="d">在左侧填写客户名，选择 profile（ticket 客服 / manufacturing 制造业）。
        <div><button class="ghost" onclick="focusCreate()">开始填写</button></div></div></div>
      <div class="chk"><span class="n">2</span><span class="t">推进 SOP 阶段，让门禁说话</span>
        <div class="d">18 个阶段、10 道门禁：每次推进都会重新校验当前阶段的 gate，通过才放行，force 推进也会留档。</div></div>
      <div class="chk"><span class="n">3</span><span class="t">沉淀第一条可复用技能</span>
        <div class="d">把现场经验写成技能草稿，评审通过后发布，进入技能库供下一个项目复用。
        <div><button class="ghost" onclick="go('skills')">去技能库</button></div></div></div>
    </div>
  </div>`;
}

function engCardsHtml(matrix) {
  if (!matrix.length) return '<div class="md-empty">还没有 engagement —— 用上面的表单创建第一条。</div>';
  return matrix.map(s => {
    const ts = Object.values(s.gate_records||{}).map(g=>g.checked_at).filter(Boolean).sort().pop() || '';
    // eid/customer travel as data-* attributes, never as inline-JS string
    // literals: a customer name with a quote would otherwise break the handler.
    return `<div class="card eng${current===s.engagement_id?' sel':''}" data-eid="${escapeHtml(s.engagement_id)}" data-customer="${escapeHtml(s.customer)}" onclick="selectEng(this.dataset.eid)">
      <div class="id">${escapeHtml(s.customer)}</div>
      <div class="meta"><span class="pill ${s.profile==='manufacturing'?'ind':'tkt'}">${escapeHtml(s.profile)}</span>
        ${s.gate?escapeHtml(s.gate)+' '+dot(s.gate_passed):'—'}</div>
      <div class="meta">${zoneLabel(escapeHtml(s.current_zone))} · ${escapeHtml(s.current_phase)}${s.is_complete?' · '+dot(true)+' 完成':''}</div>
      <div class="meta">${ts?escapeHtml(String(ts).slice(0,16).replace('T',' ')):'—'}</div>
      <div class="row" style="margin-top:6px">
        <button class="ghost sm" onclick="event.stopPropagation();askArchiveEng(this)">归档</button>
        <button class="ghost sm danger" onclick="event.stopPropagation();askDeleteEng(this)">删除</button>
      </div>
    </div>`;
  }).join('');
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
  const tag = (document.getElementById('sk-tag')||{}).value || '';
  const prof = (document.getElementById('sk-profile')||{}).value || '';
  const gate = (document.getElementById('sk-gate')||{}).value || '';
  const phase = (document.getElementById('sk-phase')||{}).value || '';
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (cat) params.set('category', cat);
  if (st) params.set('status', st);
  if (tag) params.set('tag', tag);
  if (prof) params.set('profile', prof);
  if (gate) params.set('gate', gate);
  if (phase) params.set('phase', phase);
  const [list, facets, drafts] = await Promise.all([
    api('/api/skills?' + params),
    api('/api/skills/facets'),
    api('/api/skills/drafts'),
  ]);
  const opts = (vals, cur) => ['<option value="">全部</option>']
    .concat(vals.map(v=>`<option value="${escapeHtml(v)}"${v===cur?' selected':''}>${escapeHtml(v)}</option>`)).join('');
  document.getElementById('view-skills').innerHTML = `
    <div class="card"><h2>技能库</h2>
      <div class="row"><label>搜索</label><input id="sk-q" value="${escapeHtml(q)}" placeholder="标题 / 正文关键词" onkeydown="if(event.key==='Enter')loadSkills()"></div>
      <div class="row"><label>分类</label><select id="sk-cat" onchange="loadSkills()">
        <option value="">全部</option>
        <option value="research">research</option><option value="implementation">implementation</option>
        <option value="optimization">optimization</option><option value="methodology">methodology</option></select>
        <label>状态</label><select id="sk-status" onchange="loadSkills()">
        <option value="published">published</option><option value="draft">draft</option><option value="archived">archived</option></select></div>
      <div class="row"><label>标签</label><select id="sk-tag" onchange="loadSkills()">${opts(facets.tags||[], tag)}</select>
        <label>适用画像</label><select id="sk-profile" onchange="loadSkills()">${opts(facets.profiles||[], prof)}</select></div>
      <div class="row"><label>门禁</label><select id="sk-gate" onchange="loadSkills()">${opts(facets.gates||[], gate)}</select>
        <label>阶段</label><select id="sk-phase" onchange="loadSkills()">${opts(facets.phases||[], phase)}</select></div>
      ${list.map(skillCard).join('') || '<div class="empty">无匹配技能</div>'}
    </div>
    <div class="card"><h2>草稿审阅队列</h2>${draftCards(drafts)}</div>
    <div class="card"><h2>新建技能</h2>
      <div class="row"><label>标题</label><input id="sk-title" placeholder="如：OPC UA 连接踩坑"></div>
      <div class="row"><label>分类</label><select id="sk-new-cat">
        <option value="research">research 调研</option><option value="implementation" selected>implementation 实施</option>
        <option value="optimization">optimization 调优</option><option value="methodology">methodology 方法论</option></select></div>
      <div class="row"><label>标签</label><input id="sk-tags" placeholder="逗号分隔：opcua,plc"></div>
      <div class="row"><label>正文</label><textarea id="sk-body" rows="4"></textarea></div>
      <button onclick="submitSkill()">+ 沉淀技能</button>
    </div>`;
}

function skillCard(r) {
  const esc = escapeHtml;
  const act = r.status==='draft'
    ? `<button onclick="publishSkill('${esc(r.id)}')">发布</button> <button class="ghost" onclick="editSkill('${esc(r.id)}')">编辑</button>`
    : r.status==='published'
      ? `<button class="ghost" onclick="archiveSkill('${esc(r.id)}')">归档</button>` : '';
  const body = (r.body_md||'').trim();
  const preview = body ? `<div style="margin:var(--sp1) 0 0;font-size:var(--fs-sm);line-height:1.5;color:var(--fg);white-space:pre-wrap">${esc(body.length>200?body.slice(0,200)+'…':body)}</div>` : '';
  const meta = [
    r.phase_slug?'phase: '+esc(r.phase_slug):'',
    r.gate_slug?'gate: '+esc(r.gate_slug):'',
    (r.applies_to||[]).length?'适用: '+r.applies_to.map(a=>esc(a)).join(', '):'',
    (r.export_formats||[]).length?'导出: '+r.export_formats.map(f=>esc(f)).join(', '):'',
  ].filter(Boolean).join(' · ');
  const origin = (r.source&&r.source!=='manual')?` · 来源 ${esc(r.source)}`:'';
  return `<div class="card">
    <div class="row"><b>${esc(r.title)}</b>
      <span class="pill">${esc(r.category)}</span>
      <span class="pill ${r.status==='draft'?'ind':''}">${esc(r.status)}</span>
      <span class="meta" style="margin-left:auto">v${r.version||1} · ${esc(String(r.updated_at||'').slice(0,16).replace('T',' '))}</span></div>
    ${(r.tags||[]).length?`<div class="meta">${r.tags.map(t=>'#'+esc(t)).join(' ')}</div>`:''}
    ${preview}
    <div class="meta" style="margin-top:6px">${esc(r.id)} · 创建于 ${esc(String(r.created_at||'').slice(0,16).replace('T',' '))}${origin}${r.source_engagement?' · 来自 '+esc(r.source_engagement):''}</div>
    ${meta?`<div class="meta">${meta}</div>`:''}
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
  const kinds = entries.reduce((m,e)=>{m[e.kind]=(m[e.kind]||0)+1;return m;},{});
  const linked = entries.filter(e=>e.skill_id).length;
  const stats = entries.length ? `<div class="kpi-grid" style="margin-bottom:10px">
    <div class="kpi"><div class="k">总条数</div><div class="v">${entries.length}</div></div>
    <div class="kpi"><div class="k">调研</div><div class="v">${kinds.research||0}</div></div>
    <div class="kpi"><div class="k">实施</div><div class="v">${kinds.implementation||0}</div></div>
    <div class="kpi"><div class="k">调优</div><div class="v">${kinds.optimization||0}</div></div>
    <div class="kpi"><div class="k">已沉淀技能</div><div class="v">${linked}</div></div>
  </div>` : '';
  const rows = entries.map(e => `<div class="card">
    <div class="row"><span class="pill">${esc(e.kind)}</span><span class="meta">${esc(e.ts)}</span>
      <span class="meta" style="margin-left:auto">${e.skill_id?icon('i-bulb')+' '+esc(e.skill_id):''}</span></div>
    <div>${esc(e.note)}</div>
    ${e.skill_id?'':`<button class="ghost sm" style="margin-top:var(--sp1)" onclick="journalToSkill('${esc(e.id)}')">沉淀为技能</button>`}
  </div>`).join('') || '<div class="empty">暂无现场记录</div>';
  return `<div class="card"><h2>现场记录</h2>${stats}${rows}</div>
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
    <div class="card"><h2>注意事项</h2><ul class="note-list">
      <li><b style="color:var(--fg)">数据源优先级</b>：Agent 级 <code>toolkit.sources</code> → tenant <code>sources</code> → 隐式字段（ticket 下 <code>ticket_api</code> 隐式喂 zammad/salesforce）。三处都没配的工具诚实标注 <span class="pill bad">unbound</span>，不进 Toolkit、不假装可用。</li>
      <li><b style="color:var(--fg)">审批模式决定未匹配工具的命运</b>：绑定工具自动获得 ALLOW 规则；conservative / balanced 未匹配 → ASK（HITL 人工确认），autonomous → DENY。默认 deny 恒含 access_other_tenant / delete_any / exec_shell。</li>
      <li><b style="color:var(--fg)">skills_dirs 必须真实存在</b>（含 SKILL.md 的目录），技能经 <code>Toolkit(skills_or_loaders=…)</code> 注册，路径错误装配期即报。</li>
      <li><b style="color:var(--fg)">凭据只走环境变量</b>（<code>FDE_SCOPE_MIMO_API_KEY</code> 等）——不进 manifest / tenant_config / 报告。</li>
      <li><b style="color:var(--fg)">连接器 sample 每调用最多 50 行</b>（MAX_TOOL_ROWS），是预览不是导出通道。</li>
      <li><b style="color:var(--fg)">装配 ≠ 服务</b>：<code>deploy --serve</code> 需 <code>.[agentscope]</code> extra + Redis + 可达模型；2.0 无 <code>Agent.stop</code>，停服用 <code>TenantDeployer.stop()</code>。</li>
    </ul></div>`;
  deployInit = true;
}

async function runDeployPlan() {
  const val = id => (document.getElementById(id)||{}).value || '';
  const out = document.getElementById('dp-result');
  out.innerHTML = '<div class="empty">计算中…</div>';
  try {
    // server-side parse: every dropped line comes back with a line number and
    // a reason, instead of vanishing silently like the old JS parser
    const parsed = await api('/api/deploy/parse', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agents_text: val('dp-agents'), sources_text: val('dp-sources')})});
    if ((parsed.errors||[]).length) {
      const rows = parsed.errors.map(e=>`<tr><td class="meta">${e.field}</td><td class="meta">${e.line}</td>
        <td><code>${escapeHtml(e.text)}</code></td><td class="meta">${escapeHtml(e.reason)}</td></tr>`).join('');
      out.innerHTML = `<div class="gate fail"><b>输入格式有误（${parsed.errors.length} 行）</b>
        <div class="tablewrap mt2"><table>
        <thead><tr><th>字段</th><th>行号</th><th>原始行</th><th>原因</th></tr></thead>
        <tbody>${rows}</tbody></table></div></div>`;
      return;
    }
    const plan = await api('/api/deploy/plan', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        tenant: val('dp-tenant').trim() || 'acme',
        profile: val('dp-profile'),
        approval_mode: val('dp-mode'),
        model: val('dp-model').trim() || 'qwen-max',
        agents: parsed.agents,
        sources: parsed.sources,
      })});
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
      : `<span class="pill bad" title="${esc(t.note||'')}">${esc(t.tool)} ${icon('i-x')} unbound</span>`).join(' ');
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
      <div class="kpi"><div class="k">Sandbox / Collection</div><div class="v txt">${esc(m.sandbox&&m.sandbox.backend)} · ${esc(m.corpus_collection)}</div></div>
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

async function createEng() {
  const customer = document.getElementById('new-customer').value.trim();
  if (!customer) return toast('请填写客户名','warn');
  const profile = document.getElementById('new-profile').value;
  const created = await api('/api/engagements', {method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({customer, profile})});
  document.getElementById('new-customer').value = '';
  toast('已创建 engagement','ok');
  await loadWorkbench();
  selectEng(created.engagement_id);
}

async function selectEng(eid) {
  current = eid;
  document.querySelectorAll('.eng').forEach(el=>el.classList.toggle('sel', el.dataset.eid===eid));
  const s = await api(`/api/engagements/${eid}`);
  const phases = await api(`/api/phases?profile=${s.profile}`);
  const gates = await api(`/api/engagements/${eid}/gates`);
  let guided = null;
  try { guided = await api(`/api/engagements/${eid}/guided`); } catch(e) {}
  renderDetail(s, phases, gates, guided);
}

function zoneLabel(z){return {pre_engagement:'A·Pre',build:'B·Build',operationalization:'C·Ops',handoff:'D·Handoff'}[z]||z}

function renderDetail(s, phases, gates, guided) {
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
    // the guided endpoint already computes per-gate next_steps (issue + advice);
    // reusing it keeps one source of truth for "what to do next"
    const steps = ((((guided||{}).gates||{})[slug]||{}).next_steps)||[];
    const stepsHtml = steps.map((st,i)=>`<li value="${i+1}"><b>${escapeHtml(st.issue)}</b><div class="adv">${escapeHtml(st.advice)}</div></li>`).join('');
    return `<div class="gate ${cls}"><div class="h"><b>${escapeHtml(g.name)}</b>
      <span>${g.passed?dot(true)+' PASS':dot(false)+' BLOCKED'}</span></div>
      ${blocks?`<ul>${blocks}</ul>`:''}${warns?`<ul>${warns}</ul>`:''}
      ${stepsHtml?`<div class="hint">下一步做什么</div><ol class="steps">${stepsHtml}</ol>`:''}
      <button class="ghost sm" style="margin-top:var(--sp1)" onclick="recheck('${escapeHtml(slug)}')">重新校验</button></div>`;
  }).join('') || '<div class="empty">无适用 gate（当前 profile）</div>';

  const recs = Object.entries(s.gate_records||{});
  const ledgerHtml = recs.length?`<div class="card"><h2>Gate 台账（历次校验记录）</h2><div class="tablewrap"><table>
    <thead><tr><th>Gate</th><th>结果</th><th>阻塞项</th><th>警告</th><th>备注</th><th>校验时间</th></tr></thead>
    <tbody>${recs.map(([slug,r])=>{
      const rblocks = (r.blockers||[]).map(b=>`<li class="bl">${icon('i-ban')} ${escapeHtml(b)}</li>`).join('');
      const rwarns = (r.warnings||[]).map(w=>`<li class="wn">${icon('i-alert')} ${escapeHtml(w)}</li>`).join('');
      return `<tr>
      <td><b>${escapeHtml(slug)}</b></td>
      <td>${r.passed?dot(true)+' PASS':dot(false)+' BLOCKED'}</td>
      <td>${rblocks?`<ul style="margin:0">${rblocks}</ul>`:'—'}</td>
      <td>${rwarns?`<ul style="margin:0">${rwarns}</ul>`:'—'}</td>
      <td>${escapeHtml(r.notes||'—')}</td>
      <td class="meta">${escapeHtml(r.checked_at||'')}</td>
    </tr>`;}).join('')}</tbody></table></div></div>`:'';

  const html = `
    <div class="tabs" role="tablist">
      <button class="tab active" role="tab" data-tab="overview" aria-selected="true" onclick="tab('overview',this)">概览</button>
      <button class="tab" role="tab" data-tab="guided" aria-selected="false" onclick="tab('guided',this)">引导</button>
      <button class="tab" role="tab" data-tab="sop" aria-selected="false" onclick="tab('sop',this)">SOP 阶段</button>
      <button class="tab" role="tab" data-tab="gates" aria-selected="false" onclick="tab('gates',this)">Gates</button>
      <button class="tab" role="tab" data-tab="context" aria-selected="false" onclick="tab('context',this)">Context</button>
      <button class="tab" role="tab" data-tab="forge" aria-selected="false" onclick="tab('forge',this)">Corpus Forge</button>
      <button class="tab" role="tab" data-tab="kpi" aria-selected="false" onclick="tab('kpi',this)">KPI</button>
      <button class="tab" role="tab" data-tab="journal" aria-selected="false" onclick="tab('journal',this)">现场记录</button>
      <button class="tab" role="tab" data-tab="evidence" aria-selected="false" onclick="tab('evidence',this)">证据</button>
      <button class="tab" role="tab" data-tab="handoff" aria-selected="false" onclick="tab('handoff',this)">交接</button>
      <button class="tab" role="tab" data-tab="audit" aria-selected="false" onclick="tab('audit',this)">审计</button>
      <button class="tab" role="tab" data-tab="retro" aria-selected="false" onclick="tab('retro',this)">复盘</button>
    </div>
    <div id="t-overview">
      <div class="card">
        <h2>Engagement</h2>
        <div class="row"><label>客户</label><b>${escapeHtml(s.customer)}</b></div>
        <div class="row"><label>Profile</label><span class="pill ${s.profile==='manufacturing'?'ind':'tkt'}">${escapeHtml(s.profile)}</span></div>
        <div class="row"><label>当前阶段</label><b style="color:var(--accent-text)">${escapeHtml(s.current_phase)}</b> (${escapeHtml(zoneLabel(s.current_zone))})</div>
        <div class="row"><label>下一阶段</label>${escapeHtml(s.next_phase||'— (完成)')}</div>
        <div class="row"><label>进度</label>${curIdx+1}/${phases.phases.length}</div>
        <div class="row" style="margin-top:10px">
          <button onclick="advance(false)">${icon('i-next')} 推进到下一阶段</button>
          <button class="ghost" onclick="askAdvanceForce()">force 推进</button>
          <button class="ghost" onclick="askRollback()">${icon('i-refresh')} 回滚阶段</button>
        </div>
      </div>
      <div class="card">
        <h2>数据面板</h2>
        <div class="kpi-grid">
          <div class="kpi"><div class="k">现场记录</div><div class="v">${((s.context||{}).journal||[]).length}</div></div>
          <div class="kpi"><div class="k">干系人</div><div class="v">${((s.context||{}).stakeholders||[]).length}</div></div>
          <div class="kpi"><div class="k">SLO</div><div class="v">${((s.context||{}).slos||[]).length}</div></div>
          <div class="kpi"><div class="k">成功标准</div><div class="v">${((s.context||{}).success_criteria||[]).length}</div></div>
          <div class="kpi"><div class="k">Gates 通过</div><div class="v">${Object.values(gates).filter(g=>g.passed).length}/${Object.values(gates).length}</div></div>
        </div>
      </div>
      <div class="card">
        <h2>只读分享</h2>
        <div class="meta" style="margin-bottom:10px">给干系人一条只读链接：进度 + SLA + 门禁现况 + 客户签收（签收是审计证据，不推进状态机）。token 只显示一次，落盘的是 sha256。</div>
        <div class="row"><span id="share-state" class="meta"></span></div>
        <div class="row" style="margin-top:10px">
          <button onclick="createShare()">生成链接</button>
          <button class="ghost" onclick="revokeShare()">吊销链接</button>
        </div>
        <div id="share-out" class="hint mt1"></div>
      </div>
    </div>
    <div id="t-guided" class="hidden">${guidedHtml(guided, phases)}</div>
    <div id="t-sop" class="hidden"><div class="card"><div class="phases">${phaseHtml}</div>
      <div class="row" style="margin-top:10px"><a class="btn ghost" href="/sop" target="_blank">${icon('i-book')} 阅读 SOP 全文（含 18 阶段详解）</a></div></div></div>
    <div id="t-gates" class="hidden">${ledgerHtml}${gateHtml}</div>
    <div id="t-context" class="hidden">${contextHtml(s.context)}</div>
    <div id="t-forge" class="hidden"><div class="card">
      <h2>语料锻造（CSV → CorpusReport）</h2>
      <input type="file" id="forge-file" accept=".csv">
      <div class="row mt2"><label>min_samples</label><input id="forge-min" value="5" type="number"></div>
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
    <div id="t-evidence" class="hidden"></div>
    <div id="t-handoff" class="hidden"></div>
    <div id="t-audit" class="hidden"></div>
    <div id="t-retro" class="hidden"></div>
  `;
  document.getElementById('md-detail').innerHTML = html;
  detailStatus = s;
  detailPhases = phases.phases;
  loadShare();
  // a #t:<name> hash survives reloads and post-action refreshes, so the reader
  // lands back on the pane they were reading instead of always on Overview
  const m = /^#t:([a-z]+)$/.exec(location.hash || '');
  if (m && DETAIL_TABS.includes(m[1]) && m[1] !== 'overview') tab(m[1]);
}

const DETAIL_TABS = ['overview','guided','sop','gates','context','forge','kpi','journal','evidence','handoff','audit','retro'];
// panes that fetch only when opened, so selectEng stays at its 3 blocking calls
const LAZY_TABS = {evidence: loadEvidence, handoff: renderHandoff, audit: loadAudit, retro: loadRetro};
let detailStatus = null;
let detailPhases = [];

function tab(name, el) {
  el = el || document.querySelector(`.tab[data-tab="${name}"]`);
  if (!el) return;
  DETAIL_TABS.forEach(t=>{
    const e=document.getElementById('t-'+t); if(e) e.classList.toggle('hidden', t!==name);
  });
  document.querySelectorAll('.tab').forEach(t=>{
    t.classList.remove('active');
    t.setAttribute('aria-selected','false');
  });
  el.classList.add('active');
  el.setAttribute('aria-selected','true');
  // replaceState, not location.hash: assigning the hash fires hashchange, which
  // the router at the bottom reads as a top-level view switch.
  history.replaceState(null, '', '#t:'+name);
  const lazy = LAZY_TABS[name];
  if (lazy) lazy();
}

function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

const CONTEXT_EDITABLE_KEYS = ['site','safety','success_criteria','stakeholders','slos','assets'];

function contextEditorHtml(ctx) {
  if (!ctx) return '';
  const editable = {};
  CONTEXT_EDITABLE_KEYS.forEach(k=>{ if (ctx[k] !== undefined) editable[k] = ctx[k]; });
  return `<details class="mt2"><summary>编辑上下文（JSON · 保存后门禁重评）</summary>
    <textarea id="ctx-json" rows="12" class="mono" style="margin-top:var(--sp2)">${escapeHtml(JSON.stringify(editable, null, 2))}</textarea>
    <div class="row mt2"><button onclick="saveContextJson()">保存并重评门禁</button>
      <span class="hint">可编辑键：site / safety / success_criteria / stakeholders / slos / assets；后端做字段级校验，错误带字段路径。</span></div>
    <div id="ctx-err" class="mt1"></div></details>`;
}

async function saveContextJson() {
  const errBox = document.getElementById('ctx-err');
  errBox.innerHTML = '';
  let parsed;
  try { parsed = JSON.parse(document.getElementById('ctx-json').value); }
  catch(e){ errBox.innerHTML = `<div class="gate fail">JSON 解析失败：${escapeHtml(e.message)}</div>`; return; }
  const patch = {};
  CONTEXT_EDITABLE_KEYS.forEach(k=>{ if (k in parsed) patch[k] = parsed[k]; });
  if (!Object.keys(patch).length) {
    errBox.innerHTML = '<div class="gate fail">没有可保存的字段（仅 site / safety / success_criteria / stakeholders / slos / assets）</div>';
    return;
  }
  try {
    await api(`/api/engagements/${current}/context`, {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(patch)});
    toast('已保存，门禁已重评','ok');
    selectEng(current);
  } catch(e) {
    // 422 detail is pydantic's errors(): render each with its field path
    let rows = '';
    try {
      const d = JSON.parse(e.message);
      if (Array.isArray(d.detail))
        rows = d.detail.map(x=>`<div>· <code>${escapeHtml((x.loc||[]).join('.'))}</code> — ${escapeHtml(x.msg||'')}</div>`).join('');
    } catch(_){ /* not a pydantic body */ }
    errBox.innerHTML = `<div class="gate fail"><b>字段校验失败</b>${rows ? `<div class="mt1">${rows}</div>` : `<div class="mt1 meta">${escapeHtml(String(e.message).slice(0,300))}</div>`}</div>`;
  }
}

function contextHtml(ctx) {
  if (!ctx) return '<div class="empty">无 context 数据</div>';
  const esc = escapeHtml;
  const site = ctx.site||{}, safety = ctx.safety||{}, assets = ctx.assets||{};
  // 现场 / Site
  let siteHtml;
  if (site.location) {
    const net = (site.networks||[]).map(n=>`<li>${esc(n)}</li>`).join('');
    const assetRows = (site.assets||[]).map(a=>`<tr>
      <td>${esc(a.name)}</td><td>${esc(a.type||'—')}</td><td>${esc(a.vendor||'—')}</td>
      <td><code>${esc(a.protocol||'—')}</code></td>
      <td><span class="pill ${a.criticality==='high'?'ind':''}">${esc(a.criticality||'—')}</span></td></tr>`).join('');
    siteHtml = `<div class="row"><label>地点</label><b>${esc(site.location)}</b></div>
      <div class="row"><label>班次</label>${esc(site.shift_count)} · OT/IT 隔离 ${yn(site.ot_it_separated)} · 气隙 ${yn(site.air_gapped)}</div>
      ${net?`<div class="row"><label>网络</label><ul class="note-list" style="margin:var(--sp1) 0 0">${net}</ul></div>`:''}
      <div class="row"><label>资产</label>${(site.assets||[]).length} 项 · 工会代表 ${site.works_council_represented?yn(true):'—'}</div>
      ${assetRows?`<div class="tablewrap" style="margin:4px 0 0"><table><thead><tr><th>资产</th><th>类型</th><th>厂商</th><th>协议</th><th>关键度</th></tr></thead><tbody>${assetRows}</tbody></table></div>`:''}
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
  const sloRows = (ctx.slos||[]).map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.target)}</td><td>${esc(x.error_budget||'—')}</td><td>${esc(x.alert_route||'—')}</td><td>${esc(x.window)}</td></tr>`).join('')
    || '<tr><td colspan="5" class="meta">未定义 SLO</td></tr>';
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
  const monOn = mon.data_drift||mon.quality_drift||mon.feedback_latency||(mon.dashboards||[]).length;
  const monRows = monOn ? `
      <div class="row"><label>数据漂移</label>${mon.data_drift&&mon.data_drift.enabled?dot(true)+' 启用 · 节奏 '+esc(mon.data_drift.cadence||'每日')+(mon.data_drift.threshold?' · 阈值 '+esc(mon.data_drift.threshold):''):dot(false)+' 未启用'}</div>
      <div class="row"><label>质量漂移</label>${mon.quality_drift&&mon.quality_drift.enabled?dot(true)+' 启用 · 节奏 '+esc(mon.quality_drift.cadence||'每周')+(mon.quality_drift.threshold?' · 阈值 '+esc(mon.quality_drift.threshold):''):dot(false)+' 未启用'}</div>
      ${mon.feedback_latency&&mon.feedback_latency.target_hours?`<div class="row"><label>反馈时延</label>目标 ${esc(mon.feedback_latency.target_hours)}h 内闭环</div>`:''}
      ${(mon.dashboards||[]).length?`<div class="row"><label>看板</label>${mon.dashboards.map(d=>`<a href="${esc(d.url||'#')}" target="_blank">${esc(d.name||d.url||'看板')}</a>`).join(' · ')}</div>`:''}` : '';
  return `${contextEditorHtml(ctx)}<div class="card"><h2>现场 / Site</h2>${siteHtml}</div>
    <div class="card"><h2>干系人</h2><div class="tablewrap"><table><thead><tr><th>姓名</th><th>角色</th><th>Sponsor</th><th>成功指标</th></tr></thead><tbody>${stkRows||'<tr><td colspan="4" class="meta">未记录</td></tr>'}</tbody></table></div></div>
    <div class="card"><h2>成功标准</h2><ul class="note-list">${crit}</ul></div>
    <div class="card"><h2>SLO</h2><div class="tablewrap"><table><thead><tr><th>名称</th><th>目标</th><th>错误预算</th><th>告警路由</th><th>窗口</th></tr></thead><tbody>${sloRows}</tbody></table></div></div>
    <div class="card"><h2>功能安全</h2><div class="tablewrap"><table><tbody>${safetyHtml}</tbody></table></div></div>
    <div class="card"><h2>产物与交付</h2>
      <div class="row"><label>语料</label>${esc(assets.corpus_summary||'—')}</div>
      <div class="row"><label>模型</label>${esc(assets.model_name||'—')}</div>
      ${evRows?`<div class="tablewrap mt2"><table><thead><tr><th>评估指标</th><th>值</th></tr></thead><tbody>${evRows}</tbody></table></div>`:''}
      <div class="row" style="margin-top:10px">${links.join(' ')||'—'}</div>
      ${known?`<div class="row"><label>已知局限</label><ul class="note-list">${known}</ul></div>`:''}
      ${monRows}
    </div>`;
}

let gdDraftRes = null;
let gdPhaseNames = {};
let gdPhaseIdx = {};
let gdCurSlug = '';
let gdPlanData = null;
let gdSaveTimer = null;

function guidedHtml(g, phases) {
  if (!g) return '<div class="empty">' + icon('i-alert') + '引导数据不可用<div class="hint">可能是接口瞬时失败，重新进入该 engagement 详情会重试。</div></div>';
  const esc = escapeHtml;
  const p = g.phase||{};
  gdPhaseNames = {}; gdPhaseIdx = {};
  (phases&&phases.phases||[]).forEach(x=>{gdPhaseNames[x.slug]=x.name; gdPhaseIdx[x.slug]=x.index;});
  gdCurSlug = p.slug||'';
  const deliv = (g.deliverables||[]).map(d=>`<li>${esc(d)}</li>`).join('')||'<li class="hint">—</li>';
  const gatesHtml = Object.entries(g.gates||{}).map(([slug,gt])=>{
    const steps = (gt.next_steps||[]).map((st,i)=>`<li value="${i+1}"><b>${esc(st.issue)}</b><div class="adv">${esc(st.advice)}</div></li>`).join('');
    return `<div class="gate ${gt.passed?'pass':'fail'}"><div class="h"><b>${esc(gt.name)}</b>
      <span>${gt.passed?dot(true)+' PASS':dot(false)+' BLOCKED'}</span></div>
      ${steps?`<div class="hint">下一步做什么</div><ol class="steps">${steps}</ol>`
        :(gt.passed?'<div class="hint">门禁已通过，可推进下一阶段。</div>':'')}
    </div>`;
  }).join('') || '<div class="empty">本阶段无门禁——完成产出清单后即可推进</div>';
  const isEn = document.documentElement.lang==='en';
  const pages = (g.catalog_pages||[]).map(pg=>{
    const url = (isEn && pg.url_en) ? pg.url_en : pg.url;
    return `<a class="btn ghost" href="${esc(url)}">${icon('i-book')} ${esc(pg.title)}</a>`;
  }).join(' ');
  const aiBtn = g.llm_available ? '✨ AI 起草' : '✍️ 手动填写指引';
  const aiNote = g.llm_available
    ? '用自然语言描述业务，AI 起草 现场/干系人/成功标准/SLO 草稿。写入前逐项确认，门禁通过才算数。'
    : '未配置 AI key（FDE_SCOPE_MIMO_API_KEY），可打开手动填写指引，按字段说明逐项录入。';
  return `
    ${gdGoalCard(g)}
    <div class="card"><h2>当前阶段：${esc(p.name||'')} <span class="pill">${esc(p.progress||'')}</span></h2>
      <div class="row"><label>Zone</label>${esc(zoneLabel(p.zone))}</div>
      <p class="hint mt1">${esc(p.description||'')}</p></div>
    <div class="card"><h2>本阶段要产出什么</h2><ul class="note-list">${deliv}</ul>
      <div class="hint mt2">产出写入 Context / assets 后，门禁会自动重评——引导不代替验收。</div></div>
    ${gatesHtml}
    <div class="card"><h2>AI 起草 Context</h2>
      <div class="hint">${esc(aiNote)}</div>
      <textarea id="gd-desc" rows="3" class="mt2" placeholder="例：我们是一家茶饮连锁，国内 2000 家门店，客服团队每天处理大量加盟咨询与客诉，希望用工单 AI 缩短首响时间…">${escapeHtml(window.gdLastDesc||'')}</textarea>
      <div class="row mt2"><button onclick="gdDraftCtx()">${aiBtn}</button></div>
      <div id="gd-out" class="mt2"></div></div>
    <div class="card"><h2>相关阅读（技能手册库）</h2><div class="row gap1">${pages||'<span class="hint">—</span>'}</div></div>`;
}

function gdGoalCard(g) {
  const plan = g.plan;
  let inner;
  if (plan && Array.isArray(plan.items)) {
    inner = gdPlanHtml(plan);
  } else {
    inner = `<div class="row"><input id="gd-goal" placeholder="输入项目目标（例：把客服首响缩到 8s 内，坏例率降到 5% 以下）">
      <button onclick="gdPlan()">生成任务清单</button></div>
      <div class="hint">目标会被拆解到 SOP 各阶段，勾选状态自动保存。${g.llm_available?'':'（规则版：未配置 AI key）'}</div>`;
  }
  return `<div class="card"><h2>项目目标与任务清单</h2>${inner}</div>`;
}

function gdPlanHtml(plan) {
  const esc = escapeHtml;
  gdPlanData = plan;
  let html = `<div class="row"><label>目标</label><b>${esc(plan.goal||'')}</b>
    <span class="pill">${plan.used_llm?'AI 生成':'规则生成'}</span>
    <button class="ghost" onclick="gdReplan()">重新生成</button></div>`;
  let lastSlug = null;
  (plan.items||[]).forEach(it=>{
    if (it.phase_slug!==lastSlug) {
      lastSlug = it.phase_slug;
      const isCur = it.phase_slug===gdCurSlug;
      html += `<div class="plan-group${isCur?' cur':''}"><span class="idx">${gdPhaseIdx[it.phase_slug]||''}</span>${esc(gdPhaseNames[it.phase_slug]||it.phase_slug)}${isCur?'<span class="pill">当前阶段</span>':''}</div>`;
    }
    html += `<label class="plan-item${it.done?' done':''}"><input type="checkbox" ${it.done?'checked':''} onchange="gdToggle('${esc(it.id)}',this.checked)">
      <span><span class="t">${esc(it.title)}</span>${it.detail?`<div class="d">${esc(it.detail)}</div>`:''}</span></label>`;
  });
  return html;
}

async function gdPlan() {
  const goal = (document.getElementById('gd-goal')||{}).value?.trim()||'';
  if (!goal) return toast('请先输入项目目标','warn');
  try {
    const r = await api(`/api/engagements/${current}/guided/plan`, {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({goal})});
    toast(r.used_llm?'任务清单已生成（AI）':'任务清单已生成（规则版）','ok');
    selectEng(current);
  } catch(e){ toast('生成失败：'+e.message,'bad',7000); }
}

async function gdReplan() {
  if (!gdPlanData) return;
  if (!confirm('覆盖现有任务清单？勾选状态会丢失。')) return;
  try {
    await api(`/api/engagements/${current}/guided/plan`, {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({goal: gdPlanData.goal||''})});
    toast('已重新生成','ok');
    selectEng(current);
  } catch(e){ toast('生成失败：'+e.message,'bad',7000); }
}

function gdToggle(id, done) {
  if (!gdPlanData) return;
  const it = (gdPlanData.items||[]).find(x=>x.id===id);
  if (it) it.done = done;
  clearTimeout(gdSaveTimer);
  gdSaveTimer = setTimeout(()=>{
    api(`/api/engagements/${current}/context`, {method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({assets:{guided_plan:gdPlanData}})})
      .then(()=>toast('任务状态已保存','ok'))
      .catch(()=>toast('任务状态保存失败','bad'));
  }, 400);
}

async function gdDraftCtx() {
  const desc = (document.getElementById('gd-desc')||{}).value?.trim()||'';
  if (!desc) return toast('请先描述你的业务','warn');
  window.gdLastDesc = desc;
  const out = document.getElementById('gd-out');
  out.innerHTML = '<div class="hint">起草中（最长约 1 分钟）…</div>';
  try {
    const r = await api(`/api/engagements/${current}/guided/draft-context`, {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({description:desc})});
    gdDraftRes = r;
    if (r.draft) gdRenderDiff(r);
    else {
      toast(r.used_llm?'AI 输出无法解析，已切换手动模式':'AI 不可用，已切换手动模式','warn',6000);
      gdRenderGuide(r.field_guide, '按下面的字段说明手动录入，每块单独保存（同样要过门禁才算数）。');
    }
  } catch(e){
    out.innerHTML = '<div class="empty">' + icon('i-alert') + '起草请求失败<div class="hint">' + escapeHtml(e.message) + ' —— 可重试，或改用手动填写。</div></div>';
  }
}

function gdBrief(block, v) {
  if (v==null) return '—';
  if (block==='site') return v.location ? `地点 ${v.location} · 班次 ${v.shift_count||1} · 气隙 ${v.air_gapped?'是':'否'}` : '未填写';
  if (Array.isArray(v)) return v.length ? v.length+' 条：'+v.slice(0,3).map(x=>typeof x==='string'?x:(x.name||JSON.stringify(x))).join('，') : '空';
  return JSON.stringify(v);
}

function gdRenderDiff(res) {
  const esc = escapeHtml;
  const labels = {site:'现场 / Site', stakeholders:'干系人', success_criteria:'成功标准', slos:'SLO'};
  const cur = res.current||{};
  let html = '<div class="hint">由 MiMo 起草，待你确认。勾选要采纳的块后写入；写入后门禁会实时重评。</div>';
  Object.entries(res.draft||{}).forEach(([block,val])=>{
    html += `<div class="diff"><div class="diff-h">
      <input type="checkbox" class="gd-adopt" data-block="${esc(block)}" checked aria-label="${esc(labels[block]||block)}">
      <span>${esc(labels[block]||block)}</span></div>
      <div class="diff-b">
        <div class="diff-row"><span class="k">当前值</span><span class="old">${esc(gdBrief(block,cur[block]))}</span></div>
        <div class="diff-row"><span class="k">起草值</span><span class="new">${esc(gdBrief(block,val))}</span></div>
        <details><summary>JSON 微调</summary><textarea id="gd-json-${esc(block)}" rows="4">${esc(JSON.stringify(val,null,2))}</textarea></details>
      </div></div>`;
  });
  html += `<div class="row mt2"><button onclick="gdApply()">确认写入勾选项</button>
    <button class="ghost" onclick="gdRenderGuide(gdDraftRes.field_guide,'也可完全手动录入：')">手动填写表单</button></div>`;
  document.getElementById('gd-out').innerHTML = html;
}

async function gdApply() {
  const body = {};
  for (const cb of document.querySelectorAll('.gd-adopt:checked')) {
    const block = cb.dataset.block;
    const ta = document.getElementById('gd-json-'+block);
    try { body[block] = JSON.parse(ta.value); }
    catch(e){ return toast(`${block} 的 JSON 不合法：`+e.message,'bad',7000); }
  }
  if (!Object.keys(body).length) return toast('没有勾选任何块','warn');
  await gdPostContext(body);
}

function gdRenderGuide(guide, note) {
  const esc = escapeHtml;
  window._gdGuide = guide||[];
  let html = note ? `<div class="hint">${esc(note)}</div>` : '';
  (guide||[]).forEach(b=>{
    html += `<div class="diff"><div class="diff-h"><span>${esc(b.label)}</span></div><div class="diff-b">`;
    if (b.kind==='fields') {
      (b.fields||[]).forEach(f=>{
        const id = 'gd-f-'+f.field;
        if (f.type==='bool') html += `<div class="row"><label>${esc(f.field)}</label><input type="checkbox" id="${id}"><span class="hint">${esc(f.hint||'')}</span></div>`;
        else if (f.type==='lines') html += `<div class="stack"><label class="hint" for="${id}">${esc(f.field)} · ${esc(f.hint||'')}</label><textarea id="${id}" rows="2"></textarea></div>`;
        else html += `<div class="row"><label>${esc(f.field)}</label><input id="${id}" placeholder="${esc(f.example||f.hint||'')}"></div>`;
      });
    } else {
      html += `<div class="hint">${esc(b.hint||'')} 格式：${esc(b.line_format||'')}${b.example?`（例：${esc(b.example)}）`:''}</div>
        <textarea id="gd-l-${esc(b.block)}" rows="3"></textarea>`;
    }
    html += `<div class="row"><button class="ghost" onclick="gdSubmitBlock('${esc(b.block)}')">保存${esc(b.label)}</button></div></div></div>`;
  });
  document.getElementById('gd-out').innerHTML = html;
}

function gdAssemble(b) {
  const lines = id => (((document.getElementById(id)||{}).value||'').split('\\n').map(s=>s.trim()).filter(Boolean));
  if (b.kind==='fields') {
    const site = {}; let any = false;
    (b.fields||[]).forEach(f=>{
      const el = document.getElementById('gd-f-'+f.field); if (!el) return;
      if (f.type==='bool') { site[f.field] = el.checked; if (el.checked) any = true; }
      else if (f.type==='int') { const n = parseInt(el.value,10); if (!isNaN(n)) { site[f.field] = n; any = true; } }
      else if (f.type==='lines') { const v = lines('gd-f-'+f.field); if (v.length) { site[f.field] = v; any = true; } }
      else if (el.value.trim()) { site[f.field] = el.value.trim(); any = true; }
    });
    return any ? site : null;
  }
  const rows = lines('gd-l-'+b.block);
  if (!rows.length) return null;
  const cells = r => r.split('|').map(s=>(s||'').trim());
  // \\u662f is the zh "yes" accepted in pasted CSV; escaped so the EN page stays CJK-free
  if (b.block==='stakeholders') return rows.map(r=>{const [name,role,sp,metric]=cells(r); return {name:name||'',role:role||'',is_sponsor:/^(y|yes|\\u662f)$/i.test(sp||''),success_metric:metric||''};}).filter(x=>x.name);
  if (b.block==='success_criteria') return rows;
  if (b.block==='slos') return rows.map(r=>{const [name,target,eb,route,win]=cells(r); return {name:name||'',target:target||'',error_budget:eb||'',alert_route:route||'',window:win||'14d'};}).filter(x=>x.name&&x.target);
  return null;
}

function gdSubmitBlock(block) {
  const b = (window._gdGuide||[]).find(x=>x.block===block);
  if (!b) return;
  let val;
  try { val = gdAssemble(b); } catch(e){ return toast('格式错误：'+e.message,'bad',6000); }
  if (val===null || (Array.isArray(val)&&!val.length)) return toast('没有可写入的内容','warn');
  gdPostContext({[block]: val});
}

async function gdPostContext(body) {
  try {
    await api(`/api/engagements/${current}/context`, {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    toast('已保存，门禁已重评','ok');
    selectEng(current);
  } catch(e){ toast('保存失败：'+e.message,'bad',7000); }
}


async function advance(force, reason, operator) {
  const opts = {method:'POST'};
  const fd = new URLSearchParams();
  if (reason) fd.set('reason', reason);
  if (operator) fd.set('operator', operator);
  if (reason || operator) opts.body = fd;
  const r = await api(`/api/engagements/${current}/advance?force=${!!force}`, opts);
  if (!r.advanced) {
    if (r.reason==='complete') toast('已是最后阶段，无可推进目标','warn',6000);
    else toast('推进被拦截：' + ((r.result||{}).blockers||[]).join('；'), 'bad', 7000);
  } else if (force) toast('已 force 推进（原因已入审计）','ok',6000);
  selectEng(current);
}

async function recheck(slug) {
  await api(`/api/engagements/${current}/gate/${slug}`,{method:'POST'});
  selectEng(current);
}

// ---- destructive / privileged actions: one shared confirmation dialog --------
function openActionDialog(cfg) {
  const dlg = document.getElementById('dlg-action');
  document.getElementById('dlg-action-title').textContent = cfg.title;
  document.getElementById('dlg-action-msg').innerHTML = cfg.message || '';
  document.getElementById('dlg-action-fields').innerHTML = (cfg.fields||[]).map(f=>{
    if (f.type==='select')
      return `<div class="row"><label>${f.label}</label><select id="af-${f.name}">${
        f.options.map(o=>`<option value="${o.value}">${o.text}</option>`).join('')}</select></div>`;
    return `<div class="row"><label>${f.label}</label><input id="af-${f.name}" placeholder="${f.placeholder||''}"></div>`;
  }).join('');
  const ok = document.getElementById('dlg-action-ok');
  ok.textContent = cfg.confirmLabel || '确定';
  ok.style.color = cfg.danger ? 'var(--bad)' : '';
  ok.onclick = async () => {
    const vals = {};
    (cfg.fields||[]).forEach(f=>{ const e=document.getElementById('af-'+f.name); vals[f.name] = e ? e.value : ''; });
    if (cfg.validate) { const err = cfg.validate(vals); if (err) return toast(err,'warn',6000); }
    dlg.close();
    try { await cfg.submit(vals); } catch(e){ toast('操作失败：'+e.message,'bad',8000); }
  };
  dlg.showModal();
}

function askAdvanceForce() {
  if (!detailStatus) return;
  openActionDialog({
    title:'force 推进',
    message:`force 会越过未通过的门禁把 <b>${escapeHtml(detailStatus.current_phase)}</b> 推进到下一阶段；<b>原因必填</b>，与操作人一并写入审计。`,
    fields:[
      {name:'reason', label:'原因', placeholder:'为什么必须强制推进（必填）'},
      {name:'operator', label:'操作人', placeholder:'可选'},
    ],
    confirmLabel:'强制推进', danger:true,
    validate: v => v.reason.trim() ? null : '请填写强制推进的原因',
    submit: v => advance(true, v.reason.trim(), v.operator.trim()),
  });
}

function askRollback() {
  if (!detailStatus) return;
  let curIdx = 0;
  detailPhases.forEach((p,i)=>{ if (p.slug===detailStatus.current_phase) curIdx=i; });
  const opts = detailPhases.slice(0, curIdx).map(p=>({value:p.slug, text:`${p.index} · ${p.name} (${p.slug})`}));
  if (!opts.length) return toast('已在可见阶段的最前面，无可回滚目标','warn',6000);
  openActionDialog({
    title:'回滚阶段',
    message:`当前阶段 <b>${escapeHtml(detailStatus.current_phase)}</b>。回滚只能往<b>更早</b>的阶段走，门禁会在下次推进时重新校验。`,
    fields:[
      {name:'to_phase', label:'目标阶段', type:'select', options:opts},
      {name:'reason', label:'原因', placeholder:'写入审计（可选）'},
      {name:'operator', label:'操作人', placeholder:'可选'},
    ],
    confirmLabel:'回滚', danger:true,
    submit: async v => {
      const fd = new URLSearchParams({to_phase:v.to_phase});
      if (v.reason.trim()) fd.set('reason', v.reason.trim());
      if (v.operator.trim()) fd.set('operator', v.operator.trim());
      const r = await api(`/api/engagements/${current}/rollback`, {method:'POST', body:fd});
      toast(`已回滚 ${r.from_phase} → ${r.to_phase}`,'ok',6000);
      selectEng(current);
    },
  });
}

function askArchiveEng(btn) {
  const card = btn.closest('.eng');
  const eid = card.dataset.eid, customer = card.dataset.customer || '';
  openActionDialog({
    title:'归档 engagement',
    message:`归档 <b>${escapeHtml(customer)}</b> 后它会离开所有列表（数据保留在归档目录，审计留痕）。`,
    confirmLabel:'归档', danger:true,
    submit: async () => {
      await api(`/api/engagements/${eid}/archive`, {method:'POST'});
      toast('已归档','ok');
      if (current===eid) current='';
      loadWorkbench();
    },
  });
}

function askDeleteEng(btn) {
  const card = btn.closest('.eng');
  const eid = card.dataset.eid, customer = card.dataset.customer || '';
  openActionDialog({
    title:'删除 engagement（GDPR 删除权）',
    message:`将永久删除 <b>${escapeHtml(customer)}</b> 的 engagement JSON 与全部证据文件，<b>不可恢复</b>。审计日志本身按合规要求保留。<br>请原样输入客户名以确认：`,
    fields:[{name:'confirm', label:'客户名', placeholder:customer}],
    confirmLabel:'永久删除', danger:true,
    validate: v => v.confirm === customer ? null : '客户名不一致，已取消',
    submit: async () => {
      await api(`/api/engagements/${eid}`, {method:'DELETE',
        body:new URLSearchParams({confirm:customer})});
      toast('已删除','ok');
      if (current===eid) current='';
      loadWorkbench();
    },
  });
}

// ---- evidence / handoff / audit (lazily loaded panes) ------------------------
async function loadEvidence() {
  const box = document.getElementById('t-evidence');
  box.innerHTML = '<div class="card"><div class="empty">加载中…</div></div>';
  try {
    const r = await api(`/api/engagements/${current}/evidence`);
    const rows = (r.evidence||[]).map(e=>`<tr>
      <td><b>${escapeHtml(e.name)}</b></td>
      <td><code class="digest">${escapeHtml(String(e.sha256||''))}</code></td>
      <td class="meta">${escapeHtml(String(e.bytes||0))} B</td>
      <td class="meta">${escapeHtml(String(e.ts||'').slice(0,19).replace('T',' '))}</td>
      <td class="meta">${escapeHtml(e.operator||'—')}</td></tr>`).join('');
    box.innerHTML = `<div class="card"><h2>验收证据</h2>
      <div class="hint">FAT/SAT 签字扫描件等外部凭证；留存 sha256 摘要供完整性核对。<b>摘要不是数字签名</b>，也不构成链式审计——那两项在商业版路线上。</div>
      ${rows?`<div class="tablewrap mt2"><table>
        <thead><tr><th>文件</th><th>sha256</th><th>大小</th><th>留存时间</th><th>操作人</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`:'<div class="empty">尚无证据</div>'}
      <div class="row" style="margin-top:12px"><input type="file" id="ev-file"></div>
      <div class="row"><label>名称</label><input id="ev-name" placeholder="留空则用文件名"></div>
      <div class="row"><label>操作人</label><input id="ev-op" placeholder="可选"></div>
      <button onclick="uploadEvidence()">上传证据</button>
      <div class="hint mt1">上传需要 pro / enterprise 许可（feature: evidence）；未授权时接口返回 402 与升级指引。</div>
    </div>`;
  } catch(e){ box.innerHTML = `<div class="card"><div class="empty">${icon('i-alert')}加载失败：${escapeHtml(e.message)}</div></div>`; }
}

async function uploadEvidence() {
  const inp = document.getElementById('ev-file');
  if (!inp.files || !inp.files.length) return toast('请选择文件','warn');
  const fd = new FormData();
  fd.append('name', document.getElementById('ev-name').value.trim() || inp.files[0].name);
  fd.append('file', inp.files[0]);
  const op = document.getElementById('ev-op').value.trim();
  if (op) fd.append('operator', op);
  try {
    const r = await api(`/api/engagements/${current}/evidence`, {method:'POST', body:fd});
    toast('证据已留存 '+String(r.sha256||'').slice(0,12)+'…','ok',6000);
  } catch(e){ return toast('留存失败：'+e.message,'bad',9000); }
  loadEvidence();
}

function renderHandoff() {
  document.getElementById('t-handoff').innerHTML = `<div class="card"><h2>交接包</h2>
    <div class="hint">渲染 runbook、组装 handoff package JSON，并把两个文件的 sha256 写入审计（客户勾选验收时另记一条 handoff.accepted）。</div>
    <div class="row" style="margin-top:10px"><label>操作人</label><input id="ho-op" placeholder="可选"></div>
    <div class="row"><label>适用边界<br><span class="meta">G7③</span></label><textarea id="ho-boundary" rows="2" placeholder="这套方案在哪些条件下不成立：未覆盖的门店类型、数据不回传的加盟商、历史样本不足的新品……留空则保留上次记录"></textarea></div>
    <div class="row"><label>终止条件<br><span class="meta">G7④</span></label><textarea id="ho-termination" rows="2" placeholder="什么情况下停用并回退、由谁判定：SLO 连续两个窗口破线、schema 变更后未重训……留空则保留上次记录"></textarea></div>
    <div class="row"><label>客户已验收</label><input type="checkbox" id="ho-accept"></div>
    <button onclick="runHandoff()">${icon('i-rocket')} 生成交接包</button>
    <div class="hint mt1">G7③④ 缺失不阻塞门禁，但 <code>gate check --gate handoff_signoff</code> 会给出 ⚠️ 警告——接手方没人知道边界，等于没有边界。</div>
    <div id="ho-out" class="mt2"></div></div>`;
}

async function runHandoff() {
  const fd = new URLSearchParams({accept: document.getElementById('ho-accept').checked ? 'true' : 'false'});
  const op = document.getElementById('ho-op').value.trim();
  if (op) fd.set('operator', op);
  const bd = document.getElementById('ho-boundary').value.trim();
  if (bd) fd.set('boundary', bd);
  const tm = document.getElementById('ho-termination').value.trim();
  if (tm) fd.set('termination', tm);
  try {
    const r = await api(`/api/engagements/${current}/handoff`, {method:'POST', body:fd});
    const base = p => String(p||'').split('/').pop();
    document.getElementById('ho-out').innerHTML = `
      <div class="hint">客户已验收：${yn(r.customer_accepted)}</div>
      <div class="row mt1">
        <a class="btn ghost" href="/reports/${escapeHtml(base(r.runbook))}" target="_blank">${icon('i-book')} Runbook</a>
        <a class="btn ghost" href="/reports/${escapeHtml(base(r.package))}" target="_blank">${icon('i-doc')} 交接包 JSON</a>
        <a class="btn ghost" href="/reports/" target="_blank">${icon('i-folder')} 报告目录</a>
      </div>
      <details class="mt2"><summary>交接摘要</summary><pre>${escapeHtml(r.summary||'')}</pre></details>`;
    toast('交接包已生成','ok');
  } catch(e){ toast('生成失败：'+e.message,'bad',8000); }
}

async function loadAudit() {
  const box = document.getElementById('t-audit');
  box.innerHTML = '<div class="card"><div class="empty">加载中…</div></div>';
  try {
    const r = await api(`/api/engagements/${current}/audit`);
    const rows = (r.events||[]).slice().reverse().map(e=>`<tr>
      <td class="meta">${escapeHtml(String(e.ts||'').slice(0,19).replace('T',' '))}</td>
      <td><b>${escapeHtml(e.action||'')}</b></td>
      <td class="meta">${escapeHtml(e.actor||'')}</td>
      <td class="meta"><code class="digest">${escapeHtml(JSON.stringify(e.detail||{}))}</code></td></tr>`).join('');
    box.innerHTML = `<div class="card"><h2>审计轨迹（append-only）</h2>
      <div class="hint">共 <b>${r.count||0}</b> 条本 engagement 事件，最新在前。日志为单文件 JSONL 追加写，<b>没有哈希链，也没有数字签名</b>——它证明「发生过什么」，不防篡改；防篡改在商业版路线上。</div>
      ${rows?`<div class="tablewrap mt2"><table>
        <thead><tr><th>时间</th><th>动作</th><th>来源</th><th>详情</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`:'<div class="empty">尚无审计事件</div>'}
      <div class="row" style="margin-top:12px">
        <button class="ghost" onclick="exportAudit()">${icon('i-doc')} 导出 Markdown</button>
        <span class="hint">导出需要 pro / enterprise 许可（feature: audit_export）。</span>
      </div>
      <div id="au-out" class="hint mt1"></div>
    </div>`;
  } catch(e){ box.innerHTML = `<div class="card"><div class="empty">${icon('i-alert')}加载失败：${escapeHtml(e.message)}</div></div>`; }
}

async function loadShare() {
  const el = document.getElementById('share-state');
  if (!el) return;
  try {
    const s = await api(`/api/engagements/${current}/share`);
    el.textContent = s.active
      ? `已启用 · 前缀 ${s.token_prefix} · ${String(s.created_at||'').slice(0,16).replace('T',' ')}`
      : '未启用';
  } catch(e) { el.textContent = '—'; }
}
async function createShare() {
  const r = await api(`/api/engagements/${current}/share`, {method:'POST'});
  document.getElementById('share-out').innerHTML =
    `链接（只显示这一次）：<code>${location.origin}${r.url_path}?t=${r.token}</code><br>复制给干系人后本页不再显示 token；重新生成即吊销旧链接。`;
  loadShare();
}
async function revokeShare() {
  await api(`/api/engagements/${current}/share`, {method:'DELETE'});
  document.getElementById('share-out').textContent = '已吊销';
  loadShare();
}

async function loadRetro() {
  const box = document.getElementById('t-retro');
  box.innerHTML = '<div class="card"><div class="empty">加载中…</div></div>';
  try {
    const r = await api(`/api/engagements/${current}/retrospective`);
    const slaRows = (r.sla||[]).map(m=>`<tr>
      <td><b>${escapeHtml(m.label)}</b></td>
      <td>≤${m.deadline_days}d <span class="meta">${m.deadline_source==='assets'?'契约覆盖':'默认'}</span></td>
      <td>${mark(m.status)} <b>${escapeHtml(m.status)}</b></td>
      <td class="meta">${escapeHtml(m.note||'')}</td></tr>`).join('');
    const phaseRows = (r.phases||[]).map(p=>`<tr>
      <td><b>${escapeHtml(p.slug)}</b> <span class="meta">${escapeHtml(p.name)}</span></td>
      <td>${p.visits}</td>
      <td>${p.total_days==null?'—':p.total_days+'d'}</td>
      <td class="meta">${escapeHtml(String(p.first_entered_at||'').slice(0,16).replace('T',' '))}</td>
      <td>${p.current?'●':''}</td></tr>`).join('');
    const gateRows = (r.gates||[]).map(g=>`<tr>
      <td><b>${escapeHtml(g.slug)}</b></td>
      <td>${g.evaluations==null?'—':g.evaluations}</td>
      <td>${g.first_pass==null?'—':yn(g.first_pass)}</td>
      <td>${g.passes==null?'—':g.passes}</td>
      <td>${g.latest_passed==null?'—':yn(g.latest_passed)}</td>
      <td><span class="pill">${escapeHtml(g.source)}</span></td></tr>`).join('');
    box.innerHTML = `
      ${r.timeline_consistent?'':'<div class="gate fail">审计流重放终态与当前阶段不一致——时间线可能缺失早期事件，以下数据仅供参考。</div>'}
      <div class="card"><h2>SLA 时钟</h2>
        <div class="kpi-grid">
          <div class="kpi"><div class="k">已历时</div><div class="v">${r.elapsed_days==null?'—':r.elapsed_days+'d'}</div></div>
          <div class="kpi"><div class="k">gate 首过率</div><div class="v">${r.gate_first_pass_rate==null?'—':Math.round(r.gate_first_pass_rate*100)+'%'}</div></div>
          <div class="kpi"><div class="k">推进/被拦/强制</div><div class="v">${r.advances_ok} / ${r.advances_blocked} / ${r.advances_forced}</div></div>
          <div class="kpi"><div class="k">回滚</div><div class="v">${r.rollbacks}</div></div>
        </div>
        <div class="tablewrap mt2"><table>
          <thead><tr><th>里程碑</th><th>契约</th><th>状态</th><th>说明</th></tr></thead>
          <tbody>${slaRows}</tbody></table></div>
        <div class="meta" style="margin-top:6px">时间锚: ${escapeHtml(r.started_at||'—')}（${escapeHtml(r.start_source||'—')}）· 数据源: ${escapeHtml((r.data_sources||[]).join(' · '))}</div>
      </div>
      <div class="card"><h2>阶段时间线</h2><div class="tablewrap"><table>
        <thead><tr><th>阶段</th><th>访问</th><th>累计</th><th>首次进入</th><th>当前</th></tr></thead>
        <tbody>${phaseRows}</tbody></table></div></div>
      <div class="card"><h2>Gate 统计</h2><div class="tablewrap"><table>
        <thead><tr><th>Gate</th><th>评估</th><th>首过</th><th>通过</th><th>最新</th><th>来源</th></tr></thead>
        <tbody>${gateRows}</tbody></table></div>
        <div class="meta" style="margin-top:6px">评估次数与首过来自审计流（audit.jsonl）；无审计事件的历史项目只显示 context 里的最新状态（context-only），不编造历史。</div></div>`;
  } catch(e){ box.innerHTML = `<div class="card"><div class="empty">${icon('i-alert')}加载失败：${escapeHtml(e.message)}</div></div>`; }
}

async function exportAudit() {
  try {
    const r = await api(`/api/engagements/${current}/audit/export`);
    document.getElementById('au-out').innerHTML =
      `已导出 ${r.count} 条 → <code>${escapeHtml(String(r.path||'').split('/').pop())}</code>（报告目录）`;
    toast('审计已导出','ok');
  } catch(e){ toast('导出失败：'+e.message,'bad',9000); }
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
      <div class="kpi"><div class="k">synthetic</div><div class="v">${r.synthetic}</div></div>
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
        <button class="btn ghost" onclick="showDiagram('${esc(s.id)}')">类图</button>
        <button class="btn ghost" onclick="validateTarget('${esc(s.id)}')">校验</button>
        <button class="btn ghost" onclick="showJsonld('${esc(s.id)}','')">${icon('i-doc')} JSON-LD</button>
      </div>
    </div>`).join('') || '<div class="empty">无 schema</div>';
  const stCards = stores.map(t => `
    <div class="card" style="margin-bottom:8px">
      <div class="row"><b>${esc(t.id)}</b> <span class="pill tkt">${esc(t.ontology_ref)}</span>
        <span class="meta" style="margin-left:auto">${t.individuals} individuals</span></div>
      <div class="row" style="margin-top:6px">
        <button class="btn ghost" onclick="validateTarget('${esc(t.id)}')">校验</button>
        <button class="btn ghost" onclick="showJsonld('${esc(t.id)}','')">${icon('i-doc')} JSON-LD（含 TBox）</button>
      </div>
    </div>`).join('') || '<div class="empty" style="padding:14px">工作区暂无实例库（ontology/stores/*.json）</div>';
  const schemaOpts = schemas.map(s => `<option value="${esc(s.id)}">${esc(s.id)}@${esc(s.version)}</option>`).join('');
  document.getElementById('view-ontology').innerHTML = `
    <div class="sec-head"><svg class="ic"><use href="#i-globe"/></svg><h2>本体库 · TBox + ABox</h2></div>
    <div class="card"><h2>Schema（TBox）</h2>${sCards}</div>
    <div class="card" style="margin-top:12px"><h2>版本 diff（D1-D4 + ABox 影响面）</h2>
      <div class="row"><label>旧 schema</label><select id="ot-diff-old">${schemaOpts}</select>
        <label>新 schema</label><select id="ot-diff-new">${schemaOpts}</select>
        <button onclick="runOntoDiff()">diff</button></div>
      <div id="ot-diff-out" class="mt2"></div></div>
    <div class="card" style="margin-top:12px"><h2>实例库（ABox）</h2>
      <p class="meta">ontology_ref 指向 schema@version；导出时自动并入其 TBox 上下文（JSON-LD 1.1）。</p>${stCards}</div>
    <div id="ot-tool-out"></div>`;
}

async function showDiagram(sid) {
  const r = await api(`/api/ontology/schema/${encodeURIComponent(sid)}/diagram`);
  document.getElementById('ot-tool-out').innerHTML = `
    <div class="card" style="margin-top:12px"><h2>类图 · ${escapeHtml(r.schema_id)}@${escapeHtml(r.version)}</h2>
      <p class="meta">Mermaid 源码——控制台不打包渲染器；粘贴到任意 Mermaid 渲染器（或 CLI "fde-scope ontology diagram"）出图。</p>
      <pre>${escapeHtml(r.mermaid)}</pre></div>`;
  document.getElementById('ot-tool-out').scrollIntoView({behavior:'smooth'});
}

async function validateTarget(tid) {
  const out = document.getElementById('ot-tool-out');
  out.innerHTML = '<div class="card" style="margin-top:12px"><div class="empty">校验中…</div></div>';
  try {
    const r = await api(`/api/ontology/validate/${encodeURIComponent(tid)}`);
    const rows = (r.errors||[]).map(e=>`<tr><td><span class="pill bad">${escapeHtml(e.code)}</span></td>
      <td><code>${escapeHtml(e.subject)}</code></td><td class="meta">${escapeHtml(e.message)}</td></tr>`).join('');
    out.innerHTML = `<div class="card" style="margin-top:12px">
      <h2>校验 · ${escapeHtml(r.kind === 'schema' ? 'TBox' : 'ABox')} ${escapeHtml(r.target)}</h2>
      ${r.ok ? '<div class="gate pass">通过（0 个 ONTO-* 错误）</div>'
        : `<div class="gate fail"><b>${(r.errors||[]).length} 个错误</b>
           <div class="tablewrap mt2"><table>
           <thead><tr><th>错误码</th><th>主体</th><th>说明</th></tr></thead>
           <tbody>${rows}</tbody></table></div></div>`}</div>`;
  } catch(e) {
    out.innerHTML = `<div class="card" style="margin-top:12px"><div class="gate fail">校验失败：${escapeHtml(e.message)}</div></div>`;
  }
  out.scrollIntoView({behavior:'smooth'});
}

async function runOntoDiff() {
  const oldId = document.getElementById('ot-diff-old').value;
  const newId = document.getElementById('ot-diff-new').value;
  const out = document.getElementById('ot-diff-out');
  if (!oldId || !newId) return toast('请选择两个 schema','warn');
  if (oldId === newId) return toast('旧 schema 与新 schema 相同','warn');
  out.innerHTML = '<div class="empty">计算中…</div>';
  try {
    const r = await api('/api/ontology/diff', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({old:oldId, new:newId})});
    const changeRows = list => list.map(c=>`<tr><td><span class="pill" style="color:${c.kind==='INFO'?'var(--fg)':'var(--bad)'}">${escapeHtml(c.kind)}</span></td>
      <td><code>${escapeHtml(c.subject)}</code></td><td class="meta">${escapeHtml(c.detail)}</td></tr>`).join('');
    const impactRows = (r.impact||[]).map(c=>`<tr><td><code>${escapeHtml(c.subject)}</code></td>
      <td class="meta">${escapeHtml(c.detail)}</td></tr>`).join('');
    out.innerHTML = `
      <div class="gate ${r.ok?'pass':'fail'}">${r.ok ? '无破坏性变更' : `${(r.breaking||[]).length} 个破坏性变更（D1-D4）`} ·
        ${escapeHtml(r.from)} → ${escapeHtml(r.to)}</div>
      ${(r.breaking||[]).length || (r.info||[]).length ? `<div class="tablewrap mt2"><table>
        <thead><tr><th>级别</th><th>主体</th><th>说明</th></tr></thead>
        <tbody>${changeRows(r.breaking)}${changeRows(r.info)}</tbody></table></div>` : ''}
      <p class="meta mt2">ABox 影响面：${(r.impact||[]).length} 个个体引用了被变更元素</p>
      ${impactRows ? `<div class="tablewrap"><table>
        <thead><tr><th>个体</th><th>触及</th></tr></thead><tbody>${impactRows}</tbody></table></div>` : ''}`;
  } catch(e) {
    out.innerHTML = `<div class="gate fail">diff 失败：${escapeHtml(e.message)}</div>`;
  }
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
    <div class="card mt2"><h2>类（${(s.classes||[]).length}）</h2>${classRows}</div>
    <div class="card mt2"><h2>对象属性（${(s.object_properties||[]).length}）</h2>${objRows}</div>
    <div class="card mt2"><h2>数据属性（${(s.data_properties||[]).length}）</h2>${dataRows}</div>
    <div class="card mt2"><h2>概念体系（SKOS）</h2>${schemeBlocks}</div>`;
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
    <div class="card mt2"><pre style="max-height:60vh;overflow:auto">${esc(JSON.stringify(doc, null, 2))}</pre></div>`;
}

// -- 运维（连接器 / eval / flywheel / license） ---------------------------
async function loadOps() {
  const out = document.getElementById('view-ops');
  out.innerHTML = '<div class="card"><div class="empty">加载中…</div></div>';
  let c, ev, fw, li;
  const errs = [];
  const safeGet = async (path, into) => { try { return await api(path); } catch(e){ errs.push(path.split('/')[1] + ': ' + e.message); return {}; } };
  c = await safeGet('/api/connectors'); ev = await safeGet('/api/eval/info');
  fw = await safeGet('/api/flywheel'); li = await safeGet('/api/license');
  const esc = escapeHtml;
  const yn2 = b => b ? dot(true) : dot(false);
  const connRows = (c.connectors||[]).map(k => `
    <tr><td><b>${esc(k.slug)}</b></td>
    <td>${k.import_ok ? '<span class="pill" style="color:var(--good)">已注册</span>' : '<span class="pill" style="color:var(--warn)">缺可选依赖</span>'}</td>
    <td class="meta">${esc(k.note||'')}</td>
    <td>${Object.entries(k.env||[]).length ? Object.entries(k.env).map(([n,v])=>`<span class="pill" title="${esc(n)}（只显示是否已配置，不显示值）">${esc(n.replace('FDE_SCOPE_',''))} ${v?'✓':'—'}</span>`).join(' ') : '<span class="meta">—</span>'}</td></tr>`).join('')
    || '<tr><td colspan="4" class="meta">无连接器</td></tr>';
  const metricRows = Object.entries(ev.metrics||{}).map(([k,v])=>`<tr><td><code>${esc(k)}</code></td><td class="meta">${esc(v)}</td></tr>`).join('');
  const jobRows = (fw.jobs||[]).map(j=>`<tr><td><b>${esc(j.name)}</b></td><td class="meta">cron <code>${esc(j.cron)}</code></td>
    <td class="meta">≥${esc(String(j.min_new_samples))} samples</td><td class="meta">${esc(j.kind)}</td></tr>`).join('');
  const s = fw.snapshot||{};
  const featRows = Object.entries(li.features||{}).map(([k,v])=>`<tr><td><code>${esc(k)}</code></td><td>${yn2(v)}</td></tr>`).join('');
  out.innerHTML = `
    <div class="sec-head"><svg class="ic"><use href="#i-gears"/></svg><h2>运维 · 连接器 / eval / flywheel / license</h2></div>
    ${errs.length ? `<div class="gate fail"><b>部分面板加载失败</b><div class="mt1 meta">${errs.map(esc).join('<br>')}</div></div>` : ''}
    <div class="card"><h2>连接器注册表</h2>
      <p class="meta">导入级状态：注册表里 = 依赖齐；模块表有而注册表无 = 缺可选依赖。GET 不探测客户系统连通性——那是部署时的事。凭据 env 只显示名称与「是否已配置」，值不离开本进程。</p>
      <div class="tablewrap"><table><thead><tr><th>Slug</th><th>状态</th><th>说明</th><th>凭据 env</th></tr></thead><tbody>${connRows}</tbody></table></div></div>
    <div class="card" style="margin-top:12px"><h2>Eval 基准</h2>
      <p class="meta">指标与评分口径：${esc(String(Object.keys(ev.metrics||{}).length))} 项，全部确定性打分（LLM 只出现在生成回复那一步）。</p>
      ${metricRows?`<div class="tablewrap"><table><thead><tr><th>指标</th><th>说明</th></tr></thead><tbody>${metricRows}</tbody></table></div>`:''}
      <div class="row mt2">
        <label>用例集</label><input id="ev-cases" placeholder='JSON 数组或 JSONL 路径，例：[{"id":"t1","input":"退款怎么走"}]'>
        <label>Agent</label><select id="ev-agent"><option value="mock">mock（规则，无需 LLM）</option><option value="mimo">mimo（需 LLM env）</option></select>
        <button onclick="runEval()">运行</button></div>
      <div id="ev-out" class="mt2"></div></div>
    <div class="card" style="margin-top:12px"><h2>Data Flywheel</h2>
      <p class="meta">计数器是<b>本服务进程</b>内的（引擎在内存）；retrain 任务是<b>描述符</b>——本进程没有任何调度器在跑，交给外部编排器触发。</p>
      <div class="kpi-grid" style="margin:8px 0">
        <div class="kpi"><div class="k">collected</div><div class="v">${esc(String(s.collected??'—'))}</div></div>
        <div class="kpi"><div class="k">golden</div><div class="v">${esc(String(s.golden??'—'))}</div></div>
        <div class="kpi"><div class="k">labeling</div><div class="v">${esc(String(s.labeling_queued??'—'))}</div></div>
        <div class="kpi"><div class="k">edge cases</div><div class="v">${esc(String(s.edge_cases??'—'))}</div></div>
        <div class="kpi"><div class="k">store total</div><div class="v">${esc(String(s.store_total??'—'))}</div></div>
      </div>
      ${jobRows?`<div class="tablewrap"><table><thead><tr><th>任务</th><th>计划</th><th>门槛</th><th>类型</th></tr></thead><tbody>${jobRows}</tbody></table></div>`:''}</div>
    <div class="card" style="margin-top:12px"><h2>License</h2>
      <div class="row"><label>客户</label><b>${esc(li.customer||'—')}</b></div>
      <div class="row"><label>Tier</label><span class="pill ${li.tier==='community'?'':(li.tier==='pro'?'tkt':'ind')}">${esc(li.tier||'—')}</span>
        ${li.expired?'<span class="pill bad">已过期 → community</span>':''}
        <span class="meta" style="margin-left:auto">key 来源：${esc(li.key_source||'—')}（env / 文件 / 无——只报来源，不显示 key）</span></div>
      <div class="row"><label>席位</label>${esc(String(li.seats??'—'))} · 到期 ${li.expires_at?esc(String(li.expires_at).slice(0,10)):'—'}</div>
      ${featRows?`<div class="tablewrap mt2"><table><thead><tr><th>Feature</th><th>开关</th></tr></thead><tbody>${featRows}</tbody></table></div>`:''}</div>`;
}

async function runEval() {
  const out = document.getElementById('ev-out');
  const raw = (document.getElementById('ev-cases')||{}).value||'';
  const agent = (document.getElementById('ev-agent')||{}).value||'mock';
  if (!raw.trim()) return toast('请先粘贴用例（JSON 数组）或填 JSONL 路径','warn');
  let body;
  if (raw.trim().startsWith('[')) {
    try { body = {agent, cases: JSON.parse(raw)}; }
    catch(e){ return toast('用例 JSON 解析失败：'+e.message,'bad',8000); }
  } else body = {agent, test_set: raw.trim()};
  out.innerHTML = '<div class="empty">运行中（每条用例一次回复）…</div>';
  try {
    const r = await api('/api/eval/run', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const rows = Object.entries(r.metrics||{}).map(([k,v])=>`<tr><td><code>${escapeHtml(k)}</code></td>
      <td><b>${escapeHtml(String(v))}</b></td><td class="meta">${escapeHtml((r.metric_labels||{})[k]||'')}</td></tr>`).join('');
    const bad = (r.bad_cases||{}).cases||[];
    out.innerHTML = `<div class="gate pass">${escapeHtml(String(r.case_count))} 条用例跑完</div>
      <div class="tablewrap mt2"><table><thead><tr><th>指标</th><th>值</th><th>说明</th></tr></thead><tbody>${rows}</tbody></table></div>
      ${bad.length?`<details class="mt2"><summary>bad cases（${bad.length}）</summary><pre>${escapeHtml(JSON.stringify(bad, null, 2))}</pre></details>`:''}`;
  } catch(e) {
    out.innerHTML = `<div class="gate fail">运行失败：${escapeHtml(String(e.message).slice(0,400))}</div>`;
  }
}

if (location.hash === '#skills') go('skills');
else if (location.hash === '#deploy') go('deploy');
else if (location.hash === '#ontology') go('ontology');
else if (location.hash === '#ops') go('ops');
else loadWorkbench();
window.addEventListener('hashchange', () => {
  if (location.hash === '#skills') go('skills');
  else if (location.hash === '#deploy') go('deploy');
  else if (location.hash === '#ontology') go('ontology');
  else if (location.hash === '#ops') go('ops');
  else go('workbench');
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
<dialog id="dlg-action" aria-labelledby="dlg-action-title">
  <div class="dlg-h"><svg class="ic"><use href="#i-alert"/></svg><b id="dlg-action-title"></b></div>
  <div class="dlg-b">
    <div id="dlg-action-msg" class="hint"></div>
    <div id="dlg-action-fields" class="mt2"></div>
    <div class="row" style="margin:12px 0 0;justify-content:flex-end">
      <button class="ghost" onclick="document.getElementById('dlg-action').close()">取消</button>
      <button id="dlg-action-ok"></button>
    </div>
  </div>
</dialog>
<div id="toast-host" aria-live="polite"></div>
<script>__NAV_JS__</script>
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
<symbol id="i-chev" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3.2 10.8 8 6 12.8"/></symbol>
<symbol id="i-collapse" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 5 8 9.2 12.5 5"/><path d="M3.5 12.6 8 8.4 12.5 12.6"/></symbol>
<symbol id="i-expand" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 9.4 8 5.2 12.5 9.4"/><path d="M3.5 8.6 8 12.8 12.5 8.6"/></symbol>
<symbol id="i-check" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.8 8.6l3.4 3.4 7-8"/></symbol>
<symbol id="i-sun" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="3.2"/><path d="M8 1.2v1.8M8 13v1.8M1.2 8H3M13 8h1.8M3.2 3.2l1.3 1.3M11.5 11.5l1.3 1.3M12.8 3.2l-1.3 1.3M4.5 11.5l-1.3 1.3"/></symbol>
<symbol id="i-moon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 8.53A6 6 0 1 1 7.47 2 4.67 4.67 0 0 0 14 8.53z"/></symbol>
<symbol id="i-x" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></symbol>
</defs></svg>"""

#: Labels the rail cannot derive from :data:`~fde_scope.web.layout.NAV_BANDS`
#: because they belong to the page rather than the site: the overview's
#: in-page anchors and the console's view switcher. Kept as (href, label) and
#: (key, label) pairs so both locales read off one shape.
_OVERVIEW_ANCHORS = (
    ("#sop", "完整 SOP"),
    ("#gates", "合规 Gate"),
    ("#connectors", "数据连接器"),
    ("#ontology", "Ontology 语义层"),
    ("#modules", "功能模块"),
    ("#arch", "架构清单"),
    ("#practices", "最佳实践"),
    ("#kpi", "制造业 KPI"),
    ("#quickstart", "快速上手"),
    ("#scenarios", "两种场景"),
)
_OVERVIEW_ANCHORS_EN = (
    ("#sop", "Full SOP"),
    ("#gates", "Compliance gates"),
    ("#connectors", "Data connectors"),
    ("#ontology", "Ontology layer"),
    ("#modules", "Modules"),
    ("#arch", "Architecture"),
    ("#practices", "Best practices"),
    ("#kpi", "Manufacturing KPIs"),
    ("#quickstart", "Quick start"),
    ("#scenarios", "Two scenarios"),
)
_CONSOLE_VIEWS = (
    ("workbench", "工作台"),
    ("skills", "技能库"),
    ("deploy", "Agent 部署"),
    ("ontology", "本体库"),
    ("ops", "运维"),
)
_CONSOLE_VIEWS_EN = (
    ("workbench", "Workbench"),
    ("skills", "Skills"),
    ("deploy", "Agent deploy"),
    ("ontology", "Ontology"),
    ("ops", "Ops"),
)

# ``__SIDE_NAV__`` is replaced *after* ``to_en``, never before it. The rail is
# generated per locale now (``side_nav``), and it needs different ``href``s in
# English — ``/catalog/en/index.html`` is not ``/en`` plus a prefix — so an
# exact-substring pass over hand-copied rows could translate the words and
# leave the paths zh. Hand-copying those rows is also how the eight rails
# drifted apart; the shell below is translated, the tree is compiled.
_DASHBOARD_SHELL = (
    _DASHBOARD_HTML.replace("__BASE_CSS__", BASE_CSS)
    .replace("__SHELL_CSS__", SHELL_CSS)
    .replace("__ICON_SPRITE__", _ICON_SPRITE)
)
_DASHBOARD_HTML_EN = (
    to_en(_DASHBOARD_SHELL)
    .replace("__SIDE_NAV__", side_nav("console", en=True, views=_CONSOLE_VIEWS_EN))
    .replace("__NAV_JS__", NAV_JS)
)
_N_CONNECTORS, _CONNECTOR_TILES_HTML = _connector_tiles()
_OVERVIEW_SHELL = (
    _OVERVIEW_HTML.replace("__CONNECTOR_COUNT__", str(_N_CONNECTORS))
    .replace("__CONNECTOR_TILES__", _CONNECTOR_TILES_HTML)
    .replace("__BASE_CSS__", BASE_CSS)
    .replace("__SHELL_CSS__", SHELL_CSS)
    .replace("__SHELL_JS__", SHELL_JS)
    .replace("__ICON_SPRITE__", _ICON_SPRITE)
)
# Derive EN from the *built* zh document, not the raw template: the connector
# tiles are injected at runtime, so translating before injection left
# ``__CONNECTOR_TILES__`` as visible text on /en. The overview already carries
# ``SHELL_JS`` (which is ``NAV_JS`` plus the scroll-spy), so no second script.
_OVERVIEW_HTML_EN = to_en(_OVERVIEW_SHELL).replace(
    "__SIDE_NAV__", side_nav("overview", en=True, subnav=_OVERVIEW_ANCHORS_EN)
)
_DASHBOARD_HTML = _DASHBOARD_SHELL.replace("__SIDE_NAV__", side_nav("console", views=_CONSOLE_VIEWS)).replace(
    "__NAV_JS__", NAV_JS
)
_OVERVIEW_HTML = _OVERVIEW_SHELL.replace("__SIDE_NAV__", side_nav("overview", subnav=_OVERVIEW_ANCHORS))
# certification.py and glossary.py render both locales from paired literals (no
# to_en pass: see their module docstrings), so each variant is rendered, not
# translated.
_CERTIFICATION_HTML_EN = _render_certification("en").replace("__ICON_SPRITE__", _ICON_SPRITE)
_CERTIFICATION_HTML = _render_certification("zh").replace("__ICON_SPRITE__", _ICON_SPRITE)
_GLOSSARY_HTML_EN = _render_glossary("en").replace("__ICON_SPRITE__", _ICON_SPRITE)
_GLOSSARY_HTML = _render_glossary("zh").replace("__ICON_SPRITE__", _ICON_SPRITE)
# resources.py renders both locales from the packaged YAML (paired literals,
# no to_en pass like glossary/certification). The catalog is static within a
# process, so it is rendered once at import.
_RESOURCES_HTML_EN = _render_resources("en").replace("__ICON_SPRITE__", _ICON_SPRITE)
_RESOURCES_HTML = _render_resources("zh").replace("__ICON_SPRITE__", _ICON_SPRITE)
# course.py renders the whole Level-1 course from course-level-1/*.md, again
# from paired literals; a missing directory degrades to a notice, not a crash.
_COURSE_HTML_EN = _render_course("en").replace("__ICON_SPRITE__", _ICON_SPRITE)
_COURSE_HTML = _render_course("zh").replace("__ICON_SPRITE__", _ICON_SPRITE)
# sop.py renders docs/fde_sop_full.md the same way; wheel installs have no
# docs/ and get the in-page notice instead.
_SOP_HTML_EN = _render_sop("en").replace("__ICON_SPRITE__", _ICON_SPRITE)
_SOP_HTML = _render_sop("zh").replace("__ICON_SPRITE__", _ICON_SPRITE)
# showcase.py renders the registry's rubric page. The rule table is compiled
# from course/showcase.RULES, so it is as static as the code that audits:
# rendered once at import, and it never reads the store.
_SHOWCASE_HTML_EN = _render_showcase("en").replace("__ICON_SPRITE__", _ICON_SPRITE)
_SHOWCASE_HTML = _render_showcase("zh").replace("__ICON_SPRITE__", _ICON_SPRITE)
# docs_reader.py renders the repository's own documents (README, docs/*.md,
# LICENSE, NOTICE, the examples and course quickstart READMEs) from paired
# literals; a missing file degrades to the in-page notice. Pre-rendered once
# at import: the corpus is static within a process.
_DOC_PAGES_EN = {
    _slug: _render_doc(_slug, "en").replace("__ICON_SPRITE__", _ICON_SPRITE) for _slug in _DOC_SLUGS
}
_DOC_PAGES = {_slug: _render_doc(_slug).replace("__ICON_SPRITE__", _ICON_SPRITE) for _slug in _DOC_SLUGS}
