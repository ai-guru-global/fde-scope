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
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from ..engagement import Engagement, EngagementContext
from ..engagement.engagement import AdvanceBlocked, _default_gate_registry
from ..profiles import all_profiles, get_profile

_ENGAGEMENTS_DIR = Path(".fde_scope/engagements")
_REPORTS_DIR = Path("reports")
_REPORTS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="FDE Scope", version="0.1.0")


# ---------------------------------------------------------------------------
# persistence helpers
# ---------------------------------------------------------------------------
def _eng_path(eid: str) -> Path:
    return _ENGAGEMENTS_DIR / f"{eid}.json"


def _load(eid: str) -> Engagement:
    p = _eng_path(eid)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"engagement '{eid}' not found")
    return Engagement(EngagementContext.load(p))


def _save(eng: Engagement) -> None:
    _eng_path(eng.ctx.id).parent.mkdir(parents=True, exist_ok=True)
    eng.ctx.save(_eng_path(eng.ctx.id))


def _all_engagements() -> list[Engagement]:
    if not _ENGAGEMENTS_DIR.exists():
        return []
    out = []
    for p in sorted(_ENGAGEMENTS_DIR.glob("*.json")):
        out.append(Engagement(EngagementContext.load(p)))
    return out


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/profiles")
def profiles() -> dict:
    return {slug: {"name": p.name, "industrial": p.is_industrial,
                   "connectors": p.primary_connectors,
                   "kpis": p.kpi_catalogue}
            for slug, p in all_profiles().items()}


@app.get("/api/phases")
def phases(profile: str = "ticket") -> dict:
    from ..engagement.phases import phases_for_profile

    is_industrial = get_profile(profile).is_industrial
    seq = phases_for_profile(is_industrial)
    return {"phases": [p.__dict__ for p in seq], "is_industrial": is_industrial}


@app.get("/api/engagements")
def list_engagements() -> list[dict]:
    return [eng.status() for eng in _all_engagements()]


@app.post("/api/engagements")
def create_engagement(customer: str = Form(...), profile: str = Form("ticket")) -> dict:
    eid = f"eng-{customer.lower().replace(' ', '-')}-{profile}-{uuid.uuid4().hex[:6]}"
    ctx = EngagementContext(id=eid, customer=customer, profile=profile)
    eng = Engagement(ctx)
    _save(eng)
    return eng.status()


@app.get("/api/engagements/{eid}")
def get_engagement(eid: str) -> dict:
    return _load(eid).status()


@app.get("/api/engagements/{eid}/gates")
def engagement_gates(eid: str) -> dict:
    eng = _load(eid)
    out = {}
    for slug, gate in _default_gate_registry().items():
        if gate.applies(eng.ctx):
            result = gate.check(eng.ctx)
            out[slug] = {"name": gate.name,
                         "passed": result.passed,
                         "blockers": result.blockers,
                         "warnings": result.warnings}
    return out


@app.post("/api/engagements/{eid}/advance")
def advance_engagement(eid: str, force: bool = False) -> dict:
    eng = _load(eid)
    try:
        eng.advance(force=force)
    except AdvanceBlocked as exc:
        _save(eng)
        return {"advanced": False, "result": exc.result.__dict__}
    _save(eng)
    return {"advanced": True, "status": eng.status()}


@app.post("/api/engagements/{eid}/gate/{slug}")
def evaluate_gate(eid: str, slug: str) -> dict:
    eng = _load(eid)
    result = eng.evaluate_gate(slug)
    _save(eng)
    return {"slug": slug, "passed": result.passed,
            "blockers": result.blockers, "warnings": result.warnings}


