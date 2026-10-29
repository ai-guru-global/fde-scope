# FDE Scope Web 控制台 REST API 参考

> 与 `fde_scope/web/app.py` + `fde_scope/web/guided_api.py` 实际路由逐条核对。
> 计数（**2026-10-06 快照，会随功能增长漂移**，引用前请先跑下面的复测命令）：装饰器声明
> **72** 条 verb+path；`app.openapi()` 实际暴露 **69** 条 / **63** 个路径。差值恰为
> **3** 条安装态兜底 `GET /GTM/{rest:path}`、`/catalog/{rest:path}`、`/gh-resources/{rest:path}`
> —— wheel 内由 `fde_scope/_data/` 提供，源码 checkout 里改由 `StaticFiles` 挂载承担，
> 因此不出现在 OpenAPI 表中。
> `/api/` 下 51 条（45 个路径），页面与其他端点 18 条；GET 45 / POST 22 / PATCH 1 / DELETE 1，
> **写操作 24 条**。
> 复测（served）：`python -c "from fde_scope.web.app import app; print(len({(m,p) for p,ops in app.openapi()['paths'].items() for m in ops}))"`
> 复测（declared）：`python -c "import sys;sys.path.insert(0,'tests');import test_architecture_guard as g;print(len(g._declared_routes()))"`
> 另有 11 处**对外宣称**的路由数（README ×4、features ×4、`web/app.py` ×1、`web/i18n.py` ×2），
> 由 `tests/test_architecture_guard.py::test_web_route_count_claim_is_honest` 断言三者相等：
> 新增路由后要同步的是那 11 处宣称，不是本文——本文只描述当前树里有什么。
> 默认基址 `http://127.0.0.1:8080`（`fde-scope web --host --port` 可改）。
> 所有示例假设已设置认证 token；本地未设 token 时可省略认证头。

## 认证（先读）

- token 只从环境变量 **`FDE_SCOPE_API_TOKEN`** 读取，不落文件/日志/响应。
- **未设置该变量时认证关闭，但仅限回环**：从 `127.0.0.1` / `::1` 到达的请求照常
  放行（本地单机零摩擦），从非 loopback 地址到达的请求返回
  `403 {"detail": "authentication is off and this request arrived on the …"}`。
  判据是连接被 accept 时落在哪个地址（`scope["server"]`），不是 `--host` 绑了啥：
  同一个 `0.0.0.0` 监听器，本机访问 200、局域网访问 403。
- 设置后，除白名单外的所有路由要求以下两种头之一，否则返回
  `401 {"detail": "invalid or missing API token"}`：
  - `Authorization: Bearer <token>`
  - `X-API-Key: <token>`
- 白名单路径（免认证）：`/api/health`、`/`、`/console`、`/en/`、`/en/console`
  （HTML 壳本身不含数据，其发起的 JSON 调用仍需 token）。
- 从 CLI 绑定非回环地址还需 `FDE_SCOPE_ALLOW_REMOTE=1`；`FDE_SCOPE_API_TOKEN`
  缺失时同样拒绝启动（opt-in 只声明「监听这张网卡」，不能顺带关掉认证）。
- 上面的 403 由中间件逐请求判定，所以绕过 CLI 直接 `uvicorn`/`gunicorn`
  启动也覆盖得到。**同机反向代理落在回环上，不会被它拦**——代理必须自己鉴权。

```bash
export FDE_SCOPE_API_TOKEN="$(openssl rand -hex 32)"
fde-scope web
curl -H "X-API-Key: $FDE_SCOPE_API_TOKEN" http://127.0.0.1:8080/api/engagements
```

## 通用约定

- Form 参数端点用 `-F key=value`（`multipart/form-data`）；JSON 端点用
  `-H 'Content-Type: application/json' -d '{...}'`。
- 文件上传统一上限 **10 MiB**，超限返回 413。
- 常见错误码：400 参数语义错误 · 401 未认证 · 403 认证关闭但该请求从非回环
  地址到达 · 404 资源不存在 · 413 文件过大 · 422 参数缺失/校验失败。
- engagement id（下称 `{eid}`）由服务端生成，形如 `eng-<customer>-<profile>-<6位hex>`。

---

## Health

