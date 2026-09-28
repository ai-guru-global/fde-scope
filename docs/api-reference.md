# FDE Scope Web 控制台 REST API 参考

> 与 `fde_scope/web/app.py` + `fde_scope/web/guided_api.py` 实际路由逐条核对
> （共 40 条 JSON 路由 + 4 条 HTML 页面路由）。
> 默认基址 `http://127.0.0.1:8080`（`fde-scope web --host --port` 可改）。
> 所有示例假设已设置认证 token；本地未设 token 时可省略认证头。

## 认证（先读）

- token 只从环境变量 **`FDE_SCOPE_API_TOKEN`** 读取，不落文件/日志/响应。
- **未设置该变量时认证关闭**，所有请求直接放行（本地单机模式）。
- 设置后，除白名单外的所有路由要求以下两种头之一，否则返回
  `401 {"detail": "invalid or missing API token"}`：
  - `Authorization: Bearer <token>`
  - `X-API-Key: <token>`
- 白名单路径（免认证）：`/api/health`、`/`、`/console`、`/en/`、`/en/console`
  （HTML 壳本身不含数据，其发起的 JSON 调用仍需 token）。
- 绑定非回环地址还需 `FDE_SCOPE_ALLOW_REMOTE=1`（CLI 侧安全闸）。

```bash
export FDE_SCOPE_API_TOKEN="$(openssl rand -hex 32)"
fde-scope web
curl -H "X-API-Key: $FDE_SCOPE_API_TOKEN" http://127.0.0.1:8080/api/engagements
```

## 通用约定

- Form 参数端点用 `-F key=value`（`multipart/form-data`）；JSON 端点用
  `-H 'Content-Type: application/json' -d '{...}'`。
- 文件上传统一上限 **10 MiB**，超限返回 413。
- 常见错误码：400 参数语义错误 · 401 未认证 · 404 资源不存在 ·
  413 文件过大 · 422 参数缺失/校验失败。
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
`accept`（true 时另写 `handoff.accepted` 验收事件）、`operator`。

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
| `GET /api/skills/{sid}` | 详情（404 不存在） |
| `PATCH /api/skills/{sid}` | 编辑（JSON `SkillPatch`：`title` / `tags` / `body_md`，version+1） |
| `POST /api/skills/{sid}/publish` | 发布（写审计 `skill.publish`） |
| `POST /api/skills/{sid}/archive` | 归档 |
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

## HTML 页面与静态挂载（免认证白名单内的页面）

| 路径 | 说明 |
|---|---|
| `GET /` · `GET /console` | 中文功能总览 / Engagement 控制台（白名单） |
| `GET /en/` · `GET /en/console` | English 版本（白名单） |
| `/reports/*` | 生成的 runbook / 语料报告 / 审计导出（StaticFiles；**不在白名单**，认证开启时需 token） |
| `/catalog/*` | 技能手册库静态站（仓库含生成产物时挂载；同样需 token） |

## 暂未支持（见路线图 P5）

OpenAPI/Swagger 导出、分页参数（当前全量返回）、SSO/多用户、Webhook 通知。
