# MCP 服务器总览

> 状态：✅ 已连接（2026-08-31 实测：**9 个 server · 178 个工具**）· 类型：能力底座总览 · FDE 位点：横切（所有 Zone 的上游）

## 能做什么

MCP（Model Context Protocol）是把**外部系统能力**接进 agent 会话的标准协议：每个 server 暴露一组工具，agent 按需调用。它与另外两层能力的关系是新人最该先建立的模型：

| 层 | 形态 | 例子 | 特点 |
|---|---|---|---|
| **内置工具** | 随客户端自带，零安装 | Read / Edit / Bash / Agent | 永远可用，见 [内置工具总览](../tools/overview.md) |
| **MCP 工具** | server 按协议动态暴露 | `firecrawl_scrape`、`take_screenshot` | 数量随插件版本漂移，schema 按需加载 |
| **Skill** | 方法论 + 脚本包 | firecrawl-search、chrome-devtools | 在 MCP/内置之上封装最佳实践，见各 Zone 页 |

本机已连接的 9 个 server 全景：

| Server | 工具数 | 提供方 | 一句话 |
|---|---|---|---|
| [qca（cloud-agents）](cloud-agents-qca.md) | 82 | 插件 qoder-cloud-agents v0.1.0 | 云端 agent 全生命周期管理 |
| [chrome-devtools](chrome-devtools-mcp.md) | 29 | 插件 chrome-devtools-mcp v1.2.0 | 浏览器调试全栈（性能/网络/快照） |
| [firecrawl](firecrawl-mcp.md) | 27 | 插件 firecrawl v0.1.0 | 搜索/抓取/爬站/监测/论文研究 |
| [browser-use](browser-use.md) | 16 | 客户端内置 | 轻量浏览器交互自动化 |
| [computer-use](computer-use.md) | 10 | 插件 computer-use（bundler 分发） | 原生 macOS 应用自动化 |
| [qoder-qmind](qmind-mcp.md) | 7 | 客户端内置 | QMind 知识库检索与管理 |
| [record-and-replay](record-and-replay.md) | 3 | 客户端内置 | 录制操作流 → 生成 skill |
| [extension-market](extension-market.md) | 2 | 客户端内置 | 插件市场搜索/安装 |
| [cloudflare-docs](cloudflare-docs-mcp.md) | 2 | 插件 cloudflare v1.0.0 | CF 官方文档检索/迁移指南 |

另有 sentry / datadog / postman 等 MCP 型插件已按**插件维度**建档（[sentry-mcp](../zone-c-operationalization/sentry-mcp.md) / [datadog](../zone-c-operationalization/datadog.md) / [postman](../zone-b-build/postman.md)），不重复立页。

## 何时使用

- **新人第一件事**：扫一遍本页表格建立"手边有什么"的地图，再按任务进对应页；配合"新人第一周"场景卡（门户主页顶部）走完上手路径
- **取证与自动化**：浏览器（chrome-devtools / browser-use）、桌面应用（computer-use）、网页数据（firecrawl）都是直接可调的工具面，不必先装任何东西
- **要把能力变成共享服务**：qca 的 82 个工具就是云端 agent 的完整 API 面，可被脚本与 CI 调用

**不用于**：把本页当 API 手册逐字背——参数以 live schema 为准（见最佳实践）；重复封装 skill 已覆盖的场景（先查 [手册库索引](../README.md) 有没有对应 skill）。

## 新人上手

- **触发**：入职第一天 / 接手新环境先读这页——"我手边有哪些 MCP 能力"从这张表开始
- **第一步**：扫一遍上面的 9 server 表记住"有事找哪个 server"，再拿一个工具练手 lazy-loading 三步：`mcp_list({keyword: "screenshot"})` → `mcp_get` 读 schema → `mcp_call` 调用
- **常见坑**：以为 178 个工具会话开始就全在上下文里——MCP 是 lazy-loading，不 `mcp_list` 就不存在；凭记忆传参会撞 schema 校验错，调用前必读 `mcp_get`

## 最佳实践

- **Lazy-loading 三步**：工具 schema 不在会话开始时全量注入，而是 `mcp_list`（按关键词发现）→ `mcp_get`（读单个工具的 inputSchema）→ `mcp_call`（调用）。**调用前必读 schema**，输入是扁平 JSON，不要自作主张包 `path`/`query`/`body`
- **工具数会漂移**：本页数字是 2026-08-31 快照；插件升级后以 `mcp_list` 实测为准，页内改动走 `make check-catalog` 门禁
- **skill 优先原则**：MCP 工具是"原料"，skill 是"菜谱"——firecrawl 的日常入口是 [firecrawl-search](../zone-a-pre-engagement/firecrawl-search.md) 这类 skill 页，直接调 MCP 工具留给组合与底账场景
- **破坏性工具先确认**：qca 的 `delete_*` 族、monitor 的删除、`handle_dialog` 代答确认框，都属于"先展示、再执行"
- 报错时先 `mcp_get` 复核参数名与类型，再怀疑网络/服务端

## 项目应用位点

- fde-scope 的 `connectors/` 层与 MCP 是同构思想：都把外部系统适配成统一工具面；给客户做集成时，**写一个 MCP server 本身就是可交付物之一**（参考 [mcp-criticagent](../cross-cutting/mcp-criticagent.md) 的评估标准）
- Zone B 验证环节：chrome-devtools 的性能/网络取证是 Web 交付验收标配
- Zone C：sentry / datadog（MCP 型插件）是可观测性入口；qca 是无人值守执行端

## 相关

[内置工具总览](../tools/overview.md) · [cloud-agents-qca](cloud-agents-qca.md) · [chrome-devtools](chrome-devtools-mcp.md) · [firecrawl](firecrawl-mcp.md) · [browser-use](browser-use.md) · [computer-use](computer-use.md) · [qmind](qmind-mcp.md) · [cloudflare-docs](cloudflare-docs-mcp.md) · [extension-market](extension-market.md) · [record-and-replay](record-and-replay.md) · [skill-discovery](../cross-cutting/skill-discovery.md)
