# cloud-agents

> 状态：✅ 已安装（**两个**插件并存，用途不同）· 类型：云端常驻 agent · FDE 位点：横切（Zone B 长任务 / Zone C 无人值守）
> - `cloud-agents` v1.1.0（作者 Qoder）→ **REST / `bl`-style curl 直连** CAS API，PAT 鉴权 · `~/.qoder/plugins/cache/qoder-marketplace/cloud-agents/1.1.0`
> - `qoder-cloud-agents` v0.1.0（作者 Qoder）→ **官方 MCP 连接器**驱动（本机会话实测 82 个工具，覆盖 agents/environments/sessions/files/vaults/memories/deployments/skills），身份由 Gateway 注入 · `~/.qoder/plugins/cache/qoder-marketplace/qoder-cloud-agents/0.1.0`（含 `mcp.json`）

## 能做什么
在 Cloud Agents 平台的容器里创建并运行 agent，**与本地机器解耦**：合上笔记本它继续跑、可按计划跑、可被脚本与 CI 调起、可封装成团队共享的一个 API。核心资源模型：`agent_` / `sess_` / `env_` / `evt_` / `file_` / `mem_store_` / `skill_`，支持会话消息、SSE 事件流、文件/记忆/技能上传。

本地装 skill 只服务装在谁电脑上；云端 agent 是**一个共享服务，全团队用同一个 API 调**——这是它相对本地 skill 的本质差异。

## 何时使用
- **长任务托管**：大代码库分析、批量语料处理（本地不必一直在线）
- **定时/常驻自动化**：日报、周期巡检（与 [schedule](schedule.md) 的分工：本地调度靠客户端醒着，云端调度靠平台）
- **高风险代码沙箱执行**：客户现场脚本/未知数据解析放 disposable 容器，炸了也碰不到真机
- **接入系统/CI**：PAT + curl/SDK 就是一个可调用的 AI 后端
- **团队共享工具**：给客户 IT 或同事一个入口，而不是挨个装插件

选哪个入口：**明确要 MCP 工具（`list_models`/`create_agent`/`create_session`/`send_session_events`/`run_deployment`）、或宿主环境要求托管身份 → `qoder-cloud-agents`**；要写脚本、进 CI、自己管 PAT、直连 REST → `cloud-agents`。

**不用于**：用户明确说要本地 Qoder CLI 或自托管 agent；一次性小任务（开云端会话的固定开销不划算）；需要读客户内网资源的任务（云端容器不在客户网络里，除非走 [alibabacloud-workbench-cli](../zone-b-build/alibabacloud-workbench-cli.md) 那类跳板）。

## 最佳实践
- **新账号没有默认 environment**：起会话前必须先 `POST /environments`，否则直接失败——这是最常见的入门坑
- REST 侧鉴权：`Authorization: Bearer <PAT>`，PAT 在 https://qoder.com/cloud/pat-keys 创建；Base URL `https://api.qoder.com/api/v1/cloud`
- **MCP 侧绝不要自己拼 HTTP**：用发现到的逻辑工具名，输入是扁平 JSON（不要包 `path`/`query`/`body`），并先读该工具的 live `inputSchema`
- MCP 侧**不要**送 PAT/SAT/Authorization/user ID/Gateway header——由 Gateway 供给；缺能力时如实说明并问用户，**不要静默回落到 REST 或 curl**
- 分页三选一：`page` / `after_id` / `before_id` 只用一个；`next_page` 只能再当 `page` 用，别当数字
- 大数据集走 Files API 挂成 session 资源让容器内读盘，别把内容塞进消息
- **破坏性操作清单**（MCP 契约明示）：`delete_session` 连事件一起删；`delete_vault` 连带删所有凭据；被引用过的 environment 常删不掉 → 用 archive；agent/deployment 只有 archive 无 delete
- 不自动批准 `agent.tool_use`：先展示动作，确认覆盖到它才发 `user.tool_confirmation`
- 成本与凭据：常驻 agent 每次唤醒都算 token；PAT 只放环境变量/密钥管理，**绝不写进仓库或 catalog 文档**

## 项目应用位点
- Zone B：批量语料的长时处理、[bailian-train-deploy](../zone-b-build/bailian-train-deploy.md) 训练等待期的异步盯守
- Zone C：客户侧定时报表与巡检的"不依赖我笔记本"执行端；配合 [sentry-mcp](../zone-c-operationalization/sentry-mcp.md) 做每日错误汇总
- fde-scope 的 `deploy/` 已经有 AgentScope `DockerWorkspace` 的容器化路径——云端 agent 是"托管容器"，二者是不同层的选项（一个管 agent 跑在哪，一个管客户交付物跑在哪）
- 与 PawApp 的关系：PawApp 复用 QwenPaw 宿主能力（本地桌面），云端 agent 用于团队共享与无人值守，不要混用场景

## 相关
[schedule](schedule.md) · [dispatching-parallel-agents](dispatching-parallel-agents.md) · [mcp-criticagent](mcp-criticagent.md) · [bailian-train-deploy](../zone-b-build/bailian-train-deploy.md)
