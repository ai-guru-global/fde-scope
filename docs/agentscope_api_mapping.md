# AgentScope 2.0 — 设计文档写法 vs. 真实 API 对照表

> 这是本项目的**面试核弹**。早期设计文档（产品愿景部分）写得很好，但
> 它给的代码示例大量引用了 **AgentScope 2.0（Python）里根本不存在的类**。
> 本项目刻意没有照搬那些虚构 API——而是把底层全部对齐到真实 2.0.5 的源码。
>
> 核查方法：对着 `agentscope-ai/agentscope` 仓库 `main` 分支（当前 2.0.x）
> 逐个 `__init__.py` 读源码，结论如下。**懂行的面试官扫一眼虚构 API 就能
> 识破"背概念"，而这份对照表证明你真读过源码。**

## 一句话结论

| 设计文档原写法 | 真实 AgentScope 2.0.5（Python） | 本项目处理 |
|---|---|---|
| `ReActAgent` | ❌ 不存在。统一类是 `agentscope.agent.Agent` + `ReActConfig` | deploy 用 `Agent` |
| `HarnessAgent(...)` | ❌ 不存在。2.0 的"工程化层"= `Agent` + `MiddlewareBase` 中间件 | deploy 用真实类型组装 |
| `SequentialPipeline([...])` | ❌ 这是 **1.0 概念，2.0 已删除** | corpus pipeline 改纯 Python 函数链 |
| `EventSystem.on("agent.low_confidence", cb)` | ❌ 不存在 pub/sub。事件是 `reply_stream()` 吐出的**强类型事件** | flywheel 做事件映射表 |
| `HumanInTheLoop(policy=..., timeout=...)` 类 | ❌ 不存在。HITL 是事件流 `RequireUserConfirmEvent` → `UserConfirmResultEvent` | deploy/flywheel 注明 |
| `Workspace(sandbox=SandboxConfig(resource_limit=...))` | ⚠️ `WorkspaceBase`/`DockerWorkspace` 存在，但**没有 `SandboxConfig`、没有 `resource_limit`** | `SandboxSpec.as_docker_kwargs()` 对齐真实签名 |
| `VectorStore(collection=...)` | ❌ 类名是 `VectorStoreBase`，`collection` 参数在 `KnowledgeBase` 上 | deploy 用 `KnowledgeBase(collection=)` |
| `PermissionEngine` + 5 模式 + BYPASS | ✅ **真实存在** | 原样使用 |

---

## 逐项核查（基于源码）

### 1. Agent 类
- **2.0 真实**：`from agentscope.agent import Agent`（不是 `ReActAgent`，不是 `AgentBase`）。
- 构造签名：`Agent(name, system_prompt, model, toolkit?, middlewares?, state?, offloader?, model_config?, context_config?, react_config?, injection_config?)`。
- ReAct 循环通过 `ReActConfig(max_iters=20, ...)` 配置，不是子类。
- ⚠️ **在线文档陷阱**：`doc.agentscope.io`（注意是 1.0 旧站）和 arXiv 论文里写的
  `agentscope.agent.ReActAgent` 是 **1.0 API**。2.0 文档在 `docs.agentscope.io/versions/2.0.x/`。
  Java 版（`io.agentscope.core.ReActAgent`）是另一套生态，别混。

### 2. "Harness"/工程化层 = 中间件
- **2.0 真实**：没有 `HarnessAgent`。"工程化层 over ReAct" 靠
  `agentscope.middleware.MiddlewareBase` + 内置中间件
  （`BudgetMiddleware`、RAG 中间件、长期记忆、tracing）通过 `Agent(..., middlewares=[...])` 组合。
- 中间件钩子点：`on_reply` / `on_reasoning` / `on_check_permission` / `on_acting` /
  `on_model_call` / `on_system_prompt` / `on_compress_context`。

### 3. Workspace / 沙箱
- **2.0 真实**：`agentscope.workspace.WorkspaceBase` + `LocalWorkspace` / `DockerWorkspace` /
  `E2BWorkspace` / `K8sWorkspace` / `DaytonaWorkspace` / `AppleContainerWorkspace` 等。