@app.post("/api/engagements/{eid}/context")
def update_context(eid: str, body: dict = None) -> dict:
    """Patch an engagement context (site / safety / slo / stakeholders / assets)."""
    eng = _load(eid)
    body = body or {}
    if "site" in body:
        eng.ctx.site = type(eng.ctx.site).model_validate(body["site"])
    if "safety" in body:
        eng.ctx.safety = type(eng.ctx.safety).model_validate(body["safety"])
    if "success_criteria" in body:
        eng.ctx.success_criteria = body["success_criteria"]
    if "stakeholders" in body:
        from ..engagement.context import Stakeholder

        eng.ctx.stakeholders = [Stakeholder.model_validate(s) for s in body["stakeholders"]]
    if "slos" in body:
        from ..engagement.context import SLOSpec

        eng.ctx.slos = [SLOSpec.model_validate(s) for s in body["slos"]]
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

    content = (await file.read()).decode("utf-8")
    tmp = Path(f".fde_scope/uploads/{file.filename}")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(content, encoding="utf-8")

    from ..connectors.csv_fallback import CSVConnector

    rows = CSVConnector(str(tmp)).extract_sample(100000)
    cfg = CorpusConfig(min_samples_per_category=min_samples, synth_per_gap=synth_per_gap)
    report = CorpusForge(cfg).forge_rows(rows)
    report_id = uuid.uuid4().hex[:8]
    out_html = _REPORTS_DIR / f"corpus_report_{report_id}.html"
    out_json = _REPORTS_DIR / f"corpus_report_{report_id}.json"
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
    content = (await file.read()).decode("utf-8")
    samples = [json.loads(line) for line in content.splitlines() if line.strip()]
    prof = get_profile(profile)
    return {"profile": profile, "kpis": prof.compute_kpis(samples), "sample_count": len(samples)}


from fastapi.staticfiles import StaticFiles  # noqa: E402

app.mount("/reports", StaticFiles(directory=str(_REPORTS_DIR)), name="reports")


