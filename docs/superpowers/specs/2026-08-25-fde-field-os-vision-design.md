# FDE Scope 现场操作系统 —— 跨项目 FDE 工作流支持（设计文档）

日期：2026-08-25
状态：已批准（用户确认"全部完成开发"）
范围：4 个子系统，按 C → D → A → B 顺序实施

## 1. 背景与目标

FDE Scope 目前是"单项目 SOP 工具链"（CLI + Web 控制台 + Python 库）。产品愿景是升级为
**"跨项目支撑 FDE 完整工作流的现场操作系统"**：

1. FDE 带着产品到客户现场，基于最新 AgentScope 2.0 真实部署；
2. 部署后展开多个 Agent 交互，或直接接 QwenPaw 做数字人的多 Agent 协调；
3. Web 页面支持：随时沉淀技能和方法论；跨客户进行现场调研、现场实施、现场调优。

四个子系统：

| 子系统 | 目标 | 现状 |
|---|---|---|
| C. 技能/方法论沉淀 | 沉淀 FDE 技能与方法论，跨项目复用，可导出给 Agent | ❌ 无 |
| D. FDE 工作台 | Web 页面：跨项目视图 + 沉淀入口 + 现场记录 | ⚠️ 单 engagement 控制台 |
| A. 部署运行时 | AgentScope 2.0 真实部署 + 多 Agent 展开 | ⚠️ lazy 单 Agent 组装 |
| B. QwenPaw 集成 | 技能/Agent 配置导出 + ACP 多 Agent 协调适配 | ❌ 无 |

已确认的设计决策（brainstorming 结论）：

- 沉淀形态：**Markdown 正文 + 结构化元数据**（混合）；
- 分类体系：**调研 / 实施 / 调优 / 方法论** 四类 + 自由标签，可选绑定 phase/gate；
- 消费方式：**FDE 查阅 + 导出给 Agent**（AgentScope Skills / QwenPaw 格式，本期实现）；
- 沉淀入口：**手动为主（CLI/Web）+ gate 阻塞关键点提示 + 自动捕获草稿审阅**；
- 实现方案：**独立 `skills/` 模块 + `.fde_scope/skills/` 文件库**，与 engagement 通过事件钩子解耦。

---

## 2. 子系统 C：技能/方法论沉淀

### 2.1 数据模型（`fde_scope/skills/models.py`，Pydantic v2）

```python
class SkillCategory(str, Enum):
    RESEARCH        = "research"         # 调研
    IMPLEMENTATION  = "implementation"   # 实施
    OPTIMIZATION    = "optimization"     # 调优
    METHODOLOGY     = "methodology"      # 方法论

class SkillStatus(str, Enum):
    DRAFT       = "draft"       # 草稿（自动捕获/提示产生）
    PUBLISHED   = "published"   # 已发布（可检索、可导出）
    ARCHIVED    = "archived"    # 已归档（弃用）

class SkillSource(str, Enum):
    MANUAL         = "manual"          # 手动沉淀
    GATE_HINT      = "gate_hint"       # gate 阻塞时提示生成
    AUTO_CAPTURE   = "auto_capture"    # 操作自动捕获

class SkillRecord(BaseModel):
    id: str                       # skill-<8 位随机>
    title: str                    # ≤80 字
    category: SkillCategory
    tags: list[str]               # 自由标签
    body_md: str                  # Markdown 正文
    phase_slug: str | None        # 可选绑定 18 阶段
    gate_slug: str | None         # 可选绑定 10 门禁
    applies_to: list[str]         # 适用 profile：ticket / manufacturing
    source: SkillSource
    source_engagement: str | None # 溯源 engagement id
    status: SkillStatus
    version: int                  # 每次编辑 +1
    created_at: datetime
    updated_at: datetime
    export_formats: list[str]     # 已导出格式记录
```

### 2.2 存储布局（零新增依赖）

```
.fde_scope/skills/
├── <skill-id>/
│   ├── skill.md          # 人可读正文（body_md）
│   └── meta.json         # SkillRecord 元数据（不含 body_md）
└── index.json            # 轻量索引：id → (title, category, status, tags, updated_at)
```

- 读写走 `SkillStore`（`fde_scope/skills/store.py`）：原子写（先写临时文件再 rename）、
  损坏的 meta.json 报错并跳过索引、`index.json` 可由目录重建（`rebuild_index()`）。
