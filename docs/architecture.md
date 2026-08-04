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
│  │  DockerWorkspace · PermissionEngine · KnowledgeBase       │    │
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
- 核心数据层 + SOP 层 + Profiles 层 + Web 层**完全不依赖 agentscope**。
- 仅 deploy / flywall 延迟导入 agentscope（optional extra）。
- `pip install -e ".[dev]"` + `pytest` 全绿，不需要 LLM key / docker / agentscope。

### 5. Corpus Engine 是规则版 v0
脱敏、去重、质量门、覆盖度分析、缺口检测、针对性合成、train/eval/test 分割、HTML 报告
——全部是真实规则实现，不接 LLM 也能跑通并产出可审计报告。

### 6. AgentScope API 真实化
见 `docs/agentscope_api_mapping.md`：把设计文档里的虚构 API
（`HarnessAgent`/`SequentialPipeline`/`EventSystem.on`/`HumanInTheLoop`/`VectorStore`）
逐条对齐到真实 2.0.5 API。

## 数据流

```
客户数据源
   │  connect (OPC UA / MQTT / CSV / Zammad…)
   ▼
[raw rows] → corpus forge → [CorpusReport] → HTML 报告
   │  deploy (FAT→SAT→commissioning，工业 gate 守卫)
   ▼
[DockerWorkspace + PermissionEngine + KnowledgeBase + Agent]
   │  eval (ticket 指标 或 制造业 KPI)
   ▼
[EvalReport + bad cases + 建议]
   │  flywheel (概念事件→真实事件映射→回流→周度重训)
   ▼
数据飞轮 → 产品化 → 移交包 → 客户签字 → 退场
```

## 三层隔离（多租户数据泄露防御）

| 层 | 机制 | AgentScope 2.0 真实类型 |
|---|---|---|
| 执行隔离 | 容器沙箱 | `DockerWorkspace` / `E2BWorkspace` / `K8sWorkspace` |
| 数据隔离 | 每租户独立 collection | `KnowledgeBase(collection=f"corpus_{tenant_id}")` |
| 权限隔离 | 静态+动态规则引擎 | `PermissionEngine` + `PermissionRule`（ALLOW/DENY/ASK） |

## 当前状态 vs 路线图

| 模块 | v0（本期） | v1（路线图） |
|---|---|---|
| Engagement SOP | ✅ 18 阶段 + 10 gate 状态机 | + 与 deploy/flywheel 实时联动 |
| Connector (CSV) | ✅ 真实实现 | + 工业协议真实 IO + Zammad/Salesforce HTTP |
| Corpus 清洗/合成 | ✅ 规则版 | LLM 版（同签名换内核） |
| Deploy 组装 | ✅ 真实类型组装 | + 真实启动 + 模型调用 |
| Eval | ✅ ticket + 制造业 KPI + mock reply | + 真实 Agent.reply + 分类器 |
| Flywheel | ✅ 事件映射 + 规则回流 | + 真实订阅 reply_stream + 微调 |
| Web UI | ✅ FastAPI 控制台 | + Studio 集成 + 实时事件流 |