# ---------------------------------------------------------------------------
# HTML dashboard (single self-contained page)
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return _DASHBOARD_HTML


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
.eng .meta{color:var(--muted);font-size:.78rem;margin-top:3px}
.pill{display:inline-block;padding:1px 7px;border-radius:999px;font-size:.7rem;background:#1e2738}
.pill.ind{background:#3b2a1a;color:var(--warn)}
.pill.tkt{background:#1a2e2a;color:var(--accent)}
button,.btn{background:var(--accent);color:#04201d;border:0;padding:7px 12px;border-radius:6px;font-weight:600;cursor:pointer;font-size:.85rem}
button.ghost{background:transparent;border:1px solid var(--border);color:var(--fg)}
button:disabled{opacity:.4;cursor:not-allowed}
input,select{background:var(--code);border:1px solid var(--border);color:var(--fg);padding:6px 9px;border-radius:6px;font-size:.85rem;width:100%}
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
</header>
<div class="layout">
  <aside class="sidebar">
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
    <div class="empty">← 选择或创建一个 engagement 开始</div>
  </main>
</div>

<script>
const API = '';
let current = null;

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
    <div class="card eng" onclick="selectEng('${s.engagement_id}')">
      <div class="id">${s.customer}</div>
      <div class="meta">
        <span class="pill ${s.profile==='manufacturing'?'ind':'tkt'}">${s.profile}</span>
        ${s.current_phase} · ${s.current_zone}
        ${s.is_complete?' ✅':''}
      </div>
      <div class="meta">id: ${s.engagement_id}</div>
    </div>`).join('');
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
      <span class="idx">${p.index}</span><span>${p.name}</span>
      ${p.industrial?'<span class="pill ind">🏭</span>':''}
      ${p.gate?`<span class="pill" title="gate: ${p.gate}">🚦</span>`:''}
      <span class="zone-tag">${zoneLabel(p.zone)}</span></div>`;
  }).join('');

  const gateHtml = Object.entries(gates).map(([slug,g])=>{
    const cls = g.passed?'pass':'fail';
    const blocks = g.blockers.map(b=>`<li>🚫 ${b}</li>`).join('');
    const warns = g.warnings.map(w=>`<li>⚠️ ${w}</li>`).join('');
    return `<div class="gate ${cls}"><div class="h"><b>${g.name}</b>
      <span>${g.passed?'✅ PASS':'❌ BLOCKED'}</span></div>
      ${blocks?`<ul>${blocks}</ul>`:''}${warns?`<ul>${warns}</ul>`:''}
      <button class="ghost" style="margin-top:6px;font-size:.75rem" onclick="recheck('${slug}')">重新校验</button></div>`;
  }).join('') || '<div class="empty">无适用 gate（当前 profile）</div>';

  document.getElementById('main').innerHTML = `
    <div class="tabs">
      <div class="tab active" onclick="tab('overview',this)">概览</div>
      <div class="tab" onclick="tab('sop',this)">SOP 阶段</div>
      <div class="tab" onclick="tab('gates',this)">Gates</div>
      <div class="tab" onclick="tab('context',this)">Context</div>
      <div class="tab" onclick="tab('forge',this)">Corpus Forge</div>
      <div class="tab" onclick="tab('kpi',this)">KPI</div>
    </div>
    <div id="t-overview">
      <div class="card">
        <h2>Engagement</h2>
        <div class="row"><label>客户</label><b>${s.customer}</b></div>
        <div class="row"><label>Profile</label><span class="pill ${s.profile==='manufacturing'?'ind':'tkt'}">${s.profile}</span></div>
        <div class="row"><label>当前阶段</label><b style="color:var(--accent)">${s.current_phase}</b> (${zoneLabel(s.current_zone)})</div>
        <div class="row"><label>下一阶段</label>${s.next_phase||'— (完成)'}</div>
        <div class="row"><label>进度</label>${curIdx+1}/${phases.phases.length}</div>
        <div class="row" style="margin-top:10px">
          <button onclick="advance(false)">⏭ 推进到下一阶段</button>
          <button class="ghost" onclick="advance(true)">force 推进</button>
        </div>
      </div>
    </div>
    <div id="t-sop" class="hidden"><div class="card"><div class="phases">${phaseHtml}</div></div></div>
    <div id="t-gates" class="hidden">${gateHtml}</div>
    <div id="t-context" class="hidden"><div class="card"><pre>${escapeHtml(JSON.stringify(s,null,2))}</pre></div></div>
    <div id="t-forge" class="hidden"><div class="card">
      <h2>语料锻造（CSV → CorpusReport）</h2>
      <input type="file" id="forge-file" accept=".csv">
      <div class="row" style="margin-top:8px"><label>min_samples</label><input id="forge-min" value="5" type="number"></div>
      <div class="row"><label>synth_per_gap</label><input id="forge-synth" value="3" type="number"></div>
      <button onclick="forge()">锻造</button>
      <div id="forge-out" style="margin-top:10px"></div>
    </div></div>
    <div id="t-kpi" class="hidden"><div class="card">
      <h2>KPI 计算</h2>
      <div class="row"><label>profile</label>
        <select id="kpi-profile"><option value="manufacturing">manufacturing</option><option value="ticket">ticket</option></select></div>
      <input type="file" id="kpi-file" accept=".json,.jsonl">
      <button onclick="runKpi()">计算</button>
      <div id="kpi-out" style="margin-top:10px"></div>
    </div></div>
  `;
}

function tab(name, el) {
  ['overview','sop','gates','context','forge','kpi'].forEach(t=>{
    const e=document.getElementById('t-'+t); if(e) e.classList.toggle('hidden', t!==name);
  });
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
}

function escapeHtml(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}

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
    <p>缺口: ${(r.gaps||[]).map(g=>g.category+'('+g.current_count+')').join(', ')||'无'}</p>
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
  alert('Profiles:\\n' + Object.entries(p).map(([k,v])=>`\\n${k}: ${v.name} (${v.industrial?'工业':'SaaS'})`).join(''));
}

refreshList();
</script>
</body>
</html>
"""