### `GET /api/health`（免认证）

存活 + 就绪探针。**degraded 时也返回 HTTP 200**（进程活着，子系统可能不健康）。

```bash
curl http://127.0.0.1:8080/api/health
```

响应：

```json
{
  "status": "ok",
  "version": "0.1.0",
  "checks": {
    "data_root":   {"ok": true, "path": "/abs/path"},
    "reports_dir": {"ok": true},
    "llm":         {"ok": true, "configured": false},
    "engagements_count": {"ok": true, "count": 3}
  }
}
```

`llm.configured` 只查 env 是否配置，**不**向 LLM 发请求。任一 `ok: false` → `status: degraded`。

## Profiles & Phases

### `GET /api/profiles`

返回全部场景档案（`ticket` / `manufacturing`）：`{slug: {name, industrial, connectors, kpis}}`。

### `GET /api/phases?profile=ticket`

返回该 profile 的阶段序列 `{phases: [...], is_industrial: bool}`。未知 profile → 404。

```bash
curl "http://127.0.0.1:8080/api/phases?profile=manufacturing" -H "X-API-Key: $FDE_SCOPE_API_TOKEN"
```

## Engagement

### `GET /api/engagements`

列出全部 engagement 的状态摘要数组（`eng.status()`：`engagement_id` / `customer` /
`profile` / `current_phase` / `current_zone` / `gate` / `gate_passed` / `gate_records` /
`is_complete` 等）。

### `POST /api/engagements`（Form）

创建 engagement。参数：`customer`（必填）、`profile`（默认 `ticket`）。
返回新 engagement 的状态摘要。写审计事件 `engagement.create`。

```bash
curl -X POST http://127.0.0.1:8080/api/engagements \
  -H "X-API-Key: $FDE_SCOPE_API_TOKEN" \
  -F "customer=示例客户" -F "profile=ticket"
```

### `GET /api/engagements/{eid}`

状态摘要 + 完整 `context`（现场/干系人/成功标准/SLO/功能安全/产物等）。

### `POST /api/engagements/{eid}/advance`（Form）

推进到下一阶段，**每次实时重评当前阶段所有 gate**。参数：

| 参数 | 说明 |
|---|---|
| `force` | true 时豁免拦截；**必须同时给非空 `reason`，否则 422** |
| `reason` | 强制推进理由（写审计） |
| `operator` | 操作者（写审计） |

响应二选一：

```json
{"advanced": true,  "status": { … }}
{"advanced": false, "result": {"passed": false, "blockers": ["…"], "warnings": ["…"]}}
```

走完最后一阶段返回 `{"advanced": false, "reason": "complete"}`。
写审计事件 `engagement.advance`。

### `POST /api/engagements/{eid}/gate/{slug}`（Form）

对指定 gate 做一次评估并记录。参数：`operator`（可选）。未知 slug → 404。
响应：`{"slug", "passed", "blockers", "warnings"}`。写审计 `engagement.gate_evaluate`。

### `GET /api/engagements/{eid}/gates`

实时评估所有适用 gate，返回 `{slug: {name, passed, blockers, warnings}}`（只读，不落记录）。

### `POST /api/engagements/{eid}/context`（JSON body）

补丁式更新 engagement context，支持字段：`site`、`safety`、`success_criteria`、
`stakeholders`、`slos`（均按对应模型校验，失败 422），以及 `assets`（dict merge）。
返回更新后的状态摘要。

```bash
curl -X POST http://127.0.0.1:8080/api/engagements/$EID/context \
  -H "X-API-Key: $FDE_SCOPE_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"success_criteria": ["首响时间 P95 < 5 分钟", "意图准确率 ≥ 0.9"]}'
```

### Guided mode（引导）

只读引导 + 草稿，**永不替你过 gate**；产出仍须走正常 context/gate 通道。

- `GET /api/engagements/{eid}/guided` — 当前阶段白话说明、产出清单、各 gate 的
  blocker + `next_steps`（下一步做什么）、技能手册深链、已保存的目标计划。
- `POST /api/engagements/{eid}/guided/draft-context`（JSON `{"description": "…"}`）—
  由自由文本 AI 起草 site/stakeholders/success_criteria/slos（无 LLM 时规则兜底），
  返回 `{"draft", "used_llm", "current", "field_guide"}`。**不落盘**，确认后须另行
  `POST .../context` 写入。