- **没有 `SandboxConfig` 类，没有 `resource_limit` 参数**（全仓库 grep 零命中）。
- `DockerWorkspace.__init__` 关键参数：`workspace_id, base_image, host_workdir, node_version,
  extra_pip, gateway_port, env, instructions, default_mcps, skill_paths`。资源限制交给容器运行时。
- Agent 接收 workspace 的方式是 `offloader=`（一个 `Offloader`），不是 `sandbox=` kwarg。

### 4. PermissionEngine — **文档唯一说对的部分**
- **2.0 真实**：`agentscope.permission.PermissionEngine(context: PermissionContext)`。
- 导出：`PermissionContext, PermissionRule, PermissionDecision, PermissionMode,
  PermissionBehavior, AdditionalWorkingDirectory`。
- `PermissionRule`（pydantic）：`tool_name, rule_content, behavior, source`。
- `PermissionBehavior`：`ALLOW / DENY / ASK / PASSTHROUGH`。
- `PermissionMode`：`DEFAULT / ACCEPT_EDITS / EXPLORE / BYPASS / DONT_ASK`。BYPASS 确认存在。
- 静态规则 + 动态分析 + `PermissionDecision.suggested_rules`（一次性审批可持久化为 allow 规则）。
- 注意：它是 `Agent` 内部属性，目前没有干净的公开观测 API（见 issue #2000）。

### 5. Pipeline — **2.0 已删除**
- **2.0 真实**：`src/agentscope/` 下**没有 `pipeline` 模块**。
- `MsgHub`、`SequentialPipeline`、`FanoutPipeline`、`sequential_pipeline`、
  `fanout_pipeline` 全是 **1.0 概念**，2.0 已移除。
- 2.0 模型是**单 Agent 为中心**：`await agent.reply(inputs)` 或
  `async for ev in agent.reply_stream(inputs)`。多 Agent 编排走中间件 + `app` 服务层
  （`src/agentscope/app/`：`_manager, _router, _service, message_bus, workspace_manager, rag, access`）。

### 6. 事件系统 — **没有 pub/sub `.on()`**
- **2.0 真实**：`agentscope.event` 导出 `EventType` 枚举 + ~30 个强类型事件类。
- 消费方式：迭代 `agent.reply_stream()`（`AsyncGenerator[AgentEvent | Msg, None]`）。
- 事件类：`ReplyStartEvent`, `ReplyEndEvent`, `ModelCallStart/EndEvent`,
  `TextBlockStart/Delta/EndEvent`, `ThinkingBlock*`, `DataBlock*`, `HintBlockEvent`,
  `ToolCallStart/Delta/EndEvent`, `ToolResultStart/TextDelta/DataDelta/EndEvent`,
  `ExceedMaxItersEvent`, 以及 HITL 事件 `RequireUserConfirmEvent` /
  `UserConfirmResultEvent` / `UserInterruptEvent` / `RequireExternalExecutionEvent` /
  `ExternalExecutionResultEvent`。外加 `CustomEvent` / `AgentEvent` / `ConfirmResult`。
- ⚠️ **设计文档里的 `agent.low_confidence` / `agent.human_override` / `agent.tool_error`
  三个事件名源码里根本不存在。** 本项目 `flywheel/event_mapping.py` 把这些*概念事件*
  映射到真实事件类（如 `ExceedMaxItersEvent`）。

### 7. HITL — **是事件流，不是策略对象**
- **2.0 真实**：没有 `HumanInTheLoop` 类。HITL 是一等公民事件流：
  工具调用解析为 `ASK` 时 Agent 发 `RequireUserConfirmEvent`，用
  `UserConfirmResultEvent` / `UserInterruptEvent` 喂回 `agent.reply()`。
- 没有 `timeout` 构造参数（见 issue #1431）。

