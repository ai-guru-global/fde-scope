# 子系统 D（FDE 工作台 + 现场 journal）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把单页 engagement 控制台扩展为跨项目 FDE 工作台（全局统计 + 跨项目矩阵 + 技能库页 + 现场记录 journal + 一键沉淀）。

**Architecture:** 数据层在 `EngagementContext` 增加 `journal` 字段（Pydantic 默认值保证旧 JSON 兼容）；CLI 增加 `engage journal` 子命令；Web 增加 journal CRUD + 沉淀桥 + `/api/workbench` 聚合路由；`_DASHBOARD_HTML` 单页改造为三视图（工作台/技能库/详情），复用现有 `api()`/`escapeHtml()`/`tab()` 机制，无构建步骤。

**Tech Stack:** Python 3.11+ / Pydantic v2 / Typer+Rich / FastAPI+TestClient / pytest / ruff+mypy（CI 门禁）。

## Global Constraints

- 零新增运行时依赖（中文/时间处理用标准库）。
- Web 路径相对 cwd 约定：`Path(".fde_scope/...")`（测试经 `monkeypatch.chdir(tmp_path)` 隔离）。
- FastAPI 请求体类型（`SkillDraft`/`SkillPatch` 等）模块级 import；`except` 内 `raise` 必须 `from None`（B904）。
- ruff 规则集 E/W/F/I/C4/B/SIM/UP、line-length 110；`ruff format` 与 mypy 是 CI 门禁，收尾必须全绿。
- 测试先失败再实现（TDD）；每个 task 结束全量测试通过后 commit；测试全绿才 commit。
- UI 文案中文，代码/注释沿用现有风格（英文 docstring + 必要中文注释）。
- `EngagementContext` 增加 `journal: list[JournalEntry] = Field(default_factory=list)`，旧 JSON（无 journal 字段）加载为 `[]`，无需迁移脚本。

---

### Task 1: journal 数据模型（EngagementContext.journal）

**Files:**
- Modify: `fde_scope/engagement/context.py`（新增 `JournalEntry` + `EngagementContext.journal` 字段）
- Test: `tests/test_engagement.py`

**Interfaces:**
- Produces: `JournalEntry`（Pydantic BaseModel，字段 `id: str` 默认 `jn-{secrets.token_hex(4)}`、`ts: str` 默认 UTC ISO（seconds 精度）、`kind: Literal["research","implementation","optimization"]`、`note: str`、`skill_id: str | None = None`）；`EngagementContext.journal: list[JournalEntry] = Field(default_factory=list)`。后续 Task 2/3 依赖这些名字。

- [x] **Step 1: 写失败测试**（追加到 `tests/test_engagement.py` 末尾）

```python
# ---------------------------------------------------------------------------
# journal（现场记录）
# ---------------------------------------------------------------------------


def test_journal_entry_defaults():
    e = JournalEntry(kind="research", note="现场调研")
    assert e.id.startswith("jn-")
    assert e.ts  # ISO timestamp auto-generated
    assert e.skill_id is None


def test_context_journal_roundtrip():
    ctx = EngagementContext(id="e1", customer="Acme")
    ctx.journal.append(JournalEntry(kind="optimization", note="调优：降低误报"))
    ctx2 = EngagementContext.model_validate(ctx.model_dump())
    assert len(ctx2.journal) == 1
    assert ctx2.journal[0].kind == "optimization"
    assert ctx2.journal[0].note == "调优：降低误报"


def test_legacy_context_json_without_journal_loads(tmp_path):
    p = tmp_path / "legacy.json"
    p.write_text(json.dumps({"id": "e-old", "customer": "OldCo"}), encoding="utf-8")
    ctx = EngagementContext.load(p)
    assert ctx.journal == []
```

文件头部需确保 `import json`，并 import `JournalEntry`、`EngagementContext`（按文件现有 import 风格追加）。

- [x] **Step 2: 运行确认失败**

Run: `pytest tests/test_engagement.py -q`
Expected: FAIL（`JournalEntry` 不存在 → ImportError / AttributeError）

- [x] **Step 3: 最小实现**（`fde_scope/engagement/context.py`）

