# langgraph-persistence

> 状态：📦 可安装（registry 真名 `langchain-ai/langchain-skills@langgraph-persistence`，建档名与真名一致）· 类型：工具/数据 · FDE 位点：Zone B · 客户栈适配（LangGraph 持久化/检查点）
> 安装：`npx skills add langchain-ai/langchain-skills@langgraph-persistence --directory ~/.qoder/skills -y` · 装机量：14.1K（skills.sh，2026-08-31）· 详情：https://skills.sh/langchain-ai/langchain-skills/langgraph-persistence

## 能做什么
LangChain 官方（langchain-ai org）的 LangGraph 持久化手册，覆盖"短期记忆（checkpointer）"与"长期记忆（Store）"两条线：`InMemorySaver` / `SqliteSaver` / `PostgresSaver` 三种 checkpointer 的接线（编译图时挂 `checkpointer=`，Postgres 用 `from_conn_string(...)` + `.setup()` 建表）、`thread_id` 线程管理、`get_state_history` 时间旅行回放、`update_state` 状态改写、子图 checkpointer 作用域（scoping，避免并行子图命名空间冲突）、`InMemoryStore` / `runtime.store` 跨会话长期记忆；TS 版 API（`getStateHistory` / `updateState`）同册给出。同 repo 兄弟：langgraph-human-in-the-loop（13.5K）、langchain-rag（13.8K）、langchain-middleware、langgraph-cli、eval-engineering 等。

## 何时使用
- 客户 agent 栈选定/已用 LangGraph，需要设计断点恢复、多轮会话记忆或时间旅行调试
- 在客户 air-gap 内网里选 checkpointer 后端：单机试点 `SqliteSaver`，客户有内网 Postgres 则 `PostgresSaver`
- 要给客户讲"中断-审批-恢复"（HITL）模式时，配合兄弟 skill langgraph-human-in-the-loop 的参考

**不用于**：fde-scope 自身 Engagement 状态机的持久化（本项目走 pydantic v2 + `fsutil.atomic_write_text` 原子写，与 LangGraph checkpointer 无关）；AgentScope 运行时的会话记忆配置（一律以 docs/agentscope_api_mapping.md 的真实 2.0.5 API 为准，别把 LangGraph 模板带进 fde_scope 代码）。

## 新人上手
- **触发**：对 agent 说"客户 agent 是 LangGraph，怎么加断点恢复和对话记忆"（按 catalog 规约先过 [skill-criticagent](../cross-cutting/skill-criticagent.md) 再装）
- **第一步**：`npx skills add langchain-ai/langchain-skills@langgraph-persistence --directory ~/.qoder/skills -y` 装完后，让 agent 按 skill 的 Checkpointer Setup 一节，在客户 graph 编译处补 `checkpointer=`；生产/客户环境用 `PostgresSaver.from_conn_string(...)` 并调用一次 `.setup()` 建表
- **常见坑**：demo 里的 `InMemorySaver` 直接带上生产——进程重启状态全丢，skill 原文把这条列为头号修复项；`thread_id` 忘传——config 里没有它状态根本不落盘；同一 stateful 子图并行多实例会撞命名空间（子图 scoping 一节专门处理）

## 最佳实践
- 官方 org + 14.1K 装机（本区可安装项里最高一档），风险低可直接装；仍按规约走一次 [skill-criticagent](../cross-cutting/skill-criticagent.md) 并把结论回填本页
- 分清两条记忆线：会话内恢复靠 checkpointer + `thread_id`，跨会话长期记忆靠 Store（`InMemoryStore` / `runtime.store`），混用会导致状态分裂
- 气隙客户：checkpointer 落客户内网 SQLite/Postgres，不要选依赖外网 SaaS 的托管方案；客户是 TS 栈时用 `getStateHistory` / `updateState`，别照抄 Python 名
- 定位是"客户栈适配参考"，不要往 fde-scope 依赖里加 `langgraph`

## 项目应用位点
- Zone B 构建：客户栈为 LangGraph 时的持久化/记忆设计评审与原型接线
- 客户 air-gap 内网交付：checkpointer 后端选型（内网 SQLite/Postgres）与落库位置确认
- 与 fde-scope Engagement 对照互鉴：`thread_id` 线程恢复 ↔ Engagement journal 回放、HITL 中断恢复 ↔ 门禁 ASK——思路可引用，实现不互通

## 相关
[rag-agent-builder](rag-agent-builder.md) · [bailian-train-deploy](bailian-train-deploy.md) · [huggingface-best](huggingface-best.md)