- 目录不存在时自动创建；`SkillStore(root: Path = Path(".fde_scope/skills"))` 可注入测试根目录。

### 2.3 服务层（`fde_scope/skills/service.py`）

```python
class SkillService:
    def __init__(self, store: SkillStore) -> None
    def create(self, draft: SkillDraft) -> SkillRecord          # status=draft
    def publish(self, skill_id: str) -> SkillRecord             # draft→published
    def archive(self, skill_id: str) -> SkillRecord             # →archived
    def update(self, skill_id: str, patch: SkillPatch) -> SkillRecord  # version+1
    def get(self, skill_id: str) -> SkillRecord
    def search(self, query: str | None = None, *, category=None, tags=None,
               status=None, phase_slug=None, gate_slug=None, profile=None,
               limit: int = 50) -> list[SkillRecord]
    def list_drafts(self) -> list[SkillRecord]                  # 审阅队列
    def suggest_from_gate_block(self, engagement_id: str, gate_slug: str,
                                blockers: list[str]) -> SkillRecord  # 关键点提示生成草稿
    def capture_operation(self, *, action: str, engagement_id: str,
                          phase_slug: str | None, detail: dict) -> SkillRecord | None
```

检索规则：query 对 title/tags/body 做大小写不敏感子串匹配；其余按字段精确过滤；
按 `updated_at` 倒序。`suggest_from_gate_block` 生成带预填标题与 blockers 摘要正文的草稿
（标题如"gate 被阻塞: <gate> — <首个 blocker>"），正文为模板 + 占位提示。

### 2.4 CLI（新增 `skill` 命令组）

```
fde-scope skill add        --category research --title "..." --tags a,b [--body file|--body "..."]
                           [--phase <slug>] [--gate <slug>] [--profile ticket]
                           [--engagement <id>] [--source manual]      # 创建草稿
fde-scope skill list       [--category X] [--tag x] [--status published|draft|archived]
                           [--profile p] [--gate g] [--phase p] [--search 关键词]
fde-scope skill show       <skill-id>                                  # 正文 + 元数据
fde-scope skill edit       <skill-id> --title/--tags/--body/...        # version+1
fde-scope skill publish    <skill-id>                                  # 草稿→发布
fde-scope skill archive    <skill-id>
fde-scope skill review     [--limit 20]                                # 草稿审阅队列
fde-scope skill export     <skill-id> --format agentscope|qwenpaw --out <dir>
```

实现：`cli.py` 新增 `skill_app = typer.Typer(name="skill", ...)`，注册到主 app；
输出用 rich Table（对齐现有命令风格）；错误 exit 2。

### 2.5 与 engagement 引擎的钩子（解耦）

- 在 `Engagement.advance` 被 `AdvanceBlocked` 拦截处与 `gate check` 失败处，
  CLI 打印提示：`💡 要不要把这次解法沉淀成技能？fde-scope skill add --gate <slug> --engagement <id>`。
  同时自动调用 `SkillService.suggest_from_gate_block` 生成草稿并提示
  `fde-scope skill review` 查看（仅当 `.fde_scope/skills/` 目录可写）。
- engagement 模块本身**不依赖** skills 模块：钩子由 CLI 层调用（`_maybe_suggest_skill()`），
  保持核心层零依赖。
- 自动捕获 `capture_operation`：在 `engage advance`（成功）与 `gate check`（通过）时
  记录一条轻量操作摘要草稿（source=auto_capture），不阻塞主流程，失败静默。

### 2.6 Web API（`fde_scope/web/app.py` 新增路由）

```
GET    /api/skills?q=&category=&tag=&status=&profile=&gate=&phase=
POST   /api/skills                       # 创建草稿
GET    /api/skills/{sid}
PATCH  /api/skills/{sid}                 # 编辑（version+1）
POST   /api/skills/{sid}/publish
POST   /api/skills/{sid}/archive
GET    /api/skills/drafts                # 审阅队列
POST   /api/skills/{sid}/export          # body: {"format": "agentscope"|"qwenpaw"}
                                        # → 返回导出产物（zip 或文件清单+内容）
```

### 2.7 导出器（`fde_scope/skills/exporters.py`）