文件头部 imports 增加：
```python
import secrets
from datetime import datetime, timezone
from typing import Any, Literal
```

在 `GateRecord` 类后、`EngagementContext` 前插入：
```python
class JournalEntry(BaseModel):
    """一条现场记录：调研 / 实施 / 调优（可选关联已沉淀技能）。"""

    id: str = Field(default_factory=lambda: f"jn-{secrets.token_hex(4)}")
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    kind: Literal["research", "implementation", "optimization"]
    note: str
    skill_id: str | None = None
```

`EngagementContext` 增加字段（放在 `slos` 之后、`gate_records` 之前）：
```python
    journal: list[JournalEntry] = Field(default_factory=list)
```

- [x] **Step 4: 运行确认通过**

Run: `pytest tests/test_engagement.py -q`
Expected: PASS（含 3 个新测试）

- [x] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/engagement/context.py tests/test_engagement.py && git commit -m "feat(engagement): add journal entries to engagement context"
```

---

### Task 2: CLI `engage journal` 命令

**Files:**
- Modify: `fde_scope/cli.py`（`engage_app` 命令组末尾，`engage_list` 后）
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1 的 `JournalEntry`、`EngagementContext.journal`；已有 `_load_engagement`/`_save_engagement`/`_skill_service`（cli.py 内）。
- Produces: `engage journal <id> [--kind kind] [--note text] [--link-skill sid]`——无 `--note` 时查看（Rich Table），有 `--note` 时追加；非法 kind → Exit(2)；`--link-skill` 指向不存在的技能 → Exit(2)。

- [x] **Step 1: 写失败测试**（追加到 `tests/test_cli.py` 末尾，复用已有的 `_plant_engagement` 与 `SkillStore`）

```python
# ---------------------------------------------------------------------------
# engage journal（现场记录）
# ---------------------------------------------------------------------------


