# FDE Scope 架构

> "The complete on-site operating system for a Forward Deployed Engineer."

FDE Scope 不是又一个 Agent 应用，而是 **FDE 在客户现场的完整工作台**：把 FDE
的 18 阶段标准作业流程（SOP）变成可执行、可被 gate 拦截的工程化流程，覆盖
软件/SaaS 与具身机器人/制造业两类场景。

## 分层

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLI / Web Console                           │
│    engage · gate · status · handoff · connect · corpus · …      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  SOP 层：engagement/                        [无 agentscope]│    │
│  │  4 zones / 18 阶段状态机 + 10 个可执行 gate + handoff     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │    │
│  │  │Zone A    │→│Zone B    │→│Zone C    │→│Zone D    │     │    │
│  │  │Pre-engage│ │Build     │ │Ops       │ │Handoff   │     │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Profiles：profiles/                         [无 as]      │    │
│  │  ticket（客服）· manufacturing（工厂）场景选择             │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 5: Flywheel（数据飞轮）              [延迟导入 as] │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 4: Eval（评估框架）                  [无 as]       │    │
│  │  ticket 指标 · 制造业 KPI（OEE/MTBF/抓取率）· bad case    │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 3: Deploy（多租户部署）              [延迟导入 as] │    │
│  │  Workspace 沙箱 · PermissionContext · Toolkit 工具绑定    │    │
│  │  SubAgentTemplate 蓝图 · deploy plan（web/PawApp 共享）   │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 2: Corpus Engine（语料引擎）★核心     [无 as]      │    │
│  │  脱敏 → 去重 → 质量门 → 覆盖度 → 合成 → 报告              │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Layer 1: Connector Kit（数据接入）          [无 as]      │    │
│  │  CSV★·Zammad·Salesforce·MySQL                            │    │
│  │  OPC UA·MQTT-Sparkplug·ROS2·MES·Historian（工业）         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘

