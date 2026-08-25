# FDE Scope · QwenPaw PawApp

把 FDE Scope（18 阶段 SOP 状态机 + 可执行 gate + 语料锻造 + 技能沉淀）作为
QwenPaw 的 **PawApp** 运行——在 QwenPaw 桌面端 App Center 里以独立应用出现，
复用 QwenPaw 的 LLM 运行时、记忆、安全沙箱与桌面壳。

## 架构

```
QwenPaw 桌面端（Tauri）
 └─ App Center → FDE Scope PawApp
     ├─ backend/main.py   PawApp SDK：FastAPI 路由挂在 /fde-scope/*
     │     └─ 薄封装 fde_scope 包（engagement/gates/corpus/skills/llm）
     └─ ui/index.js       运行时加载的 React 页面（/apps/fde-scope）
```

- **后端**：`PawApp(app_id="fde-scope")` + FastAPI router，路由前缀 `/fde-scope`。
  所有业务逻辑直接 import `fde_scope`（engagement 状态机、gate registry、
  CorpusForge、SkillService、MiMoClient），不复制实现。
- **前端**：无构建步骤的单文件 JS，宿主经 `window.QwenPaw.host` 提供
  React/antd；`QwenPaw.registerRoutes` 注册 `/apps/fde-scope` 路由。
- **Agent 工具**：注册了 `fde_sop_status` / `fde_sop_advance`，QwenPaw 的
  Agent 可以在对话中查询/推进 SOP 状态机。

## 依赖

- QwenPaw ≥ 2.0.1（PawApp SDK）
- `fde_scope` 可导入：把 fde-scope 仓库加入 `PYTHONPATH`，或
  `pip install -e /path/to/fde-scope`（PawApp 后端 `import fde_scope.*`）

## 安装（开发期）

```bash
# 1. fde_scope 对 QwenPaw 的 python 可见
pip install -e /path/to/fde-scope

# 2. 把本目录装为 QwenPaw 插件（本地路径安装）
qwenpaw plugin install /path/to/fde-scope/pawapp
# 或直接链接/复制到 ~/.qwenpaw/plugins/fde-scope/

# 3. 启动后打开 App Center → FDE Scope
qwenpaw app
```

## 数据

与独立 Web 控制台同约定，相对 QwenPaw 工作目录：

| 路径 | 内容 |
|---|---|
| `.fde_scope/engagements/*.json` | engagement 状态（18 阶段 + gate 记录 + context） |
| `.fde_scope/skills/` | 技能库 |
| `reports/` | 生成的语料报告 HTML |

## API（挂在 /fde-scope 下）

| 方法 路径 | 说明 |
|---|---|
| GET `/health` | 存活检查 |
| GET `/profiles` · `/phases?profile=` | 场景 profile 与阶段序列 |
| GET/POST `/engagements` | 列表 / 新建 |
| GET `/engagements/{eid}` | 状态 + context |
| GET `/engagements/{eid}/gates` | 适用 gate 的实时校验结果 |
| POST `/engagements/{eid}/advance?force=` | 推进（gate 拦截返回 blockers） |
| POST `/engagements/{eid}/gate/{slug}` | 单 gate 重新校验 |
| POST `/forge` | CSV → 语料锻造（有 MIMO key 时 LLM 合成） |
| GET `/skills` · `/skills/drafts` | 技能库检索 / 草稿队列 |
| POST `/kpi` | JSONL 样本 → profile KPI（manufacturing / ticket） |
| POST `/skills/{sid}/publish` | 发布技能草稿 |
| POST `/skills/{sid}/export?fmt=` | 导出 AgentScope / QwenPaw 格式 SKILL.md（同时写盘供 skill_provider） |
| POST `/handoff/{eid}/runbook` | 用宿主 LLM（`ctx.chat()`）起草 runbook，失败回退模板，`used_llm` 如实标注 |
| POST `/handoff/{eid}` | 组装移交包（自动携带已起草的 runbook） |

## 路线图（全部完成 ✅）

- [x] SOP 流水线视图（18 阶段 + 当前阶段高亮 + 进度）
- [x] gate 面板（blockers/warnings + 重新校验）
- [x] 推进/force 推进 + 新建 engagement
- [x] Agent 工具：fde_sop_status / fde_sop_advance
- [x] 语料锻造 UI（文件上传 + 统计预览；LLM 合成自动感知 MIMO key）
- [x] KPI 计算面板（ticket / manufacturing）
- [x] 技能库浏览器（草稿审阅 + 发布 + 导出 QwenPaw SKILL.md）
- [x] handoff 打包 + runbook（`ctx.chat()` 宿主 LLM 起草，不再需要 MIMO key）
- [x] `skill_provider()`：导出目录注册给 QwenPaw Agent（技能即能力）
- [x] `ctx.storage` 同步：engagement 状态快照（`engagements_index`）供 Agent 查询；
      文件仍为唯一事实源，storage 是尽力而为的读缓存（失败不阻断 SOP 流程）