- **AgentScope 格式**：输出 `SKILL.md`（frontmatter: name/description + body_md），
  目录结构 `skills/<skill-name>/SKILL.md`，与 AgentScope 2.0 skill 约定对齐；
  实现时检索官方文档确认 frontmatter 字段，以 `docs/agentscope_api_mapping.md` 的
  求真原则为准，不基于训练数据猜测。
- **QwenPaw 格式**：输出 QwenPaw Skills 兼容的 `SKILL.md`（QwenPaw 生态使用
  Skill 机制，v2.x 与 AgentScope skill 同源）；实现时检索 QwenPaw 官方文档确认
  字段差异。
- 导出产物写入 `--out` 目录（默认 `exports/<skill-id>/`）；export_formats 记录追加。
- 导出器为独立函数（`export_skill(record, fmt) -> list[ExportFile]`），可单测。

### 2.8 测试策略（`tests/test_skills.py`）

- 存储：创建/读取/更新/归档/重建索引/损坏文件容错（tmp_path 注入）；
- 服务：CRUD 全流程、搜索过滤组合、publish 前置条件（非 draft 拒绝）、version 递增；
- 钩子：`suggest_from_gate_block` 预填内容、`capture_operation` 摘要生成；
- 导出：两种格式的产物内容断言；
- CLI：`typer.testing.CliRunner` 覆盖 skill 子命令；
- Web：`TestClient` 覆盖 8 个路由。

---

## 3. 子系统 D：FDE 工作台

### 3.1 目标

把现有单页 engagement 控制台扩展为**跨项目 FDE 工作台**：一个页面看到所有客户项目
的状态、沉淀技能库、草稿审阅队列、现场记录入口。

### 3.2 页面结构（扩展 `web/app.py` 单页 console）

- **工作台首页**（`/console` 改造）：三段式
  - 顶部：全局统计条（进行中项目数、阶段分布、待审草稿数、技能总数）；
  - 中部：跨项目矩阵（每个 engagement 一行：客户/阶段/zone/门禁状态/最近更新时间），
    点击进入现有 engagement 详情；
  - 底部：最近沉淀（最新 published 技能列表 + "去沉淀"按钮）。
- **技能库页**（`/console#skills`）：搜索框 + 分类/标签/状态筛选 + 技能卡片列表 +
  "新建技能"表单（类别/标题/标签/正文/绑定 phase/gate/profile）+
  "草稿审阅队列"面板（自动捕获与 gate 提示产生的草稿，一键 publish/编辑）。
- 导航：单页内 tab 切换（现有结构是单 HTML，保持无构建步骤）。

### 3.3 现场记录工作流（D2）

- 新增 `EngagementContext` 可选字段 `journal: list[JournalEntry]`：
  `JournalEntry = {id, ts, kind: research|implementation|optimization, note, skill_id?}`。
- CLI：`fde-scope engage journal <id> --kind research --note "..." [--link-skill <sid>]`。
- Web：engagement 详情页新增"现场记录"tab，追加/查看记录，可从记录一键"沉淀为技能"
  （预填 source_engagement、kind→category 映射）。
- 向后兼容：`journal` 缺失时视为空列表（旧 JSON 文件可正常加载）。
- 迁移：`EngagementContext` 增加 `journal: list[JournalEntry] = Field(default_factory=list)`，
  无需数据迁移脚本。

### 3.4 测试策略

- journal：CLI 追加/查看、Web API、旧文件兼容；
- 工作台聚合 API：统计与矩阵数据正确性；
- 页面渲染：`TestClient` 断言关键 DOM 元素存在（延续现有测试风格）。

---

## 4. 子系统 A：AgentScope 2.0 真实部署运行时

### 4.1 目标

`fde-scope deploy` 在安装 `[agentscope]` extra 时真实启动：workspace + 模型接线 +
Agent 启动，并支持一个 tenant 声明多个 Agent（多 Agent 展开）。

### 4.2 现状与差距

- `TenantDeployer._assemble_agent` 已有 Agent 组装骨架（name/model/toolkit/react_config），
  但：模型 wiring 未实现（`agent.kwargs["model"] is None`）、无多 Agent 拓扑、
  无启动/健康检查/停止生命周期。
- AgentScope 2.0 无 `SequentialPipeline`；多 Agent 编排走中间件 + `agentscope.app`
  服务层（`_manager/_router/_service/message_bus`）。**实现前必须检索 2.0.x 官方文档
  核实 app 层真实 API**（延续 docs/agentscope_api_mapping.md 的求真原则）。