def test_journal_append_view_and_link(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _plant_engagement(tmp_path)
    # 先造一个技能供 --link-skill 校验
    r = runner.invoke(app, ["skill", "add", "--title", "现场技巧", "--category", "implementation"])
    assert r.exit_code == 0, r.stdout
    sid = SkillStore(tmp_path / ".fde_scope" / "skills").load_all()[0].id
    # 追加
    r2 = runner.invoke(
        app,
        ["engage", "journal", "eng-t", "--kind", "research", "--note", "产线A 调研完成", "--link-skill", sid],
    )
    assert r2.exit_code == 0, r2.stdout
    assert "产线A 调研完成" in r2.stdout
    # 查看
    r3 = runner.invoke(app, ["engage", "journal", "eng-t"])
    assert r3.exit_code == 0
    assert "产线A 调研完成" in r3.stdout
    assert sid in r3.stdout
    # 非法 kind
    r4 = runner.invoke(app, ["engage", "journal", "eng-t", "--kind", "oops", "--note", "x"])
    assert r4.exit_code == 2
    # 未知 skill
    r5 = runner.invoke(app, ["engage", "journal", "eng-t", "--note", "x", "--link-skill", "skill-nope"])
    assert r5.exit_code == 2
    # 不存在的 engagement
    r6 = runner.invoke(app, ["engage", "journal", "eng-nope"])
    assert r6.exit_code == 2
```

- [x] **Step 2: 运行确认失败**

Run: `pytest tests/test_cli.py::test_journal_append_view_and_link -v`
Expected: FAIL（`no such option: --kind` / No such command）

- [x] **Step 3: 最小实现**（`fde_scope/cli.py`，`engage_list` 后追加）

```python
@engage_app.command("journal")
def engage_journal(
    engagement_id: str = typer.Argument(..., help="Engagement id"),
    kind: str = typer.Option("research", "--kind", "-k", help="research | implementation | optimization"),
    note: str | None = typer.Option(None, "--note", "-n", help="记录内容；缺省时只查看"),
    link_skill: str | None = typer.Option(None, "--link-skill", help="关联技能 id（追加时校验存在性）"),
) -> None:
    """Record / view field notes (现场记录：调研/实施/调优)."""
    eng = _load_engagement(engagement_id)
    if note is None:  # 查看模式
        _banner(f"journal · {engagement_id}")
        if not eng.ctx.journal:
            console.print("[yellow]暂无现场记录。[/yellow]")
            console.print('  添加: fde-scope engage journal <id> --kind research --note "..."')
            return
        table = Table(title="Journal")
        for col in ("id", "ts", "kind", "note", "skill"):
            table.add_column(col)
        for e in eng.ctx.journal:
            table.add_row(e.id, e.ts, e.kind, e.note, e.skill_id or "—")
        console.print(table)
        return
    if kind not in ("research", "implementation", "optimization"):
        console.print(f"[red]Invalid kind:[/red] {kind} (research | implementation | optimization)")
        raise typer.Exit(2)
    if link_skill:
        try:
            _skill_service().get(link_skill)
        except KeyError:
            console.print(f"[red]Unknown skill:[/red] {link_skill}")
            raise typer.Exit(2) from None
    from .engagement.context import JournalEntry

    entry = JournalEntry(kind=kind, note=note, skill_id=link_skill)
    eng.ctx.journal.append(entry)
    _save_engagement(eng)
    console.print(f"✅ 已记录 [cyan]{entry.id}[/cyan] ({kind}) · {entry.note}")
```

注意 `from .engagement.context import JournalEntry` 放函数内（与 `_load_engagement` 内 import 风格一致）。

- [x] **Step 4: 运行确认通过**

Run: `pytest tests/test_cli.py::test_journal_append_view_and_link -v`
Expected: PASS

- [x] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/cli.py tests/test_cli.py && git commit -m "feat(cli): add engage journal command for field notes"
```

---

### Task 3: journal Web API + 沉淀桥

**Files:**
- Modify: `fde_scope/web/app.py`（`evaluate_gate` 后、`update_context` 前插入 3 个路由）
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: Task 1 的 `JournalEntry`；已有 `_load`/`_save`/`_skill_service`。
- Produces:
  - `GET /api/engagements/{eid}/journal` → `list[dict]`（entry.model_dump()）
  - `POST /api/engagements/{eid}/journal`，body `{kind?, note, skill_id?}` → 追加并返回 entry dict；缺 note / 非法 kind → 422
  - `POST /api/engagements/{eid}/journal/{jid}/skill` → 沉淀为技能草稿（kind→category 映射预填、source_engagement=eid），回写 `entry.skill_id` 并落盘，返回 SkillRecord dict；jid 不存在 → 404；已关联 → 409

- [x] **Step 1: 写失败测试**（追加到 `tests/test_web.py` 末尾，复用 `client` fixture）

```python
# ---------------------------------------------------------------------------
# journal（现场记录）
# ---------------------------------------------------------------------------


def test_journal_api_roundtrip(client) -> None:
    eid = client.post("/api/engagements", data={"customer": "Acme"}).json()["engagement_id"]
    assert client.get(f"/api/engagements/{eid}/journal").json() == []
    r = client.post(f"/api/engagements/{eid}/journal", json={"kind": "research", "note": "产线 A 调研"})
    assert r.status_code == 200
    jid = r.json()["id"]
    assert r.json()["kind"] == "research"
    entries = client.get(f"/api/engagements/{eid}/journal").json()
    assert len(entries) == 1 and entries[0]["note"] == "产线 A 调研"
    # 校验：非法 kind / 空 note
    assert (
        client.post(f"/api/engagements/{eid}/journal", json={"kind": "oops", "note": "x"}).status_code == 422
    )
    assert client.post(f"/api/engagements/{eid}/journal", json={"note": "  "}).status_code == 422


def test_journal_to_skill_bridge(client) -> None:
    eid = client.post("/api/engagements", data={"customer": "BMW"}).json()["engagement_id"]
    jid = client.post(
        f"/api/engagements/{eid}/journal", json={"kind": "implementation", "note": "部署完成"}
    ).json()["id"]
    r = client.post(f"/api/engagements/{eid}/journal/{jid}/skill")
    assert r.status_code == 200
    rec = r.json()
    assert rec["category"] == "implementation"  # kind → category 映射
    assert rec["source_engagement"] == eid
    assert rec["status"] == "draft"
    # skill_id 回写 journal entry
    entries = client.get(f"/api/engagements/{eid}/journal").json()
    assert entries[0]["skill_id"] == rec["id"]
    # 重复沉淀 → 409；未知 jid → 404
    assert client.post(f"/api/engagements/{eid}/journal/{jid}/skill").status_code == 409
    assert client.post(f"/api/engagements/{eid}/journal/jn-nope/skill").status_code == 404
```

- [x] **Step 2: 运行确认失败**

Run: `pytest tests/test_web.py::test_journal_api_roundtrip tests/test_web.py::test_journal_to_skill_bridge -v`
Expected: FAIL（404 Not Found）

- [x] **Step 3: 最小实现**（`fde_scope/web/app.py`，插在 `evaluate_gate` 与 `update_context` 之间）

```python
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
```

- [x] **Step 4: 运行确认通过**

Run: `pytest tests/test_web.py::test_journal_api_roundtrip tests/test_web.py::test_journal_to_skill_bridge -v`
Expected: PASS

- [x] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/web/app.py tests/test_web.py && git commit -m "feat(web): journal API and one-click skill capture bridge"
```

---

### Task 4: 工作台聚合 API `/api/workbench`

**Files:**
- Modify: `fde_scope/web/app.py`（skills API 段之前插入）
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: 已有 `_all_engagements()`、`_skill_service()`、`SkillStatus`。
- Produces: `GET /api/workbench` → `{"stats": {active_projects, phase_distribution, draft_skills, total_skills}, "matrix": [eng.status()...], "recent_skills": [SkillRecord.model_dump()...]}`（recent_skills 按 updated_at 倒序取前 5 条 published）。Task 5 页面依赖此结构。

- [x] **Step 1: 写失败测试**（追加到 `tests/test_web.py` 末尾）

```python
# ---------------------------------------------------------------------------
# workbench（工作台聚合）
# ---------------------------------------------------------------------------


def test_workbench_api_empty(client) -> None:
    data = client.get("/api/workbench").json()
    assert data["stats"] == {
        "active_projects": 0,
        "phase_distribution": {},
        "draft_skills": 0,
        "total_skills": 0,
    }
    assert data["matrix"] == []
    assert data["recent_skills"] == []


def test_workbench_api_stats_matrix_recent(client) -> None:
    client.post("/api/engagements", data={"customer": "Acme"})
    client.post("/api/engagements", data={"customer": "BMW", "profile": "manufacturing"})
    wb = client.get("/api/workbench").json()
    assert wb["stats"]["active_projects"] == 2
    assert wb["stats"]["phase_distribution"] == {"qualification": 2}
    assert len(wb["matrix"]) == 2
    assert wb["matrix"][0]["customer"] in ("Acme", "BMW")
    # 技能：草稿计入 draft_skills；发布后进入 recent_skills
    sid = client.post(
        "/api/skills", json={"title": "OPC UA 踩坑", "category": "implementation", "tags": ["opcua"]}
    ).json()["id"]
    assert client.get("/api/workbench").json()["stats"]["draft_skills"] == 1
    client.post(f"/api/skills/{sid}/publish")
    wb2 = client.get("/api/workbench").json()
    assert wb2["stats"]["draft_skills"] == 0
    assert wb2["stats"]["total_skills"] == 1
    assert wb2["recent_skills"][0]["id"] == sid
```

- [x] **Step 2: 运行确认失败**

Run: `pytest tests/test_web.py::test_workbench_api_empty tests/test_web.py::test_workbench_api_stats_matrix_recent -v`
Expected: FAIL（404 Not Found）

- [x] **Step 3: 最小实现**（`fde_scope/web/app.py`，插在 `compute_kpis` 之后、`# skills API` 段之前）

```python
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
```

- [x] **Step 4: 运行确认通过**

Run: `pytest tests/test_web.py::test_workbench_api_empty tests/test_web.py::test_workbench_api_stats_matrix_recent -v`
Expected: PASS

- [x] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/web/app.py tests/test_web.py && git commit -m "feat(web): workbench aggregation API"
```

---

### Task 5: 工作台页面改造（`_DASHBOARD_HTML` 三视图 + 技能库 + 现场记录 tab）

**Files:**
- Modify: `fde_scope/web/app.py` `_DASHBOARD_HTML`（623-944 行）
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: Task 3 的 journal API、Task 4 的 `/api/workbench`、已有 `/api/skills*` 路由。
- Produces: `/console` 三视图单页——`#view-workbench`（统计条 + 矩阵 + 最近沉淀）、`#view-skills`（搜索/筛选/卡片/新建/草稿队列）、`#view-detail`（原详情 + 新增"现场记录"tab，追加与一键沉淀）；sidebar 顶部导航按钮；`location.hash === '#skills'` 直达技能库。

- [x] **Step 1: 写失败测试**（追加到 `tests/test_web.py` 末尾）

```python
def test_console_has_workbench_and_skills_views(client) -> None:
    """控制台包含工作台/技能库视图与现场记录 tab（单页无构建）。"""
    r = client.get("/console")
    assert r.status_code == 200
    assert 'id="view-workbench"' in r.text
    assert 'id="view-skills"' in r.text
    assert "📊 工作台" in r.text
    assert "📚 技能库" in r.text
    assert "现场记录" in r.text
    assert "沉淀为技能" in r.text
    assert "草稿审阅队列" in r.text
```

- [x] **Step 2: 运行确认失败**

Run: `pytest tests/test_web.py::test_console_has_workbench_and_skills_views -v`
Expected: FAIL（`id="view-workbench"` 不在页面中）

- [x] **Step 3: 实现**（5 处 SearchReplace，均在 `_DASHBOARD_HTML` 内）

**3a. sidebar 顶部加导航**（锚点：`  <aside class="sidebar">\n    <h2>Engagements</h2>`）：

```html
  <aside class="sidebar">
    <div class="row" style="margin-bottom:14px">
      <button style="flex:1" onclick="go('workbench')">📊 工作台</button>
      <button class="ghost" style="flex:1" onclick="go('skills')">📚 技能库</button>
    </div>
    <h2>Engagements</h2>
```

**3b. main 区域改为三视图容器**（锚点：`  <main class="main" id="main">\n    <div class="empty">← 选择或创建一个 engagement 开始</div>\n  </main>`）：

```html
  <main class="main" id="main">
    <div id="view-workbench"></div>
    <div id="view-skills" class="hidden"></div>
    <div id="view-detail" class="hidden"><div class="empty">← 选择或创建一个 engagement 开始</div></div>
  </main>
```

**3c. renderDetail 的 tabs 加"现场记录"**（锚点：`      <div class="tab" onclick="tab('kpi',this)">KPI</div>\n    </div>`）：

```html
      <div class="tab" onclick="tab('kpi',this)">KPI</div>
      <div class="tab" onclick="tab('journal',this)">现场记录</div>
    </div>
```

**3d. renderDetail 的 tab 面板加 `#t-journal`**（锚点：`    <div id="t-kpi" class="hidden"><div class="card">` 整段，在 `<div id="t-kpi"...` 前插入）：

```html
    <div id="t-journal" class="hidden">${journalHtml(s.context)}</div>
    <div id="t-kpi" class="hidden"><div class="card">
```

**3e. renderDetail 末尾改渲染目标 + 显示 detail 视图**（锚点：`    </div></div>\n  `;\n}`，即 kpi 面板结束后；把 `` `;\n}`` 前两行改为）：

