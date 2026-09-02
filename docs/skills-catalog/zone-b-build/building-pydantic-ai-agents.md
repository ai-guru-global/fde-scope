# building-pydantic-ai-agents

> 状态：📦 可安装（registry 真名 `pydantic/skills@building-pydantic-ai-agents`，建档名与真名一致）· 类型：工具/数据 · FDE 位点：Zone B · 类型安全 agent 原型（Pydantic AI）
> 安装：`npx skills add pydantic/skills@building-pydantic-ai-agents --directory ~/.qoder/skills -y` · 装机量：3.8K（skills.sh，2026-08-31）· 详情：https://skills.sh/pydantic/skills/building-pydantic-ai-agents

## 能做什么
Pydantic 官方（pydantic org）的 Pydantic AI 建册手册：`Agent` 创建、`@agent.tool` / `@agent.tool_plain` 挂工具、pydantic 模型结构化输出、`deps_type` 依赖注入、流式（`run_stream`）、测试（`TestModel` + `agent.override()`）、hooks 生命周期拦截、按需加载的 capabilities、多 agent 编排，以及 `logfire.instrument_pydantic_ai()` 观测接线。正文带 Task Routing Table，11 个分主题参考文件（TOOLS-CORE、TESTING-AND-DEBUGGING、ORCHESTRATION-AND-INTEGRATIONS 等）按任务族分发。同 repo 兄弟：pydantic-ai-harness、logfire-instrumentation / logfire-query / logfire-ui。

## 何时使用
- 客户选型/已用 Pydantic AI，要交付"输出必须过校验"的类型安全 agent（工单结构、质检记录直接映射 pydantic 模型）
- 给客户展示工具调用 + 依赖注入 + 离线测试的工程化 agent 范式，而不是裸调模型的 demo
- 评估该栈时需要真实坑位清单（`RunContext` 形参约束、model string 前缀、已弃用的 `history_processors`）

**不用于**：fde-scope 自身运行时（底座是 AgentScope，以 docs/agentscope_api_mapping.md 为准）；图式编排/断点恢复场景优先看 LangGraph 持久化参考（见本目录 langgraph-persistence 页），Pydantic AI 强在类型安全单 agent 与结构化输出。

## 新人上手
- **触发**：对 agent 说"用 Pydantic AI 写一个输出经过校验的 agent"（按规约先过 [skill-criticagent](../cross-cutting/skill-criticagent.md)）
- **第一步**：`npx skills add pydantic/skills@building-pydantic-ai-agents --directory ~/.qoder/skills -y` 装完后，让 agent 按 Quick-Start 起一个 `Agent`，用 `@agent.tool_plain` 挂第一个工具、`deps_type` 注入配置，输出类型直接给 pydantic 模型
- **常见坑**：`@agent.tool` 的第一个参数必须是 `RunContext`，不需要上下文的工具要用 `@agent.tool_plain`，形参写错注册即失败；model string 必须带 provider 前缀（`openai:gpt-4o` 这类 `provider:model` 形式），漏前缀解析不到模型；测试必须 `TestModel` + `agent.override()` 注入，直连真模型跑测试既烧钱又不稳定

## 最佳实践
- 亲缘关系：fde-scope 本身就是 pydantic v2 技术栈（Python 3.12 / uv），Pydantic AI 的结构化输出模型可与 `fde_scope` 既有 pydantic v2 模型共用 schema 习惯、讲解成本低——但它是客户栈参考，**不要**把 `pydantic-ai` 加进本项目依赖
- 测试一律走 `TestModel` / `agent.override()`，交付前在客户环境才换真模型；hooks 装饰器名不重复 `on_` 前缀；`history_processors` 已弃用，新代码别用
- 需要观测时按 skill 提示接 `logfire.instrument_pydantic_ai()`（兄弟 skill logfire-instrumentation）；气隙客户注意 Logfire SaaS 有出境问题，需自托管另议
- 官方 org、3.8K 装机，装前照例过 [skill-criticagent](../cross-cutting/skill-criticagent.md) 并回填本页

## 项目应用位点
- Zone B prototype-on-real-data：客户选 Pydantic AI 时的类型安全原型范式
- Zone B validate：`TestModel` 离线测试思路与本项目 gate 思维同构，可写进客户交付说明
- 结构化输出 schema 与 `fde_scope` pydantic v2 模型的复用对齐（同一套建模语言，交付讲解顺滑）

## 相关
[rag-agent-builder](rag-agent-builder.md) · [bailian-train-deploy](bailian-train-deploy.md) · [huggingface-best](huggingface-best.md)