### 4.3 设计

- `TenantConfig` 扩展：`agents: list[AgentSpec] | None`，`AgentSpec =
  {name, role, system_prompt?, model?, toolkit?}`；缺省时沿用现有单 Agent 行为
  （name = `{tenant}_agent`），保证向后兼容。
- `TenantDeployer` 新增生命周期方法：
  - `deploy(tenant, ...)`：workspace 就绪 → 每个 AgentSpec 组装一个 Agent →
    注册到 app 服务层（如 2.0 API 允许）或记录拓扑；manifest 增加 `agents` 段；
  - `stop(deployed)`：优雅停止（实现时按 2.0 实际 API 适配）。
- 多 Agent 交互方式：优先使用 AgentScope 2.0 官方多 Agent 机制（app 服务层 /
  message_bus）；若官方 API 本期不可用，降级为"拓扑声明 + 文档说明"（manifest 完整，
  交互层留接口），**不虚构 API**。
- 模型 wiring：`AgentSpec.model` 传给 AgentScope 模型配置（model config name，
  与现有 `tenant.model` 语义一致）；缺失时保持 `None` 由运行时注入。
- 测试：沿用 fake agentscope 模式（`tests/test_deploy_assembly.py` 已有先例），
  扩展多 Agent 拓扑断言；真实启动标记为 `@pytest.mark.agentscope` 跳过。

---

## 5. 子系统 B：QwenPaw 集成

### 5.1 目标与边界

把 FDE Scope 的产物（技能、tenant 配置、corpus）导出为 QwenPaw 可消费的形态，
并提供 ACP 多 Agent 协调的适配说明。**真实 QwenPaw 实例对接不在本期验证范围**
（依赖外部产品环境），交付物为导出器 + 校验器 + 集成文档。

### 5.2 设计

- **Skills 导出**：子系统 C 的 qwenpaw 格式导出器即为此服务
  （QwenPaw 使用 SKILL.md 技能机制，与 AgentScope skill 同源；实现时以
  QwenPaw 官方文档为准）。
- **Agent 配置导出**：`fde-scope qwenpaw export --tenant <id> --out <dir>`：
  - 输出 tenant 的 agent 拓扑（来自子系统 A 的 `agents` 声明）为 QwenPaw 兼容的
    agent 配置文件（YAML/JSON）；
  - 输出 corpus collection 说明与技能包（published 技能批量导出）；
  - 输出校验报告（缺失字段、格式合法性）。
- **ACP 适配**：文档说明 FDE Scope 的 SOP 引擎如何暴露为 ACP 节点
  （`docs/qwenpaw_integration.md`），代码层预留 `fde_scope/integrations/acp.py`
  占位接口（`AcpEndpoint` 基类），本期不实现网络协议。
- CLI：`fde-scope qwenpaw export` + `fde-scope qwenpaw validate`。

### 5.3 测试策略

- 导出产物结构断言（YAML/JSON 合法性、技能包完整性）；
- 校验器对坏配置报错；
- `@pytest.mark.agentscope` 无关，纯本地可测。

---

## 6. 实施顺序与验收标准

顺序（每步完成即跑测试 + ruff + mypy）：

1. **C**：`fde_scope/skills/` 模块 + CLI + Web API + 导出器 + 测试
   → 验收：`fde-scope skill add/list/show/publish/export` 全流程可用，`pytest` 绿；
2. **D**：工作台页面 + journal + 聚合 API
   → 验收：Web 打开 `/console` 可见跨项目矩阵与技能库，engagements 兼容旧数据；
3. **A**：TenantConfig.agents + 生命周期 + 多 Agent 拓扑（先检索 2.0 文档）
   → 验收：fake agentscope 下单测绿，manifest 含 agents 段；
4. **B**：qwenpaw export/validate + 集成文档
   → 验收：导出产物可被校验器验证通过；
5. **E2E**：seed mock 数据 → 演练（沉淀 → 审阅 → 导出 → 工作台展示），更新 README。

## 7. 假设

- 单机本地部署（FDE 个人工作台），无多用户/权限体系（团队共享为后续迭代）；
- 技能库跟随 `.fde_scope/` 目录可拷贝携带；
- 搜索用子串匹配，不引入全文检索依赖；
- AgentScope 2.0 与 QwenPaw 的 API 以官方文档为准，不确定处实现前检索验证。