原：
```
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
```
改为（仅改末尾两行）：
```
      <input type="file" id="kpi-file" accept=".json,.jsonl">
      <button onclick="runKpi()">计算</button>
      <div id="kpi-out" style="margin-top:10px"></div>
    </div></div>
  `;
  document.getElementById('view-detail').innerHTML = html;
  showView('detail');
}
```
注意：`renderDetail` 中把原 `document.getElementById('main').innerHTML = \`` 改为 `const html = \``（模板字符串赋给变量），末尾再加两行。两处必须同步修改。

**3f. tab() 函数数组加 'journal'**（锚点：`  ['overview','sop','gates','context','forge','kpi'].forEach`）：

```js
  ['overview','sop','gates','context','forge','kpi','journal'].forEach(t=>{
```

**3g. 新增 JS 函数 + hash 处理**（锚点：`const API = '';\nlet current = null;` 之后插入全部新函数；锚点 `refreshList();\n</script>` 改为 hash 初始化）：

```js
function showView(name) {
  ['workbench','skills','detail'].forEach(v=>{
    const e=document.getElementById('view-'+v); if(e) e.classList.toggle('hidden', v!==name);
  });
}

function go(name) {
  showView(name);
  if (name==='skills') location.hash = 'skills';
  else if (location.hash) history.replaceState(null,'',location.pathname);
  if (name==='workbench') loadWorkbench();
  if (name==='skills') loadSkills();
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
```

