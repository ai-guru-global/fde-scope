# cloud-agents / qca（MCP server）

> 状态：✅ 已连接（插件 qoder-cloud-agents v0.1.0，带 `mcp.json`）· 类型：MCP 服务器 · **82 个工具**（本机会话 2026-08-31 实测）· FDE 位点：Zone B 长任务 / Zone C 无人值守
> 平台概念、REST 直连、成本与选型见 [cloud-agents](../cross-cutting/cloud-agents.md)；本页只讲 MCP 工具面

## 能做什么

Cloud Agents 平台的完整工具面，按资源域分组（`list_` / `create_` / `get_` / `update_` / `delete_` / `archive_` 动词族）：

| 资源域 | 工具（举要） | 说明 |
|---|---|---|
| **agents** | `create_agent` / `get_agent` / `update_agent` / `archive_agent` / `list_agents` / `list_agent_versions` | 定义 agent 与版本管理；只有 archive 没有 delete |
| **environments** | `create_environment` / `get_environment` / `update_environment` / `delete_environment` / `archive_environment` / `list_environments` | 运行环境；被引用过的删不掉，走 archive |
| **sessions** | `create_session` / `get_session` / `update_session` / `delete_session` / `cancel_session` / `archive_session` / `send_session_events` / `list_session_threads` / `list_session_events` / `list_session_event_summaries` / `list_session_thread_events` | 会话生命周期 + 事件流（SSE 语义）+ 线程 |
| **files & resources** | `list_files` / `get_file` / `get_file_content` / `delete_file` + session resources `add/get/update/delete/list_session_resource` | 大数据集挂成资源让容器内读盘 |
| **memories & stores** | `create_memory` / `get_memory` / `update_memory` / `delete_memory` / `redact_memory_version` / `list_memory_versions` + memory store 族 | agent 记忆；`redact_memory_version` 是合规利器 |
| **vaults** | `create_vault` / `list_vaults` / `delete_vault` / `archive_vault` + credentials `get/delete/archive_vault_credential` / `list_vault_credentials` / `validate_vault_credential` / `start_vault_oauth` | 凭据托管与 OAuth 流程 |
| **deployments** | `create_deployment` / `get_deployment` / `update_deployment` / `archive_deployment` / `list_deployments` / `list_deployment_runs` / `run_deployment` / `pause_deployment` / `unpause_deployment` | 计划任务/常驻服务的发布与运维 |
| **skills** | `get_skill` / `list_skills` / `list_skill_versions` / `delete_skill` / `delete_skill_version` | 云端 agent 的技能库管理 |
| **dreams & models** | `create_dream` / `get_dream` / `list_dreams` / `cancel_dream` / `archive_dream` + `list_models` | 异步意图任务与可用模型查询 |

## 何时使用

- **长任务托管**：大代码库分析、批量语料处理，合上笔记本继续跑
- **无人值守**：定时报表/巡检（与本地 [schedule](../cross-cutting/schedule.md) 的分工见下）
- **团队共享入口**：脚本/CI 通过它驱动云端 agent，不依赖任何人本机在线

**不用于**：一次性小任务（云端会话固定开销不划算）；要读客户内网资源的任务（云端容器不在客户网络里）；宿主环境要求 MCP 托管身份之外的直连场景（→ REST 入口，见 [cloud-agents](../cross-cutting/cloud-agents.md)）。

## 新人上手

- **触发**：对 agent 说"把这个长任务放到云端跑 / 定时每天巡检 / 查一下我的 cloud agents"
- **第一步**：新账号先 `create_environment`——没有环境 `create_session` 直接失败，这是最常见的入门坑；建会话前先 `list_models` 确认模型可用性
- **常见坑**：绝不给工具传 PAT/Authorization header（身份由 Gateway 注入，缺能力就问用户，不要静默回落 REST）；`delete_session` 连事件一起删、`delete_vault` 连带删凭据——破坏性调用前必须确认

## 最佳实践

- **新账号先建 environment**：`create_session` 前必须 `create_environment`，否则直接失败——最常见的入门坑
- **绝不自带鉴权**：不要给工具传 PAT/SAT/Authorization header/user ID——身份由 Gateway 注入；缺能力就如实说明并问用户，**不要静默回落到 REST/curl**
- **先 `list_models` 再 `create_agent`**：模型可用性因账号/区域而异，写死模型名是脆弱配置
- **分页参数三选一**：`page` / `after_id` / `before_id` 只用一个；`next_page` 只能再当 `page` 用，别当数字
- **破坏性操作清单**（调用前必须确认）：`delete_session` 连事件一起删、`delete_vault` 连带删所有凭据、`delete_skill_version` 不可恢复；agent/deployment/environment 被引用过删不掉 → 用 archive
- **大数据走 Files API**：把数据集挂成 session resource 让容器读盘，别把内容塞进消息
- **不自动批准 `agent.tool_use`**：先向用户展示动作，确认后才发 `user.tool_confirmation`
- 与本地 [schedule](../cross-cutting/schedule.md) 的分工：本地调度靠客户端醒着，云端调度靠平台（deployment）——要"不依赖我笔记本"就选云端

## 项目应用位点

- Zone B：批量语料长时处理、[bailian-train-deploy](../zone-b-build/bailian-train-deploy.md) 训练等待期的异步盯守
- Zone C：客户侧定时报表与巡检的"不依赖我笔记本"执行端；配合 [sentry-mcp](../zone-c-operationalization/sentry-mcp.md) 做每日错误汇总
- fde-scope 的 `deploy/`（AgentScope `DockerWorkspace`）管"客户交付物跑在哪"，qca 管"agent 跑在哪"——两个不同层的容器化选项，不要混用

## 相关

[总览](overview.md) · [cloud-agents 平台页](../cross-cutting/cloud-agents.md) · [schedule](../cross-cutting/schedule.md) · [dispatching-parallel-agents](../cross-cutting/dispatching-parallel-agents.md) · [mcp-criticagent](../cross-cutting/mcp-criticagent.md)