### 8. RAG / 向量存储
- **2.0 真实**：`agentscope.rag`。向量库基类是 `VectorStoreBase`（**不是 `VectorStore`**），
  实现：`MilvusLiteStore, QdrantStore, MongoDBStore, ElasticsearchStore`。
- **`collection` 概念存在且显式**：`KnowledgeBase(collection=...)` 构造参数；
  惰性建库走 `ensure_collection()` → `VectorStoreBase.create_collection()`。
- 其它：`ParserBase`（PDF/PPT/Word/Excel/Text/Image）、`ChunkerBase`（`ApproxTokenChunker`）。
- 长期记忆在 `agentscope.middleware._longterm_memory`，extras：`memory-mem0` / `memory-reme`。

### 9. Msg
- **2.0 真实**：`from agentscope.message import Msg, UserMsg, AssistantMsg, SystemMsg, Usage`。
- 内容块：`TextBlock, ThinkingBlock, ToolCallBlock, ToolResultBlock, DataBlock, HintBlock`。

### 10. Studio
- **2.0 真实**：独立仓库 `agentscope-ai/agentscope-studio`，发为 **npm** 包
  `@agentscope/studio`，用 `as_studio` 启动（不是 Python extra）。

---

## 安装 / 版本
- PyPI 最新：**2.0.5**（2026-07-23）。`pip install agentscope`。导入根：`agentscope`。
- 主要 extras：`model-gemini/ollama/xai`, `workspace-docker/e2b/k8s/...`,
  `vdb-milvus/mongodb/elasticsearch/qdrant`, `memory-mem0/reme`, 以及大包 `[full]`。

## 本项目如何落地
- **核心数据层**（connectors / corpus / eval）**完全不依赖 agentscope**——所以零配置可跑。
- **运行时层**（deploy / flywheel）**延迟导入** agentscope 的真实类型；装了 `[agentscope]`
  extra 才解锁真实组装，否则走 dry-run / manifest 模式。
- 每个涉及 agentscope 的源文件顶部 docstring 都标注了"真实 API vs 文档虚构 API"。

---

## 补充：新增模块与 AgentScope 的关系

本项目后来扩展了 SOP 层（`engagement/`）、场景层（`profiles/`）和 Web 控制台
（`web/`）。这些是 **FDE Scope 自己的领域层，AgentScope 里没有对应物**——
这也正是它们的定位：填补 AgentScope（一个 Agent 运行时）与"FDE 在客户现场
需要的一整套 SOP 工具链"之间的空白。

| 本项目模块 | AgentScope 2.0 有对应物吗 | 说明 |
|---|---|---|
| `engagement/`（18 阶段 SOP 状态机 + 10 gate） | ❌ 无 | AgentScope 是 Agent 运行时，不管 engagement 流程。SOP 状态机是 FDE Scope 原创。 |
| `engagement/gates/`（功能安全 / CE / 工会 / FAT-SAT / air-gap / 班次） | ❌ 无 | 工业 overlay，完全原创。AgentScope 不触及功能安全/合规。 |
| `profiles/`（ticket / manufacturing） | ❌ 无 | 场景抽象，AgentScope 无此概念。 |
| `web/`（FastAPI 控制台） | ⚠️ 有 `@agentscope/studio`（npm） | Studio 是 Agent 运行时可视化；FDE Scope 的 Web 是 **engagement/SOP 控制台**，定位不同，互补而非替代。路线图可对接 Studio。 |
| `connectors/` 工业连接器（OPC UA/MQTT/ROS2/MES） | ❌ 无 | AgentScope 不管工业数据接入。 |

**诚实边界**：FDE Scope 的 `deploy` 模块组装的 Agent 对象用的是**真实**
`agentscope.agent.Agent` + `ReActConfig` + `MiddlewareBase`（见上文对照表），
这是唯一与 AgentScope 强耦合的点，且是延迟导入。其余全部独立。
工业现场很多数据源（人形机器人 telemetry、车间语音 copilot）公开无标准，
本项目按 per-vendor adapter 建模，不假设现成可用。