初始加载（锚点 `refreshList();\n</script>`）：
```js
refreshList();
if (location.hash === '#skills') go('skills'); else loadWorkbench();
window.addEventListener('hashchange', () => {
  if (location.hash === '#skills') go('skills');
  else if (location.hash) go('workbench');
});
</script>
```

- [x] **Step 4: 运行确认通过**

Run: `pytest tests/test_web.py::test_console_has_workbench_and_skills_views -v`
Expected: PASS

- [x] **Step 5: 全量 + 提交**

```bash
pytest -q && git add fde_scope/web/app.py tests/test_web.py && git commit -m "feat(web): workbench three-view console with skill library and field journal"
```

---

### Task 6: 收尾（README + 全量门禁）

**Files:**
- Modify: `README.md`

- [x] **Step 1: README 更新**

1. CLI reference 中 `engage` 行改为：`engage    [SOP] init / status / advance / rollback / journal / list`
2. `web` 行改为：`web       Launch the Web UI (workbench + skills + engagement console)`
3. "💡 Skill 沉淀"小节后新增小节：

```markdown
## 🖥️ FDE 工作台（Workbench + 现场记录）

`fde-scope web` 打开的单页控制台现在是一个跨项目工作台：

- **工作台首页**（`/console`）：全局统计条（进行中项目 / 阶段分布 / 待审草稿 / 技能总数）、
  跨项目矩阵（客户/阶段/zone/门禁/最近更新，点击进入详情）、最近沉淀技能；
- **技能库页**（`/console#skills`）：搜索 + 分类/状态筛选 + 技能卡片 +
  新建技能表单 + 草稿审阅队列（一键发布/编辑）；