- `POST /api/engagements/{eid}/guided/plan`（JSON `{"goal": "…"}`）— 目标拆解为
  按阶段的任务清单，持久化到 `ctx.assets["guided_plan"]`，返回 `{"plan", "used_llm", "saved": true}`。

### `GET /api/engagements/{eid}/journal` / `POST`（JSON）

现场记录。GET 返回条目数组；POST body：`{"note": "…", "kind": "research|implementation|optimization", "skill_id": 可选}`。

### `POST /api/engagements/{eid}/journal/{jid}/skill`

把一条 journal 沉淀为技能草稿（kind → category 自动映射）。已关联过技能 → 409。

### `POST /api/engagements/{eid}/archive`

归档：engagement JSON 移入 `.fde_scope/archive/`，退出所有列表。写审计 `engagement.archived`。

### `DELETE /api/engagements/{eid}`（Form）

删除 engagement 与其证据目录（GDPR 删除权）。**`confirm` 必须与客户名逐字一致**，
否则 400。审计日志本身保留（删除权针对客户数据，不针对合规轨迹）。

## Audit（审计）

### `GET /api/engagements/{eid}/audit?format=md`

返回 `{"engagement_id", "count", "events": [...]}`；加 `?format=md` 额外生成
`reports/audit_{eid}.md` 并在响应中带 `path`。

### `GET /api/engagements/{eid}/audit/export`

只导出 Markdown：`{"engagement_id", "count", "path"}`。

审计日志本体是 append-only 的 `.fde_scope/audit.jsonl`，凭据永不写入。

## Handoff（移交）

### `POST /api/engagements/{eid}/handoff`（Form）

生成 runbook（`reports/runbook_{eid}.md`）+ 移交包（`reports/handoff_package_{eid}.json`），
两个文件的 sha256 + 字节数写入审计 `handoff.package`。参数：
`accept`（true 时另写 `handoff.accepted` 验收事件）、`boundary` / `termination`
（G7③ 适用边界 / G7④ 终止条件）、`operator`。

`boundary` / `termination` 落在移交包 JSON 的两个键里，**不是审计 detail 的字段**——
审计只记 `handoff_package_{eid}.json` 的 sha256 与字节数，所以这两条文本的可追溯性
来自"哈希过的文件"，不来自"审计里能直接 grep 到"。缺了它们 `handoff_signoff` 只出
⚠️，不阻塞。

两者的省略语义与四件套**相反**：省略 = 保留上一版已记的文本（重新装配快照 SLO 时
不该把 FDE 写过的自由文本冲掉）；传空串 = 删除。证据路径没有这种保留——一次装配没带
`runbook` 就是洞，静默复用上一次的路径只会让过期证据顶着新时间戳发出去。
注意 Web 控制台的交接 tab 只在文本框非空时才 `fd.set(...)`，所以**清空文本框 = 保留**，
控制台没有删除这条路；要删只能直接打 API 传 `boundary=` 或用 CLI `--boundary ""`。
代码原文：`fde_scope/engagement/handoff.py:74-92`、`fde_scope/web/app.py:385-419`、
`fde_scope/web/app.py:3405-3412`。

响应：`{"engagement_id", "customer_accepted", "runbook", "package", "summary"}`。

## Evidence（证据留存）

### `POST /api/engagements/{eid}/evidence`（Form）

附加外部证据文件（FAT/SAT 签字扫描件等）。参数：`name`（必填）、`operator`（可选）、
`file`（上传）或 `path`（服务器本地路径）**二选一**，都没有 → 422。单文件 ≤ 10 MiB。
文件存入 `.fde_scope/evidence/{eid}/`，sha256 + UTC 时间戳入索引与审计。

### `GET /api/engagements/{eid}/evidence`

返回 `{"engagement_id", "evidence": [{name, sha256, bytes, ts, operator}]}`。

## Corpus Forge（语料锻造）

### `POST /api/forge`（Form，multipart）

上传 CSV（UTF-8，≤ 10 MiB）锻成语料。参数：`file`（必填）、`min_samples`（默认 5）、
`synth_per_gap`（默认 3）。配置了 LLM env 时自动启用 LLM 补盲合成，否则纯规则。