> **横切模块 `fde_scope/llm.py`（MiMo Token Plan 客户端）**：可被 Layer 2（合成/
> 评分）、Layer 4（MiMoReplyFn）、Zone C/D（runbook）与 Web Forge 注入的可选
> LLM 能力；纯标准库实现，无 key 时全链路规则路径。详见
> [`llm_integration.md`](llm_integration.md)。
>
> **横切模块 `fde_scope/skills/`（技能沉淀库）**：现场经验 → 可复用技能的文件库
> （draft → published → archived），可导出为 AgentScope / QwenPaw 的 Agent
> Skills。详见 [`skills.md`](skills.md)。
>
> **横切模块 `fde_scope/ontology/`（本体语义层）**：领域概念的形式化
> TBox/ABox + SKOS 分类法 + JSON-LD 导出；P2/P3 将接入 corpus 覆盖度与
> skills 检索。详见 [`ontology.md`](ontology.md)。
>
> **桌面形态 `pawapp/`（QwenPaw PawApp）**：把上述全部能力以插件应用形式嵌入
> QwenPaw 桌面端（App Center），复用宿主 LLM/沙箱/记忆。详见
> [`qwenpaw_integration.md`](qwenpaw_integration.md)。
```

## 核心设计决策

### 1. SOP 层是新顶层编排
`engagement/` 把"FDE 在现场做什么"从 5 步扩展为 **4 zones / 18 阶段** 状态机：
- **Zone A · Pre-engagement**（4）：qualification → site-survey → stakeholder-map → success-criteria
- **Zone B · Build**（6）：connect → corpus → prototype-on-real-data → validate → deploy → eval
- **Zone C · Operationalization**（5）：slo-sla → runbook → monitoring-drift → change-mgmt → flywheel→productization
- **Zone D · Handoff**（3）：ops-handoff → knowledge-transfer → disengage

每个阶段有可选的 `gate`；`Engagement.advance()` 在 gate 未通过时**拒绝推进并返回 blockers**。
这是把 SOP 从口号变成工程物的关键。

#### 为什么是 gate 而不是 checklist

两者是**记录与谓词**的区别，"更严格"不是语气而是机制：

1. **清单是记录，门禁是谓词。** 勾选框陈述"曾经查过"；`Gate.check(ctx)` 在
   推进的瞬间从 engagement 上下文重新推导事实。
2. **腐化方向相反。** 清单填完那天状态最好，之后随现实漂移（代码、人员、需求）
   单向腐化；`advance()` 对当前阶段全部门禁**无条件重评估**，旧的 passed
   记录不提供豁免（`engagement/engagement.py` advance docstring：a stale pass
   record never counts）。
3. **执行点从纪律移到不变量。** blocker 在场时 `AdvanceBlocked` 让推进在物理上
   不可能，不依赖任何人记得复查。
4. **越权 ≠ 绕过。** `force=True` 仍评估并记录全部结果，例外本身进入审计日志，
   事后无法与正常通过混淆。

因此任何围绕 `evaluate_phase_gates` 的缓存/短路都会把机制退化回一张清单
（AGENTS.md 不变量 1 禁止这样做）。

### 2. 工业 Overlay（manufacturing profile 启用）
6 个 SaaS 不需要的并行 gate，每个都是 `Gate.check(ctx) -> GateResult`：

| gate | 标准 | 拦截条件 |
|---|---|---|
| site_survey | gemba walk | location 未记录 |
| fat_sat | FAT/SAT 验收 | FAT/SAT 未执行/未签字 |
| functional_safety | ISO 13849 / IEC 61508 / ISO 10218 | PL 不足 / SIL 不足 / 未做危险分析 |
| conformity | EU AI Act / CE marking | 高风险系统未 CE |
| works_council | 德国 BetrVG §87 | works council 在场但无审批 |
| air_gap | air-gapped 部署 | 缺 edge 硬件 / 遥测出网 |
| shift_handover | 24/7 生产 | 多班次未集成交接 |

### 3. Profile 机制让核心场景无关
`profiles/` 按 scenario 选 connectors / KPIs / gate overlay：
- **ticket**：CSV/Zammad/Salesforce + 意图准确率/采纳率/升级率
- **manufacturing**：OPC UA/MQTT/ROS2/MES/Historian + OEE/MTBF/FPY/DPMO/抓取率/碰撞率 + 工业 gate

### 4. 依赖分层 → 零配置可跑
- 核心数据层 + SOP 层 + Profiles 层 + Web 层零**顶层** agentscope 依赖（唯一例外见下：connectors/documents.py 的延迟 rag 导入）。
- 仅 deploy/（三支柱 5 模块）与 connectors/documents.py（rag 解析器）延迟导入 agentscope
  （optional extra，实测窗口 `>=2.0.4.post1,<3`）；flywheel 为纯规则实现。
- `pip install -e ".[dev]"` + `pytest` 全绿，不需要 LLM key / docker / agentscope。

### 5. Corpus Engine 规则为底、LLM 可选增强
脱敏、去重、质量门、覆盖度分析、缺口检测、针对性合成、train/eval/test 分割、HTML 报告
——全部是真实规则实现，不接 LLM 也能跑通并产出可审计报告。2026-08 起合成与质量
评分可选接入 MiMo（`corpus --llm`，同签名换内核，失败自动回退规则）。

### 6. AgentScope API 真实化
见 `docs/agentscope_api_mapping.md`：把设计文档里的虚构 API
（`HarnessAgent`/`SequentialPipeline`/`EventSystem.on`/`HumanInTheLoop`/`VectorStore`）
逐条对齐到真实 2.0.x API（实测窗口 `>=2.0.4.post1,<3`）。

### 7. LLM 横切层（可选、可回退、零依赖）
`fde_scope/llm.py` 是唯一的 LLM 出口（MiMo Token Plan，OpenAI 兼容，标准库 urllib）：
- **可选注入**：各层接受 `llm=None` 可选参数，无 key 时行为与旧版完全一致；
- **失败回退**：网络错误/坏 JSON/`content: null` 都回退规则路径（eval 被测 Agent
  除外——干净退出 exit 1）；
- **溯源诚实**：回退后不声称 LLM 生成（`llm_runbook` 返回 `(text, used_llm)`）；
- **凭据只走环境变量** `FDE_SCOPE_MIMO_API_KEY`，不进 git/报告/manifest。
设计与接入点详见 [`llm_integration.md`](llm_integration.md)。

### 8. 技能沉淀库（经验资产化）
`fde_scope/skills/` 把现场经验变成可复用、可导出的技能资产：
- 文件库存储（`.fde_scope/skills/`，零数据库）；四类分类 + draft→published→archived 生命周期；
- 三种自动/半自动沉淀入口（gate 阻塞提示、操作自动捕获、现场记录桥接）都产出草稿，
  `skill review` 人工审阅后才发布，保证信噪比；
- 导出遵循 Anthropic Agent Skills 规范（SKILL.md + frontmatter），
  AgentScope `Toolkit(skills_or_loaders=[...])`（部署装配的
  `AgentSpec.toolkit.skills_dirs`）与 QwenPaw `customized_skills` 双兼容。
详见 [`skills.md`](skills.md)。

### 9. 多 Agent 生产（真实 AgentScope 2.0 装配 + FDE 自定义）
**装配即真实对象。** `TenantDeployer.deploy()` 为 `tenant_config.yaml` `agents:`
段的每个 `AgentSpec` 组装一个真实 `agentscope.agent.Agent`：`spec.model` wiring
成真实 ChatModel（缺省留运行时注入）、`plan_bindings()` 按角色把连接器/语料
工具绑成真 `Toolkit`、`AgentState(permission_context=...)` 注入规则上下文、
`ReActConfig(max_iters=20)`。

**FDE 自开 Agent 有三个通道**（名字任意、中文可用）：
1. CLI `--agent 名字:角色[:模型]`（可重复）+ `--connector-source slug=path` 绑源；
2. YAML：`TenantConfig.agents` 声明 + `TenantConfig.sources` 给连接器数据源；
3. 单 Agent 覆盖：`spec.toolkit["sources"]` / `["skills_dirs"]` 覆盖该 Agent
   的数据源与挂载技能（`Toolkit(skills_or_loaders=...)` 注册）。

角色是自由文本，经 `canonical_role()` 归入数据/日志/文件三个工具桶（含中文
关键词）；未归桶的角色退化为 corpus-only。没有数据源的连接器工具保持
**unbound** 并在 manifest 里写明原因——不假装可用（`describe_bindings`）。

**协调走 2.0 官方机制**：每个 Agent 同时导出 `SubAgentTemplate` 蓝图进真实
`create_app(custom_subagent_templates=...)`；leader 通过 `AgentCreate` 按
`subagent_type` 派活、成员经 `TeamSay` 回报（CI 真库测试覆盖）。**装配 ≠ 服务**：
不带 `--serve`，deploy 是真对象装配 + 诚实 manifest（dry-run/审计友好）；
`deploy --serve`（`build_app()` + uvicorn）起真实 app 服务，需要 agentscope
extra + Redis + 可达模型。生命周期：2.0 无 `Agent.stop`，`TenantDeployer.stop()`
关闭 workspace/engine 句柄并标记 manifest。

### 10. QwenPaw 桌面形态（PawApp）
`pawapp/` 把整个引擎做成 QwenPaw 的 PawApp（App Center 插件应用）：
- 后端薄封装 `fde_scope`（18 路由由宿主挂载到 `/api/fde-scope`）+ 3 个 Agent 工具
  （`fde_sop_status` / `fde_sop_advance` / `fde_deploy_plan`）；
- runbook 起草用宿主 `ctx.chat()`（不再需要外部 LLM key）；
- `ctx.storage` 同步 engagement 快照（文件仍为唯一事实源）；
- `skill_provider()` 把导出的技能目录直接注册给宿主 Agent（技能即能力）。
安装/契约详见 [`qwenpaw_integration.md`](qwenpaw_integration.md)。

### 11. 本体语义层（ontology/）

`fde_scope/ontology/` 把领域概念形式化为 TBox（`OntologySchema`：类层级、
对象/数据属性、SKOS 概念体系、命名空间、版本）+ ABox（`InstanceStore`：
个体与属性断言），零新依赖（pydantic + pyyaml）。内置 `fde-core` 与
ISA-95 `mfg-overlay` 为包内只读 YAML（狗粮校验：内置本体必须通过自己的
SHACL-lite 校验器）；用户本体/实例库在 `.fde_scope/ontology/` 工作区
（工作区覆盖内置），全部写入走 `fsutil.atomic_write_text`。JSON-LD 1.1
导出保证互操作（`ontology export`）。校验返回错误码报告（ONTO-xxx）而非
异常——记录与谓词分离，与 gate 哲学一致。语义层向两个模块单向桥接：
corpus（`--ontology` 概念注解 → 概念级覆盖 → 定向合成）与 skills
（`skills_bridge.py` 检索时推导概念，`--concept` 经 narrower 闭包扩展
检索、导出可选 `concepts:` frontmatter）；桥接不回写、不持久化。详见
[`ontology.md`](ontology.md)。

## 数据流

```
客户数据源
   │  connect (OPC UA / MQTT / CSV / Zammad…)
   ▼