- **现场记录**（详情页 tab）：`research / implementation / optimization` 三类记录，
  任意一条可一键"沉淀为技能"（kind → category 自动映射、关联来源 engagement）。

CLI 等价入口：`fde-scope engage journal <id> --kind research --note "..." [--link-skill <sid>]`。
```

- [x] **Step 2: 全量门禁**

```bash
ruff check fde_scope tests && ruff format --check fde_scope tests && mypy fde_scope && pytest -q
```

Expected: 全部通过（ruff 0 错误、format 无 diff、mypy 0 错误、pytest 全绿；测试计数 296 + 新增数）。若有格式问题：`ruff check --fix fde_scope tests && ruff format fde_scope tests` 后重跑。若 mypy 报错：按类型收窄修复（如 `body.get(...)` 加 `isinstance` 检查），不得 `# type: ignore`。

- [x] **Step 3: 提交**

```bash
git add README.md && git commit -m "docs: document workbench and field journal"
```

---

## 计划自审记录

- spec §3.2（三段式工作台）→ Task 4（API）+ Task 5（页面）；§3.2 技能库页 → Task 5 `loadSkills`（搜索/筛选/卡片/新建/草稿队列）；§3.3 journal → Task 1（模型）/Task 2（CLI）/Task 3（Web + 沉淀桥 + 兼容）；§3.4 测试策略 → 各 Task 测试。
- 兼容性：`journal` 字段带 `default_factory`，Task 1 有专门旧 JSON 测试。
- 类型一致性：`JournalEntry.kind` 为 `Literal["research","implementation","optimization"]`，Task 3 映射 dict 键即这三值；`recent_skills`/`matrix`/`stats` 字段名在 Task 4 定义、Task 5 消费。
- 已知偏差（相对 spec 简化，YAGNI）：技能库不做编辑弹窗（`prompt()` 编辑正文）；新建表单不含 phase/gate/profile 高级字段（保留 API 能力，页面保持最小）；矩阵"最近更新时间"用 gate_records 最新 checked_at。