```bash
curl -X POST http://127.0.0.1:8080/api/forge \
  -H "X-API-Key: $FDE_SCOPE_API_TOKEN" \
  -F file=@examples/quickstart_csv/sample_tickets.csv -F min_samples=5
```

响应：`{"report_id", "html_url", "total", "real", "synthetic", "dropped", "pii_masked", "gaps"}`。
报告落盘 `reports/corpus_report_{report_id}.html/.json`，HTML 经 `/reports/` 可直接浏览。

## KPI

### `POST /api/kpi`（Form，multipart）

参数：`profile`（默认 `manufacturing`）、`file`（JSONL，每行一个样本对象）。
返回 `{"profile", "kpis": {...}, "sample_count"}`。未知 profile → 404；非 JSONL → 422。

## Deploy（部署预检）

### `POST /api/deploy/plan`（JSON body）

`fde-scope deploy` 的 dry-run：对 tenant payload 返回装配计划 manifest——每个角色
Agent 绑定了哪些连接器工具、对哪个物理源、哪些还缺数据源（诚实标注 unbound 及原因）。
与 CLI / PawApp 同一实现（`build_deploy_plan`），零 AgentScope 依赖、不调模型。
body 校验失败 → 422。

```bash
curl -X POST http://127.0.0.1:8080/api/deploy/plan \
  -H "X-API-Key: $FDE_SCOPE_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"id":"acme","agents":[{"name":"数据员","role":"数据分析"}],"sources":{"csv":"data/t.csv"}}'
```

## Workbench

### `GET /api/workbench`

跨项目聚合：`{"stats": {active_projects, phase_distribution, draft_skills, total_skills},
"matrix": [...], "recent_skills": [...(最近 5 条 published)]}`。

## Skills（技能库）

| 方法/路径 | 说明 |
|---|---|
| `GET /api/skills?q=&category=&tag=&status=published&profile=&gate=&phase=` | 检索（status 默认 published） |
| `POST /api/skills` | 创建草稿（JSON `SkillDraft`：`title` / `category` / `tags` / `body_md` / `phase_slug` / `gate_slug` / `applies_to` / `source` / `source_engagement`；`id` 由服务端生成） |
| `GET /api/skills/drafts` | 草稿审阅队列 |
| `GET /api/skills/facets` | 技能库去重后的 facet 取值（供控制台过滤器） |
| `GET /api/skills/{sid}` | 详情（404 不存在） |
| `PATCH /api/skills/{sid}` | 编辑（JSON `SkillPatch`：`title` / `tags` / `body_md` / `phase_slug` / `gate_slug` / `applies_to`；未提供的字段保持不变，`id` 不可外部设置。任一变更 → `version` +1 并刷新 `updated_at`） |
| `POST /api/skills/{sid}/publish` | 发布（仅 `draft` 可发布，否则 400；写审计 `skill.publish`） |
| `POST /api/skills/{sid}/archive` | 归档（已归档再归档 400） |
| `POST /api/skills/{sid}/export` | 导出，JSON body `{"format": "agentscope"}`（或 `"qwenpaw"`），返回 `{"skill_id", "format", "files": [{name, content}]}` |

category ∈ `research | implementation | optimization | methodology`；
status ∈ `draft | published | archived`。

## Ontology（本体库，只读）

| 方法/路径 | 说明 |
|---|---|
| `GET /api/ontology/schemas` | TBox schema 列表（内置 fde-core / mfg-overlay / fde-corpus-taxonomy） |
| `GET /api/ontology/stores` | 工作区 ABox 实例库列表 |
| `GET /api/ontology/schema/{schema_id}` | schema 详情（404 未知） |
| `GET /api/ontology/store/{store_id}` | 实例库详情（404 未知） |
| `GET /api/ontology/export/{target_id}` | JSON-LD 1.1 导出：schema 直出；store 联同其 TBox 上下文（与 CLI `fde-scope ontology export` 同语义） |

## HTML 页面与静态挂载（免认证白名单）