[raw rows] → corpus forge（可选 LLM 合成/评分，`--llm`）→ [CorpusReport] → HTML 报告
   │  deploy (FAT→SAT→commissioning，工业 gate 守卫；manifest 可选携带 llm 段)
   ▼
[Workspace 沙箱 + PermissionContext(经 AgentState 注入) + Toolkit 绑定角色连接器/语料工具 + Agent]
   │  eval (ticket 指标 或 制造业 KPI；被测 Agent 可用 mock 或 MiMo)
   ▼
[EvalReport + bad cases + 建议]
   │  runbook（可选 `handoff --llm` 由 MiMo 起草）
   │  skills（现场经验 → 草稿 → 发布 → 导出 Agent Skills）
   │  flywheel (概念事件→真实事件映射→回流→周度重训)
   ▼
数据飞轮 → 产品化 → 移交包 → 客户签字 → 退场

可选宿主形态：QwenPaw 桌面端（pawapp/ PawApp，复用宿主 LLM/沙箱/记忆）
```

## 三层隔离（多租户数据泄露防御）

| 层 | 机制 | AgentScope 2.0 真实类型 |
|---|---|---|
| 执行隔离 | 容器沙箱 | `DockerWorkspace` / `LocalWorkspace`（经 `SandboxSpec` 组装） |
| 数据隔离 | 租户专属 collection 命名空间；语料检索为绑定该 corpus 的关键词工具 | collection 名 `corpus_{tenant_id}`；`agentscope.rag.KnowledgeBase` 需 embedding model，见路线图 |
| 权限隔离 | 规则上下文随 `AgentState` 注入 agent（bound 工具自动 ALLOW，未匹配按审批策略 ASK/DENY） | `PermissionContext` + `PermissionRule`（ALLOW/DENY/ASK） |

## 当前状态 vs 路线图

| 模块 | v0（本期） | v1（路线图） |
|---|---|---|
| Engagement SOP | ✅ 18 阶段 + 10 gate 状态机 | + 与 deploy/flywheel 实时联动 |
| Connector (CSV) | ✅ 真实实现 | + 工业协议真实 IO + Zammad/Salesforce HTTP |
| Corpus 清洗/合成 | ✅ 规则版 + MiMo LLM 可选增强（同签名换内核） | + 批量样本 LLM 评分 |
| LLM 横切层 | ✅ MiMoClient + 6 接入点（`llm.py`） | + 流式输出 + 多 provider 路由 |
| Deploy 组装 | ✅ 真实 Agent 装配（模型 wiring + Toolkit + PermissionContext）+ `--serve` 真实启动 | + serve 端到端实测（Redis + 模型） |
| Eval | ✅ ticket + 制造业 KPI + mock/mimo reply | + 真实 AgentScope Agent.reply + 分类器 |
| Runbook | ✅ Jinja 模板 + MiMo 起草（`handoff --llm`） | + 客户定制模板 |
| Skills 沉淀库 | ✅ 四类分类 + 生命周期 + 双格式导出（AgentScope/QwenPaw） | + 技能检索嵌入化 + 跨项目同步 |
| 多 Agent 生产 | ✅ 每规格真实 Agent 装配 + SubAgentTemplate 蓝图 + FDE 三通道自定义 | + serve 端到端实测（Redis + 模型） |
| Flywheel | ✅ 事件映射 + 规则回流 | + 真实订阅 reply_stream + 微调 |
| Web 工作台 | ✅ 三视图控制台（workbench 聚合 + journal + skills） | + 实时事件流 |
| QwenPaw 集成 | ✅ qwenpaw export/validate + PawApp（真机验证通过） | + ACP 适配 + Studio 集成 |