`auth.PUBLIC_PATHS` 共 **76 条精确路径**（不是前缀，匹配是
`request.url.path in PUBLIC_PATHS`，所以 `/docs/` 本身、`/catalog/` 仍被拦）。
下表只列最常访问的，**全量以「路由全量对照」+ `auth.py` 为准**：

| 路径 | 说明 |
|---|---|
| `GET /` · `GET /console` | 中文功能总览 / Engagement 控制台（白名单，但页面里的 JSON 调用仍需 token） |
| `GET /en/` · `GET /en/console` | English 版本（白名单） |
| `GET /certification` · `/glossary` · `/course` · `/sop` · `/resources` · `/docs/{slug}`（及各 `/en/` 变体） | 只读内容壳，无 engagement 数据 → 白名单 |
| `GET /static/favicon.svg` | 浏览器取图标不带认证头，故白名单 |
| `/reports/*` | 生成的 runbook / 语料报告 / 审计导出（StaticFiles；**不在白名单**，认证开启时需 token） |
| `/catalog/*` | 技能手册库静态站（仓库含生成产物时挂载；两个 `index.html` 在白名单，其余需 token） |

## 路由全量对照（69 条 served）

上面各节按功能挑选讲解，**不声称穷举**；本节是穷举锚点：69 条 served
`(verb, path)` 逐条列出，与 `app.openapi()` 一一对应。

**本表没有测试守卫**（`test_architecture_guard.py` 只核对代码里的声明数与
`served` 数，不读本文）。它靠下面的命令重生成来保持正确——新增路由后请重跑，
而不是手工加行：

```bash
python - <<'PY'
import inspect
from fastapi.routing import APIRoute
from fde_scope.web.app import app
from fde_scope.web import guided_api
pairs = []
def walk(rs):
    for r in rs:
        sub = getattr(r, "routes", None)
        if sub: walk(sub)
        if isinstance(r, APIRoute):
            for m in r.methods: pairs.append((m.lower(), r.path, r.endpoint))
walk(app.routes)
for r in guided_api.router.routes:          # _IncludedRouter 隐藏这 3 条
    if isinstance(r, APIRoute):
        for m in r.methods: pairs.append((m.lower(), r.path, r.endpoint))
served = {(m.lower(), p) for p, ops in app.openapi()["paths"].items() for m in ops}
assert served <= {(m, p) for m, p, _ in pairs}
for m, p, ep in sorted(pairs, key=lambda t: (t[1], t[0])):
    if (m, p) in served:
        doc = (inspect.getdoc(ep) or "").split("\n\n")[0].replace("\n", " ")
        print(f"{m.upper():6} {p:52} {doc[:70]}")
PY
```

- 说明列取自每个 `APIRoute` `endpoint` 的 docstring **首段**（折叠换行，不截断）。
- 带 `†` 的 28 条处理函数**没有 docstring**，说明按处理函数源码逐条核对补写。
  给它们补 docstring 才是根治（见文末「文档自身的已知缺口」）。
- **读/写列是 HTTP verb，不是「是否落盘」**。两条方向都有例外：
  `POST /api/deploy/parse`、`POST /api/deploy/plan`（docstring 自称 dry-run）、
  `POST /api/engagements/{eid}/guided/draft-context`（docstring 自称 pure draft）和
  `POST /api/ontology/diff`（只 load + 比较）四条 POST **不写任何状态**；反过来
  `POST/PATCH /api/skills*` 的写发生在 `_skill_service()` → store 层，处理函数体里
  看不见。不变式 7 关心的是 verb，所以本表按 verb 标。
- 另有 3 条安装态兜底 `GET /GTM/{rest:path}`、`GET /catalog/{rest:path}`、
  `GET /gh-resources/{rest:path}` **不在本表**：wheel 内由 `fde_scope/_data/` 提供、
  源码 checkout 里由 `StaticFiles` 挂载承担，因此不出现在 `app.openapi()` 中
  （声明 72 − served 69 = 这 3 条）。

| Verb + path | 读/写 | 说明 |
|---|---|---|
| `GET /` | 读 | The landing page: a one-screen overview of every capability. |
| `GET /api/connectors` | 读 | Connector registry status. Import-level truth only: a slug in the registry imported cleanly, one in the module table but not the registry is missing its optional dependency. Runtime reachability of a customer system is deliberately NOT probed from a GET — constructing connections is a deploy-time act. Env credentials surface as booleans, never values. |
| `POST /api/deploy/parse` | 写 | Parse the deploy form's raw textarea text server-side. |
| `POST /api/deploy/plan` | 写 | Dry-run `fde-scope deploy` for a tenant payload and return the manifest. |
| `GET /api/engagements` | 读 | 全部 engagement 的 `status()` 摘要数组。 † |
| `POST /api/engagements` | 写 | 创建 engagement（Form：`customer`、`profile`）。 † |
| `DELETE /api/engagements/{eid}` | 写 | Delete the engagement JSON + its evidence (right to erasure). |
| `GET /api/engagements/{eid}` | 读 | 单个 engagement：`status()` + 完整 `context`。 † |
| `POST /api/engagements/{eid}/advance` | 写 | 推进状态机；**每次调用都重评当前阶段门禁**（不变式 1）。 † |
| `POST /api/engagements/{eid}/archive` | 写 | Archive the engagement (out of every listing) via the storage backend. |
| `GET /api/engagements/{eid}/audit` | 读 | Audit events for one engagement (JSON); `?format=md` also exports a file. |
| `GET /api/engagements/{eid}/audit/export` | 读 | Write a Markdown audit report for *eid* into the reports dir. |
| `POST /api/engagements/{eid}/context` | 写 | Patch an engagement context (site / safety / slo / stakeholders / assets). |
| `GET /api/engagements/{eid}/evidence` | 读 | 证据索引（`_read_evidence_index`），不含文件内容。 † |
| `POST /api/engagements/{eid}/evidence` | 写 | Attach an external evidence file (signed FAT/SAT scan …) to an engagement. |
| `POST /api/engagements/{eid}/gate/{slug}` | 写 | 评估单个 gate 并落审计（未知 slug 404）。 † |
| `GET /api/engagements/{eid}/retrospective` | 读 | 复盘报告：audit 流重放成阶段时间线 + SLA 里程碑（≤14d/≤90d/≤120d，`assets["success_criteria_sla"]` 可覆盖）+ gate 首过统计；纯读零持久化，`timeline_consistent=false` 标注不完整审计流。 |
| `POST /api/engagements/{eid}/share` | 写 | 生成（或轮换）只读分享 token；**明文只在本次响应出现一次**，落盘 sha256 + 8 位前缀。 |
| `GET /api/engagements/{eid}/share` | 读 | 分享状态（是否启用、前缀、创建时间）——永不回传 token 本体。 |
| `DELETE /api/engagements/{eid}/share` | 写 | 吊销分享链接（幂等）。 |
| `GET /share/{eid}?t=` | 读（share token） | 干系人只读页：进度 + SLA + 门禁现况 + 签收表单。凭据是链接里的 share token（auth 中间件 share 分支校验），无效/撤销/不存在一律 404。 |
| `POST /share/{eid}/ack?t=` | 写（share token） | 客户签收 → `share.ack` 审计事件（证据，不推进状态机）；正式验收仍走 authed accept 流程。 |
| `GET /api/engagements/{eid}/gates` | 读 | 对当前 context 适用（`applies()`）的每个 gate 实时 `check()`。 † |
| `GET /api/engagements/{eid}/guided` | 读 | guided 模式只读载荷（阶段建议 + 字段指引）。 † |
| `POST /api/engagements/{eid}/guided/draft-context` | 写 | AI-draft context cards from a free-text description. Pure draft: nothing is persisted until the user applies it via POST .../context. |
| `POST /api/engagements/{eid}/guided/plan` | 写 | Break a project goal into a per-phase task plan, persisted to `ctx.assets["guided_plan"]`. Rule skeleton first; the LLM only rewrites task wording when available. Never touches gates/phases. |
| `POST /api/engagements/{eid}/handoff` | 写 | Render the runbook, assemble the handoff package, hash both into the audit trail. |
| `GET /api/engagements/{eid}/journal` | 读 | 现场记录列表（`ctx.journal` 逐条 dump）。 † |
| `POST /api/engagements/{eid}/journal` | 写 | 追加一条现场记录。 † |
| `POST /api/engagements/{eid}/journal/{jid}/skill` | 写 | 把一条现场记录沉淀为技能草稿（kind → category 映射预填）。 |
| `POST /api/engagements/{eid}/rollback` | 写 | Roll an engagement back to an earlier phase. |
| `GET /api/eval/info` | 读 | What the eval panel needs before running: metric names + honest labels, and whether a real LLM is configured (mock runs need nothing). |
| `POST /api/eval/run` | 写 | Run the FDE benchmark over inline cases or a JSON/JSONL test-set path. |
| `GET /api/flywheel` | 读 | Flywheel snapshot + retrain job descriptors, honestly labelled. |
| `POST /api/forge` | 写 | Upload a CSV, forge a corpus, return a CorpusReport summary + report id. |
| `GET /api/health` | 读 | Liveness + readiness probe: real subsystem state, HTTP 200 even when degraded (probe semantics — the process is up, subsystems may not be). Public route (auth.PUBLIC_PATHS); never exposes credentials. |
| `POST /api/kpi` | 写 | 上传 JSONL 样本按 profile 计算 KPI（Form + File）。 † |
| `GET /api/license` | 读 | Read-only license facts. The key and its signature never appear here — only where the key was found (env / key file / none). |
| `POST /api/ontology/diff` | 写 | TBox 版本 diff（D1-D4）+ 全部引用工作区实例库的 ABox 影响面 （与 CLI `ontology diff` 同语义；影响面是迁移工作量证据，不是推断）。 |
| `GET /api/ontology/export/{target_id}` | 读 | JSON-LD 导出：schema 直出；store 联同其 TBox 上下文（与 CLI ontology export 同语义）。 |
| `GET /api/ontology/schema/{schema_id}` | 读 | 单个 TBox schema。 † |
| `GET /api/ontology/schema/{schema_id}/diagram` | 读 | Mermaid 类图（与 CLI `ontology diagram` 同语义：父类继承 + 对象属性边 + 数据属性行）。 |
| `GET /api/ontology/schemas` | 读 | TBox schema 列表。 † |
| `GET /api/ontology/store/{store_id}` | 读 | 单个 ABox 实例库。 † |
| `GET /api/ontology/stores` | 读 | ABox 实例库列表。 † |
| `GET /api/ontology/validate/{target_id}` | 读 | SHACL-lite 校验：schema 走 TBox（含 import 合并视图），store 走 ABox（对 `ontology_ref` 指向的 TBox）——与 CLI `ontology validate` / `check` 同语义。 |
| `GET /api/phases` | 读 | 按 profile 返回阶段序列（工业 profile 与非工业不同）。 † |
| `GET /api/profiles` | 读 | profile 目录：名称、是否工业、主连接器、KPI 目录。 † |
| `GET /api/skills` | 读 | 技能检索；`status` 默认 `published`，见上文查询参数。 † |
| `POST /api/skills` | 写 | 创建技能草稿；`id`/`status`/`version` 由服务端生成（`SkillDraft` 无 `id` 字段，不变式 2）。 † |
| `GET /api/skills/drafts` | 读 | 草稿审阅队列。 † |
| `GET /api/skills/facets` | 读 | Distinct facet values across the skill store, for the console filters. |
| `GET /api/skills/{sid}` | 读 | 技能详情（不存在 404）。 † |
| `PATCH /api/skills/{sid}` | 写 | 编辑（JSON `SkillPatch`：`title` / `tags` / `body_md` / `phase_slug` / `gate_slug` / `applies_to`；未提供的字段保持不变，`id` 不可外部设置；任一变更 `version` +1。状态不限，服务层不校验 `draft`）。 † |
| `POST /api/skills/{sid}/archive` | 写 | 归档技能；不存在 404，已归档再归档 400。 † |
| `POST /api/skills/{sid}/export` | 写 | 按 `body.format` 导出，`fmt` 仅 `agentscope` / `qwenpaw`（其余 400）；返回单个 `{name: "<slug>/SKILL.md", content}`。Web 层不传 `ontology`，故导出恒为无 TBox 上下文的 frontmatter。 † |
| `POST /api/skills/{sid}/publish` | 写 | 发布技能并写审计事件 `skill.publish`；仅 `draft` 可发布，否则 400。 † |
| `GET /api/workbench` | 读 | 工作台聚合：engagement 矩阵 + 技能/缺口计数。 † |
| `GET /certification` | 读 | The FDE certification centre: vendor exam specs, the public outline, sourced practice items and the channel due-diligence checklist. |
| `GET /console` | 读 | The engagement console (the detailed workbench). |
| `GET /course` | 读 | The Level-1 beginner course, rendered from `course-level-1/`. |
| `GET /docs/images/{name}` | 读 | 文档内联图片；路径经白名单校验，未知 404。 † |
| `GET /docs/{slug}` | 读 | Render one repository document (README, docs/*.md, LICENSE, NOTICE). |
| `GET /en/` | 读 | English variant of the landing page. |
| `GET /en/certification` | 读 | English variant of the certification centre. |
| `GET /en/console` | 读 | English variant of the engagement console. |
| `GET /en/course` | 读 | English variant of the course page (chrome translated, lessons are served as the Chinese authors wrote them). |
| `GET /en/docs/{slug}` | 读 | English chrome over the same document corpus (bodies stay as authored). |
| `GET /en/glossary` | 读 | English variant of the glossary. |
| `GET /en/resources` | 读 | English variant of the GitHub-resource index. |
| `GET /en/sop` | 读 | English variant of the SOP page (chrome translated, the document is served as the Chinese authors wrote it). |
| `GET /glossary` | 读 | The field vocabulary shared by the SOP, the outline and the console. |
| `GET /resources` | 读 | The GitHub-resource index: every harvested FDE repository, provenance-stamped and searchable, rendered from the packaged YAML. |
| `GET /sop` | 读 | The full FDE SOP, rendered from `docs/fde_sop_full.md`. |
| `GET /static/favicon.svg` | 读 | 图标，`Cache-Control: max-age=86400`。 † |

## OpenAPI / Swagger（已内置，非「暂未支持」）

FastAPI 默认挂载，实测均为 200：

| 路径 | 内容 |
|---|---|
| `GET /openapi.json` | 机器可读的 69 条 served 路由 + 全部请求/响应 schema |
| `GET /docs` | Swagger UI |
| `GET /redoc` | ReDoc |

三者都**不在** `auth.PUBLIC_PATHS` 里：设置 `FDE_SCOPE_API_TOKEN` 后直接访问返回
401，带 token 才 200（路由表本身是信息暴露面，默认收紧是对的）。
**本页与 `/openapi.json` 冲突时，以 `/openapi.json` 为准。**

## 暂未支持（见路线图 P5）

分页参数（列表端点当前全量返回）、SSO/多用户、Webhook 通知、
提交进仓库的版本化 OpenAPI 产物（现在只有运行时 `/openapi.json`）。

## 文档自身的已知缺口

写在这里是为了下一次修，而不是让它悄悄漂着：

1. **28 条 served 路由的处理函数没有 docstring**（上表的 `†` 行）。本表对它们的
   说明是我逐条读 `fde_scope/web/app.py` / `guided_api.py` 处理函数体补写的，
   因此**不受任何自动核对保护**——代码改了说明不会跟着报错。根治办法是给这 28 个
   函数补 docstring（`tests/test_web.py` 已覆盖其中大部分行为，补注释成本很低），
   补完后上表可全部机器生成。
2. **3 条安装态兜底路由不在 OpenAPI 里**（`/GTM`、`/catalog`、`/gh-resources`
   的 `{rest:path}`），所以本表的「穷举」只覆盖 served 集；声明 72 与 served 69
   的差值由 `test_architecture_guard.py` 钉住，但**本文没有任何测试读取**。
3. **上文各节是精选讲解，覆盖了多少条 served 路由没有可靠度量**：正文里同一路由可能写成
   `GET /api/x`、也可能拆成表格里两列或 curl 代码块里的 URL，任何「覆盖率」百分比都取决于
   匹配口径，换个口径就换个数（本文一度写 44/25，重测得到 46/23、47/22，全是口径差异）。
   所以上表才是穷举锚点——它与 `app.openapi()` 一一对应，不依赖文字匹配。要补示例，直接对照
   上表找正文没有小节的条目即可；完整字段定义以 `/openapi.json` 为唯一权威，与本页冲突时以它为准。
